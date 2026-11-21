# SPDX-License-Identifier: AGPL-3.0-only
"""Yazı tanımanın ürettiği çöp sözcükleri ayıklar ve okumaları puanlar.

Nino Game Translator'ın OcrNoise.swift dosyasından taşındı (core/Sources/CouchSubsCore/OcrNoise.swift; Windows:
CouchSubs.Core/OcrNoise.cs).

Süslü yazı tiplerinde, solan ya da titreyen altyazıda yazı tanıma bazı sözcükleri harf, rakam ve simge karışımı çöpe
çevirir ("ou$3e", "waters2aljd"). Bunlar hiçbir dilde sözcük değildir; çevirmen onları olduğu gibi taşır. Sözcük
ortasında simge ya da harflerle rakamların iç içe geçtiği parçalar atılır; gerçek bir sözcüğe yapışmış çöp
("waters2aljd") sözcükten ayrılır. "PS5", "R2", "2nd", "100m", "$500" gibi olağan biçimler korunur.
`pipeline.clean_ocr`'dan önce, her OCR satırına ayrı ayrı uygulanır (oradaki "|" → "I" dönüşümü buradaki akıllı
"|"/"l" kuralını gizler).
"""

from __future__ import annotations

import re
import unicodedata

_SYMBOLS = frozenset("$@#%^*_=|\\~<>{}¢£¥§©®°±µ¶¤")
_QUOTES = frozenset("\"'“”‘’«»()[]")


def _edge_punctuation(character: str) -> bool:
    """Sözcüğün başından/sonundan ayrılan noktalama: P* ve S* kategorileri (simgeler hariç) ve tırnak/parantezler."""
    if character in _QUOTES:
        return True
    return unicodedata.category(character)[0] in "PS" and character not in _SYMBOLS


def clean(line: str) -> str:
    """Satırdaki çöp sözcükleri, artık noktalamayı ve göstergenin satıra yapışan sayısını atar."""
    kept: list[str] = []
    tokens = line.split()
    for index, token in enumerate(tokens):
        lead, core, trail = _split(token)
        # Tek başına "l" ya da "|" çoğu zaman yanlış okunmuş "I"dır ("l don't know", "|'ll go"); ardından küçük
        # harfle başlayan sözcük yoksa ve token ?/! ile bitmiyorsa altyazı kutusunun kenarı olabilir.
        pronoun = _misread_i(core)
        if pronoun is not None:
            following = None
            if index + 1 < len(tokens):
                following = next((c for c in tokens[index + 1] if c.isalpha()), None)
            ends_question_or_exclamation = any(c in "?!" for c in trail)
            if pronoun != "I" or (following is not None and following.islower()) or ends_question_or_exclamation:
                kept.append(lead + pronoun + trail)
            continue
        # Yalnız "?!", ".", "," gibi işaretlerden oluşan parça: satır başında ya da cümle bittikten sonra yazı
        # tanımanın uydurmasıdır ("?! Where", "car. ?!"); sözcükten ayrı düşmüşse sözcüğe yapışır ("going ?!").
        if not core and _is_stray_punctuation(token):
            if kept and kept[-1] and kept[-1][-1] not in ".?!…,;:":
                kept[-1] = kept[-1] + token
            continue
        fixed = _clean_core(core)
        if fixed is not None:
            kept.append(lead + fixed + trail)
        elif trail and kept:
            # Atılan çöpün ardındaki noktalama cümleye aittir ("ou$3e," → virgül kalır).
            kept[-1] = kept[-1] + trail
    # Altyazının yanındaki göstergenin sayısı satırın başına yapışıyor ("9? We'll lose", "100. Mac and John").
    # Mesafe işareti de öyle ("23m CESARE: Here!"). Tek başına sayı ve ardından büyük harfle başlayan cümle: sayı atılır.
    if len(kept) >= 3 and _GAUGE.search(kept[0]) and kept[1][:1].isupper():
        kept.pop(0)
    return " ".join(kept)


_GAUGE = re.compile(r"^\d+(?:m|km|ft|yd)?[.?!:;]?$")


def score(text: str) -> int:
    """Bir okumanın ne kadar sözcük gibi göründüğü: düzgün sözcüklerin harfleri artı, çöp ve karışık büyük-küçük
    harfli parçalar ("CESAREiVJütt'h") eksi sayılır (Windows: OcrNoise.Score)."""
    total = 0
    for token in text.split():
        core = _split(token)[1]
        letters = "".join(c for c in core if c.isalpha())
        if not letters:
            continue
        total += len(letters) if _is_clean_word(core, letters) else -2 * len(letters)
    return total


def looks_garbled(text: str) -> bool:
    """Okuma çöp gibi mi: harflerinin altıda birinden çoğu bozuk sözcüklerde (karışık büyük-küçük harf, simge, ünlüsüz
    "Gtt"). Altyazılar geçişte birbirinin üstüne solarken yazı tanıma iki satırı karıştırıp ("Gtt solkolfege.")
    noktayla biten bir çöp okuyordu; nokta yüzünden ilk karede çevriliyor, TV'de anlamsız bir cümle beliriyordu."""
    good = bad = 0
    for token in text.split():
        core = _split(token)[1]
        letters = "".join(c for c in core if c.isalpha())
        if not letters:
            continue
        if _is_clean_word(core, letters):
            good += len(letters)
        else:
            bad += len(letters)
    return bad * 6 > good + bad


def _is_clean_word(core: str, letters: str) -> bool:
    # Sözcük ortasındaki parantez ("the[lil") de okuma karışıklığıdır.
    return _clean_core(core) == core and _normal_case(core) and not any(c in "[]()" for c in core) \
        and not _vowelless(letters)


def _vowelless(letters: str) -> bool:
    """Üç ve daha çok harfli, ünlüsüz ve kısaltma olmayan (tümü büyük harf değil) sözcük: İngilizcede olmaz ("Gtt")."""
    return len(letters) >= 3 and not all(c.isupper() for c in letters) \
        and not any(c in "aeiouyäöüıàáâèéêìíîòóôùúû" for c in letters.lower()) \
        and _collapsed(letters.lower()) not in INTERJECTIONS


# Ünlüsüz ama gerçek ünlemler ("Hmm", "Shh", "Brr", "Grr", "Psst", "Pfft", "Mmm", "Zzz", "Tsk"); art arda tekrarlar tek harf.
INTERJECTIONS = frozenset(["hm", "m", "sh", "br", "gr", "pst", "pft", "tsk", "hrm", "z", "pht"])


def _collapsed(text: str) -> str:
    result = ""
    for character in text:
        if not result or character != result[-1]:
            result += character
    return result


def _normal_case(core: str) -> bool:
    """"word", "WORD", "Word", "McDonald", "don't": büyük harf yalnız başta ya da baştan bir dizi."""
    letters = [c for c in core if c.isalpha()]
    if all(c.isupper() for c in letters) or all(c.islower() for c in letters[1:]):
        return True
    # Tek iç büyük harf ("McDonald", "iPhone") olağan; daha fazlası OCR karışıklığıdır.
    return sum(1 for c in letters[1:] if c.isupper()) == 1 and sum(1 for c in letters if c.islower()) >= 2


def _misread_i(core: str) -> str | None:
    """"l", "|", "l'm", "|'ll" → "I", "I'm", "I'll" (None: böyle bir okuma değil)."""
    if not core or core[0] not in ("l", "|"):
        return None
    rest = core[1:]
    if not rest:
        return "I"
    if rest[0] not in ("'", "’") or rest[1:] not in ("m", "ll", "ve", "d"):
        return None
    return "I" + rest


def _is_stray_punctuation(token: str) -> bool:
    """Yalnız ? ! . , ; : işaretlerinden oluşan parça; üç nokta ("...") gerçek noktalamadır."""
    return bool(token) and all(c in "?!.,;:" for c in token) and not (len(token) >= 2 and all(c == "." for c in token))


def _clean_core(core: str) -> str | None:
    """Sözcüğün kendisi; None ise tamamen çöptür."""
    letters = sum(1 for c in core if c.isalpha())
    digits = sum(1 for c in core if c.isnumeric())
    has_symbol = any(c in _SYMBOLS for c in core)
    if letters == 0:
        return core  # "24", "$500", "…"
    if not has_symbol and digits == 0:
        return core
    if not has_symbol and _is_usual_mix(core):
        return core
    # Gerçek sözcüğe yapışmış çöp: baştaki en az 3 harf korunur ("waters2aljd" → "waters").
    end = 0
    while end < len(core) and (core[end].isalpha() or core[end] in "'’-"):
        end += 1
    prefix = core[:end]
    if sum(1 for c in prefix if c.isalpha()) >= 3:
        return prefix
    return None


_USUAL = re.compile(
    r"^(?:[A-Za-z]{1,4}\d{1,4}|\d+(?:st|nd|rd|th|s|k|K|m|km|kg|cm|mm|p|x|fps|hp|HP|XP|xp|v|V|D|d)|[xX]\d{1,3}"
    r"|\d+[.,]\d+[A-Za-z]{0,3}|\d{1,2}[:.]\d{2}(?:am|pm|AM|PM)?)$"
)


def _is_usual_mix(core: str) -> bool:
    """"PS5", "R2", "MK2", "2nd", "100m", "4K", "60fps", "x2", "1980s": olağan harf-rakam karışımları."""
    # "R2-D2" gibi tireli adlarda her parça ayrı denetlenir.
    for part in (p for p in core.split("-") if p):
        if any(c.isnumeric() for c in part) and not _USUAL.search(part):
            return False
    return True


def _split(token: str) -> tuple[str, str, str]:
    start, end = 0, len(token)
    while start < end and _edge_punctuation(token[start]):
        start += 1
    while end > start and _edge_punctuation(token[end - 1]):
        end -= 1
    return token[:start], token[start:end], token[end:]
