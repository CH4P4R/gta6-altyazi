"""Tam ekran çeviri: telefon mesajları, menüler, harita gibi bölgelerin dışındaki tüm yazılar.

Kısayolla (ya da telefondaki kumanda sayfasından) istenince o anki kare genel amaçlı bir yazı tespit
modeliyle (PP-OCR tespit + tanıma) taranır, satırlar paragraflara birleştirilir ve her paragraf
yerinde çevrilir. Sürekli çalışmaz; istek başına ~0.3-0.8 sn.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import numpy as np

log = logging.getLogger(__name__)

_LETTER = re.compile(r"[A-Za-z]")


@dataclass
class Block:
    text: str
    rect: tuple[float, float, float, float]   # kare oranı
    line_h: float                              # kare yüksekliğine oran


@dataclass
class _Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def h(self) -> float:
        return self.y1 - self.y0


def group_lines(lines: list[_Line]) -> list[list[_Line]]:
    """Alt alta, aynı hizada ve benzer boydaki satırları paragraf yap."""
    lines = sorted(lines, key=lambda l: (l.y0, l.x0))
    blocks: list[list[_Line]] = []
    for ln in lines:
        for b in blocks:
            last = b[-1]
            similar = 0.7 < ln.h / max(last.h, 1) < 1.4
            gap = ln.y0 - last.y1
            aligned = abs(ln.x0 - last.x0) < 2.5 * last.h or (ln.x0 < last.x1 and ln.x1 > last.x0)
            if similar and -0.3 * last.h <= gap <= 0.9 * last.h and aligned:
                b.append(ln)
                break
        else:
            blocks.append([ln])
    return blocks


def useful(text: str) -> bool:
    letters = len(_LETTER.findall(text))
    return letters >= 3 and letters >= 0.45 * len(text.replace(" ", ""))


class FullScreenReader:
    def __init__(self, min_score: float = 0.6):
        from rapidocr_onnxruntime import RapidOCR

        self.engine = RapidOCR()
        self.min_score = min_score

    def read_lines(self, img: np.ndarray) -> list[tuple[str, tuple[float, float, float, float]]]:
        """Tek tek satırlar: [(metin, (x0, y0, x1, y1) piksel)] (ekran yazıları izleyicisi kullanır)."""
        result, _ = self.engine(np.ascontiguousarray(img[..., :3]), use_cls=False)
        out = []
        for box, text, score in result or []:
            if float(score) < self.min_score or not text.strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            out.append((text.strip(), (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))))
        return out

    def read(self, frame: np.ndarray) -> list[Block]:
        img = frame[..., :3]
        h, w = img.shape[:2]
        result, _ = self.engine(np.ascontiguousarray(img), use_cls=False)
        lines = []
        for box, text, score in result or []:
            if float(score) < self.min_score or not text.strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append(_Line(text.strip(), min(xs), min(ys), max(xs), max(ys)))
        blocks = []
        for group in group_lines(lines):
            text = " ".join(l.text for l in group)
            if not useful(text):
                continue
            x0 = min(l.x0 for l in group)
            y0 = min(l.y0 for l in group)
            x1 = max(l.x1 for l in group)
            y1 = max(l.y1 for l in group)
            lh = float(np.median([l.h for l in group]))
            blocks.append(Block(text, (x0 / w, y0 / h, x1 / w, y1 / h), lh / h))
        return blocks
