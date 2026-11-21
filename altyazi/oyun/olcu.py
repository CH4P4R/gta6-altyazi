# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın LineMetrics.swift dosyasından taşındı.

TV'ye giden son altyazı satırının ölçümleri: yazı tanımanın süresi, çevirinin süresi ve satırın okunduğu karenin
geldiği andan TV'ye gönderildiği ana kadar geçen süre. Hepsi gerçek ölçümdür.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class Origin(str, Enum):
    """Çevirinin nereden geldiği."""
    PACK = "pack"        # oyun paketindeki hazır Türkçe (çeviri motoru çağrılmadı)
    ENGINE = "engine"    # çeviri motoru (ya da önbelleği)


# Ekrandaki parçaların biçimleri (Swift'teki yerelleştirme anahtarları İngilizce).
LABELS_EN = {"ocr": "OCR {} ms", "pack": "Ready pack", "translation": "Translation {} ms", "delay": "Delay {} ms",
             "confidence": "Confidence {}%"}
LABELS_TR = {"ocr": "OCR {} ms", "pack": "Hazır paket", "translation": "Çeviri {} ms", "delay": "Gecikme {} ms",
             "confidence": "Güven %{}"}


def _ms(value: float) -> int:
    return max(0, int(round(value)))


@dataclass(frozen=True)
class LineMetrics:
    ocr_ms: int | None           # satırı okuyan yazı tanımanın süresi; bilinmiyorsa None
    translation_ms: int | None   # çevirinin süresi; paketten gelen satırda None
    total_ms: int                # karenin geldiği andan TV'ye gönderildiği ana kadar
    confidence: int | None       # yazı tanımanın güveni (yüzde, 0–100); okuyucu vermiyorsa None
    origin: Origin

    @classmethod
    def measure(cls, captured_at: float, ocr_ms: float | None, translation: tuple[float, float] | None,
                sent_at: float, confidence: float | None, origin: Origin) -> LineMetrics:
        """Ölçüm anlarından (aynı milisaniye saatiyle) satırın ölçümleri; eksi süreler 0 olur.
        `translation`: çevirinin başladığı ve bittiği an (paketten gelen satırda None); `confidence`: 0–1."""
        return cls(
            ocr_ms=None if ocr_ms is None else _ms(ocr_ms),
            translation_ms=None if translation is None else _ms(translation[1] - translation[0]),
            total_ms=_ms(sent_at - captured_at),
            confidence=None if confidence is None else math.floor(min(1.0, max(0.0, confidence)) * 100 + 0.5),
            origin=Origin(origin),
        )

    def parts(self, labels: dict[str, str] = LABELS_EN) -> list[str]:
        """Sırayla: "OCR 42 ms", "Translation 310 ms" (paketse "Ready pack"), "Delay 520 ms", "Confidence 93%".
        Bilinmeyen değer yazılmaz. Türkçe için `labels=LABELS_TR`."""
        out = []
        if self.ocr_ms is not None:
            out.append(labels["ocr"].format(self.ocr_ms))
        if self.origin is Origin.PACK:
            out.append(labels["pack"])
        elif self.translation_ms is not None:
            out.append(labels["translation"].format(self.translation_ms))
        out.append(labels["delay"].format(self.total_ms))
        if self.confidence is not None:
            out.append(labels["confidence"].format(self.confidence))
        return out

    def summary(self, labels: dict[str, str] = LABELS_EN) -> str:
        """Parçalar tek satırda."""
        return " · ".join(self.parts(labels))
