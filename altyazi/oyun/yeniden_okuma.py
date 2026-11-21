# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın Pipeline/Rereads.swift dosyasından taşındı.

Aynı altyazının farklı okumalarını tanıma kuralları. Hat yarım ya da bozuk okumayı kısa süre bekletip aynı satırın en
iyi okumasını çevirir; bu kurallar hangi okumanın aynı satır sayılacağını söyler.
"""

from __future__ import annotations

from . import metin
from .paket_bulanik import damaged


def looks_misread(text: str) -> bool:
    """Okuma bozuk mu (OCR izi taşıyor mu)."""
    return damaged(text)


def score(text: str) -> int:
    """Okumanın puanı: daha çok gerçek sözcük, daha uzun."""
    return metin.ocr_score(text)


def _words(text: str) -> list[str]:
    return metin.normalize(text).split()


def _lines(text: str) -> list[str]:
    return [ln.strip(" \t") for ln in text.split("\n") if ln.strip(" \t")]


def looks_complete(text: str) -> bool:
    """Her satırı büyük harfle başlayıp nokta, soru, ünlem ya da üç noktayla biten okuma."""
    lines = _lines(text)
    if not lines:
        return False
    for line in lines:
        first = next((ch for ch in line if metin.is_letter(ch)), None)
        if first is None or not first.isupper() or not metin.ends_sentence(line):
            return False
    return True


def related(a: str, b: str) -> bool:
    """İki okuma aynı altyazının okunuşları mı: ortak sözcükler kısa olanın en az yarısı (iki sözcükten kısa
    satırlarda biri ötekini içermeli)."""
    x, remaining = _words(a), _words(b)
    y_size = len(remaining)
    if not x or y_size == 0:
        return False
    shared = 0
    for word in x:
        if word in remaining:
            remaining.remove(word)
            shared += 1
    shorter = min(len(x), y_size)
    return shared >= 1 if shorter <= 1 else (shared >= 2 and shared * 2 >= shorter)


def _gapped_subsequence(x: list[str], y: list[str]) -> bool:
    """`x` sözcükleri `y`'de aynı sırada geçiyor ama bitişik bir parça değil."""
    i, first, last = 0, -1, -1
    for j, word in enumerate(y):
        if i >= len(x):
            break
        if word != x[i]:
            continue
        if first < 0:
            first = j
        last = j
        i += 1
    return i == len(x) and last - first + 1 > len(x)


def is_reread_of(newer: str, older: str) -> bool:
    """`newer`, `older`'ın yeniden okuması mı: biri bozuksa ortak sözcükler yeter; ikisi de temizse yeni okuma eskinin
    kesilmiş bir parçası olmalı ve cümle sonu işareti taşımamalı ("Get Franklin close to the")."""
    # Eskide olmayan olumsuzluk ya da sayı taşıyan okuma yeniden okuma değil, düzeltmedir.
    if metin.adds_meaning(newer, older):
        return False
    norm_newer, norm_older = metin.normalize(newer), metin.normalize(older)
    x, y = norm_newer.split(), norm_older.split()
    if len(norm_newer) >= 4 and len(x) == len(y) and metin.is_similar(norm_newer, norm_older, 0.75):
        return True
    if len(x) >= 2 and len(x) == len(y):
        differing = [i for i in range(len(x)) if x[i] != y[i]]
        if differing and len(differing) * 2 <= len(x) and all(looks_misread(x[i]) for i in differing):
            return True
    if looks_misread(newer) or looks_misread(older):
        return related(newer, older)
    if not x or len(x) > len(y):
        return False
    if 2 <= len(x) < len(y) and _gapped_subsequence(x, y):
        return True
    head = newer.lstrip()[:1]
    starts_lower = not (head and head.isupper())
    if metin.ends_sentence(newer) and not (starts_lower and len(x) < len(y)):
        return False
    return any(y[s:s + len(x)] == x for s in range(len(y) - len(x) + 1))


def _covered(line: str, previous: str) -> bool:
    norm = metin.normalize(line)
    if not norm:
        return True
    if is_reread_of(line, previous.replace("\n", " ")):
        return True
    return any(metin.normalize(old) == norm or is_reread_of(line, old) for old in previous.split("\n") if old)


def all_lines_covered(reading: str, previous: str) -> bool:
    """Okumanın her satırı az önce çevrilenin (aynı ya da yeniden okunmuş) bir satırı mı."""
    lines = _lines(reading)
    return bool(lines) and all(_covered(ln, previous) for ln in lines)


def keep_missing_lines(better: str, older: str) -> str:
    """Daha iyi okuma bekleyenin yerine geçerken bekleyende olup yenisinde olmayan temiz satırlar korunur (iki satırlı
    altyazının ikinci satırı bir okumada çıkıp ötekinde kaçabiliyor)."""
    corrected = [ln for ln in better.split("\n") if ln]
    extra = [
        line for line in _lines(older)
        if not looks_misread(line) and not _covered(line, better) and not any(
            metin.adds_meaning(fixed, line) and metin.is_similar(metin.normalize(fixed), metin.normalize(line))
            for fixed in corrected)
    ]
    if not extra:
        return better
    return better.rstrip() + "\n" + "\n".join(extra)
