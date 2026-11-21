# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.sahne.harita: Nino'nun MapCardTests.swift dosyasından aktarılan sınamalar."""

import os

import numpy as np
import pytest

from altyazi.sahne import harita, menu
from altyazi.sahne.metin import Reading, TextBox, TextLine


def line(text, left, top, right, bottom):
    return TextLine(text, TextBox(left, top, right, bottom))


def map_reading():
    """Gerçek kareden (GTA 6 haritası, "Buy Flowers" seçili)."""
    return Reading([
        line("STORY", 0.018, 0.04, 0.071, 0.075),
        line("Pick Up Lucia", 0.081, 0.12, 0.166, 0.145),
        line("OPTIONAL", 0.053, 0.18, 0.108, 0.205),
        line("Buy Flowers", 0.081, 0.238, 0.157, 0.263),
        line("Buy Lucia a Necklace", 0.081, 0.297, 0.214, 0.322),
        line("$1,200", 0.913, 0.12, 0.961, 0.147),
        line("0.63 mi", 0.484, 0.503, 0.517, 0.523),
        line("BUY FLOWERS", 0.577, 0.425, 0.662, 0.458),
        line("Lucia will appreciate this", 0.568, 0.478, 0.725, 0.506),
        line("Have some flowers delivered to the", 0.548, 0.521, 0.775, 0.549),
        line("house for Lucia.", 0.548, 0.556, 0.649, 0.584),
        line("RECENTER", 0.906, 0.757, 0.960, 0.777),
        line("2D VIEW", 0.918, 0.805, 0.960, 0.825),
        line("ADD MARKER", 0.893, 0.853, 0.960, 0.873),
        line("SET DESTINATION", 0.872, 0.901, 0.960, 0.921),
    ])


def test_map_screen_is_recognized_by_its_button_list():
    assert harita.is_map_screen(map_reading())
    assert not harita.is_map_screen(Reading([line("You trying to kill me?", 0.4, 0.88, 0.6, 0.915)]))


def test_card_title_and_sentences_are_found():
    card = harita.find(map_reading())
    assert card is not None
    assert card.title == "BUY FLOWERS"
    assert card.sentences == ["Lucia will appreciate this", "Have some flowers delivered to the house for Lucia."]
    assert abs(card.box.top - 0.425) <= 0.001
    assert abs(card.box.bottom - 0.584) <= 0.001


def test_no_card_without_sentences():
    """Kart yokken (yalnız menü ve harita) bir şey bulunmaz."""
    drop = {"BUY FLOWERS", "Lucia will appreciate this", "Have some flowers delivered to the", "house for Lucia."}
    empty = Reading([ln for ln in map_reading().lines if ln.text not in drop])
    assert harita.find(empty) is None


def test_distance_and_icon_crumbs_are_dropped():
    reading = Reading([
        line("CAL'S ERRAND", 0.56, 0.40, 0.66, 0.43),
        line("(43) Cal challenged you to grab", 0.52, 0.45, 0.76, 0.48),
        line("the package before he does. 1.53 km", 0.548, 0.49, 0.80, 0.52),
    ])
    card = harita.find(reading)
    assert card is not None
    assert card.title == "CAL'S ERRAND"
    assert card.sentences == ["Cal challenged you to grab the package before he does."]
    assert reading.lines[1].box.left == 0.52, "okumanın kutusu değişmez"


def test_probe_real_frames():
    """Elle (Swift: NINO_FRAME klasöründeki karelerde harita kartı). Apple Vision yazı tanıması gerekiyor."""
    if not os.environ.get("NINO_FRAME"):
        pytest.skip("NINO_FRAME yok")
    pytest.skip("Apple Vision yazı tanıması (VisionReader) gerekiyor; Python tarafında karşılığı yok")


def test_frame_finds_the_dark_card_on_a_light_map():
    """Kartın koyu çerçevesi haritanın aydınlık zemininden ayrılarak bulunur (Swift'te sınaması yok)."""
    img = np.full((1080, 1920, 3), (180, 200, 190), np.uint8)
    # Koyu kart: x 0.53–0.80, y 0.40–0.62.
    img[int(0.40 * 1080):int(0.62 * 1080), int(0.53 * 1920):int(0.80 * 1920)] = (30, 25, 25)
    text = TextBox(0.548, 0.425, 0.775, 0.584)
    found = harita.frame(text, img)
    assert found is not None
    assert abs(found.left - 0.53) < 0.01
    assert abs(found.right - 0.80) < 0.01
    assert abs(found.top - 0.40) < 0.01
    assert abs(found.bottom - 0.62) < 0.01


def test_frame_on_a_dark_map_uses_padded_text_box():
    img = np.full((1080, 1920, 3), 20, np.uint8)
    text = TextBox(0.548, 0.425, 0.775, 0.584)
    found = harita.frame(text, img)
    assert found is not None
    assert abs(found.left - (0.548 - 0.015)) < 1e-9
    assert abs(found.right - (0.775 + 0.02)) < 1e-9
    assert abs(found.bottom - (0.584 + 0.02)) < 1e-9
    assert abs(found.top - (0.425 - 0.02)) < 1e-9


def test_frame_without_dark_card_is_none():
    img = np.full((1080, 1920, 3), 230, np.uint8)
    assert harita.frame(TextBox(0.548, 0.425, 0.775, 0.584), img) is None


def test_map_keys_go_through_menu_clean():
    assert menu.clean("◎ RECENTER") == "RECENTER"
    assert harita.is_map_screen(Reading([TextLine("◎ RECENTER"), TextLine("[] CLOSE MENU")]))
