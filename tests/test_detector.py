import pytest

from altyazi.config import BolgeCfg
from altyazi.detector import ZoneDetector, zone_rect
from altyazi.ocr import Recognizer
from tests.synth import background, draw_help_box, draw_subtitle, jpeg

W, H = 1920, 1080
SUB = BolgeCfg()
HELP = BolgeCfg(ad="yardim", alan=[0.0, 0.0, 0.36, 0.32], tur="arayuz", hizalama="sol", capa="ust")


@pytest.fixture(scope="module")
def rec():
    r = Recognizer(use_gpu=False)
    r.warmup()
    return r


def crop(frame, z):
    x0, y0, x1, y1 = zone_rect(z, W, H)
    return frame[y0:y1, x0:x1]


def read(rec, frame, z):
    ev = ZoneDetector(z).process(crop(frame, z), 0.0)
    assert ev is not None and ev.kind == "text"
    return [r.text for r in rec.recognize([ln.image for ln in ev.lines])]


@pytest.mark.parametrize("q", [100, 50])
def test_two_line_subtitle_over_bright_noisy_background(rec, q):
    lines = ["You think you can just walk in here", "and take what's mine, man?"]
    f = jpeg(draw_subtitle(background(W, H, 0), lines), q)
    assert read(rec, f, SUB) == lines


def test_highlighted_word_is_included(rec):
    f = draw_subtitle(background(W, H, 1), ["Go to the car."], highlight="car")
    assert read(rec, f, SUB) == ["Go to the car."]


def test_help_box(rec):
    f = draw_help_box(background(W, H, 2), ["Press X to enter the vehicle.", "Hold L2 to aim."])
    assert read(rec, f, HELP) == ["Press X to enter the vehicle.", "Hold L2 to aim."]


def test_no_text_no_event():
    d = ZoneDetector(SUB)
    f = background(W, H, 3)
    assert all(d.process(crop(f, SUB), t / 60) is None for t in range(5))


def test_state_machine_same_new_and_clear():
    d = ZoneDetector(SUB)
    a = draw_subtitle(background(W, H, 4), ["First line of dialogue."])
    a2 = jpeg(draw_subtitle(background(W, H, 4), ["First line of dialogue."]), 60)  # aynı yazı, bozulmuş kare
    b = draw_subtitle(background(W, H, 4), ["A completely different sentence now."])
    empty = background(W, H, 4)
    assert d.process(crop(a, SUB), 0.00).kind == "text"
    assert d.process(crop(a2, SUB), 0.02) is None
    assert d.process(crop(b, SUB), 0.04).kind == "text"
    assert d.process(crop(empty, SUB), 0.06) is None           # silme gecikmesi henüz dolmadı
    assert d.process(crop(empty, SUB), 0.30).kind == "clear"


def test_reject_retries_next_frame():
    d = ZoneDetector(SUB)
    a = draw_subtitle(background(W, H, 5), ["Retry me please."])
    assert d.process(crop(a, SUB), 0.0).kind == "text"
    d.reject()
    assert d.process(crop(a, SUB), 0.02).kind == "text"
