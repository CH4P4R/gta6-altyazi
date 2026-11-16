import threading
import time

from altyazi.config import BolgeCfg, CeviriCfg, Config
from altyazi.pipeline import Pipeline, clean_ocr, looks_like_text
from altyazi.translate import FAST, REFINED, Cache, Result, TranslationEngine, normalize
from tests.synth import background, draw_subtitle


class FakeRec:
    def __init__(self, text):
        self.text = text

    def recognize(self, imgs):
        from altyazi.ocr import OcrLine
        return [OcrLine(self.text, 0.95)] + [OcrLine("", 0.0)] * (len(imgs) - 1)


class Sink:
    def __init__(self):
        self.items, self.ev = [], threading.Event()

    def show(self, it):
        self.items.append(it)
        self.ev.set()

    def clear(self, zone):
        pass


class Echo:
    def __init__(self, name, delay=0.0):
        self.name, self.delay = name, delay

    def translate(self, text, kind="", context=None):
        time.sleep(self.delay)
        return f"{self.name}:{text}"


def make_engine(tmp_path, fast=None, refine=None):
    e = TranslationEngine(CeviriCfg(hizli="yok", kalite="yok", onbellek=str(tmp_path / "c.sqlite")))
    e.fast, e.refine = fast, refine
    return e


def test_fast_then_refined_and_cache(tmp_path):
    cfg = Config(bolgeler=[BolgeCfg()])
    sink = Sink()
    eng = make_engine(tmp_path, Echo("hizli"), Echo("claude", 0.05))
    p = Pipeline(cfg, sink, FakeRec("Get in the car."), eng)
    p.process(draw_subtitle(background(1920, 1080, 0), ["Get in the car."]), time.perf_counter())
    deadline = time.time() + 2
    while len(sink.items) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert [i.text for i in sink.items] == ["hizli:Get in the car.", "claude:Get in the car."]
    assert sink.items[0].quality == FAST and sink.items[1].quality == REFINED
    assert eng.cache.get("Get in the car") == ("claude:Get in the car.", REFINED, "claude")
    # bir dahaki sefere OCR bir harf yanlış okusa da önbellekten kaliteli hali gelir
    got = []
    eng.submit("Get in the cor.", "altyazi", got.append)
    assert got and got[0].text == "claude:Get in the car."


def test_stale_translation_is_dropped(tmp_path):
    cfg = Config(bolgeler=[BolgeCfg()])
    sink = Sink()
    p = Pipeline(cfg, sink, FakeRec("x"), make_engine(tmp_path))
    with p._lock:
        p._current["altyazi"] = (2, "new", 0)
    from altyazi.pipeline import DisplayItem
    base = DisplayItem("altyazi", (0, 0, 1, 1), (0, 0, 1, 1), 0.03, "old", "", "orta", "alt", 200, 1.0, seq=1)
    p._on_translation(base, time.perf_counter(), Result("eski", "yerel", 1, FAST))
    assert sink.items == []


def test_ocr_cleanup():
    assert clean_ocr("Lucia, we can' t stay  here !") == "Lucia, we can't stay here!"
    assert clean_ocr("We gotta' get out") == "We gotta' get out"
    assert looks_like_text("Go to the car.")
    assert not looks_like_text("|:;.-")
    assert normalize("Get in the CAR!!") == "get in the car"


def test_cache_persists(tmp_path):
    c = Cache(str(tmp_path / "c.sqlite"), 92)
    c.put("Hello there friend", "Selam dostum", REFINED, "claude")
    c.put("Hello there friend", "Merhaba", FAST, "yerel")          # düşük kalite üstüne yazamaz
    c2 = Cache(str(tmp_path / "c.sqlite"), 92)
    assert c2.get("hello there friend!")[0] == "Selam dostum"


def test_fullscreen_translate_shows_blocks_and_toggles_off(tmp_path):
    from altyazi.fullscreen import Block
    cfg = Config(bolgeler=[BolgeCfg()])
    sink = Sink()
    cleared = []
    sink.clear = cleared.append
    p = Pipeline(cfg, sink, FakeRec("x"), make_engine(tmp_path, Echo("tr")))

    class Reader:
        def read(self, frame):
            return [Block("Where are you?", (0.75, 0.25, 0.93, 0.32), 0.025),
                    Block("Bring the cash.", (0.75, 0.44, 0.9, 0.51), 0.027)]
    p._fs_reader = Reader()
    p.request_fullscreen()
    p.process(background(1920, 1080, 0), time.perf_counter())
    deadline = time.time() + 2
    while len(sink.items) < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert sorted(i.text for i in sink.items) == ["tr:Bring the cash.", "tr:Where are you?"]
    assert all(i.align == "sol" for i in sink.items)
    p.request_fullscreen()                    # ikinci basış kapatır
    assert sorted(cleared) == ["tam0", "tam1"]


def test_pause_clears_and_skips(tmp_path):
    cfg = Config(bolgeler=[BolgeCfg()])
    sink = Sink()
    cleared = []
    sink.clear = cleared.append
    p = Pipeline(cfg, sink, FakeRec("Get in the car."), make_engine(tmp_path, Echo("tr")))
    p.process(draw_subtitle(background(1920, 1080, 0), ["Get in the car."]), time.perf_counter())
    sink.ev.wait(2)
    assert p.toggle_pause() is True and cleared == ["altyazi"]
    n = len(sink.items)
    p.process(draw_subtitle(background(1920, 1080, 0), ["Something else entirely now."]), time.perf_counter())
    time.sleep(0.2)
    assert len(sink.items) == n
    assert p.toggle_pause() is False
