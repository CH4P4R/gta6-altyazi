"""Apple Vision katmanı: Mac dışında saf kısımlar (satırları birleştirme, sonuçları dağıtma, motor seçimi)."""

import sys

import numpy as np

from altyazi import fullscreen, ocr, ocr_vision
from altyazi.config import OcrCfg


def test_stack_and_distribute_round_trip():
    a = np.full((40, 300, 3), 255, np.uint8)
    b = np.full((20, 500, 3), 255, np.uint8)          # kısa satır büyütülür
    canvas, spans = ocr_vision.stack([a, b])
    assert canvas.shape[1] >= 500 and len(spans) == 2
    assert spans[0][1] <= spans[1][0]
    assert spans[1][1] - spans[1][0] == ocr_vision._MIN_H
    mid0 = sum(spans[0]) / 2
    mid1 = sum(spans[1]) / 2
    found = [("Lucia.", 1.0, (220, mid0 - 5, 300, mid0 + 5)),
             ("You said", 0.5, (10, mid0 - 5, 200, mid0 + 5)),
             ("Get in", 1.0, (10, mid1 - 5, 90, mid1 + 5)),
             ("the car!", 1.0, (95, mid1 - 3, 200, mid1 + 6))]
    out = ocr_vision.distribute(found, spans)
    assert out[0][0] == "You said Lucia." and out[1][0] == "Get in the car!"
    assert out[0][1] == 0.75


def test_distribute_keeps_empty_lines():
    out = ocr_vision.distribute([("Hi", 1.0, (0, 5, 10, 15))], [(0, 20), (40, 60)])
    assert out == [("Hi", 1.0), ("", 0.0)]


def test_not_available_off_mac(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert not ocr_vision.available()


def test_make_recognizer_falls_back_to_ppocr(monkeypatch):
    made = []

    class FakeRec:
        def __init__(self, *a, **kw):
            made.append((a, kw))
            self.device = "CPU"

    monkeypatch.setattr(ocr, "Recognizer", FakeRec)
    monkeypatch.setattr(ocr_vision, "available", lambda: True)

    def broken(*_a, **_k):
        raise RuntimeError("okuyamadı")

    monkeypatch.setattr(ocr, "_checked_vision", broken)
    rec = ocr.make_recognizer(OcrCfg())
    assert isinstance(rec, FakeRec) and made                 # Vision bozuksa PP-OCR
    made.clear()
    monkeypatch.setattr(ocr, "_checked_vision", lambda m, allow_fast=False: "vision")
    assert ocr.make_recognizer(OcrCfg()) == "vision"
    assert isinstance(ocr.make_recognizer(OcrCfg(motor="ppocr")), FakeRec)


def test_vision_recognizer_scales_confidence(monkeypatch):
    monkeypatch.setattr(ocr_vision, "read", lambda img, fast=False: [
        ("Hello there", 0.5, (10, 20, 200, 50))])
    rec = ocr_vision.VisionRecognizer()
    out = rec.recognize([np.full((40, 300, 3), 255, np.uint8), np.full((40, 300, 3), 255, np.uint8)])
    assert out[0].text == "Hello there" and out[0].score == 1.0
    assert out[1].text == "" and out[1].score == 0.0


def test_fullscreen_reader_uses_vision_and_falls_back(monkeypatch):
    monkeypatch.setattr(ocr_vision, "available", lambda: True)
    monkeypatch.setattr(ocr_vision, "read", lambda img: [("BUY FLOWERS", 1.0, (1300, 270, 1700, 310)),
                                                         ("x", 0.1, (0, 0, 5, 5))])
    r = fullscreen.FullScreenReader(min_score=0.5)
    assert r.vision and r.engine is None
    assert r.read_lines(np.zeros((1080, 1920, 3), np.uint8)) == [("BUY FLOWERS", (1300, 270, 1700, 310))]

    def broken(img):
        raise RuntimeError("yok")

    monkeypatch.setattr(ocr_vision, "read", broken)

    class FakeRapid:
        def __call__(self, img, use_cls=False):
            return [([[10, 20], [100, 20], [100, 40], [10, 40]], "Meet me", 0.9)], None

    import rapidocr_onnxruntime
    monkeypatch.setattr(rapidocr_onnxruntime, "RapidOCR", FakeRapid)
    assert r.read_lines(np.zeros((100, 200, 3), np.uint8)) == [("Meet me", (10.0, 20.0, 100.0, 40.0))]
    assert not r.vision


def test_checked_vision_needs_exact_reading_and_speed(monkeypatch):
    import pytest

    class FakeVision:
        texts = {False: ocr.SAMPLE, True: ocr.SAMPLE}
        delay = {False: 0.0, True: 0.0}

        class VisionRecognizer:
            def __init__(self, fast=False):
                self.fast = fast

            def recognize(self, imgs):
                import time
                time.sleep(FakeVision.delay[self.fast])
                return [ocr.OcrLine(FakeVision.texts[self.fast], 1.0)]

    rec = ocr._checked_vision(FakeVision)
    assert not rec.fast and "doğru" in rec.device
    FakeVision.texts[False] = "said, where were you last night. Jason?"      # "I" kaçtı
    with pytest.raises(RuntimeError):
        ocr._checked_vision(FakeVision)                                       # otomatik: PP-OCR'a geç
    assert ocr._checked_vision(FakeVision, allow_fast=True).fast             # ayar vision: hızlı kip
    FakeVision.texts[False] = ocr.SAMPLE
    monkeypatch.setattr(ocr, "VISION_MAX_MS", -1)                             # doğru kip yavaş
    with pytest.raises(RuntimeError):
        ocr._checked_vision(FakeVision)
