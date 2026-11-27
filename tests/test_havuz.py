"""Ortak çeviri havuzu: gerçek sunucu (sunucu/havuz/havuz_sunucu.py) + istemci (altyazi/havuz.py) uçtan uca."""

import importlib
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sunucu" / "havuz"))


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("HAVUZ_VERI", str(tmp_path / "havuz.sqlite"))
    import havuz_sunucu
    hs = importlib.reload(havuz_sunucu)
    store = hs.Store(tmp_path / "havuz.sqlite")
    packs = hs.Packs(store, min_votes=2)
    packs.rebuild()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), hs.make_handler(store, packs, hs.RateLimit()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", store, packs, hs
    httpd.shutdown()


def client(base, n):
    from altyazi.havuz import PoolClient
    return PoolClient(base, f"{n:032x}", every=999)


def test_two_installs_make_a_line_public(server, tmp_path):
    base, store, packs, hs = server
    from altyazi.packs import load, key
    a, b = client(base, 1), client(base, 2)
    assert a.add("Get in the car, we got company!", "Arabaya bin, misafirimiz var!", "claude")
    assert not a.add("Get in the car, we got company!", "Arabaya bin, misafirimiz var!", "claude"), "aynı satır bir kez"
    assert not a.add("Hello there friend", "Merhaba dostum", "yerel"), "yerel model havuza gitmez"
    a.add("Where is Lucia?", "Lucia nerede?", "gemini")
    assert a.flush() == 2
    packs.rebuild()
    assert a.update_pack(tmp_path) is None, "tek kurulumun satırı henüz paket değil"
    b.add("Get in the car, we got company!", "Arabaya bin, misafirimiz var!", "deepl")
    assert b.flush() == 1
    packs.rebuild()
    path = b.update_pack(tmp_path)
    assert path is not None and path.name == "havuz-gta-6.json.gz"
    pack = load(path)
    assert pack.entries == {key("Get in the car, we got company!"): "Arabaya bin, misafirimiz var!"}
    assert b.update_pack(tmp_path) is None, "değişmediyse yeniden inmez"


def test_most_voted_translation_wins_and_junk_is_rejected(server):
    base, store, packs, hs = server
    for i, tr in enumerate(["Gidelim.", "Gidelim.", "Hadi gidelim.", "Gidelim."]):
        c = client(base, 10 + i)
        c.add("Let's go now, come on", tr, "claude")
        c.flush()
    junk = client(base, 99)
    junk.add("Get in the car right now please", "Get in the car right now please", "claude")   # çevrilmemiş
    junk.add("Visit our site", "Siteye gir https://kotu.example", "claude")
    assert junk.flush() == 0
    assert list(store.best("gta-6", 2).values()) == ["Gidelim."]
    assert hs.acceptable("Get in the car", "Arabaya bin")
    assert not hs.acceptable("This is what you get for the deal", "This is what you get for the deal now")


def test_bad_requests_and_block(server):
    base, store, packs, hs = server
    import urllib.error
    import urllib.request
    req = urllib.request.Request(base + "/v1/satir", data=json.dumps({"client": "x", "game": "gta-6", "items": []})
                                 .encode(), method="POST")
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 400
    c = client(base, 5)
    c.add("Hold the line, I am coming", "Hattı tut, geliyorum", "claude")
    assert c.flush() == 1
    assert store.block(f"{5:032x}") == 1
    c.add("Another line for the pool", "Havuz için başka satır", "claude")
    assert c.flush() == 0, "engellenen kurulumun satırı alınmaz"
    with urllib.request.urlopen(base + "/v1/saglik", timeout=5) as r:
        assert json.loads(r.read())["ok"]


def test_engine_shares_only_ai_translations(tmp_path):
    from altyazi.translate import TranslationEngine

    class Pool:
        def __init__(self):
            self.got = []

        def add(self, en, tr, source):
            self.got.append((en, tr, source))

    eng = TranslationEngine.__new__(TranslationEngine)
    eng.pool, eng.game_pack = Pool(), None
    eng._share("Where are you?", "Neredesin?", "claude")
    assert eng.pool.got == [("Where are you?", "Neredesin?", "claude")]
    eng._share("x", "", "claude")
    assert len(eng.pool.got) == 1


def test_pool_is_on_by_default_with_our_server():
    from altyazi.config import Config
    from altyazi.havuz import DEFAULT_URL
    h = Config().havuz
    assert h.acik and h.gonder and h.al and h.adres == ""
    assert DEFAULT_URL.startswith("http") and ":8787" in DEFAULT_URL
