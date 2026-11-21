# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın LineMetricsTests.swift denemelerinden taşındı."""

from altyazi.oyun.olcu import LABELS_TR, LineMetrics, Origin


def test_measures_each_stage_from_the_same_clock():
    m = LineMetrics.measure(captured_at=1000, ocr_ms=42, translation=(1100, 1410), sent_at=1520,
                            confidence=0.934, origin=Origin.ENGINE)
    assert m == LineMetrics(ocr_ms=42, translation_ms=310, total_ms=520, confidence=93, origin=Origin.ENGINE)


def test_pack_line_has_no_translation_time():
    m = LineMetrics.measure(captured_at=1000, ocr_ms=30, translation=None, sent_at=1045, confidence=None,
                            origin=Origin.PACK)
    assert m.translation_ms is None
    assert m.confidence is None
    assert m.total_ms == 45


def test_negative_durations_and_out_of_range_confidence_are_clamped():
    m = LineMetrics.measure(captured_at=2000, ocr_ms=-5, translation=(10, 5), sent_at=1500, confidence=1.7,
                            origin=Origin.ENGINE)
    assert (m.ocr_ms, m.translation_ms, m.total_ms, m.confidence) == (0, 0, 0, 100)


def test_summary_lists_only_known_values_in_order():
    engine = LineMetrics(ocr_ms=40, translation_ms=300, total_ms=520, confidence=91, origin=Origin.ENGINE)
    assert engine.summary() == "OCR 40 ms · Translation 300 ms · Delay 520 ms · Confidence 91%"
    pack = LineMetrics(ocr_ms=None, translation_ms=None, total_ms=60, confidence=None, origin=Origin.PACK)
    assert pack.summary() == "Ready pack · Delay 60 ms"


def test_turkish_labels():
    engine = LineMetrics(ocr_ms=40, translation_ms=300, total_ms=520, confidence=91, origin=Origin.ENGINE)
    assert engine.summary(LABELS_TR) == "OCR 40 ms · Çeviri 300 ms · Gecikme 520 ms · Güven %91"


def test_float_milliseconds_from_perf_counter_are_rounded():
    m = LineMetrics.measure(captured_at=10.2, ocr_ms=41.6, translation=(11.0, 320.4), sent_at=530.9,
                            confidence=0.5, origin="engine")
    assert (m.ocr_ms, m.translation_ms, m.total_ms, m.confidence, m.origin) == (42, 309, 521, 50, Origin.ENGINE)
