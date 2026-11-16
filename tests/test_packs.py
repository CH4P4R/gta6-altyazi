import gzip
import json

from altyazi import packs


GOLDEN = {
    "You fucked up now, boy!": "e7f18c8f6d1083ab",
    "İstanbul": "751c59fe1fa734e6",
    "Ｆｕｌｌ　ｗｉｄｔｈ ５": "ff5126e112d609b8",
    "<b><h>SCANNATURI SPECIALE</></> KNIFE": "1e9ae63d544282c4",
}


def test_golden_keys():
    for text, k in GOLDEN.items():
        assert packs.key(text) == k, text
    assert packs.key("...") is None


def test_library_lookup_and_sentences(tmp_path):
    folder = tmp_path / "paketler"
    folder.mkdir()
    data = {"format": 2, "id": "deneme", "title": "Deneme",
            "entries": {packs.key("Get in the car."): "Arabaya bin.",
                        packs.key("Lose the cops."): "Polislerden kurtul."}}
    (folder / "deneme.json.gz").write_bytes(gzip.compress(json.dumps(data).encode()))
    lib = packs.PackLibrary(folder)
    assert lib.packs[0].count == 2
    assert lib.lookup("GET IN THE CAR!") == ("Arabaya bin.", "deneme")
    assert lib.lookup("Get in the car. Lose the cops.") == ("Arabaya bin. Polislerden kurtul.", "deneme")
    assert lib.lookup("Get in the car. Go home.") is None


def test_export_roundtrip(tmp_path):
    dest = tmp_path / "out.json.gz"
    n = packs.export_cache([("Go to the hospital.", "Hastaneye git."), ("", "x")], dest)
    assert n == 1
    folder = tmp_path / "lib"
    folder.mkdir()
    dest.rename(folder / dest.name)
    assert packs.PackLibrary(folder).lookup("go to the hospital") == ("Hastaneye git.", "gta6-altyazi-onbellek")


def test_engine_uses_pack_without_ai(tmp_path, monkeypatch):
    from altyazi import paths, translate

    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    (tmp_path / "paketler").mkdir()
    data = {"id": "p", "title": "P", "entries": {packs.key("Lose the cops."): "Polislerden kurtul."}}
    (tmp_path / "paketler" / "p.json").write_text(json.dumps(data), encoding="utf-8")
    eng = translate.TranslationEngine.__new__(translate.TranslationEngine)
    eng.packs = packs.PackLibrary(tmp_path / "paketler")
    got = eng.packs.lookup("Lose the cops.")
    assert got == ("Polislerden kurtul.", "p")


def test_speaker_label_lookup(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    data = {"id": "x", "title": "X", "entries": {packs.key("Get in the car."): "Arabaya bin."}}
    (folder / "x.json").write_text(json.dumps(data), encoding="utf-8")
    lib = packs.PackLibrary(folder)
    assert lib.lookup("FRANKLIN: Get in the car.") == ("FRANKLIN: Arabaya bin.", "x")
    assert lib.lookup("- Get in the car.") == ("Arabaya bin.", "x")      # çizgi sadeleştirmede zaten düşer
    assert lib.lookup("Lamar: Go home.") is None
