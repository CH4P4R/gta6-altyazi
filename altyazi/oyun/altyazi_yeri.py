# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın Pipeline/SubtitleLayout.swift dosyasından taşındı.

Her oyunun altyazısının ekranda nerede durduğunu öğrenir. Oyunlar altyazıyı farklı yüksekliklere koyar; sabit bir
kural ("ekranın %88'inin altı altyazı değildir") altyazısı en altta duran oyunlarda gerçek altyazıyı atlar. Gösterilen
her altyazının kutusu kaydedilir; yeterince örnek olunca o oyunun altyazı şeridi bilinir. Şeridin altında başlayan
yazılar (görev, öğretici, menü) altyazı sayılmaz. Bütün değerler ekranın oranıdır (0–1, üstten).
"""

from __future__ import annotations

import copy
import json
import logging
import math
import os
import threading
from pathlib import Path
from typing import NamedTuple

log = logging.getLogger(__name__)


class TextBox(NamedTuple):
    """Yazının kutusu, ekranın oranı olarak (0–1, sol üstten). DisplayItem.rect ile aynı sıra: (x0, y0, x1, y1)."""
    left: float
    top: float
    right: float
    bottom: float


def as_box(box) -> TextBox:  # noqa: ANN001
    """TextBox, (x0, y0, x1, y1) dörtlüsü ya da left/top/right/bottom alanlı herhangi bir nesne."""
    if isinstance(box, TextBox):
        return box
    if hasattr(box, "top") and hasattr(box, "bottom"):
        return TextBox(float(getattr(box, "left", 0.0)), float(box.top), float(getattr(box, "right", 1.0)),
                       float(box.bottom))
    x0, y0, x1, y1 = box
    return TextBox(float(x0), float(y0), float(x1), float(y1))


def _quantile(values: list[float], q: float) -> float:
    """Sıralı listede q dilimi (Swift'teki gibi yarımlar yukarı yuvarlanır)."""
    if not values:
        return 0.0
    index = min(len(values) - 1, max(0, math.floor((len(values) - 1) * q + 0.5)))
    return values[index]


class SubtitleLayout:
    MINIMUM_SAMPLES = 8          # öğrenmek için gereken en az altyazı
    MAXIMUM_SAMPLES = 60         # oyun başına en çok örnek (eskiler düşer; oyun güncellenip yer değişirse uyum sağlanır)
    # Öğrenene kadar kullanılan sınır: ekranın en alt şeridi. GTA 6 ve RDR2'de tek satırlık altyazı 0.879–0.884'te
    # başlar, görev yazısı ≈0.93'te.
    FALLBACK_HUD_TOP = 0.895
    # Bundan yukarıda biten kutu örnek sayılmaz (ayarlar menüsündeki açıklamalar altyazının yerini unutturuyordu).
    LOWEST_USEFUL_BOTTOM = 0.80
    READ_MARGIN = 0.05           # okunan şeridin öğrenilen şeridin üstüne bırakılan payı
    BASELINE_SAMPLES = 12        # taban çizgisi için gereken en az örnek
    BASELINE_MARGIN = 0.07       # tabanın bu kadar üstünde biten blok altyazının yerinde değil (GTA 6: ≈0.915 → ≈0.845)

    def __init__(self, samples: dict[str, list[tuple[float, float]]] | None = None):
        # Oyun başına son kutuların (üst, alt) kenarları
        self.samples: dict[str, list[tuple[float, float]]] = samples or {}

    def record(self, box, game: str) -> None:  # noqa: ANN001
        b = as_box(box)
        if not (b.bottom > b.top and b.top >= 0 and b.bottom <= 1 and b.bottom >= self.LOWEST_USEFUL_BOTTOM):
            return
        lst = self.samples.setdefault(game, [])
        lst.append((b.top, b.bottom))
        if len(lst) > self.MAXIMUM_SAMPLES:
            del lst[:len(lst) - self.MAXIMUM_SAMPLES]

    def band(self, game: str) -> tuple[float, float] | None:
        """Oyunun altyazı şeridi (üst, alt); yeterli örnek yoksa None. Uç değerler atılır."""
        lst = self.samples.get(game)
        if not lst or len(lst) < self.MINIMUM_SAMPLES:
            return None
        tops, bottoms = sorted(t for t, _ in lst), sorted(b for _, b in lst)
        return _quantile(tops, 0.1), _quantile(bottoms, 0.9)

    def hud_top(self, game: str) -> float | None:
        """Bu çizginin altında başlayan satır altyazı sayılmaz. Öğrenilmişse şeridin biraz altı, öğrenilmemişse eski
        sınır; altyazısı ekranın dibinde duran oyunda sınır kalkar (None). Öğrenilen çizgi sınırı yalnız aşağı indirir."""
        band = self.band(game)
        if band is None:
            return self.FALLBACK_HUD_TOP
        lst = self.samples[game]
        # Şeridin altına bir satır yüksekliği pay: iki satırlık altyazının ikinci satırı kesilmesin.
        line_height = _quantile(sorted(b - t for t, b in lst), 0.5)
        line = band[1] + max(0.012, line_height)
        return None if line >= 0.97 else max(line, band[0] + 0.03, self.FALLBACK_HUD_TOP)

    def baseline_floor(self, game: str) -> float | None:
        """Altyazının oturduğu taban çizgisinin biraz üstü: bloğun alt kenarı bu çizginin üstünde kalıyorsa blok
        altyazının yerinde değildir (tabela, pano, menü). Örneklerin çoğu aynı tabanda değilse None."""
        lst = self.samples.get(game)
        if not lst or len(lst) < self.BASELINE_SAMPLES:
            return None
        bottoms = sorted(b for _, b in lst)
        base = _quantile(bottoms, 0.5)
        near = sum(1 for b in bottoms if abs(b - base) <= 0.03)
        if near < len(bottoms) * 0.7:
            return None
        return base - self.BASELINE_MARGIN

    def read_top(self, game: str) -> float | None:
        """Altyazının yeri öğrenildiyse yalnız o şerit okunur: şeridin bu kadar üstünden başlanır. Öğrenilmemişse None
        (ayarlardaki alan okunur)."""
        band = self.band(game)
        return None if band is None else band[0] - self.READ_MARGIN

    # Swift Codable ile aynı biçim: {"samples": {"oyun": [{"top": .., "bottom": ..}]}}
    def to_json(self) -> dict:
        return {"samples": {g: [{"top": t, "bottom": b} for t, b in lst] for g, lst in self.samples.items()}}

    @classmethod
    def from_json(cls, data: dict) -> SubtitleLayout:
        samples: dict[str, list[tuple[float, float]]] = {}
        for game, lst in (data.get("samples") or {}).items():
            samples[str(game)] = [(float(s["top"]), float(s["bottom"])) for s in lst]
        return cls(samples)


class SubtitleLayoutStore:
    """Öğrenilenleri diskte saklar (ör. veri klasöründe subtitle-layout.json). İş parçacığı güvenli."""

    def __init__(self, path: Path | str | None):
        self.path = Path(path) if path else None
        self._lock = threading.Lock()
        self._layout = SubtitleLayout()
        if self.path and self.path.is_file():
            try:
                self._layout = SubtitleLayout.from_json(json.loads(self.path.read_text("utf-8")))
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
                log.warning("Altyazı yeri dosyası okunamadı (%s): %s", self.path, e)

    @property
    def current(self) -> SubtitleLayout:
        """O anki öğrenilenlerin kopyası."""
        with self._lock:
            return SubtitleLayout(copy.deepcopy(self._layout.samples))

    def record(self, box, game: str) -> None:  # noqa: ANN001
        with self._lock:
            self._layout.record(box, game)
            data = json.dumps(self._layout.to_json())
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(data, "utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.debug("Altyazı yeri yazılamadı: %s", e)
