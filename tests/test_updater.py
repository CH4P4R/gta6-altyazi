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


def test_update_script_waits_for_app_and_reports(tmp_path):
    from altyazi import updater
    s = updater.update_script(tmp_path / "Setup.exe", r"C:\Program Files\O'X\GTA6Altyazi.exe", 4242, tmp_path / "g.log")
    assert "Wait-Process -Id 4242" in s                               # önce program kapanır
    assert "Stop-Process -Id 4242 -Force" in s
    assert s.index("Wait-Process") < s.index("Start-Process -FilePath")  # kurulum ancak sonra başlar
    assert "/VERYSILENT" in s and '"/LOG=' in s and "WaitForExit()" in s and "-Wait " not in s
    assert r"'C:\Program Files\O''X\GTA6Altyazi.exe'" in s            # yol güvenle tırnaklanır
    assert "if ($code -ne 0)" in s                                  # başarısızsa eski program yeniden açılır


def test_failed_update_is_reported_once(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from altyazi import updater
    (tmp_path / "guncelleme.json").write_text(json.dumps({"hedef": "99.0.0", "eski": "0.1.0"}))
    (tmp_path / "guncelleme.sonuc").write_text("5")
    msg = updater.last_update_problem()
    assert "99.0.0" in msg and "kod 5" in msg
    assert updater.last_update_problem() is None                     # bir kez söylenir
    (tmp_path / "guncelleme.json").write_text(json.dumps({"hedef": "0.0.1"}))
    assert updater.last_update_problem() is None                     # güncelleme olmuş: sessiz
