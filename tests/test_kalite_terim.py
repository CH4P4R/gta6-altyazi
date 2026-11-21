# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.terim — Nino Game Translator'ın FreeTranslationTests.swift'indeki TermProtectionTests'ten taşındı."""

import pytest

from altyazi.kalite.sozluk import Glossary
from altyazi.kalite.terim import PLACEHOLDERS, Slot, TermProtector

GOW = Glossary.parse("""
    { "terms": { "Leviathan Axe": "Leviathan Baltası", "Midgard": "Midgard", "health potion": "can iksiri" },
      "keep": ["Kratos", "Atreus"] }
""")


def test_replaces_terms_with_placeholder_names():
    protector = TermProtector(GOW, [""])
    text, slots = protector.protect("Kratos, take the Leviathan Axe to Midgard. Kratos!")
    assert text == "Zarmon, take the Velkor to Dorvan. Zarmon!"
    assert [s.english for s in slots] == ["Kratos", "Leviathan Axe", "Midgard"]


@pytest.mark.parametrize("output,expected", [
    ("Zarmon, Velkor'u Dorvan'a götür. Zarmon!", "Kratos, Leviathan Baltası'nı Midgard'a götür. Kratos!"),
    ("ZARMON, VELKOR'U DORVAN'A GÖTÜR. ZARMON!", "Kratos, Leviathan Baltası'nı Midgard'a GÖTÜR. Kratos!"),
    ("Zarmon, Velkor ’u Dorvana götür. Zarmon!", "Kratos, Leviathan Baltası'nı Midgard'a götür. Kratos!"),
])
def test_restores_terms_with_suffixes_despite_case_and_spacing(output, expected):
    protector = TermProtector(GOW, [""])
    slots = protector.protect("Kratos, take the Leviathan Axe to Midgard. Kratos!")[1]
    assert TermProtector.restore(output, expected=slots, all_slots=protector.all_slots) == expected


def test_missing_placeholder_means_unreliable():
    protector = TermProtector(GOW, [""])
    slots = protector.protect("Take the Leviathan Axe to Midgard.")[1]
    assert TermProtector.restore("Baltayı Dorvan'a götür.", expected=slots, all_slots=protector.all_slots) is None


def test_placeholder_from_another_part_means_unreliable():
    protector = TermProtector(GOW, [""])
    protector.protect("Kratos!")
    slots = protector.protect("Go to Midgard.")[1]
    assert TermProtector.restore("Zarmon Velkor'a git.", expected=slots, all_slots=protector.all_slots) is None
    assert TermProtector.restore("Velkor'a git.", expected=slots, all_slots=protector.all_slots) == "Midgard'a git."


def test_common_noun_at_sentence_start_is_capitalized():
    protector = TermProtector(GOW, [""])
    slots = protector.protect("Drink the health potion. Health potion first!")[1]
    assert TermProtector.restore("Zarmon'u iç. Önce Zarmon!", expected=slots) == "Can iksirini iç. Önce can iksiri!"


def test_quoted_placeholder_is_not_a_suffix():
    protector = TermProtector(GOW, [""])
    slots = protector.protect("He said 'Midgard' again.")[1]
    assert TermProtector.restore("Yine 'Zarmon' dedi.", expected=slots) == "Yine 'Midgard' dedi."


def test_placeholder_already_in_the_source_is_skipped():
    protector = TermProtector(GOW, ["Zarmon met Kratos."])
    assert protector.protect("Zarmon met Kratos.")[0] == "Zarmon met Velkor."


def test_text_without_terms_is_unchanged():
    protector = TermProtector(GOW, [""])
    text, slots = protector.protect("We go now.")
    assert text == "We go now."
    assert slots == []
    assert TermProtector.restore("Şimdi gidiyoruz.", expected=slots, all_slots=protector.all_slots) == "Şimdi gidiyoruz."


def test_same_term_reuses_its_placeholder_and_runs_out_gracefully():
    many = Glossary.from_dict({"keep": [f"Name{c}" for c in "ABCDEFGHIJ"]})
    protector = TermProtector(many, [""])
    text, slots = protector.protect(" ".join(f"Name{c}" for c in "ABCDEFGHIJ") + " NameA")
    # Sekiz ad var; dokuzuncu ve onuncu terim korunmaz, aynı terim aynı adı alır.
    assert len(slots) == len(PLACEHOLDERS)
    assert text.split() == list(PLACEHOLDERS) + ["NameI", "NameJ", "Zarmon"]


def test_curly_apostrophe_is_used_for_suffixes():
    protector = TermProtector(GOW, [""])
    slots = protector.protect("Go to Midgard.")[1]
    assert TermProtector.restore("Zarmon'a git.", expected=slots, apostrophe="’") == "Midgard’a git."
    assert Slot("Zarmon", "Midgard", "Midgard") == slots[0]
