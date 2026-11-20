"""Gerçek Mac'te uçtan uca deneme (GitHub Actions macos-latest, Apple Silicon). Windows'taki e2e_windows.py'nin karşılığı.

1. (Önceki Mac sürümü varsa) eski .dmg'den kurar, açar; uygulama içi güncellemenin betiğiyle yeni .dmg'ye geçirir:
   sürüm değişti mi, program yeniden açıldı mı, Claude anahtarı duruyor mu.
2. Yeni sürümü .dmg'den kurar ve açar; İngilizce altyazılı oyun karesinden çeviriyi başlatır: OCR, yerel model,
   Türkçe TV akışına (/events) geliyor mu.

    python tools/e2e_mac.py dist/GTA6Altyazi-mac.dmg [eski.dmg]
"""

from __future__ import annotations

import json
import plistlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

APPS = Path.home() / "Applications"
BUNDLE = APPS / "GTA6 Altyazı.app"
EXE = BUNDLE / "Contents" / "MacOS" / "GTA6Altyazi"
DATA = Path.home() / "Library" / "Application Support" / "GTA6Altyazi"
PORT = 8787
KEY = "sk-ant-e2e-deneme-anahtari"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok, detail: str = "") -> bool:  # noqa: ANN001
    results.append((name, bool(ok), detail))
    print(("  OK  " if ok else "  HATA") + f"  {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def wait(cond, timeout: float, step: float = 1.0):  # noqa: ANN001, ANN201
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = cond()
            if v:
                return v
        except Exception:  # noqa: BLE001
            pass
        time.sleep(step)
    return None


def http(path: str, method: str = "GET", timeout: float = 5) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def app_pids() -> list[int]:
    out = subprocess.run(["pgrep", "-f", str(EXE)], capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if x.isdigit()]


def kill_app() -> None:
    for pid in app_pids():
        subprocess.run(["kill", "-9", str(pid)], capture_output=True)
    wait(lambda: not app_pids(), 15)


def bundle_version() -> str | None:
    try:
        return plistlib.loads((BUNDLE / "Contents" / "Info.plist").read_bytes()).get("CFBundleShortVersionString")
    except OSError:
        return None


def install_from_dmg(dmg: Path) -> bool:
    mnt = Path(tempfile.mkdtemp(prefix="gta6dmg"))
    r = subprocess.run(["hdiutil", "attach", "-nobrowse", "-quiet", "-noautoopen", "-mountpoint", str(mnt), str(dmg)])
    if r.returncode != 0:
        return False
    try:
        src = next(mnt.glob("*.app"))
        APPS.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(BUNDLE, ignore_errors=True)
        subprocess.run(["ditto", str(src), str(BUNDLE)], check=True)
    finally:
        subprocess.run(["hdiutil", "detach", "-quiet", str(mnt)])
    return EXE.exists()


def launch() -> None:
    subprocess.Popen([str(EXE)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def write_config(frame: Path) -> None:
    import yaml
    DATA.mkdir(parents=True, exist_ok=True)
    cfg = {"kaynak": {"tur": "resim", "dosya": str(frame)},
           "ceviri": {"kalite": "yok", "claude_anahtar": KEY},
           "otomatik": {"paket_guncelle": False, "surum_denetle": False, "chiaki_gorunce_baslat": False},
           "tv": {"ip": "", "otomatik": False}}
    (DATA / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


def key_in_config() -> bool:
    import yaml
    try:
        return ((yaml.safe_load((DATA / "config.yaml").read_text(encoding="utf-8")) or {}).get("ceviri") or {}) \
            .get("claude_anahtar") == KEY
    except OSError:
        return False


def make_frame() -> Path:
    import cv2
    from synth import background, draw_subtitle
    path = DATA.parent / "gta6-e2e-kare.png"
    cv2.imwrite(str(path), draw_subtitle(background(1920, 1080, seed=3), ["Get in the car, we have to go."], size=44))
    return path


def step_update(new_dmg: Path, old_dmg: Path | None, new_version: str) -> None:
    print("\n== 1. Eski Mac sürümünden uygulama içi güncelleme", flush=True)
    if not old_dmg or not old_dmg.exists():
        print("  (önceki Mac sürümü yok; bu ilk Mac sürümü, güncelleme adımı atlandı)")
        return
    check("eski sürüm .dmg'den kuruldu", install_from_dmg(old_dmg), str(bundle_version()))
    launch()
    pid = wait(lambda: (app_pids() or [None])[0], 60)
    check("eski program açık", bool(pid), f"pid {pid}")
    if not pid:
        return
    from altyazi import updater
    log_file = DATA / "guncelleme.log"
    for f in (log_file, log_file.with_suffix(".sonuc"), log_file.with_suffix(".adim")):
        f.unlink(missing_ok=True)
    script = DATA / "guncelle-e2e.sh"
    script.write_text(updater.mac_update_script(new_dmg, BUNDLE, pid, log_file), encoding="utf-8")
    subprocess.Popen(["/bin/bash", str(script)], start_new_session=True)
    time.sleep(2)
    subprocess.run(["kill", str(pid)], capture_output=True)       # uygulama içinde program kendini kapatır
    done = wait(lambda: log_file.with_suffix(".sonuc").exists(), 300, 2)
    code = log_file.with_suffix(".sonuc").read_text().strip() if done else "?"
    check("güncelleme bitti", done and code == "0", f"kod {code}")
    check("yeni sürüm kurulu", bundle_version() == new_version, f"paket sürümü {bundle_version()}")
    check("program güncellemeden sonra kendiliğinden açıldı", wait(lambda: [p for p in app_pids() if p != pid], 60))
    check("Claude anahtarı güncellemeden sonra duruyor", key_in_config())
    if not (done and code == "0"):
        for f in (log_file.with_suffix(".adim"), log_file):
            if f.exists():
                print(f"  --- {f.name} ---\n" + f.read_text(errors="replace")[-3000:])
    kill_app()


def step_translate(new_dmg: Path, new_version: str) -> None:
    print("\n== 2. Çeviri: oyun karesi → OCR → yerel model → TV akışı", flush=True)
    if bundle_version() != new_version:
        check("yeni sürüm .dmg'den kuruldu", install_from_dmg(new_dmg) and bundle_version() == new_version,
              str(bundle_version()))
    launch()
    hello = wait(lambda: http("/hello"), 120)
    check("program açıldı, sunucu yanıt veriyor (/hello)", hello and hello.get("app") == "gta6altyazi", str(hello))
    ready = wait(lambda: http("/komut/durum", "POST").get("durum") in ("hazir", "calisiyor"), 240, 2)
    check("çeviri motorları hazır", bool(ready))
    events: list[tuple[str, dict]] = []

    def reader() -> None:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/events", timeout=120) as r:
                name = None
                for raw in r:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line.startswith("event:"):
                        name = line[6:].strip()
                    elif line.startswith("data:") and name:
                        try:
                            events.append((name, json.loads(line[5:])))
                        except ValueError:
                            pass
        except Exception as e:  # noqa: BLE001
            print("  /events okuma bitti:", e)

    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)
    if hello and http("/komut/durum", "POST").get("durum") != "calisiyor":
        http("/komut/baslat_durdur", "POST")
    sub = wait(lambda: next((d for n, d in events if n == "subtitle" and d.get("text")), None), 120)
    text = (sub or {}).get("text", "")
    check("İngilizce altyazı okunup Türkçesi TV akışına geldi", bool(text) and "car" not in text.lower(), text)
    log = DATA / "altyazi.log"
    if log.exists():
        print("  --- altyazi.log (son satırlar) ---")
        for ln in log.read_text(errors="replace").splitlines()[-25:]:
            print("  " + ln)


def main() -> int:
    new_dmg = Path(sys.argv[1]).resolve()
    old_dmg = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 and sys.argv[2] else None
    import altyazi
    new_version = altyazi.__version__
    print(f"Yeni sürüm {new_version}; eski: {old_dmg}")
    kill_app()
    write_config(make_frame())
    try:
        step_update(new_dmg, old_dmg, new_version)
        step_translate(new_dmg, new_version)
    finally:
        kill_app()
    failed = [r for r in results if not r[1]]
    print(f"\n== SONUÇ: {len(results) - len(failed)}/{len(results)} başarılı")
    for name, _, detail in failed:
        print(f"  HATA: {name} ({detail})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
