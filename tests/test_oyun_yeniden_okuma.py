# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın RereadsTests.swift denemelerinden taşındı."""

from altyazi.oyun import yeniden_okuma as r


def test_half_read_line_is_reread_of_whole_line():
    assert r.is_reread_of("Get Franklin close to the", "Get Franklin close to the house.")


def test_separate_short_sentence_is_not_reread():
    assert not r.is_reread_of("You kill me!", "I swear to God, you kill me!")


def test_dropped_word_is_reread():
    assert r.is_reread_of("Go to Bluffs", "Go to Pacific Bluffs.")


def test_completeness():
    assert r.looks_complete("Hold the gate.")
    assert not r.looks_complete("hold the gate")
    assert not r.looks_complete("Get Franklin close to the")


def test_missing_second_line_is_kept():
    assert r.keep_missing_lines("You did it.", older="You did it.\nI don't care!") == "You did it.\nI don't care!"


def test_related():
    assert r.related("Get Franklin close", "Get Franklin close to the house.")
    assert not r.related("And you watch your language!", "r guage! fair!")


# Swift denemelerinde olmayan ek denetimler
def test_added_negation_is_a_correction_not_a_reread():
    assert not r.is_reread_of("I can't do that for you right now.", "I can do that for you right now.")


def test_all_lines_covered_and_score():
    assert r.all_lines_covered("You did it.\nI don't", "You did it.\nI don't care!")
    assert not r.all_lines_covered("Something else entirely.", "You did it.")
    assert r.score("Get in the car.") > r.score("Gtt ou$3e cAr.")
