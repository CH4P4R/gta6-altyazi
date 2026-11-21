# SPDX-License-Identifier: AGPL-3.0-only
"""Harita ekranında seçilen görevin bilgi kartı (GTA 6).

Nino'nun MapCard.swift dosyasından aktarıldı. Kart: büyük harfli başlık ("BUY FLOWERS"), altında bir iki cümle
("Lucia will appreciate this", "Have some flowers delivered to the house for Lucia."). Menü çevrilmez ama kartın
Türkçesi kartın hemen altına yarı saydam yazılır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import menu
from .metin import Reading, TextBox, has_lower, letter_count, stride_to, trim
from .telefon import sampler


@dataclass
class Found:
    # Başlık (yoksa boş) ve cümleler, yukarıdan aşağı; her cümle ayrı çevrilir.
    title: str
    sentences: list[str] = field(default_factory=list)
    # Kartın yazılarını çevreleyen kutu (0–1, kareye göre).
    box: TextBox = field(default_factory=lambda: TextBox(0, 0, 0, 0))
    line_height: float = 0.0


_MAP_KEYS = frozenset(["recenter", "2d view", "3d view", "add marker", "remove marker", "set destination",
                       "remove destination", "close menu"])
_DISTANCE = re.compile(r"\s*\b\d+(?:[.,]\d+)?\s?(?:km|mi|ft|m)\b\s*")
_LEAD = re.compile(r"^(?:[^A-Za-z\s]+\s+)+(?=[A-Z])")
_ICON_CRUMBS = re.compile(r"^([iI•●◆△▲]|\S*\d\S*|ml)(\s+([iI•●◆△▲]|\S*\d\S*|ml))*\s+(?=[A-Z])")
_TITLE_TAIL = re.compile(r"(\s+[^A-Za-z\s]{1,3})+$")


def is_map_screen(reading: Reading) -> bool:
    """Harita ekranı mı: sağ alttaki tuş listesi ("RECENTER", "2D VIEW", "ADD MARKER", "SET DESTINATION"…)."""
    found = {t for t in (menu.clean(line.text).lower() for line in reading.lines) if t in _MAP_KEYS}
    return len(found) >= 2


def _ends_sentence_char(text: str) -> bool:
    return bool(text) and text[-1] in ".!?"


def find(reading: Reading) -> Optional[Found]:
    """Haritadaki kart: sol menü ve sağ alttaki tuş listesi dışında kalan, alt alta duran cümle satırları ve hemen
    üstlerindeki büyük harfli başlık."""
    lines: list[tuple[str, TextBox]] = []
    for line in reading.lines:
        if line.box is None or not line.box.right > 0.30:
            continue
        box = line.box.copy()
        text = trim(line.text)
        # Haritadaki uzaklık etiketi ("1.53 km") kartın satırıyla birlikte okunabiliyor; atılır ve satırın sol kenarı
        # kartın içinden sayılır.
        if _DISTANCE.search(text):
            text = trim(_DISTANCE.sub(" ", text))
            if box.left < 0.5:
                box.left = max(box.left, 0.5)
        # Haritadaki simge harf/sayı okunup satırın başına eklenebiliyor ("(43) Cal challenged…"); atılır, sol kenar
        # kalan yazıya göre kaydırılır.
        lead = _LEAD.search(text)
        if lead:
            share = lead.end() / max(1, len(text))
            box.left += (box.right - box.left) * share
            text = text[:lead.start()] + text[lead.end():]
        if not (box.left > 0.30 and letter_count(text) >= 3):
            continue
        if letter_count(text) >= 2:
            lines.append((text, box))
    lines.sort(key=lambda ln: ln[1].top)

    # Cümle satırı: küçük harfli, en az üç sözcük (yer adları ve uzaklıklar değil).
    def is_sentence(text: str) -> bool:
        return len([w for w in text.split(" ") if w]) >= 3 and sum(1 for c in text if c.islower()) >= 6

    body = [ln for ln in lines if is_sentence(ln[0])]
    if not body:
        return None
    first = body[0]
    # İlk cümleyle aynı kartta olanlar: alt alta ve yatayda üst üste. Cümlenin kısa son satırı ve paragraf
    # boşluğundan sonraki ikinci paragraf da karttadır; cümle olmayan satır yalnız önceki satırın hemen altında ve
    # aynı hizadaysa alınır.
    card = [first]
    for ln in lines:
        if not ln[1].top > first[1].top:
            continue
        last = card[-1]
        height = last[1].bottom - last[1].top
        gap = ln[1].top - last[1].bottom
        overlaps = ln[1].left < last[1].right and last[1].left < ln[1].right
        if is_sentence(ln[0]) and gap < height * 2.6 and overlaps and abs(ln[1].left - first[1].left) < 0.06:
            card.append(ln)
        elif (gap < height * 1.2 and abs(ln[1].left - last[1].left) < 0.03 and has_lower(ln[0])
              and not _ends_sentence_char(last[0])):
            card.append(ln)
    # Cümleler: sol kenarı aynı olan art arda satırlar tek cümledir; simgeyle başlayan satır biraz içeridedir, ayrı
    # cümledir. Erken biten satırdan sonra büyük harfle başlayan satır da yeni cümledir.
    reach = max(ln[1].right for ln in card)
    sentences: list[list[tuple[str, TextBox]]] = []
    for ln in card:
        # Küçük harfle başlayan satır her zaman önceki cümlenin devamıdır ("… dropped off" / "at his trailer.").
        prev_text = sentences[-1][-1][0] if sentences else ""
        prev_ended = not prev_text or prev_text[-1] in ".!?"
        continues = ln[0][:1].islower() and not prev_ended
        if sentences:
            head = sentences[-1][0]
            last = sentences[-1][-1]
            if continues or (abs(ln[1].left - head[1].left) < 0.03
                             and ln[1].top - last[1].bottom < (last[1].bottom - last[1].top) * 1.0
                             and not (last[1].right < reach - 0.04 and ln[0][:1].isupper())):
                sentences[-1].append(ln)
                continue
        sentences.append([ln])
    top = first[1]
    title = None
    for ln in lines:
        if (ln[1].bottom <= top.top + 0.01 and top.top - ln[1].bottom < 0.06
                and ln[1].left < top.right and top.left < ln[1].right + 0.05
                and ln[0] == ln[0].upper() and letter_count(ln[0]) >= 3):
            title = ln
    box = first[1].copy()
    for ln in card[1:]:
        box = box.union(ln[1])
    if title is not None:
        box = box.union(title[1])
    # Kartın altındaki hedef satırı ("GOAL  $100 / $5,000") cümle değildir ama karttadır; Türkçe onun üstüne binmesin.
    for ln in lines:
        if not ln[1].top >= box.bottom - 0.005:
            continue
        if not (ln[1].top - box.bottom < 0.05 and ln[1].left > box.left - 0.03 and ln[1].right < box.right + 0.08):
            continue
        box = box.union(ln[1])
    heights = sorted(ln[1].bottom - ln[1].top for ln in card)
    # Bilgi simgesi ("ⓘ") harf okunur; simge kırıntıları ("4 ml", "△", "00") baştan atılır. Satır sonunda tireyle
    # bölünen kelime ("burned-" / "out the") birleşik kalır.
    texts = [_ICON_CRUMBS.sub("", " ".join(ln[0] for ln in s).replace("- ", "-")) for s in sentences]
    heading = _TITLE_TAIL.sub("", title[0] if title is not None else "")
    return Found(heading, texts, box, heights[len(heights) // 2])


def frame(box: TextBox, image) -> Optional[TextBox]:
    """Kartın koyu çerçevesi, haritanın aydınlık zemininden ayrılarak görüntüden bulunur: yazıların kutusundan dışa
    doğru koyu kısım bitene kadar gidilir. `image`: HxWx3 (BGR) ya da HxWx4 (BGRA) uint8 dizi."""
    color = sampler(image, width=640, height=360)

    def dark(x: float, y: float) -> bool:
        c = color(x, y)
        if c is None:
            return False
        return (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000 < 130

    rows = list(stride_to(box.top + 0.01, box.bottom, 0.02))
    columns = list(stride_to(box.left + 0.01, box.right, 0.03))
    if not rows or not columns:
        return None

    # Bir yönde koyu satır/sütunların çoğu bitene kadar ilerlenir.
    def edge(start: float, step: float, limit: float, dark_at: Callable[[float], int], total: int) -> float:
        position = start
        while abs(position - start) < limit and dark_at(position + step) * 2 >= total:
            position += step
        return position

    # Kenar sınıra kadar bulunamadıysa (gece haritası da koyu) o yanda yazıların kutusu biraz paylı kullanılır.
    def bounded(found: float, start: float, limit: float, fallback: float) -> float:
        return fallback if abs(found - start) >= limit - 0.004 else found

    def dark_rows(x: float) -> int:
        return sum(1 for y in rows if dark(x, y))

    def dark_columns(y: float) -> int:
        return sum(1 for x in columns if dark(x, y))

    left = bounded(edge(box.left, -0.003, 0.04, dark_rows, len(rows)), box.left, 0.04, box.left - 0.015)
    right = bounded(edge(box.right, 0.003, 0.09, dark_rows, len(rows)), box.right, 0.09, box.right + 0.02)
    bottom = bounded(edge(box.bottom, 0.004, 0.08, dark_columns, len(columns)), box.bottom, 0.08, box.bottom + 0.02)
    top = bounded(edge(box.top, -0.004, 0.06, dark_columns, len(columns)), box.top, 0.06, box.top - 0.02)
    # Kart en az yazıların kutusu kadardır; koyu zemin bulunamadıysa (karanlık harita) yazıların kutusu kullanılır.
    if not right - left > box.right - box.left:
        return None
    return TextBox(left, top, right, bottom)
