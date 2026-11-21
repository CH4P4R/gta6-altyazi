# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın TextMatch.swift ve OcrNoise.swift dosyalarından taşındı.

Yalnız yeniden_okuma.py'nin kullandığı parçalar: sadeleştirme, Levenshtein benzerliği, anlam ekleyen fark
(olumsuzluk/sayı) ve okumanın sözcük puanı.
"""

from __future__ import annotations

import re
import unicodedata


def _cat(ch: str) -> str:
    return unicodedata.category(ch)


def is_letter(ch: str) -> bool:
    return _cat(ch)[0] == "L"


def is_number(ch: str) -> bool:
    return _cat(ch)[0] == "N"


# ------------------------------------------------------------------------------------------------- TextMatch
def normalize(s: str) -> str:
    """Küçük harf, yalnız harf/rakam (ve işaretleri), tek boşluk."""
    out = [ch if _cat(ch)[0] in "LMN" else " " for ch in s.lower()]
    return " ".join("".join(out).split())


def levenshtein_ratio(x, y) -> float:  # noqa: ANN001
    """1 - uzaklık / uzun olanın boyu (dizgi ya da sözcük listesi)."""
    if not x or not y:
        return 1.0 if not x and not y else 0.0
    previous = list(range(len(y) + 1))
    for i in range(1, len(x) + 1):
        row = [i] + [0] * len(y)
        xi = x[i - 1]
        for j in range(1, len(y) + 1):
            row[j] = min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (0 if xi == y[j - 1] else 1))
        previous = row
    return 1 - previous[len(y)] / max(len(x), len(y))


def is_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """Levenshtein oranı eşik ve üstündeyse benzer. Boş metin hiçbir metne benzemez."""
    if a == b:
        return bool(a)
    if not a or not b:
        return False
    return levenshtein_ratio(a, b) >= threshold


# Olumsuzluk sözcükleri; kesme işaretini kaçıran okumalar ("dont", "cant") da sayılır.
_NEGATIONS = {
    "not", "no", "never", "nothing", "nobody", "none", "nowhere", "neither", "nor", "cannot",
    "dont", "doesnt", "didnt", "cant", "wont", "isnt", "arent", "wasnt", "werent", "aint",
    "couldnt", "shouldnt", "wouldnt", "havent", "hasnt", "hadnt", "mustnt", "neednt",
}
_DIGIT_FOLDS = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})


def _ascii_digit(ch: str) -> bool:
    return "0" <= ch <= "9"


def _fold_digits(word: str) -> str:
    """OCR'ın harfle karıştırdığı rakamlar harfe çevrilir ("n0t" → "not")."""
    return word.translate(_DIGIT_FOLDS)


def _same_glyph_word(word: str, sent: str) -> bool:
    return word == sent or (bool(word) and all(map(_ascii_digit, word)) and _fold_digits(word) == sent)


def _meaning_marks(words: list[str]) -> tuple[int, list[str]]:
    negations, numbers = 0, []
    for i, original in enumerate(words):
        if original and all(map(_ascii_digit, original)):
            numbers.append(original)
            continue
        word = _fold_digits(original) if any(map(_ascii_digit, original)) else original
        if word in _NEGATIONS or (word == "t" and i > 0 and _fold_digits(words[i - 1]) + "t" in _NEGATIONS):
            negations += 1
    return negations, numbers


def adds_meaning(reread: str, sent: str) -> bool:
    """`reread`, `sent`'te olmayan bir anlam işareti taşıyor mu: daha çok olumsuzluk ya da yeni bir sayı.
    Yalnız EKLENEN işaret sayılır; işareti düşüren okuma çoğu zaman OCR kaybıdır."""
    words = normalize(reread).split()
    sent_words = normalize(sent).split()
    neg, numbers = _meaning_marks(words)
    sent_neg, sent_numbers = _meaning_marks(sent_words)
    if neg > sent_neg:
        return True
    if not numbers:
        return False

    def drop(word: str) -> None:
        if word in numbers:
            numbers.remove(word)

    # Eşit uzunlukta sözcük konumu, eksik/ek sözcükte eşleşen baş/son bölüm kullanılır.
    if len(words) == len(sent_words):
        for w, s in zip(words, sent_words):
            if w != s and _same_glyph_word(w, s):
                drop(w)
    else:
        prefix = 0
        while prefix < min(len(words), len(sent_words)) and _same_glyph_word(words[prefix], sent_words[prefix]):
            if words[prefix] != sent_words[prefix]:
                drop(words[prefix])
            prefix += 1
        i, j = len(words) - 1, len(sent_words) - 1
        while i >= prefix and j >= prefix and _same_glyph_word(words[i], sent_words[j]):
            if words[i] != sent_words[j]:
                drop(words[i])
            i -= 1
            j -= 1
    for number in numbers:
        if number not in sent_numbers:
            return True
        sent_numbers.remove(number)
    return False


# ------------------------------------------------------------------------------------------------- OcrNoise
_SYMBOLS = set("$@#%^*_=|\\~<>{}¢£¥§©®°±µ¶¤")
_QUOTES = set("\"'“”‘’«»()[]")


def _edge(ch: str) -> bool:
    """Sözcüğün başında/sonunda atılan noktalama (çöp simgeleri hariç)."""
    if ch in _QUOTES:
        return True
    return _cat(ch)[0] in "PS" and ch not in _SYMBOLS


def _split(token: str) -> tuple[str, str, str]:
    start, end = 0, len(token)
    while start < end and _edge(token[start]):
        start += 1
    while end > start and _edge(token[end - 1]):
        end -= 1
    return token[:start], token[start:end], token[end:]


_USUAL = re.compile(
    r"^(?:[A-Za-z]{1,4}\d{1,4}|\d+(?:st|nd|rd|th|s|k|K|m|km|kg|cm|mm|p|x|fps|hp|HP|XP|xp|v|V|D|d)|[xX]\d{1,3}"
    r"|\d+[.,]\d+[A-Za-z]{0,3}|\d{1,2}[:.]\d{2}(?:am|pm|AM|PM)?)$")


def _usual_mix(core: str) -> bool:
    """"PS5", "R2", "2nd", "100m", "4K": olağan harf-rakam karışımları (tireli adlarda her parça ayrı)."""
    return all(not any(map(is_number, part)) or _USUAL.search(part) for part in core.split("-") if part)


def _clean_core(core: str) -> str | None:
    """Sözcüğün kendisi; None ise tamamen çöptür."""
    letters = sum(map(is_letter, core))
    digits = sum(map(is_number, core))
    has_symbol = any(ch in _SYMBOLS for ch in core)
    if letters == 0:
        return core
    if not has_symbol and digits == 0:
        return core
    if not has_symbol and _usual_mix(core):
        return core
    # Gerçek sözcüğe yapışmış çöp: baştaki en az 3 harf korunur ("waters2aljd" → "waters").
    i = 0
    while i < len(core) and (is_letter(core[i]) or core[i] in "'’-"):
        i += 1
    prefix = core[:i]
    if sum(map(is_letter, prefix)) >= 3:
        return prefix
    return None


def _normal_case(core: str) -> bool:
    """"word", "WORD", "Word", "McDonald": büyük harf yalnız başta ya da baştan bir dizi."""
    letters = [ch for ch in core if is_letter(ch)]
    if all(ch.isupper() for ch in letters) or all(ch.islower() for ch in letters[1:]):
        return True
    return sum(ch.isupper() for ch in letters[1:]) == 1 and sum(ch.islower() for ch in letters) >= 2


_INTERJECTIONS = {"hm", "m", "sh", "br", "gr", "pst", "pft", "tsk", "hrm", "z", "pht"}
_VOWELS = set("aeiouyäöüıàáâèéêìíîòóôùúû")


def _collapsed(text: str) -> str:
    out = []
    for ch in text:
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def _vowelless(letters: str) -> bool:
    """Üç ve daha çok harfli, ünlüsüz, kısaltma olmayan sözcük ("Gtt", "rnnk"); gerçek ünlemler hariç."""
    return (len(letters) >= 3 and not all(ch.isupper() for ch in letters)
            and not any(ch in _VOWELS for ch in letters.lower())
            and _collapsed(letters.lower()) not in _INTERJECTIONS)


def ocr_score(text: str) -> int:
    """Okumanın sözcük puanı: düzgün sözcüklerin harfleri artı, çöp ve karışık harfli parçalar eksi."""
    score = 0
    for token in text.split():
        core = _split(token)[1]
        letters = "".join(ch for ch in core if is_letter(ch))
        if not letters:
            continue
        clean = (_clean_core(core) == core and _normal_case(core) and not any(ch in "[]()" for ch in core)
                 and not _vowelless(letters))
        score += len(letters) if clean else -2 * len(letters)
    return score


def ends_sentence(raw: str) -> bool:
    """Nokta, soru, ünlem ya da üç noktayla bitiyor mu (kapanış tırnağı/ayraç atlanır). SubtitleStabilizer.swift."""
    text = raw.strip()
    while text and text[-1] in "\"'”’»)]":
        text = text[:-1]
    return bool(text) and text[-1] in ".!?…"
