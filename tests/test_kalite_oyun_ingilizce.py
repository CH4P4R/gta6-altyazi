# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.oyun_ingilizce — Nino Game Translator'ın GameEnglishTests.swift'inden taşındı."""

import pytest

from altyazi.kalite import oyun_ingilizce


@pytest.mark.parametrize("english,plain", [
    ("Hold your fire! They're friendlies!", "Hold your fire! They're allies!"),
    ("I got your six.", "I've got your back."),
    ("Heads up! Incoming!", "Watch out! Incoming!"),
    ("Took you long enough.", "You're late."),
    ("Careful, we've got company.", "Careful, enemies are coming."),
    ("Copy that. Moving in.", "Copy that. Going in."),
])
def test_game_idioms_become_plain_english(english, plain):
    assert oyun_ingilizce.plain(english) == plain


@pytest.mark.parametrize("text", ["The friendliest town in the north.", "Stand down!"])
def test_other_text_is_unchanged(text):
    assert oyun_ingilizce.plain(text) == text


def test_every_phrase_in_the_list_is_rewritten():
    assert oyun_ingilizce.plain("check your six, lock and load, sitting ducks") \
        == "watch behind you, get ready, easy targets"
    assert oyun_ingilizce.plain("I've got your six") == "I've got your back"
