# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın SubtitleLayoutTests.swift denemelerinden taşındı."""

import json

import pytest

from altyazi.oyun.altyazi_yeri import SubtitleLayout, SubtitleLayoutStore, TextBox

L = SubtitleLayout


def box(top: float, bottom: float) -> TextBox:
    return TextBox(left=0.3, top=top, right=0.7, bottom=bottom)


def test_uses_fallback_until_learned():
    layout = L()
    for _ in range(L.MINIMUM_SAMPLES - 1):
        layout.record(box(0.80, 0.86), "rdr2")
    assert layout.hud_top("rdr2") == L.FALLBACK_HUD_TOP
    assert layout.band("rdr2") is None


def test_learns_band_above_tutorial_line():
    layout = L()
    for i in range(12):
        layout.record(box(0.79 + (i % 3) * 0.01, 0.85 + (i % 3) * 0.01), "rdr2")
    hud = layout.hud_top("rdr2")
    # Şerit 0.79–0.87; bir satır payıyla sınır öğretici yazısının (≈0.93) üstünde kalır.
    assert hud is not None and 0.89 < hud < 0.93


def test_game_with_low_subtitles_is_not_cut():
    """Altyazısı en altta duran oyunda en alt satırlar da altyazıdır: sınır aşağı iner ya da kalkar."""
    layout = L()
    for _ in range(10):
        layout.record(box(0.90, 0.95), "low")
    hud = layout.hud_top("low")
    assert hud is None or hud > 0.95


def test_outlier_does_not_move_band():
    layout = L()
    for _ in range(20):
        layout.record(box(0.80, 0.86), "g")
    layout.record(box(0.30, 0.35), "g")
    assert layout.band("g")[0] == pytest.approx(0.80, abs=0.001)


def test_menu_text_does_not_teach_the_subtitle_place():
    """Ayarlar menüsündeki açıklamalar (ekranın ortası) örnek sayılmaz."""
    layout = L()
    for i in range(40):
        layout.record(box(0.62 + (i % 5) * 0.02, 0.69 + (i % 5) * 0.02), "genel")
    assert layout.band("genel") is None
    assert layout.hud_top("genel") == L.FALLBACK_HUD_TOP


def test_learned_line_never_rises_above_fallback():
    layout = L()
    for _ in range(20):
        layout.record(box(0.78, 0.822), "g")
    hud = layout.hud_top("g")
    assert hud is not None and hud >= L.FALLBACK_HUD_TOP and hud > 0.884


def test_menu_text_does_not_push_real_samples_out():
    layout = L()
    for _ in range(20):
        layout.record(box(0.881, 0.916), "g")
    learned = layout.hud_top("g")
    for _ in range(200):
        layout.record(box(0.63, 0.69), "g")
    assert layout.hud_top("g") == learned
    assert learned > 0.94


def test_baseline_floor_is_learned_from_bottom_anchored_subtitles():
    """GTA 6: tek satır 0.881–0.916, iki satır 0.839–0.915: hepsi aynı tabanda biter. Taban çizgisi ≈0.845."""
    layout = L()
    for i in range(20):
        layout.record(box(0.839, 0.915) if i % 4 == 0 else box(0.881, 0.916), "g")
    floor = layout.baseline_floor("g")
    assert floor == pytest.approx(0.846, abs=0.005)
    assert 0.915 > floor > 0.72


def test_no_baseline_floor_until_enough_samples_or_when_subtitles_wander():
    few = L()
    for _ in range(L.BASELINE_SAMPLES - 1):
        few.record(box(0.881, 0.916), "g")
    assert few.baseline_floor("g") is None
    wandering = L()
    for i in range(30):
        wandering.record(box(0.80 + (i % 6) * 0.02, 0.84 + (i % 6) * 0.025), "g")
    assert wandering.baseline_floor("g") is None


def test_games_are_separate():
    layout = L()
    for _ in range(10):
        layout.record(box(0.90, 0.95), "a")
    assert layout.hud_top("b") == L.FALLBACK_HUD_TOP


def test_read_top_is_band_top_minus_margin():
    layout = L()
    assert layout.read_top("g") is None
    for _ in range(10):
        layout.record(box(0.88, 0.915), "g")
    assert layout.read_top("g") == pytest.approx(0.88 - L.READ_MARGIN)


def test_record_accepts_display_item_rect_tuple():
    layout = L()
    for _ in range(8):
        layout.record((0.2, 0.88, 0.8, 0.915), "g")
    assert layout.band("g") == (0.88, 0.915)


def test_store_round_trips(tmp_path):
    f = tmp_path / "alt" / "subtitle-layout.json"
    store = SubtitleLayoutStore(f)
    for _ in range(9):
        store.record(box(0.8, 0.86), "g")
    assert SubtitleLayoutStore(f).current.band("g") is not None
    # Swift Codable ile aynı biçim
    assert json.loads(f.read_text())["samples"]["g"][0] == {"top": 0.8, "bottom": 0.86}


def test_store_survives_a_broken_file(tmp_path):
    f = tmp_path / "subtitle-layout.json"
    f.write_text("{bozuk")
    store = SubtitleLayoutStore(f)
    assert store.current.band("g") is None
    store.record(box(0.8, 0.86), "g")
    assert json.loads(f.read_text())["samples"]["g"]


def test_store_without_path_keeps_memory_only():
    store = SubtitleLayoutStore(None)
    for _ in range(8):
        store.record(box(0.8, 0.86), "g")
    assert store.current.band("g") is not None
