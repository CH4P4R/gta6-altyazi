# SPDX-License-Identifier: AGPL-3.0-only
"""Mac'te Apple'ın kendi yazı tanıması (Vision, Neural Engine): ek model yok, internet yok.

GameTranslator ve Nino'nun Mac uygulamaları da altyazıyı bununla okur. İki kullanım:
  - VisionRecognizer: detector.py'nin çıkardığı altyazı satırları (beyaz zemin, koyu yazı). Satırlar alt alta tek
    görüntüde birleştirilip tek istekte okunur; sonuç satırlara geri dağıtılır.
  - read(): tam karede yazı bulma + okuma (telefon, harita, menü; fullscreen.py).
Vision yoksa (Windows, Linux, eski Mac) available() False döner ve PP-OCR (ocr.py) kullanılır.
"""

from __future__ import annotations

import threading
import logging
import sys

import numpy as np

log = logging.getLogger(__name__)

_GAP = 0.6          # birleştirilmiş görüntüde satır arası boşluk (satır yüksekliğine oran)
_MIN_H = 32         # Vision küçük yazıyı kaçırır: satır bundan kısaysa büyütülür


_VISION_LOCK = threading.Lock()

def available() -> bool:
    if sys.platform != "darwin":
        return False
    try:
        import Vision  # noqa: F401
        import Quartz  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _cgimage(img: np.ndarray):  # noqa: ANN202
    import cv2
    import Quartz
    from Foundation import NSData

    if img.ndim == 2:
        rgba = cv2.cvtColor(img, cv2.COLOR_GRAY2RGBA)
    else:
        rgba = cv2.cvtColor(np.ascontiguousarray(img[..., :3]), cv2.COLOR_BGR2RGBA)
    rgba = np.ascontiguousarray(rgba)
    h, w = rgba.shape[:2]
    raw = rgba.tobytes()
    provider = Quartz.CGDataProviderCreateWithCFData(NSData.dataWithBytes_length_(raw, len(raw)))
    space = Quartz.CGColorSpaceCreateDeviceRGB()
    return Quartz.CGImageCreate(w, h, 8, 32, w * 4, space,
                                Quartz.kCGImageAlphaNoneSkipLast | Quartz.kCGBitmapByteOrderDefault,
                                provider, None, False, Quartz.kCGRenderingIntentDefault)


def read(img: np.ndarray, fast: bool = False, correction: bool = True,
         ) -> list[tuple[str, float, tuple[float, float, float, float]]]:
    """[(metin, güven 0-1, (x0, y0, x1, y1) piksel)] — yukarıdan aşağı, soldan sağa."""
    import objc
    import Vision

    h, w = img.shape[:2]
    out = []
    # Vision aynı anda iki iş parçacığından çağrılınca Intel Mac'te (Neural Engine yok) program çöküyordu (CI'da
    # görüldü: altyazı hattı ve ekran yazıları izleyicisi aynı anda okuyordu). Okumalar sıraya alınır.
    with _VISION_LOCK, objc.autorelease_pool():
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast if fast
                                 else Vision.VNRequestTextRecognitionLevelAccurate)
        req.setRecognitionLanguages_(["en-US"])
        req.setUsesLanguageCorrection_(bool(correction))
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(_cgimage(img), None)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(f"Vision okuyamadı: {err}")
        for obs in req.results() or []:
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            text = str(cands[0].string()).strip()
            if not text:
                continue
            bb = obs.boundingBox()                    # oran, sol alt köşe başlangıç
            x0 = bb.origin.x * w
            x1 = (bb.origin.x + bb.size.width) * w
            y1 = (1.0 - bb.origin.y) * h
            y0 = (1.0 - bb.origin.y - bb.size.height) * h
            out.append((text, float(cands[0].confidence()), (x0, y0, x1, y1)))
    out.sort(key=lambda r: (round(r[2][1] / max(h * 0.02, 1)), r[2][0]))
    return out


def stack(images: list[np.ndarray]) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Satır görüntülerini beyaz zeminde alt alta dizer. Döner: (görüntü, her satırın (y0, y1) aralığı)."""
    import cv2

    rows = []
    for im in images:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR) if im.ndim == 2 else im[..., :3]
        if im.shape[0] < _MIN_H:
            s = _MIN_H / max(im.shape[0], 1)
            im = cv2.resize(im, (max(1, int(im.shape[1] * s)), _MIN_H), interpolation=cv2.INTER_CUBIC)
        rows.append(im)
    height = max(r.shape[0] for r in rows)
    gap = int(height * _GAP)
    width = max(r.shape[1] for r in rows) + 2 * gap
    total = sum(r.shape[0] for r in rows) + gap * (len(rows) + 1)
    canvas = np.full((total, width, 3), 255, np.uint8)
    spans = []
    y = gap
    for r in rows:
        canvas[y:y + r.shape[0], gap:gap + r.shape[1]] = r
        spans.append((float(y), float(y + r.shape[0])))
        y += r.shape[0] + gap
    return canvas, spans


def distribute(found: list[tuple[str, float, tuple[float, float, float, float]]],
               spans: list[tuple[float, float]]) -> list[tuple[str, float]]:
    """Okunan parçaları dikey ortalarına göre satırlara dağıtır; bir satırda birden çok parça soldan sağa birleşir."""
    parts: list[list[tuple[float, str, float]]] = [[] for _ in spans]
    for text, conf, (x0, y0, _x1, y1) in found:
        mid = (y0 + y1) / 2
        best = min(range(len(spans)), key=lambda i: 0 if spans[i][0] <= mid <= spans[i][1]
                   else min(abs(mid - spans[i][0]), abs(mid - spans[i][1])))
        parts[best].append((x0, text, conf))
    out = []
    for p in parts:
        p.sort()
        text = " ".join(t for _, t, _ in p)
        conf = float(np.mean([c for _, _, c in p])) if p else 0.0
        out.append((text, conf))
    return out


class VisionRecognizer:
    """ocr.Recognizer ile aynı arayüz: recognize(satır görüntüleri) -> [OcrLine]."""

    device = "Apple Neural Engine (Vision)"

    def __init__(self, fast: bool = False):
        self.fast = fast

    def warmup(self) -> None:
        import cv2

        dummy = np.full((48, 360, 3), 255, np.uint8)
        cv2.putText(dummy, "warmup text", (5, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        for _ in range(2):
            self.recognize([dummy])

    def recognize(self, images: list[np.ndarray]) -> list:
        from .ocr import OcrLine

        if not images:
            return []
        canvas, spans = stack(images)
        # Vision'ın güveni kaba basamaklı (0.3 / 0.5 / 1.0): okunabilen satırı PP-OCR eşiklerinden geçecek ölçeğe taşı
        return [OcrLine(t, (1.0 if c >= 0.3 else c) if t else 0.0)
                for t, c in distribute(read(canvas, fast=self.fast), spans)]

