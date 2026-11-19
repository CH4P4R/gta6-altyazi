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


def test_couchsubs_catalog_and_verified_download(tmp_path):
    """CouchSubs paket sunucusu: liste + SHA-256 doğrulamalı indirme (GTA 6 paketi burada dağıtılıyor)."""
    import hashlib
    raw = gzip.compress(json.dumps({"format": 2, "id": "gta-6", "title": "Grand Theft Auto VI",
                                    "entries": {packs.key("Get in the sea plane."): "Deniz uçağına bin."}}).encode())
    index = {"packs": [{"id": "gta-6", "title": "Grand Theft Auto VI", "version": 3, "size": len(raw), "entries": 1,
                        "sha256": hashlib.sha256(raw).hexdigest()},
                       {"id": "../kötü", "title": "x", "sha256": "0" * 64}]}
    cat = packs.couchsubs_catalog(fetch=lambda url: index)
    assert [p["id"] for p in cat] == ["gta-6"]                 # geçersiz kimlik ayıklanır
    pack = packs.download_couchsubs(cat[0], tmp_path, fetch=lambda url: raw)
    assert pack.title == "Grand Theft Auto VI"
    assert packs.PackLibrary(tmp_path).lookup("Get in the sea plane.") == ("Deniz uçağına bin.", "gta-6")
    bad = dict(cat[0], sha256="1" * 64)
    try:
        packs.download_couchsubs(bad, tmp_path / "b", fetch=lambda url: raw)
        raise AssertionError("doğrulama yapılmadı")
    except ValueError:
        pass
    assert packs.couchsubs_catalog(fetch=lambda url: (_ for _ in ()).throw(OSError("yok"))) == []


def test_own_release_catalog_and_bundled_packs(tmp_path):
    """Paketler kendi GitHub sürümümüzden iner; kurulumla gelen paketler de yüklenir, indirilen sürüm önce gelir."""
    import hashlib
    gz = gzip.compress(json.dumps({"id": "gta-6", "title": "Grand Theft Auto VI",
                                   "entries": {packs.key("Get in the sea plane."): "Deniz uçağına bin."}}).encode())
    index = {"packs": [{"id": "gta-6", "title": "Grand Theft Auto VI", "entries": 1, "source": "CouchSubs",
                        "sha256": hashlib.sha256(gz).hexdigest(), "size": len(gz), "version": 5}]}
    cat = packs.own_catalog(fetch=lambda url: index)
    assert cat[0]["own"] and cat[0]["source"] == "CouchSubs"
    data = tmp_path / "data"
    packs.download_own(cat[0], data, fetch=lambda url: gz)
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    old = {"id": "gta-6", "title": "eski", "entries": {packs.key("Get in the sea plane."): "ESKİ"}}
    (bundled / "gta-6.json.gz").write_bytes(gzip.compress(json.dumps(old).encode()))
    other = {"id": "gta-v", "title": "GTA V", "entries": {packs.key("Lose the cops."): "Polislerden kurtul."}}
    (bundled / "gta-v.json.gz").write_bytes(gzip.compress(json.dumps(other).encode()))
    lib = packs.PackLibrary(data, bundled)
    assert lib.lookup("Get in the sea plane.") == ("Deniz uçağına bin.", "gta-6")   # indirilen, gömülüden önce
    assert lib.lookup("Lose the cops.") == ("Polislerden kurtul.", "gta-v")         # gömülü paket de çalışır
