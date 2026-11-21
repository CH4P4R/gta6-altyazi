# SPDX-License-Identifier: AGPL-3.0-only
"""Sol üstteki ipucu kutusunu haritadaki yer adlarından ayırır.

Nino'nun CornerBlock.swift dosyasından aktarıldı. İpucu kutusu alt alta, birbirine yakın, yatay satırlardan oluşan ve
birkaç kelimelik cümle içeren bir bloktur; harita yer adları tek tek, kısa ve dağınıktır.
"""

from __future__ import annotations

from typing import Optional

from .metin import Reading, TextLine, letter_count, split_where, trim

# Bloğun çevrilmeye değmesi için en az kelime sayısı ("Cumberland Falls" gibi iki kelimelik yer adı geçmez).
MINIMUM_WORDS = 4


def tip_box(reading: Reading, aspect: float = 16.0 / 9.0) -> Reading:
    """Okunan satırlardan ipucu kutusunu seçer; yoksa boş okuma döner. `aspect`: ekranın en/boy oranı."""
    candidates = []
    for line in reading.lines:
        box = line.box
        if box is None:
            continue
        # Yan ya da dik yazılmış yazı (harita) atlanır: gerçek en/boy oranıyla yatay olmalı.
        if not (box.right - box.left) * aspect > (box.bottom - box.top) * 1.2:
            continue
        # "CA", "NH" gibi kısaltmalar ve tek harfler atlanır.
        if letter_count(line.text) >= 3:
            candidates.append(line)
    candidates.sort(key=lambda ln: ln.box.top if ln.box is not None else 0)

    blocks: list[list[TextLine]] = []
    for line in candidates:
        box = line.box
        if blocks and blocks[-1] and blocks[-1][-1].box is not None:
            block = blocks[-1]
            last = block[-1].box
            span = _span(block)
            if span is not None:
                height = _median_height(block)
                close = box.top - last.bottom <= height * 1.8
                overlaps = box.left < span[1] and box.right > span[0]
                if close and overlaps:
                    block.append(line)
                    continue
        blocks.append([line])
    if not blocks:
        return Reading([])
    best = max(blocks, key=words)
    if not (words(best) >= MINIMUM_WORDS or (words(best) >= 2 and starts_with_marker(best))):
        return Reading([])
    return Reading(list(best))


def starts_with_marker(block: list[TextLine]) -> bool:
    """Görev işaretiyle ("◆ Escape the mine") başlayan kısa satır da görevdir; harita adlarının işareti yoktur."""
    if not block:
        return False
    text = trim(block[0].text)
    if not text:
        return False
    first = text[0]
    return not first.isalpha() and not first.isnumeric() and not first.isspace() and first not in "\"'("


def words(block: list[TextLine]) -> int:
    return sum(len([w for w in split_where(line.text, lambda c: not c.isalpha() and c != "'") if len(w) >= 2])
               for line in block)


def _span(block: list[TextLine]) -> Optional[tuple[float, float]]:
    boxes = [line.box for line in block if line.box is not None]
    if not boxes:
        return None
    return min(b.left for b in boxes), max(b.right for b in boxes)


def _median_height(block: list[TextLine]) -> float:
    heights = sorted(line.box.bottom - line.box.top for line in block if line.box is not None)
    return heights[len(heights) // 2] if heights else 0.03
