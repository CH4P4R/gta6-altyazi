import gzip
import hashlib
import json

from altyazi import packs, updater


def _gz(title, tr):
    return gzip.compress(json.dumps({"id": "gta-6", "title": title,
                                     "entries": {packs.key("Get in the sea plane."): tr}}).encode())


def test_installed_pack_is_updated_silently(tmp_path):
    """Kurulumla gelen GTA 6 paketinin yenisi GitHub'da varsa kurulum yapmadan indirilir; olmayan paket indirilmez."""
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    (bundled / "gta-6.json.gz").write_bytes(_gz("GTA VI (eski)", "eski"))
    new = _gz("Grand Theft Auto VI", "Deniz uçağına bin.")
    cat = [{"id": "gta-6", "title": "Grand Theft Auto VI", "entries": 1, "sha256": hashlib.sha256(new).hexdigest()},
           {"id": "elden-ring", "title": "Elden Ring", "entries": 9, "sha256": "0" * 64}]
    got = []

    def dl(info, folder):
        got.append(info["id"])
        return packs.download_own(info, folder, fetch=lambda url: new)
    data = tmp_path / "data"
    done = updater.update_packs(data, bundled, catalog=cat, download=dl)
    assert got == ["gta-6"] and done[0].title == "Grand Theft Auto VI"
    lib = packs.PackLibrary(data, bundled)
    assert lib.lookup("Get in the sea plane.") == ("Deniz uçağına bin.", "gta-6")
    # ikinci açılışta zaten güncel: indirme yok
    got.clear()
    assert updater.update_packs(data, bundled, catalog=cat, download=dl) == [] and got == []


def test_latest_release_picks_newest_version_with_setup():
    rels = [{"tag_name": "paketler", "assets": [{"name": "gta-6.json.gz"}]},
            {"tag_name": "v0.4.9", "assets": [{"name": "GTA6Altyazi-Setup.exe", "browser_download_url": "u49",
                                               "size": 10}]},
            {"tag_name": "v0.4.10", "assets": [{"name": "GTA6Altyazi-Setup.exe", "browser_download_url": "u410",
                                                "size": 11}], "body": "notlar"},
            {"tag_name": "v0.5.0", "assets": []}]                      # kurulum dosyası henüz yüklenmemiş
    rel = updater.latest_release(fetch=lambda url: rels)
    assert rel["version"] == "0.4.10" and rel["url"] == "u410"
    assert updater.newer_than_current(rel, "0.4.9")
    assert not updater.newer_than_current(rel, "0.4.10")
    assert updater.latest_release(fetch=lambda url: (_ for _ in ()).throw(OSError())) is None
