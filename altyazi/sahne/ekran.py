# SPDX-License-Identifier: AGPL-3.0-only
"""Ekrandaki bir yazının Türkçesi ve TV'de duracağı yer (ScreenItem).

Nino'nun ScreenTranslation.swift dosyasındaki `Item` yapısından aktarıldı; `to_json` SubtitleServer.sendScreen'in
öğe JSON'uyla aynıdır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .metin import TextBox, swift_round


def _round4(value: float) -> float:
    """Kutu ve satır yüksekliği: 0–1 arasına sıkıştırılıp 4 basamağa yuvarlanır."""
    return swift_round(max(0.0, min(1.0, value)) * 10000) / 10000


def box_json(box: TextBox) -> dict[str, float]:
    """SubtitleServer.json(_ box:): left/top/right/bottom anahtarları."""
    return {"left": _round4(box.left), "top": _round4(box.top),
            "right": _round4(box.right), "bottom": _round4(box.bottom)}


@dataclass
class ScreenItem:
    """Çevrilen bir ekran yazısı. `translation`: parçaların çevirisi, her parça ayrı satırda."""

    source: str
    translation: str
    box: TextBox
    line_height: float
    # Kutusuz, oyunun kendi yazısı gibi gölgeli sade yazı.
    plain: bool = False
    # Eğik yazı (telefon araması: "Paradise Taxi aranıyor…").
    italic: bool = False
    # Oyunun kendi kutusunun rengi ("#e9e9ec"); verilmişse Türkçe o kutunun üstüne aynı zeminle, `ink` renginde yazılır.
    fill: Optional[str] = None
    ink: Optional[str] = None
    # Yazının dönme açısı (derece, saat yönü artı): eğik tutulan telefonun balonları da eğiktir.
    angle: Optional[float] = None
    # Zeminin saydamlığı (0–1; `fill` ile).
    alpha: Optional[float] = None
    # Oyunun kutusunun üstünde değil yanında duran balon.
    side: bool = False
    # Yazısız zemin (telefonun yanındaki mesajlaşma paneli).
    backdrop: bool = False
    # Harita kartının Türkçesi; TV oyunun kartı gibi çizer.
    card: bool = False
    # Birden çok parça: TV satır satır, sola yaslı gösterir. Swift'te `translation` "\n" içeriyorsa kendiliğinden
    # doğrudur; burada ayrıca elle de açılabilir.
    paragraphs: bool = False

    @property
    def has_paragraphs(self) -> bool:
        return self.paragraphs or "\n" in self.translation

    def to_json(self) -> dict[str, Any]:
        """SubtitleServer.sendScreen'deki öğe: isteğe bağlı anahtarlar yalnız verilmişse yazılır."""
        json: dict[str, Any] = {"box": box_json(self.box), "line": _round4(self.line_height), "text": self.translation}
        if self.has_paragraphs:
            json["paragraphs"] = True
        if self.plain:
            json["plain"] = True
        if self.italic:
            json["italic"] = True
        if self.fill is not None:
            json["fill"] = self.fill
        if self.ink is not None:
            json["ink"] = self.ink
        if self.angle is not None and abs(self.angle) >= 0.3:
            json["angle"] = swift_round(self.angle * 10) / 10
        if self.alpha is not None:
            json["alpha"] = swift_round(max(0.0, min(1.0, self.alpha)) * 100) / 100
        if self.side:
            json["side"] = True
        if self.backdrop:
            json["backdrop"] = True
        if self.card:
            json["card"] = True
        return json
