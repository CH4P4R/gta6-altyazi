# SPDX-License-Identifier: AGPL-3.0-only
"""Uzun çevirinin ekranda dengeli satırlara bölünmesi.

Nino Game Translator'ın SubtitleWrap.swift dosyasından taşındı (core/Sources/CouchSubsCore/SubtitleWrap.swift;
Android SubtitleWrap.kt, Windows SubtitleWrap.cs, TV sayfası ve OBS sayfası aynı kuralları uygular).

Satır başına en çok `MAX_CHARS` karakter, en çok 3 satır, kelime sınırından ve dengeli bölünür. 3 satıra sığmayacak
kadar uzunsa yazı biraz küçülür (`scale`, en çok `MIN_SCALE`'e kadar). Konuşan adı ("ARTHUR: ...") bölünmez, hep ilk
satırdadır.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

MAX_CHARS = 42
MAX_LINES = 3
MIN_SCALE = 0.75


@dataclass(frozen=True)
class Result:
    text: str
    scale: float


def fit(text: str) -> Result:
    """Bölünmüş metin ve yazı boyu çarpanı. Zaten satır sonu içeren ya da kısa metin olduğu gibi döner."""
    length = len(text)
    if length <= MAX_CHARS or "\n" in text:
        return Result(text, 1.0)
    words = tokens(text)
    if len(words) <= 1:
        return Result(text, 1.0)
    scale = min(max(max(MIN_SCALE, MAX_CHARS * MAX_LINES / length), MIN_SCALE), 1.0)
    cap = math.floor(MAX_CHARS / scale)
    lines = min(MAX_LINES, max(2, math.ceil(length / cap)))
    return Result(balance(words, min(lines, len(words))), scale)


def tokens(text: str) -> list[str]:
    """Sözcükler; konuşan adı ("ARTHUR:") sonraki sözcükle birleşik tutulur, böylece ad satır sonunda tek kalmaz."""
    words = text.split()
    colon = next((i for i, w in enumerate(words[:3]) if w.endswith(":") or w.endswith("：")), None)
    if colon is not None and colon + 1 < len(words):
        words[0:colon + 2] = [" ".join(words[0:colon + 2])]
    return words


def balance(words: Sequence[str], lines: int) -> str:
    """En uzun satırı en kısa yapan bölme; eşitlikte uzunlukların kareleri toplamı küçük olan (daha dengeli) seçilir."""
    count = len(words)

    def width(start: int, end: int) -> int:
        return sum(len(w) for w in words[start:end]) + (end - start - 1)

    best: tuple[int, int, list[int]] | None = None

    def consider(cuts: list[int]) -> None:
        nonlocal best
        edges = [0] + cuts + [count]
        widths = [width(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
        key = (max(widths, default=0), sum(w * w for w in widths))
        if best is None or key < (best[0], best[1]):
            best = (key[0], key[1], cuts)

    if lines == 2:
        for a in range(1, count):
            consider([a])
    elif count >= 3:
        for a in range(1, count - 1):
            for b in range(a + 1, count):
                consider([a, b])
    else:
        for a in range(1, count):
            consider([a])
    if best is None:
        return " ".join(words)
    edges = [0] + best[2] + [count]
    return "\n".join(" ".join(words[edges[i]:edges[i + 1]]) for i in range(len(edges) - 1))
