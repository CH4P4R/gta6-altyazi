# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın ReadScheduler.swift dosyasından taşındı.

Hangi karede yazı tanıma yapılacağını seçer. Oyun süresinin çoğunda bölge boştur ya da değişmez; işlemcinin büyük
kısmı bu karelerde boşa gider. Bölgenin küçük bir gri izi (64×12) bir önceki kareyle karşılaştırılır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .altyazi_yeri import as_box

DEFAULT_MAX_REUSE, FAST_MAX_REUSE = 20, 2
SIGNATURE_WIDTH, SIGNATURE_HEIGHT = 64, 12     # bölge izi: satır başına 64 gri örnek, 12 satır
DEFAULT_CHANGE_THRESHOLD = 16                  # video gürültüsü bu farkı aşmaz; bir harf eklenmesi aşar


@dataclass(frozen=True)
class Reuse:
    """Bölge değişmedi, son okuma geçerli."""
    text: str


@dataclass(frozen=True)
class Read:
    """Yazı tanıma yapılır; `deep` ise boş bölgede kısa satırlar için büyütülmüş okuma da denenir."""
    deep: bool


def _arr(sig) -> np.ndarray:  # noqa: ANN001
    return np.frombuffer(bytes(sig), np.uint8) if isinstance(sig, (bytes, bytearray)) \
        else np.asarray(sig, dtype=np.int64).ravel()


def changed(a, b, threshold: int, within=None) -> bool:  # noqa: ANN001
    """İki bölge izi farklı mı: bir örnek `threshold`'dan çok değiştiyse. `within` (kutu, bölgeye oranla) verilirse
    yalnız o kutunun örttüğü örneklere bakılır; bölgenin başka yerindeki kıpırtı sayılmaz."""
    x, y = _arr(a).astype(np.int64), _arr(b).astype(np.int64)
    if x.size != y.size:
        return True
    columns = SIGNATURE_WIDTH
    rows = x.size // columns
    if within is None or rows <= 0 or x.size % columns != 0:
        return bool(np.any(np.abs(x - y) > threshold))
    box = as_box(within)
    left = min(max(math.floor(box.left * columns), 0), columns - 1)
    right = min(max(math.ceil(box.right * columns), left + 1), columns)
    top = min(max(math.floor(box.top * rows), 0), rows - 1)
    bottom = min(max(math.ceil(box.bottom * rows), top + 1), rows)
    diff = np.abs(x - y).reshape(rows, columns)[top:bottom, left:right]
    return bool(np.any(diff > threshold))


def signature_of(image: np.ndarray) -> bytes:
    """Bölge görüntüsünün izi (64×12 gri, satır satır). BGR/RGB ya da gri numpy görüntü."""
    img = np.asarray(image)
    if img.ndim == 3:
        img = img[..., :3].astype(np.float32).mean(axis=2)
    img = img.astype(np.float32)
    h, w = img.shape[:2]
    if h == 0 or w == 0:
        return bytes(SIGNATURE_WIDTH * SIGNATURE_HEIGHT)
    try:
        import cv2
        small = cv2.resize(img, (SIGNATURE_WIDTH, SIGNATURE_HEIGHT), interpolation=cv2.INTER_AREA)
    except ImportError:              # cv2 yoksa en yakın örnek
        ys = (np.arange(SIGNATURE_HEIGHT) * h // SIGNATURE_HEIGHT)
        xs = (np.arange(SIGNATURE_WIDTH) * w // SIGNATURE_WIDTH)
        small = img[ys][:, xs]
    return np.clip(small, 0, 255).astype(np.uint8).tobytes()


class ReadScheduler:
    DEFAULT_MAX_REUSE, FAST_MAX_REUSE = DEFAULT_MAX_REUSE, FAST_MAX_REUSE
    SIGNATURE_WIDTH, SIGNATURE_HEIGHT = SIGNATURE_WIDTH, SIGNATURE_HEIGHT
    DEFAULT_CHANGE_THRESHOLD = DEFAULT_CHANGE_THRESHOLD

    def __init__(self, change_threshold: int = DEFAULT_CHANGE_THRESHOLD, max_reuse: int = DEFAULT_MAX_REUSE,
                 deep_every: int = 3):
        self.change_threshold = change_threshold
        self.max_reuse = max_reuse
        self.deep_every = deep_every
        self.reset()

    @classmethod
    def always(cls) -> ReadScheduler:
        """Her kare okunur ve boş kareler hep derin okunur."""
        return cls(change_threshold=-1, max_reuse=0, deep_every=1)

    def plan(self, signature) -> Reuse | Read:  # noqa: ANN001
        sig = _arr(signature)
        try:
            if self._previous is not None and self._reused < self.max_reuse \
                    and not changed(self._previous, sig, self.change_threshold):
                self._reused += 1
                return Reuse(self._last_text)
            self._reused = 0
            return Read(deep=self._empty_reads % self.deep_every == 0)
        finally:
            self._previous = sig

    def record(self, text: str) -> None:
        self._last_text = text
        # Yazı yeni kalktıysa derin okuma sırası hemen gelmez.
        self._empty_reads = self._empty_reads + 1 if not text else 1

    def reset(self) -> None:
        self._previous: np.ndarray | None = None
        self._last_text = ""
        self._reused = 0
        self._empty_reads = 0

    changed = staticmethod(changed)
