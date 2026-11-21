# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.sahne.menu: Nino'nun MenuBlockTests.swift dosyasından aktarılan sınamalar (MenuBlock, MenuScreen; aynı
dosyadaki Reading etiket/yol tarifi sınamaları test_sahne_metin.py'de, MessageCard sınamaları test_sahne_mesaj.py'de)."""

from altyazi.sahne import menu
from altyazi.sahne.metin import Reading, TextBox, TextLine


def line(text, left, top, width, height=0.03):
    return TextLine(text, TextBox(left, top, left + width, top + height))


def test_pause_menus_are_found_and_subtitles_are_not():
    reading = Reading([
        line("Map", 0.10, 0.25, 0.05),
        line("Game", 0.10, 0.33, 0.06),
        line("Store", 0.10, 0.41, 0.06),
        line("Help", 0.10, 0.49, 0.05),
        line("Retry Checkpoint", 0.76, 0.30, 0.14),
        line("Restart Mission", 0.78, 0.36, 0.12),
        line("GONE FISHING", 0.79, 0.22, 0.11),
        # Altyazı: uzun ve ortalı.
        line("Now, who the hell built this outhouse back here? She's a beaut.", 0.25, 0.82, 0.5),
        line("I need me one of those.", 0.38, 0.87, 0.24),
    ])
    groups = menu.groups(reading)
    assert len(groups) == 2
    assert [ln.text for ln in groups[0].lines] == ["Map", "Game", "Store", "Help"]
    assert not groups[0].right_aligned
    assert [ln.text for ln in groups[1].lines] == ["GONE FISHING", "Retry Checkpoint", "Restart Mission"]
    assert groups[1].right_aligned


def test_two_lines_are_not_a_menu():
    reading = Reading([line("Map", 0.1, 0.25, 0.05), line("Game", 0.1, 0.33, 0.06)])
    assert menu.groups(reading) == []


def test_far_apart_lines_are_not_a_menu():
    reading = Reading([line("Map", 0.1, 0.05, 0.05), line("Game", 0.1, 0.30, 0.06), line("Store", 0.1, 0.55, 0.06)])
    assert menu.groups(reading) == []


def test_translation_goes_beside_not_on_top():
    left = line("Map", 0.10, 0.25, 0.05)
    beside = menu.place_beside(left, "Harita", right_aligned=False)
    assert beside.left > left.box.right
    right = line("Retry Checkpoint", 0.76, 0.30, 0.14)
    before = menu.place_beside(right, "Kontrol noktasından tekrar dene", right_aligned=True)
    assert before.right < right.box.left
    assert before.left >= 0


def test_icons_are_stripped_and_common_words_known():
    assert menu.clean("⊙ Store") == "Store"
    assert menu.clean("0] Photo Studio") == "Photo Studio"
    assert menu.clean("1 Help") == "Help"
    assert menu.clean("i Settings") == "Settings"
    assert menu.clean("ii Map") == "Map"
    assert menu.clean("Go Home") == "Go Home"
    assert menu.clean("i Ayarlar") == "Ayarlar"
    assert menu.clean("Chapter 1") == "Chapter 1"
    assert menu.known_turkish("Settings") == "Ayarlar"
    assert menu.known_turkish("CHAPTER 1") == "Bölüm 1"
    assert menu.known_turkish("Get in the car") is None


def test_column_is_aligned_and_clear_of_the_words():
    group = menu.Group([line("Map", 0.10, 0.25, 0.05), line("Photo Studio", 0.10, 0.33, 0.12),
                        line("Settings", 0.10, 0.41, 0.08)], right_aligned=False)
    boxes = menu.place_column(group, ["Harita", "Fotoğraf Stüdyosu", "Ayarlar"])
    assert len({b.left for b in boxes}) == 1
    assert boxes[0].left > 0.22
    right = menu.Group([line("CHAPTER 1", 0.80, 0.2, 0.1), line("Retry Checkpoint", 0.76, 0.3, 0.14),
                        line("Restart Mission", 0.78, 0.36, 0.12)], right_aligned=True)
    rb = menu.place_column(right, ["Bölüm 1", "Kontrol Noktasından Tekrar Dene", "Görevi Yeniden Başlat"])
    assert len({b.right for b in rb}) == 1
    assert rb[0].right < 0.76


def test_map_and_pause_screens_are_recognised():
    assert menu.is_menu_screen(Reading([TextLine("JASON & LUCIA MAP BRIEF PROGRESS")]))
    assert menu.is_menu_screen(Reading([TextLine("ii Map"), TextLine("Game"), TextLine("Store")]))
    assert not menu.is_menu_screen(Reading([TextLine("Let's check the map."), TextLine("Game on.")]))
    assert menu.is_menu_screen(Reading([TextLine("SPEED"), TextLine("ACCELERATION"), TextLine("ASPHALT HANDLING")]))
    assert not menu.is_menu_screen(Reading([TextLine("Slow down, you're going too fast.")]))
    assert menu.is_menu_screen(Reading([TextLine("SHOW TEXT △"), TextLine("FLIP □"), TextLine("PUT BACK ○")]))


def test_menu_line_rules():
    assert menu.is_menu_line(line("Retry Checkpoint", 0.1, 0.1, 0.1))
    assert not menu.is_menu_line(line("Retry.", 0.1, 0.1, 0.1))
    assert not menu.is_menu_line(line("Where?", 0.1, 0.1, 0.1))
    assert not menu.is_menu_line(line("Map", 0.1, 0.1, 0.1, height=0.08))
    assert not menu.is_menu_line(TextLine("Map"))
