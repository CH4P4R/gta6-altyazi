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


def make_engine(tmp_path, fast=None, refine=None, wait_ms=0):
    e = TranslationEngine(CeviriCfg(hizli="yok", kalite="yok", onbellek=str(tmp_path / "c.sqlite"),
                                    kalite_bekleme_ms=wait_ms))
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
    # bir dahaki sefere OCR i/l harfini karıştırsa da önbellekten kaliteli hali gelir
    got = []
    eng.submit("Get ln the car.", "altyazi", got.append)
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


def test_fullscreen_with_claude_vision_uses_ocr_boxes_and_adds_missed_text(tmp_path):
    from altyazi.fullscreen import Block
    cfg = Config(bolgeler=[BolgeCfg()])
    sink = Sink()
    eng = make_engine(tmp_path, Echo("yerel"))
    seen = {}

    class Vision:
        name = "claude"

        def read_screen(self, jpeg, regions):
            seen["jpeg"], seen["regions"] = jpeg, regions
            return [{"id": 0, "english": "Where are you? The deal starts at midnight.",
                     "turkish": "Neredesin? İş gece yarısı başlıyor.", "box": [0, 0, 0, 0]},
                    {"id": -1, "english": "MISSION PASSED", "turkish": "GÖREV TAMAMLANDI", "box": [300, 400, 700, 460]},
                    {"id": 5, "english": "", "turkish": "", "box": [0, 0, 0, 0]}]
    eng.refine = Vision()
    p = Pipeline(cfg, sink, FakeRec("x"), eng)

    class Reader:
        def read(self, frame):
            return [Block("Where are you? The dea starts at midnight.", (0.75, 0.25, 0.93, 0.32), 0.025)]
    p._fs_reader = Reader()
    p._run_fullscreen(background(1920, 1080, 0), time.perf_counter())
    final = {i.zone: i for i in sink.items if i.source == "claude-görsel"}
    assert seen["jpeg"][:2] == b"\xff\xd8" and seen["regions"] == [(0, "Where are you? The dea starts at midnight.")]
    assert sorted(i.text for i in final.values()) == ["GÖREV TAMAMLANDI", "Neredesin? İş gece yarısı başlıyor."]
    by_text = {i.text: i for i in final.values()}
    assert by_text["Neredesin? İş gece yarısı başlıyor."].rect == (0.75, 0.25, 0.93, 0.32)   # OCR'ın kesin konumu
    assert by_text["GÖREV TAMAMLANDI"].rect == (0.3, 0.4, 0.7, 0.46)                     # OCR'ın kaçırdığı yazı
    assert eng.cache.get("MISSION PASSED")[0] == "GÖREV TAMAMLANDI"


class Fails:
    name = "claude"

    def translate(self, text, kind="", context=None):
        raise RuntimeError("ağ hatası")


def collect(eng, text, timeout=2.0, n=None):
    got = []
    eng.submit(text, "altyazi", got.append)
    deadline = time.time() + timeout
    while time.time() < deadline and (n is None or len(got) < n):
        time.sleep(0.01)
    return got


def test_quality_first_hides_fast_when_refined_is_quick(tmp_path):
    eng = make_engine(tmp_path, Echo("yerel"), Echo("claude", 0.05), wait_ms=300)
    got = collect(eng, "We gonna hit the bank.", timeout=0.6)
    assert [r.text for r in got] == ["claude:We gonna hit the bank."]


def test_quality_first_shows_fast_when_refined_is_slow(tmp_path):
    eng = make_engine(tmp_path, Echo("yerel"), Echo("claude", 0.6), wait_ms=150)
    t = time.perf_counter()
    got = collect(eng, "Get in the car.", n=2)
    assert [r.source for r in got] == ["yerel", "claude"]
    assert got[0].text == "yerel:Get in the car."
    assert time.perf_counter() - t < 1.5


def test_quality_first_shows_fast_immediately_when_refined_fails(tmp_path):
    eng = make_engine(tmp_path, Echo("yerel"), Fails(), wait_ms=2000)
    t = time.perf_counter()
    got = collect(eng, "Hold on.", n=1)
    assert [r.source for r in got] == ["yerel"] and time.perf_counter() - t < 1.0


def test_local_model_gets_standard_english(tmp_path):
    eng = make_engine(tmp_path, Echo("yerel"))
    got = collect(eng, "Ain't nobody tellin' the cops nothin'.", n=1)
    assert got[0].text == "yerel:Nobody is telling the police nothing."


def test_slang_rules():
    from altyazi.slang import normalize as n
    assert n("Yo homie, we gonna hit the bank or what?") == "Yo friend, we are going to hit the bank or what?"
    assert n("I ain't goin' back to jail.") == "I am not going back to jail."
    assert n("Five-O! Get in the whip, Lucia!") == "Police! Get in the car, Lucia!"
    assert n("Bet.") == "Okay."
    assert n("GTA stands for Grand Theft Auto.") == "GTA stands for Grand Theft Auto."   # dokunulmaz
    assert n("That ain't right.") == "That is not right."


def test_worse_reread_is_ignored():
    from altyazi.pipeline import worse_reread
    assert worse_reread("Get in the car, Franklin.", "Get in the car, Frank1in.")
    assert not worse_reread("Get in the car, Frank1in.", "Get in the car, Franklin.")   # düzelme kabul
    assert not worse_reread("I can do it.", "I can not do it.")                        # anlam değişti
    assert not worse_reread("Go.", "Run!")


def test_game_idioms_normalized():
    from altyazi.slang import normalize
    assert normalize("Heads up, we got company!") == "Watch out, enemies are coming!"
    assert normalize("Shake the cops and lay low.") == "Lose the police and hide for a while."


def test_objective_and_dialogue_are_separate_paragraphs():
    """Altta görev yazısı, üstünde diyalog: ayrı çevrilir, ikisi tek cümle olmaz."""
    from altyazi.pipeline import group_blocks
    lh = 30
    pad = lh // 4
    def box(y, x0=300, x1=900):      # detector kutuları: satır + lh/4 pay
        return (x0 - pad, y - pad, x1 + pad, y + lh + pad)
    # iki satırlık diyalog (satır arası küçük), altında bir satır boşluk ve görev yazısı
    boxes = [box(100), box(100 + lh + 8), box(100 + 2 * lh + 8 + lh)]
    texts = ["Hurry up, they are right", "behind us!", "Go to the car."]
    blocks = group_blocks(boxes, texts, lh)
    assert [t for t, _ in blocks] == ["Hurry up, they are right behind us!", "Go to the car."]
    # aynı satırdaki iki parça tek satır
    same_row = group_blocks([box(100, 100, 300), box(102, 400, 700)], ["Press", "to enter"], lh)
    assert [t for t, _ in same_row] == ["Press to enter"]


def test_paragraph_keys_stay_stable():
    from altyazi.pipeline import match_keys
    # önce yalnız görev yazısı (altta)
    k1 = match_keys("altyazi", {}, [(200, 240)])
    assert k1 == ["altyazi"]
    # diyalog üstüne çıktı: görev yazısı adını korur, diyalog yeni ad alır
    k2 = match_keys("altyazi", {"altyazi": (200, 240)}, [(120, 190), (200, 240)])
    assert k2 == ["altyazi.2", "altyazi"]
    # görev yazısı kalktı, diyalog kaldı
    k3 = match_keys("altyazi", {"altyazi.2": (120, 190), "altyazi": (200, 240)}, [(120, 190)])
    assert k3 == ["altyazi.2"]


def test_objective_under_dialogue_real_detector_and_ocr():
    """Gerçek bölge tespiti ve OCR ile: diyalog (2 satır) ve altındaki görev yazısı iki ayrı paragraf."""
    from altyazi.detector import ZoneDetector, zone_rect
    from altyazi.ocr import Recognizer
    from altyazi.pipeline import group_blocks

    f = background(1920, 1080)
    f = draw_subtitle(f, ["Hurry up, they are right behind us!", "Lose the cops first."], y_bottom=0.875)
    f = draw_subtitle(f, ["Go to the car."], y_bottom=0.95, highlight="car")
    z = BolgeCfg(ad="altyazi", alan=[0.10, 0.74, 0.90, 0.97])
    det = ZoneDetector(z)
    x0, y0, x1, y1 = zone_rect(z, 1920, 1080)
    ev = None
    for i in range(5):
        e = det.process(f[y0:y1, x0:x1], i * 0.033)
        if e and e.kind == "text":
            ev = e
            break
    assert ev is not None
    res = Recognizer().recognize([ln.image for ln in ev.lines])
    texts = [r.text if r.score >= z.min_skor else "" for r in res]
    blocks = [clean_ocr(t) for t, _ in group_blocks([ln.box for ln in ev.lines], texts, ev.line_height,
                                                     z.paragraf_boslugu)]
    assert len(blocks) == 2
    assert "behind us" in blocks[0] and "Lose the cops" in blocks[0]
    assert blocks[1] == "Go to the car."


def test_wide_line_spacing_unfinished_sentence_stays_together():
    from altyazi.pipeline import group_blocks
    lh, pad = 30, 7
    def box(y):
        return (300 - pad, y - pad, 900 + pad, y + lh + pad)
    # satır arası geniş (0.9 lh) ama ilk satırın cümlesi bitmemiş: tek paragraf
    wide = [box(100), box(100 + lh + int(0.9 * lh) + 2 * pad)]
    assert [t for t, _ in group_blocks(wide, ["Hurry up, they are right", "behind us!"], lh)] == \
        ["Hurry up, they are right behind us!"]
    # aynı boşluk, ilk cümle bitmiş: iki paragraf (diyalog + görev yazısı)
    assert len(group_blocks(wide, ["They are behind us!", "Go to the car."], lh)) == 2


def test_fuzzy_cache_does_not_mix_different_sentences(tmp_path):
    c = Cache(str(tmp_path / "c.db"), 92)
    c.put("Go to the car.", "Arabaya git.", REFINED, "t")
    c.put("You have $500.", "500 doların var.", REFINED, "t")
    c.put("Get in the car, Franklin.", "Arabaya bin Franklin.", REFINED, "t")
    assert c.get("Go to the bar.") is None
    assert c.get("You have $5000.") is None
    assert c.get("Get in the car, Frank1in.")[0] == "Arabaya bin Franklin."
