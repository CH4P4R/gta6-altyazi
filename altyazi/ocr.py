"""OCR: PP-OCR tanıma modelini doğrudan ONNX Runtime ile (GPU varsa CUDA) çalıştırır.

Tespit (detection) modelini atlıyoruz: metin satırlarını detector.py zaten
piksel maskesinden çıkarıyor. Böylece her satır için sadece tanıma modeli
çalışıyor (GPU'da satır başına ~1-3 ms, CPU'da ~5-15 ms).
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

REC_HEIGHT = 48


@dataclass
class OcrLine:
    text: str
    score: float


def _default_model_path() -> Path:
    """rapidocr_onnxruntime paketinin içindeki tanıma modelini bul."""
    import rapidocr_onnxruntime

    models = Path(rapidocr_onnxruntime.__file__).parent / "models"
    for name in sorted(os.listdir(models), reverse=True):  # en yeni sürüm önce
        if "rec" in name and name.endswith(".onnx"):
            return models / name
    raise FileNotFoundError(f"{models} içinde tanıma modeli bulunamadı")


class Recognizer:
    def __init__(self, model_path: str | None = None, keys_path: str | None = None,
                 use_gpu: bool = True, batch: int = 8):
        import onnxruntime as ort

        path = Path(model_path) if model_path else _default_model_path()
        providers = ["CPUExecutionProvider"]
        if use_gpu and "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.log_severity_level = 3
        self.session = ort.InferenceSession(str(path), sess_options=so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.device = "GPU" if self.session.get_providers()[0] == "CUDAExecutionProvider" else "CPU"
        self.batch = batch

        meta = self.session.get_modelmeta().custom_metadata_map
        if keys_path:
            chars = Path(keys_path).read_text(encoding="utf-8").splitlines()
        elif "character" in meta:
            chars = meta["character"].splitlines()
        else:
            raise ValueError("Model karakter listesi içermiyor, ocr.anahtar_dosyasi verin")
        self.chars = ["<blank>"] + chars + [" "]
        log.info("OCR modeli: %s (%s)", path.name, self.device)

    def warmup(self) -> None:
        dummy = np.full((REC_HEIGHT, 320, 3), 255, np.uint8)
        cv2.putText(dummy, "warmup", (5, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        for _ in range(3):
            self.recognize([dummy])

    def _prep(self, img: np.ndarray, width: int) -> np.ndarray:
        h, w = img.shape[:2]
        rw = min(width, int(math.ceil(REC_HEIGHT * w / h)))
        x = cv2.resize(img, (max(rw, 1), REC_HEIGHT), interpolation=cv2.INTER_AREA if h > REC_HEIGHT else cv2.INTER_LINEAR)
        x = x.astype(np.float32).transpose(2, 0, 1) * (2.0 / 255.0) - 1.0
        out = np.zeros((3, REC_HEIGHT, width), np.float32)
        out[:, :, :rw] = x
        return out

    def _decode(self, preds: np.ndarray) -> list[OcrLine]:
        idx = preds.argmax(axis=2)
        prob = preds.max(axis=2)
        res = []
        for b in range(idx.shape[0]):
            seq, p = idx[b], prob[b]
            keep = seq != 0
            keep[1:] &= seq[1:] != seq[:-1]
            text = "".join(self.chars[i] for i in seq[keep] if i < len(self.chars))
            score = float(p[keep].mean()) if keep.any() else 0.0
            res.append(OcrLine(text.strip(), score))
        return res

    def recognize(self, images: list[np.ndarray]) -> list[OcrLine]:
        """BGR satır görüntülerini tanır. Sıra korunur."""
        if not images:
            return []
        imgs = [cv2.cvtColor(i, cv2.COLOR_GRAY2BGR) if i.ndim == 2 else i for i in images]
        order = np.argsort([i.shape[1] / i.shape[0] for i in imgs])
        out: list[OcrLine | None] = [None] * len(imgs)
        for s in range(0, len(imgs), self.batch):
            chunk = order[s:s + self.batch]
            ratio = max(max(imgs[k].shape[1] / imgs[k].shape[0] for k in chunk), 320 / REC_HEIGHT)
            width = int(math.ceil(REC_HEIGHT * ratio))
            batch = np.stack([self._prep(imgs[k], width) for k in chunk])
            preds = self.session.run(None, {self.input_name: batch})[0]
            for k, line in zip(chunk, self._decode(preds)):
                out[k] = line
        return out  # type: ignore[return-value]


def timed(fn, *a, **kw):
    t = time.perf_counter()
    r = fn(*a, **kw)
    return r, (time.perf_counter() - t) * 1000
