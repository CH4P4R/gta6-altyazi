# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.sahne.metin ve ekran: Reading yardımcıları (Nino'nun MenuBlockTests.swift içindeki ItemLabel, NavigationHint,
PaintCan sınamaları) ve ScreenItem JSON'u (SubtitleServer.sendScreen)."""

import json

import pytest

from altyazi.sahne.ekran import ScreenItem
from altyazi.sahne.metin import (ButtonPrompts, Reading, TextBox, TextLine, ends_sentence, normalize, stride_through,
                                 stride_to, swift_round)


def test_game_labels_are_not_subtitles():
    for label in ["TRAP SANDALS", "BLACK", "WORTHAM", "COMBAT RIFLE", "A LOOT", "MILK", "RV PARK",
                  "ADD TO TRUNK (1/5) □ WEAR ✕ EXIT ○", "STRAIGHT JEANS", "GONE FISHIN'", "COLLECTION",
                  "JASON'S '70 GANADO", "ASS MAN.", "\"ASS\" MAN", "NYWL, SSY."]:
        assert Reading.is_item_label(label), label
    for text in ["GET DOWN!", "WHAT?", "NO WAY!", "ENZO: Get in the car.", "I'm Jason.", "Lucia.", "Okay, how do I look?",
                 "Yeah, well, maybe change the plates", "Thanks for the tip."]:
        assert not Reading.is_item_label(text), text


def test_turn_by_turn_lines_are_not_subtitles():
    for hint in ["Turn Right 405 ft 432 ft", "Keep Left O ft 2 ft", "U-Turn Left 5 ft 24 ft", "Turn Left 366 ft—",
                 "-turn Right 67 ft 82 ft", "Turn Right i 100 ft 103 ft", "Keep Right 3.9 km"]:
        assert Reading.is_navigation_hint(hint), hint
    for subtitle in ["Turn right at the lights, okay?", "Keep left and you'll be fine, 20 ft or so",
                     "Keep it down!", "I said turn left, 50 ft back there you idiot."]:
        assert not Reading.is_navigation_hint(subtitle), subtitle
    reading = Reading([TextLine("Turn Right 405 ft"), TextLine("Where the hell are we going?")])
    assert [ln.text for ln in reading.without_navigation_hints().lines] == ["Where the hell are we going?"]


def test_product_labels_are_item_labels():
    for text in ["LOW ODOR, ZERO VOC", "MAKE IT A RIMM JOB!", "IGHT CRAY BAS!", "[POXY, ZINC, PHOSPHA?"]:
        assert Reading.is_item_label(text), text
    for text in ["GET DOWN!", "WHAT?", "We'll find him, man. Don't worry about it.", "Okay."]:
        assert not Reading.is_item_label(text), text


def test_reading_filters_blank_lines_and_helpers():
    reading = Reading([TextLine("  "), TextLine("Hello", TextBox(0.1, 0.2, 0.3, 0.25), 0.8),
                       TextLine("there", TextBox(0.2, 0.3, 0.5, 0.35), 0.6)])
    assert [ln.text for ln in reading.lines] == ["Hello", "there"]
    assert reading.text == "Hello\nthere"
    assert reading.box == TextBox(0.1, 0.2, 0.5, 0.35)
    assert reading.confidence == pytest.approx(0.7)
    assert Reading.from_text("a\n\n b \r\nc").text == "a\nb\nc"
    assert Reading([]).box is None and Reading([]).confidence is None


def test_text_box_helpers():
    box = TextBox(0.1, 0.2, 0.4, 0.3)
    assert box.width == pytest.approx(0.3) and box.height == pytest.approx(0.1)
    assert box.union(TextBox(0.0, 0.25, 0.2, 0.5)) == TextBox(0.0, 0.2, 0.4, 0.5)
    placed = TextBox(0.5, 0.5, 1.0, 1.0).placed(TextBox(0.2, 0.4, 0.6, 0.8))
    assert (placed.left, placed.top, placed.right, placed.bottom) == pytest.approx((0.4, 0.6, 0.6, 0.8))
    assert TextBox(0.4, 0.8, 0.55, 0.85).centered_on_screen() == TextBox(0.4, 0.8, 0.6, 0.85)
    assert TextBox(0.05, 0.1, 0.2, 0.15).centered_on_screen() == TextBox(0.05, 0.1, 0.2, 0.15)


def test_joining_rows_and_subtitle_block():
    reading = Reading([TextLine("hold on.", TextBox(0.45, 0.80, 0.60, 0.84), 0.9),
                       TextLine("Arthur:", TextBox(0.35, 0.80, 0.44, 0.84), 0.7)])
    joined = reading.joining_rows()
    assert [ln.text for ln in joined.lines] == ["Arthur: hold on."]
    assert joined.lines[0].confidence == 0.7
    area = TextBox(0, 0, 1, 1)
    block = Reading([
        TextLine("MAP", TextBox(0.05, 0.10, 0.10, 0.13)),
        TextLine("HELP", TextBox(0.05, 0.14, 0.10, 0.17)),
        TextLine("SETTINGS", TextBox(0.05, 0.18, 0.12, 0.21)),
        TextLine("We have to go now,", TextBox(0.38, 0.80, 0.62, 0.84)),
        TextLine("before they see us.", TextBox(0.39, 0.85, 0.61, 0.89)),
    ]).subtitle_block(area)
    assert block.text == "We have to go now,\nbefore they see us."


def test_oversized_and_clipped_lines():
    area = TextBox(0, 0.5, 1, 1)
    reading = Reading([TextLine("YARD SALE", TextBox(0.3, 0.1, 0.7, 0.3)),
                       TextLine("What happened?", TextBox(0.3, 0.5, 0.7, 0.66)),
                       TextLine("Ok.", TextBox(0.3, 0.7, 0.7, 0.75))])
    assert [ln.text for ln in reading.without_oversized_lines(area).lines] == ["What happened?", "Ok."]
    clipped = Reading([TextLine("…rental, pay for play, or…", TextBox(0.0, 0.1, 1.0, 0.2)), TextLine("Hi.", TextBox(0.4, 0.3, 0.6, 0.4))])
    assert [ln.text for ln in clipped.without_clipped_lines().lines] == ["Hi."]
    assert Reading([TextLine(str(i)) for i in range(6)]).is_oversized_block(area)


def test_button_prompts():
    assert ButtonPrompts.is_prompt("R2 Swing")
    assert ButtonPrompts.is_prompt("Press ✕ to jump")
    assert ButtonPrompts.is_prompt("Hold to see nearby places")
    assert not ButtonPrompts.is_prompt("Get in the car, now.")
    assert ButtonPrompts.normalized_icons("13) Stand up") == "L3 Stand up"
    assert ButtonPrompts.normalized_icons("Hold ✕ ✕ to sprint") == "Hold ✕ to sprint"
    assert ButtonPrompts.display("RZ") == "R2"
    assert ButtonPrompts.is_icon("Ⓑ")
    assert [ln.text for ln in Reading([TextLine("△ Pick up"), TextLine("Hello there.")]).without_button_prompts().lines] \
        == ["Hello there."]


def test_text_helpers_match_swift():
    assert normalize("  Book Ryde ($82)!  ") == "book ryde 82"
    assert ends_sentence("He said \"go.\"")
    assert not ends_sentence("Wait")
    assert swift_round(2.5) == 3 and swift_round(-2.5) == -3 and swift_round(0.49) == 0
    # Swift'in Double adımı FMA ile hesaplanır: 0.15 + 7·0.1 = 0.8500000000000001 > 0.85, dahil değil.
    assert len(list(stride_through(0.15, 0.85, 0.1))) == 7
    assert list(stride_through(0.0, 1.0, 0.5)) == [0.0, 0.5, 1.0]
    assert list(stride_to(0.0, 1.0, 0.5)) == [0.0, 0.5]


def test_screen_item_json():
    item = ScreenItem("On my way", "Geliyorum", TextBox(0.12344, -0.1, 0.98765, 1.2), 0.023456)
    assert item.to_json() == {"box": {"left": 0.1234, "top": 0.0, "right": 0.9877, "bottom": 1.0},
                              "line": 0.0235, "text": "Geliyorum"}
    item.fill = "#e9e9ec"
    item.ink = "#2c2c2e"
    item.angle = 9.46
    item.alpha = 0.955
    item.side = True
    item.backdrop = True
    item.card = True
    item.plain = True
    item.italic = True
    data = item.to_json()
    assert data["fill"] == "#e9e9ec" and data["ink"] == "#2c2c2e"
    assert data["angle"] == 9.5
    assert data["alpha"] == 0.96
    assert data["side"] and data["backdrop"] and data["card"] and data["plain"] and data["italic"]
    assert "paragraphs" not in data
    item.angle = 0.2
    assert "angle" not in item.to_json(), "küçük açı gönderilmez"
    item.translation = "Bir\nİki"
    assert item.to_json()["paragraphs"] is True
    json.dumps(item.to_json(), ensure_ascii=False)
