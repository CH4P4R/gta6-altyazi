"""Gerçek Windows'ta uçtan uca deneme (GitHub Actions'ta her kurulum derlemesinde çalışır).

Kullanıcının yaptığını yapar, kurulu programı dışarıdan (HTTP, süreç, kayıt defteri) denetler:

1. Eski sürümü (bir önceki GitHub sürümü) sessiz kurar; ayar dosyasında bir Claude anahtarı vardır.
2. Uygulama içi güncellemenin kullandığı betikle, açık programı yeni kurulum dosyasıyla günceller:
   sürüm gerçekten değişti mi, program kendiliğinden yeniden açıldı mı, anahtar duruyor mu.
3. Açık programda çeviriyi başlatır: kaynak, İngilizce altyazılı bir oyun karesi. OCR okuyor mu, yerel model
   çeviriyor mu, Türkçe TV akışına (/events) geliyor mu.
4. Güvenlik duvarı iznini gerçekten yazar ve doğrular.

    python tools/e2e_windows.py dist\\GTA6Altyazi-Setup.exe [eski-kurulum.exe]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

APP_ID = "{6B6F1E5A-3C2D-4F8E-9A71-6A0C7D2B9E41}_is1"
INSTALL = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "GTA6Altyazi"
EXE = INSTALL / "GTA6Altyazi.exe"
DATA = Path(os.environ["APPDATA"]) / "GTA6Altyazi"
PORT = 8787
KEY = "sk-ant-e2e-deneme-anahtari"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(("  OK  " if ok else "  HATA") + f"  {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return bool(ok)


def installed_version() -> str | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}") as k:
            return winreg.QueryValueEx(k, "DisplayVersion")[0]
    except OSError:
        return None


def app_pids() -> list[int]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          f"Get-Process | Where-Object {{ $_.Path -eq '{EXE}' }} | ForEach-Object {{ $_.Id }}"],
                         capture_output=True, text=True).stdout
    return [int(x) for x in out.split() if x.strip().isdigit()]


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
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def run_install(setup: Path) -> int:
    p = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={DATA / 'e2e-kurulum.log'}"],
                       timeout=600)
    return p.returncode


def write_config(frame: Path) -> None:
    import yaml
    DATA.mkdir(parents=True, exist_ok=True)
    cfg = {
        "kaynak": {"tur": "resim", "dosya": str(frame)},
        "ceviri": {"kalite": "yok", "claude_anahtar": KEY},
        "otomatik": {"paket_guncelle": False, "surum_denetle": False, "chiaki_gorunce_baslat": False},
        "tv": {"ip": "", "otomatik": False},
    }
    (DATA / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")


def make_frame() -> Path:
    from synth import background, draw_subtitle
    import cv2
    f = draw_subtitle(background(1920, 1080, seed=3), ["Get in the car, we have to go."], size=44)
    path = DATA.parent / "gta6-e2e-kare.png"
    cv2.imwrite(str(path), f)
    return path


def key_in_config() -> bool:
    import yaml
    try:
        data = yaml.safe_load((DATA / "config.yaml").read_text(encoding="utf-8")) or {}
        return (data.get("ceviri") or {}).get("claude_anahtar") == KEY
    except OSError:
        return False


def kill_app() -> None:
    for pid in app_pids():
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    wait(lambda: not app_pids(), 20)


# ------------------------------------------------------------------------------------------ adımlar
def step_update(new_setup: Path, old_setup: Path | None, new_version: str) -> None:
    print("\n== 1-2. Eski sürüm kurulu programın uygulama içi güncellemesi", flush=True)
    if old_setup is None or not old_setup.exists():
        check("eski sürüm kurulum dosyası", False, "bulunamadı; güncelleme adımı atlandı")
        return
    rc = run_install(old_setup)
    old = installed_version()
    check("eski sürüm sessiz kuruldu", rc == 0 and old and old != new_version, f"kod {rc}, sürüm {old}")
    if not app_pids():                                     # eski kurulum programı açmadıysa elle aç
        subprocess.Popen([str(EXE)], cwd=str(INSTALL))
    pid = wait(lambda: (app_pids() or [None])[0], 60)
    check("eski program açık", bool(pid), f"pid {pid}")
    if not pid:
        return
    from altyazi import updater
    log_file = DATA / "guncelleme.log"
    for f in (log_file, log_file.with_suffix(".sonuc"), log_file.with_suffix(".adim")):
        f.unlink(missing_ok=True)
    # uygulamanın kullandığı başlatıcının aynısı
    updater.launch_script(updater.update_script(new_setup, str(EXE), pid, log_file))
    # uygulama içi güncellemede program kendini kapatır; burada aynısı: kapatma isteği (kısa gecikmeyle)
    time.sleep(3)
    subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
    done = wait(lambda: log_file.with_suffix(".sonuc").exists(), 300, 2)
    code = log_file.with_suffix(".sonuc").read_text().strip() if done else "?"
    check("güncelleme kurulumu bitti", done and code == "0", f"kurulum çıkış kodu {code}")
    check("yeni sürüm kurulu", installed_version() == new_version, f"kayıtlı sürüm {installed_version()}")
    new_pid = wait(lambda: [p for p in app_pids() if p != pid], 60)
    check("program güncellemeden sonra kendiliğinden açıldı", bool(new_pid), f"pid {new_pid}")
    check("Claude anahtarı güncellemeden sonra duruyor", key_in_config())
    if not (done and code == "0"):
        for f in (log_file.with_suffix(".adim"), log_file):
            if f.exists():
                print(f"  --- {f.name} ---")
                print(f.read_text(encoding="utf-8", errors="replace")[-3000:])
            else:
                print(f"  ({f.name} yok)")


def step_translate(new_setup: Path, new_version: str) -> None:
    print("\n== 3. Çeviri: oyun karesi → OCR → yerel model → TV akışı", flush=True)
    if installed_version() != new_version:
        rc = run_install(new_setup)
        check("yeni sürüm sessiz kuruldu", rc == 0 and installed_version() == new_version, f"kod {rc}")
    if not app_pids():
        subprocess.Popen([str(EXE)], cwd=str(INSTALL))
    hello = wait(lambda: http("/hello"), 90)
    check("program sunucusu yanıt veriyor (/hello)", hello and hello.get("app") == "gta6altyazi", str(hello))
    ready = wait(lambda: http("/komut/durum", "POST").get("durum") in ("hazir", "calisiyor"), 180, 2)
    check("çeviri motorları hazır", bool(ready), str(http("/komut/durum", "POST")) if hello else "")
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

    import threading
    threading.Thread(target=reader, daemon=True).start()
    time.sleep(2)
    check("TV akışı önce stil gönderiyor", events and events[0][0] == "style", events[0][0] if events else "olay yok")
    if http("/komut/durum", "POST").get("durum") != "calisiyor":
        print("  ", http("/komut/baslat_durdur", "POST"))
    sub = wait(lambda: next((d for n, d in events if n == "subtitle" and d.get("text")), None), 90)
    text = (sub or {}).get("text", "")
    check("İngilizce altyazı okunup Türkçesi TV akışına geldi", bool(text) and "car" not in text.lower(), text)
    if sub:
        b = sub.get("box", {})
        check("altyazı kutusu ekranın altında", b.get("top", 0) > 0.7, json.dumps(b))
    log = DATA / "altyazi.log"
    if log.exists():
        tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        print("  --- altyazi.log (son satırlar) ---")
        for ln in tail:
            print("  " + ln)


def step_firewall() -> None:
    print("\n== 4. Güvenlik duvarı izni (gerçek kural)", flush=True)
    from altyazi import winutil
    check("ağ profili okunabiliyor", winutil.network_is_public() in (True, False), str(winutil.network_is_public()))
    res = winutil.firewall_allow(make_private=False)
    check("İzin ver: kural yazıldı ve doğrulandı", res == "tamam", res)
    check("durum denetimi izni görüyor", winutil.firewall_ok() is True, str(winutil.firewall_ok()))


def main() -> int:
    new_setup = Path(sys.argv[1]).resolve()
    old_setup = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 and sys.argv[2] else None
    import altyazi
    new_version = altyazi.__version__
    print(f"Yeni sürüm {new_version}; eski kurulum: {old_setup}")
    kill_app()
    frame = make_frame()
    write_config(frame)
    try:
        step_update(new_setup, old_setup, new_version)
        step_translate(new_setup, new_version)
        step_firewall()
    finally:
        kill_app()
    failed = [r for r in results if not r[1]]
    print(f"\n== SONUÇ: {len(results) - len(failed)}/{len(results)} başarılı")
    for name, _, detail in failed:
        print(f"  HATA: {name} ({detail})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
