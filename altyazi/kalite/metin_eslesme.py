# SPDX-License-Identifier: AGPL-3.0-only
"""OCR çıktılarını karşılaştırmak için sadeleştirme ve gürültüye dayanıklı benzerlik.

Nino Game Translator'ın TextMatch.swift dosyasından taşındı (core/Sources/CouchSubsCore/TextMatch.swift; Windows:
CouchSubs.Core/TextMatch.cs). `pipeline.worse_reread` ve `pipeline.normalize_text`'in daha kapsamlı karşılığıdır.
Levenshtein uzaklığı varsa rapidfuzz ile (aynı sonuç, daha hızlı), yoksa saf Python ile hesaplanır.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Hashable, Sequence

from . import ocr_gurultu

try:  # rapidfuzz projede zaten bağımlılık; yoksa aynı hesabı yapan saf Python sürümü kullanılır.
    from rapidfuzz.distance import Levenshtein as _Levenshtein
except ImportError:  # pragma: no cover
    _Levenshtein = None


def _levenshtein_python(x: Sequence[Hashable], y: Sequence[Hashable]) -> int:
    previous = list(range(len(y) + 1))
    for i in range(1, len(x) + 1):
        row = [i] + [0] * len(y)
        for j in range(1, len(y) + 1):
            row[j] = min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (0 if x[i - 1] == y[j - 1] else 1))
        previous = row
    return previous[len(y)]


def _levenshtein(x: Sequence[Hashable], y: Sequence[Hashable]) -> int:
    if _Levenshtein is not None:
        return _Levenshtein.distance(x, y)
    return _levenshtein_python(x, y)


def normalize(text: str) -> str:
    """Küçük harf, yalnız harf/rakam, tek boşluk."""
    kept = "".join(c if unicodedata.category(c)[0] in "LMN" else " " for c in text.lower())
    return " ".join(w for w in kept.split(" ") if w)


def is_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    """Levenshtein oranı `threshold` ve üstündeyse benzer sayılır. Boş metin hiçbir metne benzemez."""
    if a == b:
        return bool(a)
    if not a or not b:
        return False
    return 1 - _levenshtein(a, b) / max(len(a), len(b)) >= threshold


def normalize_rows(text: str) -> str:
    """Satırları ayrı ayrı sadeleştirip alt alta birleştirir; `is_same_subtitle` kaçırılan satırı bundan anlar."""
    rows = (normalize(row) for row in text.replace("\r\n", "\n").split("\n"))
    return "\n".join(row for row in rows if row)


def is_same_subtitle(reread: str, sent: str) -> bool:
    """Yeni okuma, gönderilmiş altyazının yeniden okuması mı (sadeleştirilmiş metinler; `sent` satırları
    `normalize_rows` ile alt alta verilebilir). Süslü yazı tipinde ya da solarken OCR bir iki sözcüğü her karede başka
    çöpe çevirir ya da iki satırlık altyazının bir satırını kaçırır; karakter benzerliği düşse de sözcükler aynı kalır.
    Rakam karışmış sözcükler ve tek harfler çöp sayılıp karşılaştırmaya girmez. Başına ya da sonuna sözcük eklenmiş
    metin (daktilo efekti) yenidir; sondan kısalmış metin ise ancak tam bir satırı eksikse aynı altyazıdır."""
    rows = sent.split("\n")
    flat = " ".join(rows)
    # Gönderilende olmayan olumsuzluk ya da sayı taşıyan okuma, karakterce ne kadar benzese de başka bir cümledir.
    if adds_meaning(reread, flat):
        return False
    x, y = _clean_words(reread), _clean_words(flat)
    # Uzayan metin (daktilo efekti ya da aynı sözlerle başlayan yeni satır) karakterce benzese de yenidir.
    if y and len(x) > len(y) and (x[:len(y)] == y or x[-len(y):] == y):
        return False
    if is_similar(reread, flat):
        return True
    # Baştan ya da sondan kesilmiş okuma: altyazının yalnız tam satırları okunduysa aynıdır, yoksa başka bir cümledir.
    if x and len(x) < len(y) and (y[:len(x)] == x or y[-len(x):] == x):
        return _is_whole_rows(len(x), rows, from_start=y[:len(x)] == x)
    shared = _shared_count(x, y)
    # Arasından çöp sözcükler düşmüş okuma: yeni okumanın sözcüklerinin hemen hepsi gönderilende var.
    if len(x) >= 4 and len(x) <= len(y) and shared >= len(x) * 0.85:
        return True
    # Kısa satırda tek sözcük anlamı değiştirir ("where is the boy" / "ship"); orada yalnız karakter benzerliği geçerli.
    longer, shorter = max(len(x), len(y)), min(len(x), len(y))
    if shorter < 6 or shorter / longer < 0.75:
        return False
    return shared / longer >= 0.75


def is_revision(new: str, old: str) -> bool:
    """Yeni satır, az önce gösterilen satırın uzamış ya da düzelmiş okuması mı: daktilo efektinde büyüyen cümle,
    belirirken yarım okunan satır, bir iki sözcüğü başka okunan aynı cümle. TV böyle bir çeviriyi öncekinin üstüne
    yığmaz, yerine koyar. Ham metinler verilir (Swift: `isRevision(_:of:)`)."""
    x, y = normalize(new), normalize(old)
    if not x or not y:
        return False
    if is_growth(new, old) or is_growth(old, new):
        return True
    if is_similar(x, y, threshold=0.8):
        return True
    a, b = _clean_words(x), _clean_words(y)
    shorter, longer = min(len(a), len(b)), max(len(a), len(b))
    if shorter < 5:
        return False
    if _similarity(a, b) >= 0.65:
        return True
    return _shared_count(a, b) / longer >= 0.7


def is_worse_reread(reread: str, sent: str) -> bool:
    """Okuma, gönderilmiş satırın aynı cümleyi bozuk okuyan ve ondan daha iyi olmayan bir yeniden okuması mı. Sözcük
    sırasıyla karşılaştırılır (en çok üç sözcükte bir fark) ya da karakterce çok benzer; uzayan ve baştan/sondan kısalan
    metin `is_same_subtitle`'a kalır. Daha çok sözcük okuyan (puanı belirgin yüksek) okuma kötü sayılmaz, yeniden
    çevrilir (Swift: `isWorseReread(_:of:)`)."""
    a, b = normalize(reread), normalize(sent)
    x, y = _clean_words(a), _clean_words(b)
    if len(x) < 5 or not y or is_growth(reread, sent) or is_growth(sent, reread) or adds_meaning(reread, sent):
        return False
    reads = _similarity(x, y) >= 0.65 or is_similar(a, b, threshold=0.75)
    return reads and ocr_gurultu.score(reread) < ocr_gurultu.score(sent) + 4


# Olumsuzluk sözcükleri; kesme işaretini kaçıran okumalar ("dont", "cant") da sayılır.
NEGATIONS = frozenset([
    "not", "no", "never", "nothing", "nobody", "none", "nowhere", "neither", "nor", "cannot",
    "dont", "doesnt", "didnt", "cant", "wont", "isnt", "arent", "wasnt", "werent", "aint",
    "couldnt", "shouldnt", "wouldnt", "havent", "hasnt", "hadnt", "mustnt", "neednt",
])


def adds_meaning(reread: str, sent: str) -> bool:
    """`reread`, `sent`'te olmayan bir anlam işareti taşıyor mu: daha çok olumsuzluk ya da gönderilende bulunmayan bir
    sayı. Bu farklar karakterce küçüktür ama cümleyi tersine çevirir. Yalnız EKLENEN işaret sayılır: işareti düşüren
    okuma ("can't" → "can") çoğu zaman OCR kaybıdır. Rakam karışmış sözcük ("n0t") harfe çevrilip sayılır; kesmenin tek
    başına kalan "t"si ("can t") bilinen bir olumsuz kısaltmayı tamamladığında olumsuzluktur. Ham ya da sadeleştirilmiş
    metin verilebilir (Swift: `addsMeaning(_:to:)`)."""
    words = [w for w in normalize(reread).split(" ") if w]
    sent_words = [w for w in normalize(sent).split(" ") if w]
    negations, numbers = _meaning_marks(words)
    sent_negations, sent_numbers = _meaning_marks(sent_words)
    if negations > sent_negations:
        return True
    if not numbers:
        return False
    # Eşit uzunlukta sözcük konumunu, eksik/ek sözcükte eşleşen baş/son bölümü kullan.
    # Baştaki "I", başka konumdaki gerçek "5 → 1" değişimini gizlememeli.
    if len(words) == len(sent_words):
        for i in range(len(words)):
            if words[i] != sent_words[i] and _same_glyph_word(words[i], sent_words[i]) and words[i] in numbers:
                numbers.remove(words[i])
    else:
        prefix = 0
        while prefix < min(len(words), len(sent_words)) and _same_glyph_word(words[prefix], sent_words[prefix]):
            if words[prefix] != sent_words[prefix] and words[prefix] in numbers:
                numbers.remove(words[prefix])
            prefix += 1
        i, j = len(words) - 1, len(sent_words) - 1
        while i >= prefix and j >= prefix and _same_glyph_word(words[i], sent_words[j]):
            if words[i] != sent_words[j] and words[i] in numbers:
                numbers.remove(words[i])
            i -= 1
            j -= 1
    for number in numbers:
        if number not in sent_numbers:
            return True
        sent_numbers.remove(number)
    return False


def _is_ascii_digits(word: str) -> bool:
    return all(c in "0123456789" for c in word)


def _same_glyph_word(word: str, sent: str) -> bool:
    return word == sent or (_is_ascii_digits(word) and _fold_digits(word) == sent)


def _meaning_marks(words: Sequence[str]) -> tuple[int, list[str]]:
    negations = 0
    numbers: list[str] = []
    for i, original in enumerate(words):
        if _is_ascii_digits(original):
            numbers.append(original)
            continue
        word = _fold_digits(original) if any(c in "0123456789" for c in original) else original
        if word in NEGATIONS or (word == "t" and i > 0 and _fold_digits(words[i - 1]) + "t" in NEGATIONS):
            negations += 1
    return negations, numbers


_FOLDS = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b"})


def _fold_digits(word: str) -> str:
    """OCR'ın harfle karıştırdığı rakamlar harfe çevrilir ("n0t" → "not")."""
    return word.translate(_FOLDS)


def _similarity(x: Sequence[Hashable], y: Sequence[Hashable]) -> float:
    """Levenshtein oranı (sözcük dizileri için)."""
    if not x or not y:
        return 1.0 if not x and not y else 0.0
    return 1 - _levenshtein(x, y) / max(len(x), len(y))


def _shared_count(x: Sequence[str], y: Sequence[str]) -> int:
    remaining = list(y)
    shared = 0
    for word in x:
        if word in remaining:
            remaining.remove(word)
            shared += 1
    return shared


def is_growth(new: str, old: str) -> bool:
    """`new`, `old`'un sonuna sözcük eklenmiş hali mi (daktilo efekti; satırın başı okunmamışsa başına eklenmiş hali)."""
    x = [w for w in normalize(new).split(" ") if w]
    y = [w for w in normalize(old).split(" ") if w]
    if not y or len(x) <= len(y):
        return False
    return x[:len(y)] == y or (len(y) >= 2 and x[-len(y):] == y)


def _is_whole_rows(count: int, rows: Sequence[str], from_start: bool) -> bool:
    """Baştan (ya da sondan) `count` sözcük tam satırlara denk geliyor mu."""
    total = 0
    for row in (rows if from_start else list(reversed(rows))):
        total += len(_clean_words(row))
        if total == count:
            return True
        if total > count:
            return False
    return False


def _clean_words(normalized: str) -> list[str]:
    # Tek harfler ("a", "I" ya da OCR'ın uydurduğu "O") karşılaştırmaya bir şey katmaz.
    return [w for w in normalized.split(" ") if len(w) > 1 and not any(c.isnumeric() for c in w)]
