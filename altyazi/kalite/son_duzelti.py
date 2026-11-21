# SPDX-License-Identifier: AGPL-3.0-only
"""Yerel çevirinin Türkçesine yapılan güvenli düzeltmeler.

Nino Game Translator'ın TurkishPostEdit.swift dosyasından taşındı (core/Sources/CouchSubsCore/TurkishPostEdit.swift;
Windows: CouchSubs.Core/TurkishPostEdit.cs, aynı kurallar).

Yalnız anlamı değiştirmeyen biçim kuralları ve dar bir hitap kuralı vardır:
- noktalamadan önceki boşluk silinir ("Dur !" → "Dur!")
- kaynağın "!", "?", "?!", "…" sonu korunur (model "Koş!"u "Koş." yapabiliyor)
- tırnaklar kaynaktaki gibi düz ya da kıvrık olur
- aynı satırda "sen" ile konuşulurken model emri "siz"li verdiyse ("Sana söyledim. Bekleyin!") bilinen emirler
  "sen"li olur ("Bekle!"). Yalnız listedeki fiiller, yalnız emir yerindeyse (ardından noktalama gelir) ve cümlede
  "siz" geçmiyorsa.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from ._harf import bosluk_satir_kirp, harf_var, sinif, tr_buyuk, tr_kucuk

# Boşluk, sekme ve bölünmez boşluk (U+00A0).
_SPACE_BEFORE_PUNCTUATION = re.compile("[ \t ]+(?=[,.!?;:…])")
_REPEATED_SPACES = re.compile("[ \t ]{2,}")


def apply(source: str, translation: str) -> str:
    """Tek cümlenin çevirisini düzeltir; `source` İngilizce cümledir."""
    if not harf_var(translation):
        return translation
    text = quotes(source, translation)
    text = _SPACE_BEFORE_PUNCTUATION.sub("", text)
    text = bosluk_satir_kirp(_REPEATED_SPACES.sub(" ", text))
    return ending(source, text)


def ending(source: str, translation: str) -> str:
    """Kaynağın ünlem/soru/üç nokta sonu çeviride başka bir sonla bittiyse kaynağınki konur."""
    _, source_end, source_closers = _split_end(source)
    if not _is_expressive(source_end):
        return translation
    body, end, closers = _split_end(translation)
    # Kaynakta son noktalama tırnağın içindeyse (He said "Run!") çeviride tırnak sonda olmayabilir; dokunulmaz.
    if (source_closers == "") != (closers == ""):
        return translation
    if end == source_end or not (end == "" or end == "." or _is_expressive(end)) or not harf_var(body):
        return translation
    return body + source_end + closers


def _is_expressive(end: str) -> bool:
    return bool(end) and ("!" in end or "?" in end or "…" in end or end == "...")


def _split_end(text: str) -> tuple[str, str, str]:
    """Metin = gövde + son noktalama (. ! ? …) + kapanış tırnak/parantezleri."""
    characters = text.rstrip()
    closer_start = len(characters)
    while closer_start > 0 and characters[closer_start - 1] in "\"'”’)]»":
        closer_start -= 1
    end_start = closer_start
    while end_start > 0 and characters[end_start - 1] in ".!?…":
        end_start -= 1
    return characters[:end_start], characters[end_start:closer_start], characters[closer_start:]


def quotes(source: str, translation: str) -> str:
    """Kaynak kıvrık tırnak kullanıyorsa çeviri de kullanır; yoksa düz tırnak.

    Not: Swift'teki `case "“", "”", "„", "‟" where !curlyDouble` satırında `where` yalnız son desene uygulanır, yani
    Swift sürümü kıvrık kaynakta da çevirideki “ ” „ ve ’ işaretlerini düz tırnağa çevirir. Burada belgedeki ve
    Windows'taki (TurkishPostEdit.cs, `when` bütün desene uygulanır) amaç izlenir: dönüşüm yalnız kaynak düzse yapılır.
    """
    curly_double = "“" in source or "”" in source
    curly_single = "’" in source or "‘" in source
    output = []
    previous: str | None = None
    for character in translation:
        opening = previous is None or previous.isspace() or previous in "([-–—"
        if character in "“”„‟" and not curly_double:
            output.append('"')
        elif character == '"' and curly_double:
            output.append("“" if opening else "”")
        elif character in "’‘" and not curly_single:
            output.append("'")
        elif character == "'" and curly_single:
            output.append("‘" if opening else "’")
        else:
            output.append(character)
        previous = character
    return "".join(output)


def apostrophe(source: str) -> str:
    """Kaynakta kıvrık kesme varsa Türkçe eklerde de o kullanılır."""
    return "’" if "’" in source else "'"


_SEN_WORDS = frozenset(["sen", "seni", "sana", "senin", "sende", "senden", "seninle", "senle"])
_SIZ_WORDS = frozenset(["siz", "sizi", "size", "sizin", "sizde", "sizden", "sizinle", "sizler"])

# "Siz"li emir → "sen"li emir; çoğul ya da kibar anlamı da olabilen sözcükler bilerek yok ("Alın" = alın).
IMPERATIVES: tuple[tuple[str, str], ...] = (
    ("dikkat edin", "dikkat et"), ("acele edin", "acele et"), ("ateş edin", "ateş et"), ("yardım edin", "yardım et"),
    ("takip edin", "takip et"), ("sessiz olun", "sessiz ol"), ("hazır olun", "hazır ol"), ("sakin olun", "sakin ol"),
    ("bekleyin", "bekle"), ("durun", "dur"), ("gelin", "gel"), ("koşun", "koş"), ("gidin", "git"), ("bakın", "bak"),
    ("dinleyin", "dinle"), ("saklanın", "saklan"), ("kaçın", "kaç"), ("savaşın", "savaş"), ("dövüşün", "dövüş"),
    ("durdurun", "durdur"), ("çekilin", "çekil"), ("eğilin", "eğil"), ("atlayın", "atla"), ("tutun", "tut"),
    ("bırakın", "bırak"), ("söyleyin", "söyle"), ("gösterin", "göster"), ("getirin", "getir"), ("kalkın", "kalk"),
    ("odaklanın", "odaklan"), ("yaklaşın", "yaklaş"), ("uzaklaşın", "uzaklaş"),
)
_IMPERATIVE_PATTERNS = [
    (re.compile("(?<![" + sinif("L") + "])" + re.escape(polite) + r"(?=\s*[!.,?…]|\s*$)", re.IGNORECASE), informal)
    for polite, informal in IMPERATIVES
]


def register(translations: Sequence[str | None]) -> list[str | None]:
    """Bir altyazının cümle çevirileri: herhangi birinde "sen" geçiyorsa (seni, sana…), "siz" geçmeyen cümlelerdeki
    bilinen "siz"li emirler "sen"li olur. Başka hiçbir şeye dokunulmaz."""
    if not any(t is not None and _contains_word(t, _SEN_WORDS) for t in translations):
        return list(translations)
    return [s if s is None or _contains_word(s, _SIZ_WORDS) else _informal(s) for s in translations]


def _informal(sentence: str) -> str:
    text = sentence
    for pattern, informal in _IMPERATIVE_PATTERNS:
        def replacement(match: re.Match, informal: str = informal) -> str:
            return tr_buyuk(informal[0]) + informal[1:] if match.group(0)[0].isupper() else informal
        text = pattern.sub(replacement, text)
    return text


def _contains_word(text: str, words: frozenset[str]) -> bool:
    word = ""
    for character in tr_kucuk(text) + " ":
        if character.isalpha():
            word += character
            continue
        if word in words:
            return True
        word = ""
    return False
