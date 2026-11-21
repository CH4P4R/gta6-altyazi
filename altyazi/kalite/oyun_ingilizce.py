# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun deyimlerini çeviriden önce düz İngilizceye çevirir.

Nino Game Translator'ın GameEnglish.swift dosyasından taşındı (core/Sources/CouchSubsCore/GameEnglish.swift; Windows'taki
`GameEnglish` ile aynı liste).

Oyunlarda sık geçen, yerel çevirinin kelime kelime çevirdiği ifadeler ("I've got your six" → "Altını aldım") aynı
anlamdaki düz İngilizceye çevrilir. `altyazi/slang.py` bu listenin bir kısmını farklı karşılıklarla içerir; ikisi
birlikte kullanılacaksa sıra README_entegrasyon'da.
"""

from __future__ import annotations

import re

PHRASES: tuple[tuple[str, str], ...] = (
    ("friendlies", "allies"),
    ("(?:I've|I) got your six", "I've got your back"),
    ("check your six", "watch behind you"),
    ("heads up", "watch out"),
    ("took you long enough", "you're late"),
    ("we've got company", "enemies are coming"),
    ("lock and load", "get ready"),
    ("sitting ducks", "easy targets"),
    ("moving in", "going in"),
)
_PATTERNS = [(re.compile(r"\b" + pattern + r"\b", re.IGNORECASE), plain) for pattern, plain in PHRASES]


def plain(sentence: str) -> str:
    """Bilinen ifadeler düz İngilizceye çevrilir; cümle başındaki büyük harf korunur."""
    text = sentence
    for pattern, replacement_text in _PATTERNS:
        def replacement(match: re.Match, replacement_text: str = replacement_text) -> str:
            if match.group(0)[:1].isupper():
                return replacement_text[:1].upper() + replacement_text[1:]
            return replacement_text
        text = pattern.sub(replacement, text)
    return text
