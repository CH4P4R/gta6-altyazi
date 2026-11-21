# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.sahne.mesaj: Nino'nun MenuBlockTests.swift içindeki MessageCard sınamalarından aktarıldı."""

from altyazi.sahne import mesaj
from altyazi.sahne.metin import Reading, TextBox, TextLine


def card_line(text, top):
    return TextLine(text, TextBox(0.4, top, 0.8, top + 0.04))


def short_line(text, left, top):
    return TextLine(text, TextBox(left, top, left + 0.2, top + 0.04))


def test_phone_message_is_a_card():
    card = Reading([card_line("Donnie", 0.70), card_line("You did good looking out for Brian earlier.", 0.76),
                    card_line("We're all in this together, remember that!", 0.81)])
    assert mesaj.is_card(card)
    assert mesaj.parts(card).name == "Donnie"
    assert mesaj.parts(card).body == ("You did good looking out for Brian earlier. "
                                      "We're all in this together, remember that!")
    assert not mesaj.is_card(Reading([card_line("ENZO: Get in.", 0.7), card_line("Now, before they see us.", 0.76)]))
    assert not mesaj.is_card(Reading([card_line("Okay.", 0.7), card_line("Let's go have some fun.", 0.76)]))
    assert not mesaj.is_card(Reading([card_line("Lucia", 0.7)]))
    assert mesaj.is_card(Reading([card_line("Chuck's Gun Shop", 0.70),
                                  card_line("Hey Jason. You okay? Saw those assholes", 0.76),
                                  card_line("coming at you outside the shop and...", 0.81)]))


def test_short_message_on_the_right_is_a_card():
    """Kısa mesaj ("On my way") sağdaki kartta duruyorsa karttır."""
    assert mesaj.is_card(Reading([short_line("Cal", 0.72, 0.80), short_line("On my way", 0.72, 0.85)]))
    assert mesaj.is_card(Reading([short_line("Donnie", 0.70, 0.80), short_line("Ok", 0.70, 0.85)]))
    # Ortadaki iki satırlık altyazı kart değildir.
    assert not mesaj.is_card(Reading([short_line("Jason", 0.40, 0.80), short_line("Yeah", 0.40, 0.85)]))
    # Gövdesi yalnız rakam ya da simge olan okuma kart değildir.
    assert not mesaj.is_card(Reading([short_line("Cal", 0.72, 0.80), short_line("12:45", 0.72, 0.85)]))


def test_short_card_body_read_without_its_name_is_not_a_subtitle():
    assert mesaj.repeats("On my way", "On my way")
    assert mesaj.repeats("my way", "On my way")
    assert not mesaj.repeats("Get in the car", "On my way")


def test_part_of_the_card_is_not_a_subtitle():
    body = "Hey Jason. You okay? Saw those assholes coming at you outside the shop and"
    assert mesaj.repeats("Hey Jason. You okay? Saw those assholes", body)
    assert not mesaj.repeats("Get in the car, we're leaving now.", body)


def test_inbox_is_neither_card_nor_subtitle():
    texts = ["Joey", "Hey this is Joey from ...", "Lucia (Yolanda phon", "Outside living better t...",
             "Shirley", "Oh that's nice hon. ar..."]
    lst = Reading([TextLine(t, TextBox(0.4, 0.3 + i * 0.05, 0.7, 0.34 + i * 0.05)) for i, t in enumerate(texts)])
    assert mesaj.is_list(lst)
    assert not mesaj.is_card(lst)
    assert Reading.is_item_label("WhatUp")
    assert Reading.is_item_label("Contacts")
    assert not Reading.is_item_label("Okay.")


def test_billboard_is_not_a_message():
    sign = Reading([TextLine("TREADBounD", TextBox(0.1, 0.3, 0.4, 0.36)),
                    TextLine("Take nature before it takes you", TextBox(0.1, 0.38, 0.4, 0.44))])
    assert not mesaj.is_card(sign)


def call_card(status):
    return Reading([TextLine("Paradise Taxi", TextBox(0.1, 0.8, 0.3, 0.83)),
                    TextLine(status, TextBox(0.1, 0.84, 0.2, 0.87))])


def test_call_card():
    assert mesaj.call(call_card("Calling...")).status == "aranıyor…"
    assert mesaj.call(call_card("Calling...")).name == "Paradise Taxi"
    assert mesaj.call(call_card("00:05")).status == ""
    assert mesaj.call(call_card("We need to talk about the money.")) is None
    assert mesaj.call(Reading([TextLine("Get in the car.", TextBox(0.3, 0.8, 0.6, 0.83)),
                               TextLine("Calling...", TextBox(0.3, 0.84, 0.5, 0.87))])) is None


def test_call_card_states():
    assert mesaj.call(call_card("Incoming call")).status == "seni arıyor…"
    assert mesaj.call(call_card("Call ended.")).status == "arama bitti"
    assert mesaj.call(call_card("1:02:33")).status == ""


def test_single_word_sender_is_card():
    card = Reading([TextLine("Brian", TextBox(0.5, 0.55, 0.6, 0.59)),
                    TextLine("One more thing, left your", TextBox(0.5, 0.62, 0.9, 0.66)),
                    TextLine("pay for those packages and", TextBox(0.5, 0.67, 0.9, 0.71))])
    assert mesaj.is_card(card)


def test_name_rules():
    assert mesaj.is_name("Chuck's Gun Shop")
    assert mesaj.is_name("Cal")
    assert not mesaj.is_name("ENZO")
    assert not mesaj.is_name("TREADBounD")
    assert not mesaj.is_name("Okay.")
    assert mesaj.parts(Reading([])) == ("", "")
