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


def test_mac_update_script_replaces_bundle(tmp_path):
    """macOS güncelleme betiği: sahte hdiutil/ditto ile gerçek bash'te çalıştırılır."""
    import os
    import shutil
    import subprocess
    import sys
    if not shutil.which("bash"):
        import pytest
        pytest.skip("bash yok")
    from altyazi import updater
    app = tmp_path / "Applications" / "GTA6 Altyazı.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "MacOS" / "GTA6Altyazi").write_text("eski")
    assert updater.mac_bundle(str(app / "Contents" / "MacOS" / "GTA6Altyazi")) == app
    new_app = tmp_path / "dmg" / "GTA6 Altyazı.app" / "Contents" / "MacOS"
    new_app.mkdir(parents=True)
    (new_app / "GTA6Altyazi").write_text("yeni")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # hdiutil attach: dmg içeriğini bağlama noktasına kopyala; ditto: cp -R; open/xattr: hiçbir şey
    (bin_dir / "hdiutil").write_text(f'#!/bin/bash\nif [ "$1" = attach ]; then for a; do last=$m; m=$a; done; '
                                     f'mnt=$(echo "$@" | sed "s/.*-mountpoint \\([^ ]*\\).*/\\1/"); '
                                     f'cp -R "{tmp_path / "dmg"}/." "$mnt/"; fi\n')
    (bin_dir / "ditto").write_text('#!/bin/bash\ncp -R "$1" "$2"\n')
    (bin_dir / "open").write_text(f'#!/bin/bash\necho "$1" > "{tmp_path / "acildi"}"\n')
    (bin_dir / "xattr").write_text("#!/bin/bash\nexit 0\n")
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    log = tmp_path / "guncelleme.log"
    script = updater.mac_update_script(tmp_path / "x.dmg", app, 999999, log)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    subprocess.run(["bash", "-c", script], env=env, timeout=60, check=True)
    assert (app / "Contents" / "MacOS" / "GTA6Altyazi").read_text() == "yeni"
    assert log.with_suffix(".sonuc").read_text().strip() == "0"
    assert (tmp_path / "acildi").read_text().strip() == str(app)


def test_release_asset_per_platform():
    from altyazi import updater
    assert updater.asset_name("darwin") == "GTA6Altyazi-mac.dmg"
    assert updater.asset_name("win32") == "GTA6Altyazi-Setup.exe"
