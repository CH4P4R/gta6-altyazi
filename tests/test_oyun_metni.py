"""Oyun metniyle okuma düzeltme: dizin kurulur, OCR hatalı satır gerçek satıra oturur, emin olunmayan satır kalır."""

from pathlib import Path

from altyazi import oyun_metni as om

HEAD = "table\ttable_offset\tidx\thash\ttext\n"


def _db(tmp_path: Path) -> Path:
    src = tmp_path / "raw.tsv"
    src.write_text(HEAD + "".join(f"0000\t0x0\t{i}\tAB\t{t}\n" for i, t in enumerate([
        "~sl:0:2.41~That's the hotel over there. Triple homicide...~sl:0.66~They never found the ear.",
        "Stop your vehicle!",
        "Keep 'em contained. Backup's on the way.",
        "Press ~INPUT_CONTEXT~ to enter the ~b~vehicle~s~.",
        "Get in the car, we got company!",
        "Hi.",
    ])), encoding="utf-8")
    dest = tmp_path / "gta6.sqlite"
    assert om.build(dest, [src]) >= 6
    return dest


def test_clean_splits_segments_and_strips_codes():
    assert om.clean("~sl:0:1~Hello there friend.~sl:0.5~How are you doing?") == [
        "Hello there friend.", "How are you doing?", "Hello there friend. How are you doing?"]
    assert om.clean("Press ~INPUT_CONTEXT~ to enter the ~b~vehicle~s~.") == ["Press to enter the vehicle ."]
    assert om.clean("Hi.") == []


def test_snap(tmp_path):
    ix = om.ScriptIndex(_db(tmp_path))
    assert ix.snap("They never found the eor.") == "They never found the ear."
    assert ix.snap("Stop your vehic1e!") == "Stop your vehicle!"
    assert ix.snap("Keep em contained. Backups on the way.") == "Keep 'em contained. Backup's on the way."
    assert ix.snap("Get in the car, we got company!") is None          # zaten doğru
    assert ix.snap("I like turtles and pizza very much") is None       # oyunda yok: dokunma
    assert ix.exact("stop your VEHICLE")


def test_engine_snap_keeps_speaker(tmp_path, monkeypatch):
    from altyazi.translate import TranslationEngine
    ix = om.ScriptIndex(_db(tmp_path))
    eng = TranslationEngine.__new__(TranslationEngine)
    eng.script, eng.game_pack = ix, None
    assert eng.snap("LUCIA: Get in the cor, we got cornpany!") == "LUCIA: Get in the car, we got company!"
    assert eng.snap("Nothing like this in the game here") == "Nothing like this in the game here"


def test_pack_hit_does_not_wait_for_script_search(tmp_path):
    """Hız: satır pakette varsa oyun metninde arama yapılmaz; yalnız pakette yoksa düzeltilip yeniden bakılır."""
    from altyazi.translate import TranslationEngine

    class Script:
        calls = 0

        def snap(self, text):
            Script.calls += 1
            return "Get in the car, we got company!" if "cornpany" in text else None

    class Packs:
        packs = []

        def lookup(self, text):
            return ("Arabaya bin, misafirimiz var!", "gta-6") if text == "Get in the car, we got company!" else None

    class Cache:
        def get(self, text):
            return None

    eng = TranslationEngine.__new__(TranslationEngine)
    eng.script, eng.game_pack, eng.packs, eng.cache = Script(), None, Packs(), Cache()
    eng.pack_lookup = lambda text: Packs().lookup(text)
    eng.cfg = type("C", (), {"paket_kullan": True})()
    eng.context, eng.ctx_lock = __import__("collections").deque(maxlen=0), __import__("threading").Lock()
    got = []
    eng.submit("Get in the car, we got company!", "altyazi", got.append)
    assert got[0].text == "Arabaya bin, misafirimiz var!" and Script.calls == 0
    eng.submit("Get in the car, we got cornpany!", "altyazi", got.append)
    assert got[1].text == "Arabaya bin, misafirimiz var!" and Script.calls == 1
