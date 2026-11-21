# SPDX-License-Identifier: AGPL-3.0-only
"""Telefona gelen mesaj kartı, arama kartı ve mesaj listesi.

Nino'nun MessageCard.swift dosyasından aktarıldı. GTA 6'da gelen mesaj kartı (üstte gönderenin adı "Donnie", altında
mesaj) altyazı değildir: Türkçesi siyah altyazı kutusunda değil, kartın üstünde yarı saydam yazıyla gösterilir.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

from .metin import Reading, has_letter, has_lower, normalize, split_spaces, trim

# Kısa mesajlı kartın sol kenarı en az burada olmalı (okunan alana oranla; GTA 6'da kart sağ alttadır).
SHORT_CARD_LEFT = 0.55

_PUNCT = ".,!?:;…\""


class Call(NamedTuple):
    name: str
    status: str


class Parts(NamedTuple):
    name: str
    body: str


def is_card(reading: Reading) -> bool:
    """İlk satır kısa bir ad (kişi ya da dükkân), altında en az üç sözcüklük küçük harfli mesaj varsa karttır.
    Konuşan adı iki noktalıysa ("ENZO: ...") altyazıdır, kart değildir."""
    lines = reading.lines
    if is_list(reading):
        return False
    if len(lines) < 2:
        return False
    name = lines[0]
    name_box = name.box
    first_body = lines[1].box
    if name_box is None or first_body is None:
        return False
    text = trim(name.text)
    # Gönderen: 1-4 sözcük, her biri büyük harfle başlar, cümle noktalaması yok.
    words = split_spaces(text)
    if not (2 <= len(text) <= 30 and 1 <= len(words) <= 4
            and all(w[0].isupper() or w[0] == "&" for w in words)
            # Tabela/reklam yazısı ("TREADBounD") ad değildir: sözcüğün içinde birden çok büyük harf olmaz.
            and all(sum(1 for c in w[1:] if c.isupper()) <= 1 for w in words)
            and has_lower(text)
            and not any(c in _PUNCT for c in text)):
        return False
    if not name_box.bottom <= first_body.top + 0.01:
        return False
    body = " ".join(line.text for line in lines[1:])
    body_words = len(split_spaces(body))
    if body_words >= 3:
        return has_lower(body)
    # Kısa mesaj ("On my way", "Ok"): ad + 1-2 sözcük yalnız okunan alanın sağ yarısında duruyorsa karttır.
    return body_words >= 1 and has_letter(body) and min(name_box.left, first_body.left) >= SHORT_CARD_LEFT


def call(reading: Reading) -> Optional[Call]:
    """Telefon araması kartı (üstte ad, altında "Calling...", "Incoming call" ya da süre "00:05"). Durumun Türkçesi
    hazırdır; süre gösterilirken (konuşma sürüyor) durum boştur."""
    lines = [t for t in (trim(line.text) for line in reading.lines) if t]
    if len(lines) != 2 or not is_name(lines[0]):
        return None
    state = lines[1].lower().strip(".… ")
    if state in ("calling", "dialing", "dialling", "connecting", "ringing"):
        return Call(lines[0], "aranıyor…")
    if state in ("incoming call", "incoming"):
        return Call(lines[0], "seni arıyor…")
    if state in ("call ended", "ended", "call failed", "busy", "no answer", "unavailable"):
        return Call(lines[0], "arama bitti")
    if re.search(r"^\d{1,2}:\d{2}(:\d{2})?$", lines[1]):
        return Call(lines[0], "")
    return None


def is_list(reading: Reading) -> bool:
    """Telefonun mesaj listesi (gönderen adları ve "…" ile kesilmiş önizlemeler alt alta)."""
    lines = [trim(line.text) for line in reading.lines]
    names = sum(1 for t in lines if is_name(t))
    truncated = sum(1 for t in lines if t.endswith("...") or t.endswith("…"))
    return len(lines) >= 3 and (names >= 2 or truncated >= 2)


def is_name(text: str) -> bool:
    words = split_spaces(text)
    return (2 <= len(text) <= 30 and 1 <= len(words) <= 4
            and all(w[0].isupper() or w[0] == "&" for w in words)
            and all(sum(1 for c in w[1:] if c.isupper()) <= 1 for w in words)
            and has_lower(text) and not any(c in _PUNCT for c in text))


def parts(reading: Reading) -> Parts:
    """Gönderenin adı ve mesaj metni."""
    name = trim(reading.lines[0].text) if reading.lines else ""
    return Parts(name, " ".join(trim(line.text) for line in reading.lines[1:]))


def repeats(text: str, body: str) -> bool:
    """Okuma, kartın metninin bir parçası mı (adı okunamayan kart): sözcüklerinin en az yarısı kartta geçiyorsa."""
    read = {w for w in split_spaces(normalize(text)) if len(w) > 1}
    card = set(split_spaces(normalize(body)))
    # Kısa mesajın adı okunmayan karesi: okunan sözcüklerin hepsi kartta geçiyorsa o da kartın parçasıdır.
    if len(card) <= 2:
        return bool(read) and read <= card
    if len(read) < 2:
        return False
    return len(read & card) / len(read) >= 0.5
