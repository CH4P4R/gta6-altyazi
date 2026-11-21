# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.ocr_gurultu — Nino Game Translator'ın OcrNoiseTests.swift ve SubtitleBlockTests.swift
(testGaugeNumberStuckToLineIsDropped) dosyalarından taşındı. Reading.withoutOcrNoise testi taşınmadı (o kod bu
pakette yok)."""

import pytest

from altyazi.kalite import ocr_gurultu


def test_garbled_words_are_removed():
    # Süslü yazıda bir sözcük her karede başka çöpe dönüşüyordu.
    assert ocr_gurultu.clean("Across the deep waters, Pbo ou$3e went, hoping a boat would carry him home.") \
        == "Across the deep waters, Pbo went, hoping a boat would carry him home."
    assert ocr_gurultu.clean("Across the deep waters2aljd O went, Hoping a boat.") \
        == "Across the deep waters O went, Hoping a boat."
    assert ocr_gurultu.clean("He left 3e, at dawn.") == "He left, at dawn."


@pytest.mark.parametrize("line", [
    "Turn on the PS5 now.", "Hold R2-D2 still.", "It costs $500.", "Meet me at 3:00pm.",
    "The 2nd gate is 100m away.", "Run at 60fps, 4K.", "Score x2!", "Year 1984.", "I can't — wait…",
    "\"Kratos!\" she said.", "Mk2 rifle, 9.5kg.", "L1 + R1 Spartan Rage",
])
def test_usual_tokens_are_kept(line):
    assert ocr_gurultu.clean(line) == line


@pytest.mark.parametrize("raw,clean", [
    ("?! Where do you think you're going?", "Where do you think you're going?"),
    ("Where do you think you're going ?!", "Where do you think you're going?!"),
    ("Get in the car, Enzo. ?!", "Get in the car, Enzo."),
    ("Wait, ?! Don Salieri wants you.", "Wait, Don Salieri wants you."),
    (". Get in the car.", "Get in the car."),
    ("| Get in the car, Enzo.", "Get in the car, Enzo."),
    ("Get in the car, Enzo. |", "Get in the car, Enzo."),
    ("Leave it. l", "Leave it."),
])
def test_stray_punctuation_and_box_edges_are_removed(raw, clean):
    assert ocr_gurultu.clean(raw) == clean


@pytest.mark.parametrize("raw,clean", [
    ("l don't know, Don Salieri.", "I don't know, Don Salieri."),
    ("| don't know.", "I don't know."),
    ("l'm telling you, l saw him.", "I'm telling you, I saw him."),
    ("|'ll be right back.", "I'll be right back."),
    ("You and l've been here before.", "You and I've been here before."),
    ("Who am l?", "Who am I?"),
    ("Where are you, |?", "Where are you, I?"),
    ("I don't know, l!", "I don't know, I!"),
    ("Leave it. l.", "Leave it."),
])
def test_misread_pronoun_becomes_i(raw, clean):
    assert ocr_gurultu.clean(raw) == clean


@pytest.mark.parametrize("line", [
    "What?! The door opened by itself!", "- Where? - Home.", "Wait... what?", "I... I don't know.",
    "\"Run!\" he said.", "So, you're Enzo?", "... and then he left.", "Wait ... what?", "I said no!",
    "Leave it, I said.", "Press L to aim.",
])
def test_real_punctuation_is_kept(line):
    assert ocr_gurultu.clean(line) == line


def test_clean_reading_scores_higher_than_garbled():
    assert ocr_gurultu.score("CESARE: Wait for me!") > ocr_gurultu.score("- CESAREiVJütt'h!")
    assert ocr_gurultu.score("We go to McDonald's now.") > 0
    assert ocr_gurultu.score("T hats the[lil Should be quiet now.") < ocr_gurultu.score("That should be quiet now.")
    assert ocr_gurultu.score("Get to the gate now.") > ocr_gurultu.score("Gtt to the gate now.")
    for word in ["Hmm", "Shh", "Brr", "Psst", "Mmm"]:
        assert ocr_gurultu.score(f"{word}!") > 0, word


@pytest.mark.parametrize("text", ["Gtt solkolfege.", "- CESAREiVJütt'h!", "Wrrk thng."])
def test_garbled_readings_are_recognised(text):
    assert ocr_gurultu.looks_garbled(text)


@pytest.mark.parametrize("text", ["Hold the gate.", "The FBI and the NPC agents.", "Hmm, I don't know about that, boy.",
                                  "Go to college."])
def test_ordinary_readings_are_not_garbled(text):
    assert not ocr_gurultu.looks_garbled(text)


def test_reading_line_that_was_only_noise_becomes_empty():
    # Reading.withoutOcrNoise satırları tek tek temizler; yalnız çöpten oluşan satır boş kalır.
    assert ocr_gurultu.clean("ou$3e 2aljd") == ""
    assert ocr_gurultu.clean("We go now.") == "We go now."


def test_gauge_number_stuck_to_line_is_dropped():
    assert ocr_gurultu.clean("9? We'll lose these tracks.") == "We'll lose these tracks."
    assert ocr_gurultu.clean("100. Mac and John...") == "Mac and John..."
    assert ocr_gurultu.clean("23m CESARE: It's here! Shoot him!") == "CESARE: It's here! Shoot him!"
    assert ocr_gurultu.clean("100 men came") == "100 men came"
