# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.ek — Nino Game Translator'ın FreeTranslationTests.swift'indeki TurkishSuffixTests'ten taşındı."""

import pytest

from altyazi.kalite import ek

PROPER = [
    ("Kratos", "u", "Kratos'u"), ("Kratos", "un", "Kratos'un"), ("Kratos", "a", "Kratos'a"), ("Kratos", "da", "Kratos'ta"),
    ("Kratos", "dan", "Kratos'tan"), ("Kratos", "la", "Kratos'la"), ("Kratos", "dur", "Kratos'tur"),
    ("Atreus", "un", "Atreus'un"), ("Atreus", "a", "Atreus'a"),
    ("Midgard", "a", "Midgard'a"), ("Midgard", "da", "Midgard'da"), ("Midgard", "u", "Midgard'ı"),
    ("Midgard", "un", "Midgard'ın"), ("Midgard", "daki", "Midgard'daki"),
    ("Freya", "u", "Freya'yı"), ("Freya", "a", "Freya'ya"), ("Freya", "un", "Freya'nın"), ("Freya", "la", "Freya'yla"),
    ("Freya", "da", "Freya'da"),
    ("Mimir", "a", "Mimir'e"), ("Mimir", "u", "Mimir'i"), ("Mimir", "un", "Mimir'in"), ("Mimir", "dan", "Mimir'den"),
    ("Brok", "da", "Brok'ta"), ("Brok", "u", "Brok'u"),
    ("Jötunheim", "a", "Jötunheim'e"), ("Jötunheim", "da", "Jötunheim'de"),
    ("Thor", "un", "Thor'un"), ("Baldur", "u", "Baldur'u"), ("Sindri", "un", "Sindri'nin"), ("Sindri", "u", "Sindri'yi"),
    ("Odin", "a", "Odin'e"), ("Odin", "ya", "Odin'e"), ("Freya", "nın", "Freya'nın"), ("Kratos", "nın", "Kratos'un"),
    ("Kratos", "", "Kratos"),
]

COMPOUND = [
    ("Leviathan Baltası", "u", "Leviathan Baltası'nı"), ("Leviathan Baltası", "a", "Leviathan Baltası'na"),
    ("Leviathan Baltası", "da", "Leviathan Baltası'nda"), ("Leviathan Baltası", "dan", "Leviathan Baltası'ndan"),
    ("Leviathan Baltası", "un", "Leviathan Baltası'nın"), ("Leviathan Baltası", "la", "Leviathan Baltası'yla"),
    ("Dünya Ağacı", "a", "Dünya Ağacı'na"), ("Kaos Bıçakları", "u", "Kaos Bıçakları'nı"),
]

COMMON = [
    ("can iksiri", "u", "can iksirini"), ("kontrol noktası", "a", "kontrol noktasına"),
    ("bekleme süresi", "da", "bekleme süresinde"), ("envanter", "a", "envantere"), ("envanter", "da", "envanterde"),
    ("kılıç", "u", "kılıcı"), ("kitap", "u", "kitabı"), ("bıçak", "u", "bıçağı"), ("renk", "u", "rengi"), ("top", "u", "topu"),
    ("balta", "u", "baltayı"), ("balta", "lar", "baltalar"), ("kalkan", "lar", "kalkanlar"), ("kalkan", "dan", "kalkandan"),
    ("kalkan", "la", "kalkanla"),
]


@pytest.mark.parametrize("term,suffix,expected", PROPER)
def test_proper_nouns_take_harmonized_suffix_with_apostrophe(term, suffix, expected):
    assert ek.attach(term, suffix) == expected


@pytest.mark.parametrize("term,suffix,expected", COMPOUND)
def test_compound_names_take_the_buffer_n(term, suffix, expected):
    assert ek.attach(term, suffix) == expected


@pytest.mark.parametrize("term,suffix,expected", COMMON)
def test_common_nouns_are_written_together(term, suffix, expected):
    assert ek.attach(term, suffix) == expected


def test_apostrophe_abbreviations_and_capitals():
    assert ek.attach("Kratos", "un", apostrophe="’") == "Kratos’un"
    assert ek.attach("XP", "u") == "XP'yi"
    assert ek.attach("Midgard", "A") == "Midgard'a"


def test_non_suffix_is_kept_as_is():
    # Python'a özgü: 12 harften uzun ya da harf dışı "ek" ek sayılmaz, kesmeyle olduğu gibi eklenir.
    assert ek.attach("Kratos", "abcdefghijklm") == "Kratos'abcdefghijklm"
    assert ek.attach("Kratos", "u2") == "Kratos'u2"
    assert ek.attach("", "u") == ""


def test_harmonize_keeps_ki_and_soften_rules():
    assert ek.harmonize("daki", "a") == "daki"
    assert ek.harmonize("dan", "e") == "den"
    assert ek.soften("kitap") == "kitab"
    assert ek.soften("top") == "top"
    assert ek.soften("renk") == "reng"
    assert ek.soften("kalt") == "kalt"
