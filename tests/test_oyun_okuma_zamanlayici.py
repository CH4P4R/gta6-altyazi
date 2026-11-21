# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın ReadSchedulerTests.swift denemelerinden taşındı."""

import numpy as np

from altyazi.oyun.altyazi_yeri import TextBox
from altyazi.oyun.okuma_zamanlayici import (DEFAULT_CHANGE_THRESHOLD, SIGNATURE_HEIGHT, SIGNATURE_WIDTH, Read,
                                            ReadScheduler, Reuse, changed, signature_of)

STILL = [40] * 16


def test_first_frame_is_always_read():
    assert ReadScheduler().plan(STILL) == Read(deep=True)


def test_unchanged_region_reuses_the_last_reading():
    s = ReadScheduler()
    s.plan(STILL)
    s.record("Hello there")
    assert s.plan(STILL) == Reuse("Hello there")


def test_video_noise_counts_as_unchanged():
    s = ReadScheduler()
    s.plan(STILL)
    s.record("")
    noisy = list(STILL)
    noisy[3] += 8
    assert s.plan(noisy) == Reuse("")


def test_one_changed_sample_triggers_a_reading():
    """Daktilo efektinde yalnız bir harf eklenir; ortalama değil en büyük fark bakılır."""
    s = ReadScheduler()
    s.plan(STILL)
    s.record("Hel")
    typed = list(STILL)
    typed[3] += 40
    assert s.plan(typed) == Read(deep=False)


def test_reused_reading_is_refreshed_after_a_limit():
    s = ReadScheduler(max_reuse=2, deep_every=2)
    s.plan(STILL)
    s.record("a line")
    assert s.plan(STILL) == Reuse("a line")
    assert s.plan(STILL) == Reuse("a line")
    assert s.plan(STILL) == Read(deep=False)


def test_slower_search_runs_only_on_every_third_empty_frame():
    s = ReadScheduler(deep_every=3)
    plans = []
    for value in range(6):
        plans.append(s.plan([value * 50] * 16))
        s.record("")
    assert plans == [Read(True), Read(False), Read(False), Read(True), Read(False), Read(False)]


def test_text_found_resets_the_slower_search_count():
    s = ReadScheduler(deep_every=2)
    s.plan([1, 1])
    s.record("line")
    assert s.plan([90, 90]) == Read(deep=False)
    s.record("")
    assert s.plan([180, 180]) == Read(deep=True)


def test_reset_forgets_the_previous_frame():
    s = ReadScheduler()
    s.plan(STILL)
    s.record("old")
    s.reset()
    assert s.plan(STILL) == Read(deep=True)


def test_new_size_is_always_a_change():
    s = ReadScheduler()
    s.plan(STILL)
    s.record("x")
    assert s.plan([40, 40]) == Read(deep=False)


def test_change_within_a_box_ignores_the_rest_of_the_region():
    """Kutu verilince yalnız kutunun örttüğü örneklere bakılır."""
    w = SIGNATURE_WIDTH
    still = [120] * (w * SIGNATURE_HEIGHT)
    box = TextBox(left=0.3, top=0.6, right=0.7, bottom=0.85)
    elsewhere = list(still)
    elsewhere[0] = 250
    elsewhere[8 * w + 10] = 250
    assert changed(still, elsewhere, DEFAULT_CHANGE_THRESHOLD)
    assert not changed(still, elsewhere, DEFAULT_CHANGE_THRESHOLD, within=box)
    inside = list(still)
    inside[8 * w + 30] = 180
    assert changed(still, inside, DEFAULT_CHANGE_THRESHOLD, within=box)
    inside[8 * w + 30] = 130
    assert not changed(still, inside, DEFAULT_CHANGE_THRESHOLD, within=(0.3, 0.6, 0.7, 0.85))


def test_always_read_disables_reuse():
    s = ReadScheduler.always()
    s.plan(STILL)
    s.record("")
    assert s.plan(STILL) == Read(deep=True)


def test_signature_of_image_is_64_by_12_and_bytes_work():
    img = np.zeros((90, 640, 3), np.uint8)
    sig = signature_of(img)
    assert len(sig) == SIGNATURE_WIDTH * SIGNATURE_HEIGHT
    img[40:50, 300:340] = 255                 # bir harf belirdi
    s = ReadScheduler()
    s.plan(sig)
    s.record("")
    assert s.plan(signature_of(img)) == Read(deep=False)
