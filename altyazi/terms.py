"""Sözlük terimlerini yerel çeviri modelinden korur.

OPUS-MT özel adları bazen çevirir ya da bozar ("Vice City" → "Kusur Şehri"). Çeviriden önce her terim uydurma bir
özel adla (Zarmon, Velkor...) değiştirilir; model bu adı olduğu gibi bırakıp Türkçe ekini takar ("Zarmon'a").
Çeviriden sonra ad, sözlükteki Türkçe karşılıkla değiştirilir ve ek ünlü uyumuna göre yeniden kurulur
("Vice City'ye"). Uydurma ad çeviride kaybolursa None döner; çağıran korumasız çeviriye döner.

Fikir CouchSubs'ın TermProtection'ından (https://github.com/yorulmazsinan/couchsubs, AGPL-3.0, Sinan Yorulmaz).
"""

from __future__ import annotations

import re

PLACEHOLDERS = ["Zarmon", "Velkor", "Dorvan", "Kelmar", "Tolvar", "Brandur", "Halvor", "Feldor"]
_VOWELS = "aeıioöuü"
_BACK = "aıou"
_ROUND = "oöuü"
_VOICELESS = "fstkçşhp"
_LOWER = str.maketrans("Iİ", "ıi")


def _low(s: str) -> str:
    return s.translate(_LOWER).lower()


def protect(text: str, glossary: dict[str, str]) -> tuple[str, dict[str, str]]:
    """(korunmuş metin, {uydurma ad: Türkçe terim})"""
    mapping: dict[str, str] = {}
    if not glossary:
        return text, mapping
    for term in sorted(glossary, key=len, reverse=True):
        if len(mapping) >= len(PLACEHOLDERS):
            break
        pat = re.compile(rf"(?<![\w']){re.escape(term)}(?![\w])")
        if not pat.search(text) or any(p in text for p in PLACEHOLDERS[len(mapping):len(mapping) + 1]):
            continue
        ph = PLACEHOLDERS[len(mapping)]
        text = pat.sub(ph, text)
        mapping[ph] = glossary[term]
    return text, mapping


def _sound(term: str) -> tuple[str, bool, str]:
    """(son ünlü, ünlüyle mi bitiyor, son harf) — İngilizce adlarda sondaki 'y' 'i' gibi okunur (City)."""
    w = _low(term.strip())
    if w.endswith("y") and len(w) > 1 and w[-2] not in _VOWELS:
        w = w[:-1] + "i"
    vowels = [c for c in w if c in _VOWELS]
    last_vowel = vowels[-1] if vowels else "e"
    last = w[-1] if w else "e"
    return last_vowel, last in _VOWELS, last


def harmonize(term: str, suffix: str) -> str:
    """Zarmon'a eki → term'e uygun ek (Vice City + a → Vice City'ye)."""
    if not suffix:
        return term
    vowel, ends_vowel, last = _sound(term)
    out = []
    for i, ch in enumerate(_low(suffix)):
        if ch in "ae":
            ch = "a" if vowel in _BACK else "e"
        elif ch in "ıiuü":
            back, rnd = vowel in _BACK, vowel in _ROUND
            ch = ("u" if rnd else "ı") if back else ("ü" if rnd else "i")
        elif i == 0 and ch in "dt":
            ch = "t" if (not ends_vowel and last in _VOICELESS) else "d"
        if ch in _VOWELS:
            vowel = ch
        out.append(ch)
    s = "".join(out)
    if ends_vowel and s[0] in _VOWELS:
        s = ("n" if s[:2] in ("ın", "in", "un", "ün") else "y") + s
    elif ends_vowel and s[:2] in ("la", "le"):           # ile: Lucia'yla
        s = "y" + s
    return f"{term}'{s}"


def restore(translation: str, mapping: dict[str, str]) -> str | None:
    if not mapping:
        return translation
    out = translation
    for ph, term in mapping.items():
        pat = re.compile(rf"{ph}(?:['’]?([a-zçğıöşü]+))?", re.IGNORECASE)
        if not pat.search(out):
            return None
        out = pat.sub(lambda m, t=term: harmonize(t, m.group(1) or ""), out)
    return out
