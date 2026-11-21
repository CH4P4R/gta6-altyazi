# SPDX-License-Identifier: AGPL-3.0-only
"""Sözlük teriminin Türkçe eki.

Nino Game Translator'ın TurkishSuffix.swift dosyasından taşındı (core/Sources/CouchSubsCore/TurkishSuffix.swift;
Windows: CouchSubs.Core/TurkishSuffix.cs, aynı kurallar).

Çeviri motoru terimin yerindeki yer tutucu ada bir ek koyar ("Zarmon'a", "Zarmon'un", "Zarmon'da"); ek, hangi hâl
olduğu korunarak gerçek terime göre yeniden kurulur:
- ünlü uyumu: Kratos'u, Midgard'ı, Freya'yı; Atreus'un, Midgard'ın
- kaynaştırma: ünlüyle biten terime y / n gelir (Freya'ya, Freya'nın)
- ünsüz benzeşmesi: sert ünsüzden sonra -da/-dan → -ta/-tan (Kratos'ta)
- özel ad (büyük harfle başlayan terim) kesmeyle ayrılır; cins ad bitişik yazılır, p/ç/k yumuşar (kılıcı)
- çok sözcüklü ve dar ünlüyle biten terim tamlama sayılır: hâl ekinden önce n gelir (Leviathan Baltası'nı)
"""

from __future__ import annotations

from collections.abc import Sequence

from ._harf import tr_kucuk

_UNLULER = frozenset("aeıioöuü")
_KALIN = frozenset("aıou")
_YUVARLAK = frozenset("oöuü")
_DAR = frozenset("ıiuü")
_SERT = frozenset("fstkçşhp")
# Daha uzun "ek" büyük olasılıkla ek değildir; dokunulmaz.
MAX_SUFFIX_LENGTH = 12


def attach(term: str, suffix: str, apostrophe: str = "'") -> str:
    """`term` + ek. `suffix` motorun yer tutucuya koyduğu ektir (kesmesiz: "a", "un", "ya", "dan"); boşsa terim döner."""
    if not term or not suffix:
        return term
    body = list(tr_kucuk(suffix))
    if len(body) > MAX_SUFFIX_LENGTH or not all(c.isalpha() for c in body):
        return term + apostrophe + suffix

    proper = term[0].isupper()
    words = [w for w in term.split(" ") if w]
    last_word = tr_kucuk(words[-1] if words else term)
    last_letter = next((c for c in reversed(last_word) if c.isalpha()), " ")
    last_vowel = next((c for c in reversed(last_word) if c in _UNLULER), None)
    # Ünlüsüz kısaltma ("XP", "HP") harf adlarıyla okunur: "iks-pe" → ince, ünlüyle biter.
    ends_with_vowel = last_vowel is None or last_letter in _UNLULER
    if last_vowel is None:
        last_vowel = "e"
    compound = " " in term and last_letter in _DAR and len(last_word) >= 3
    is_voiceless = not ends_with_vowel and last_letter in _SERT

    # Baştaki kaynaştırma harfi yer tutucuya göreydi ("Zarmon" ünsüzle biter, çoğu zaman yoktur); atılır.
    if len(body) >= 2 and body[0] == "y" and (body[1] in _UNLULER or body[1] == "l"):
        body.pop(0)
    elif len(body) >= 3 and body[0] == "n" and body[1] in _DAR and body[2] == "n":
        body.pop(0)

    genitive = len(body) >= 2 and body[0] in _DAR and body[1] == "n" and (len(body) == 2 or body[2] not in _UNLULER)
    instrumental = (len(body) >= 2 and body[0] == "l" and body[1] in ("a", "e")
                    and not (len(body) >= 3 and body[2] == "r"))
    buffer = ""
    if body[0] in _UNLULER:
        if compound or (ends_with_vowel and genitive):
            buffer = "n"
        elif ends_with_vowel:
            buffer = "y"
    elif body[0] in ("d", "t"):
        if compound:
            buffer = "n"
        body[0] = "d" if compound or not is_voiceless else "t"
    elif instrumental and (ends_with_vowel or compound):
        buffer = "y"

    harmonized = harmonize(body, last_vowel)
    if proper:
        return term + apostrophe + buffer + harmonized
    stem = soften(term) if not buffer and harmonized[0] in _UNLULER else term
    return stem + buffer + harmonized


def harmonize(body: Sequence[str], after: str) -> str:
    """Ekteki a/e ve ı/i/u/ü ünlülerini önceki ünlüye (`after`) uydurur; "-ki" (Midgard'daki) değişmez."""
    output = []
    previous = after
    for index, original in enumerate(body):
        character = original
        invariant_ki = character == "i" and index > 0 and body[index - 1] == "k" and index == len(body) - 1
        if not invariant_ki and character in ("a", "e"):
            character = "a" if previous in _KALIN else "e"
        elif not invariant_ki and character in _DAR:
            back = previous in _KALIN
            rounded = previous in _YUVARLAK
            character = ("u" if rounded else "ı") if back else ("ü" if rounded else "i")
        if character in _UNLULER:
            previous = character
        output.append(character)
    return "".join(output)


def soften(term: str) -> str:
    """Cins adın son p/ç/k'si ünlüyle başlayan ekten önce yumuşar (kitap → kitabı, kılıç → kılıcı, bıçak → bıçağı,
    renk → rengi). Tek heceli sözcükler yumuşamaz (top → topu); t çoğu sözcükte yumuşamadığı için dokunulmaz."""
    if len(term) < 2:
        return term
    last = term[-1]
    words = [w for w in tr_kucuk(term).split(" ") if w]
    word = words[-1] if words else ""
    if word.endswith("nk"):
        return term[:-1] + "g"
    if sum(1 for c in word if c in _UNLULER) < 2:
        return term
    softened = {"p": "b", "ç": "c", "k": "ğ"}.get(last)
    return term[:-1] + softened if softened else term
