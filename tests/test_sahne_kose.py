# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.sahne.kose: Nino'nun CornerBlockTests.swift dosyasından aktarılan sınamalar (değerler gerçek RDR2
karelerinden): sol üstte yalnız ipucu kutusu çevrilir; harita yer adları değil."""

from altyazi.sahne import kose
from altyazi.sahne.metin import Reading, TextBox, TextLine


def line(text, left, top, width, height):
    return TextLine(text, TextBox(left, top, left + width, top + height))


def test_tip_box_is_kept():
    reading = Reading([
        line("Bring Pearson animals to supply the", 0.02, 0.03, 0.21, 0.02),
        line("camp. He can use the meat for food", 0.02, 0.05, 0.21, 0.03),
        line("and the skins to craft Satchels with", 0.02, 0.08, 0.21, 0.02),
        line("increased capacity.", 0.02, 0.11, 0.11, 0.02),
    ])
    assert len(kose.tip_box(reading).lines) == 4


def test_map_labels_are_dropped():
    reading = Reading([
        line("Cumberiand", 0.09, 0.01, 0.07, 0.02),
        line("Fatis", 0.12, 0.03, 0.03, 0.01),
        line("CA", 0.38, 0.16, 0.02, 0.02),
        line("Dakota River", 0.06, 0.19, 0.03, 0.17),
    ])
    assert kose.tip_box(reading).lines == []


def test_mission_card_keeps_its_title_but_not_the_map():
    reading = Reading([
        line("Cumberland", 0.09, 0.01, 0.08, 0.02),
        line("REVEREND SWANSON", 0.06, 0.08, 0.20, 0.04),
        line("CA", 0.38, 0.16, 0.02, 0.02),
        line("WHO IS NOT WITHOUT SIN", 0.10, 0.16, 0.13, 0.02),
    ])
    assert [ln.text for ln in kose.tip_box(reading).lines] == ["REVEREND SWANSON", "WHO IS NOT WITHOUT SIN"]


def test_single_word_is_not_a_tip():
    assert kose.tip_box(Reading([line("grizzlies", 0.02, 0.03, 0.06, 0.02)])).lines == []


def test_marker_line_is_a_tip():
    """Görev işaretiyle ("◆ Escape the mine") başlayan kısa satır da görevdir."""
    reading = Reading([line("◆ Escape the mine", 0.02, 0.03, 0.12, 0.02)])
    assert [ln.text for ln in kose.tip_box(reading).lines] == ["◆ Escape the mine"]
    assert kose.tip_box(Reading([line("\"Escape mine\"", 0.02, 0.03, 0.12, 0.02)])).lines == []


def test_empty_reading():
    assert kose.tip_box(Reading([])).lines == []
    assert kose.tip_box(Reading([TextLine("No box here at all")])).lines == []
