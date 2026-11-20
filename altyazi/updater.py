"""Güncellemeler: hazır paketler sessizce, uygulama tek tıkla.

- Paketler: açılışta kendi GitHub 'paketler' sürümümüzün listesine bakılır; bilgisayarda olan (indirilmiş ya da
  kurulumla gelen) bir paketin daha yenisi varsa arka planda indirilir. Kurulumu yeniden yapmaya gerek yoktur.
- Uygulama: GitHub sürümlerinden en yeni sürüm bulunur; daha yeniyse ana ekranda Güncelle düğmesi çıkar. Düğme kurulum
  dosyasını indirir, sessiz kurar (ayarlar %APPDATA%'da kaldığı için korunur) ve uygulama yeniden açılır.
  (Fikir GameTranslator'ın uygulama içi güncellemesinden.)
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from . import __version__, packs, paths

log = logging.getLogger(__name__)

REPO = "CH4P4R/gta6-altyazi"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=15"
SETUP_NAME = "GTA6Altyazi-Setup.exe"
MAC_NAME = "GTA6Altyazi-mac.dmg"


def asset_name(platform: str = sys.platform) -> str:
    return MAC_NAME if platform == "darwin" else SETUP_NAME
_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _ver(v: str) -> tuple[int, ...]:
    m = _TAG.match(v if v.startswith("v") else "v" + v)
    return tuple(int(x) for x in m.groups()) if m else (0,)


# ------------------------------------------------------------------------------------------- paketler
def _local_sha(pid: str, folder: Path, bundled: Path | None) -> str | None:
    for base in (folder, bundled):
        if base is not None:
            f = base / f"{pid}.json.gz"
            if f.exists():
                return hashlib.sha256(f.read_bytes()).hexdigest()
    return None


def update_packs(folder: Path | None = None, bundled: Path | None = None, catalog=None, download=None) -> list:  # noqa: ANN001
    """Bilgisayardaki paketlerin yenisini indir. Güncellenen paketleri döndürür."""
    folder = folder or paths.data("paketler")
    bundled = bundled if bundled is not None else paths.resource("paketler")
    cat = catalog if catalog is not None else packs.own_catalog()
    download = download or packs.download_own
    updated = []
    for info in cat:
        local = _local_sha(info["id"], folder, bundled)
        if local is None or local == info["sha256"]:
            continue                                   # bilgisayarda yok ya da zaten güncel
        try:
            updated.append(download(info, folder))
            log.info("Paket güncellendi: %s (%d satır)", info["title"], info["entries"])
        except Exception as e:  # noqa: BLE001
            log.warning("Paket güncellenemedi (%s): %s", info["id"], e)
    return updated


# ------------------------------------------------------------------------------------------- uygulama
def latest_release(fetch=None) -> dict | None:  # noqa: ANN001
    """{'version': '0.5.0', 'url': kurulum dosyası, 'size': bayt, 'notes': metin} ya da None."""
    try:
        if fetch is None:
            req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "gta6-altyazi",
                                                                "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                rels = json.loads(r.read().decode("utf-8"))
        else:
            rels = fetch(RELEASES_API)
    except Exception as e:  # noqa: BLE001
        log.info("Güncelleme denetlenemedi: %s", e)
        return None
    best = None
    for r in rels:
        tag = str(r.get("tag_name", ""))
        if not _TAG.match(tag) or r.get("draft"):
            continue
        asset = next((a for a in r.get("assets") or [] if a.get("name") == asset_name()), None)
        if not asset:
            continue
        if best is None or _ver(tag) > _ver("v" + best["version"]):
            best = {"version": tag[1:], "url": asset["browser_download_url"], "size": asset.get("size", 0),
                    "notes": r.get("body") or ""}
    return best


def newer_than_current(rel: dict | None, current: str = __version__) -> bool:
    return bool(rel) and _ver("v" + rel["version"]) > _ver("v" + current)


def download_setup(rel: dict, progress=None) -> Path:  # noqa: ANN001
    ext = "dmg" if sys.platform == "darwin" else "exe"
    dest = Path(tempfile.gettempdir()) / f"GTA6Altyazi-Setup-{rel['version']}.{ext}"
    req = urllib.request.Request(rel["url"], headers={"User-Agent": "gta6-altyazi"})
    done = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(dest.with_suffix(".part"), "wb") as f:
        total = int(r.headers.get("Content-Length") or rel.get("size") or 0)
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            done += len(b)
            if progress and total:
                progress(done / total)
    if rel.get("size") and done != rel["size"]:
        raise RuntimeError("Kurulum dosyası eksik indi; tekrar dene.")
    dest.with_suffix(".part").replace(dest)
    return dest


def _q(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def update_script(setup: Path, exe: str, pid: int, log_file: Path) -> str:
    """Program TAMAMEN kapandıktan sonra kurulumu çalıştıran PowerShell betiği.

    Eskiden kurulum program kapanmadan başlıyordu: dosyalar kullanımdayken sessiz kurulum hiçbir şey demeden iptal
    oluyor, eski sürüm kalıyordu. Şimdi: programın bitmesi beklenir (gerekirse kapatılır), kurulum günlükle çalışır,
    başarılıysa kurulum programı yeni sürümü açar (installer.iss), başarısızsa eski program yeniden açılır ve
    açılışta neden kurulamadığı gösterilir.
    """
    trace = _q(log_file.with_suffix(".adim"))
    # /LOG yolunda boşluk olabilir (C:\Users\Ali Veli\...): argüman tırnaklı tek metin olarak verilir.
    # Start-Process -Wait kurulumun açtığı programı da beklerdi (bitmezdi): yalnız kurulum süreci beklenir.
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
function Adim($m) {{ Add-Content -Path {trace} -Value ((Get-Date -Format 'HH:mm:ss') + ' ' + $m) }}
Adim 'basladi'
Wait-Process -Id {int(pid)} -Timeout 45
Stop-Process -Id {int(pid)} -Force
Get-Process | Where-Object {{ $_.Path -eq {_q(exe)} }} | Stop-Process -Force
Start-Sleep -Seconds 1
Adim 'program kapandi, kurulum basliyor'
$code = -1
try {{
  $p = Start-Process -FilePath {_q(setup)} -ArgumentList {_q('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCANCEL /CLOSEAPPLICATIONS "/LOG=' + str(log_file) + '"')} -PassThru -ErrorAction Stop
  $p.WaitForExit()
  $code = $p.ExitCode
}} catch {{ Adim ('kurulum baslatilamadi: ' + $_) }}
Adim ('kurulum bitti, kod ' + $code)
Set-Content -Path {_q(log_file.with_suffix('.sonuc'))} -Value $code
if ($code -ne 0) {{ Start-Process -FilePath {_q(exe)} }}
"""


def mac_bundle(exe: str = sys.executable) -> Path | None:
    """Çalışan programın .app paketi (…/GTA6 Altyazı.app/Contents/MacOS/GTA6Altyazi → …/GTA6 Altyazı.app)."""
    p = Path(exe).resolve()
    for parent in p.parents:
        if parent.suffix == ".app":
            return parent
    return None


def mac_update_script(dmg: Path, bundle: Path, pid: int, log_file: Path) -> str:
    """macOS: program kapanınca .dmg'yi bağla, yeni .app'i eskisinin yerine koy, yeni sürümü aç. Başarısızsa eski
    program açılır; nedeni günlükte (Windows'taki update_script'in karşılığı)."""
    import shlex
    q = shlex.quote
    trace, result = q(str(log_file.with_suffix(".adim"))), q(str(log_file.with_suffix(".sonuc")))
    return f"""#!/bin/bash
adim() {{ echo "$(date +%H:%M:%S) $1" >> {trace}; }}
bitir() {{ echo "$1" > {result}; adim "bitti, kod $1"; open {q(str(bundle))}; exit 0; }}
adim basladi
for i in $(seq 1 90); do kill -0 {int(pid)} 2>/dev/null || break; sleep 0.5; done
kill -9 {int(pid)} 2>/dev/null
adim 'program kapandi'
MNT=$(mktemp -d /tmp/gta6altyazi.XXXXXX)
hdiutil attach -nobrowse -quiet -noautoopen -mountpoint "$MNT" {q(str(dmg))} >> {q(str(log_file))} 2>&1 || bitir 2
SRC=$(ls -d "$MNT"/*.app 2>/dev/null | head -1)
[ -n "$SRC" ] || {{ hdiutil detach -quiet "$MNT"; bitir 3; }}
NEW={q(str(bundle) + ".yeni")}
rm -rf "$NEW"
ditto "$SRC" "$NEW" >> {q(str(log_file))} 2>&1 || {{ hdiutil detach -quiet "$MNT"; bitir 4; }}
hdiutil detach -quiet "$MNT"
rm -rf {q(str(bundle))} && mv "$NEW" {q(str(bundle))} || bitir 5
xattr -dr com.apple.quarantine {q(str(bundle))} 2>/dev/null
bitir 0
"""


def run_setup(setup: Path, version: str = "") -> None:
    """Programdan bağımsız bir betik, program kapanınca kurulumu yapar (Windows: update_script, macOS:
    mac_update_script)."""
    if sys.platform == "darwin":
        _run_mac_update(setup, version)
        return
    if sys.platform != "win32":
        raise RuntimeError("Güncelleme yalnız Windows'ta ve macOS'ta kurulabilir.")
    import os

    log_file = paths.data("guncelleme.log")
    for f in (log_file, log_file.with_suffix(".sonuc"), log_file.with_suffix(".adim")):
        f.unlink(missing_ok=True)
    paths.data("guncelleme.json").write_text(json.dumps({"hedef": version, "eski": __version__}), encoding="utf-8")
    launch_script(update_script(setup, sys.executable, os.getpid(), log_file))


def _run_mac_update(dmg: Path, version: str) -> None:
    import os

    bundle = mac_bundle()
    if bundle is None:
        raise RuntimeError("Program bir .app paketinden çalışmıyor; güncellemeyi elle kur.")
    log_file = paths.data("guncelleme.log")
    for f in (log_file, log_file.with_suffix(".sonuc"), log_file.with_suffix(".adim")):
        f.unlink(missing_ok=True)
    paths.data("guncelleme.json").write_text(json.dumps({"hedef": version, "eski": __version__}), encoding="utf-8")
    script = paths.data("guncelle.sh")
    script.write_text(mac_update_script(dmg, bundle, os.getpid(), log_file), encoding="utf-8")
    script.chmod(0o755)
    subprocess.Popen(["/bin/bash", str(script)], start_new_session=True, close_fds=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def launch_script(script: str) -> subprocess.Popen:
    """Betiği programdan bağımsız, gizli konsollu PowerShell'de başlat (program kapanınca da sürer).

    DETACHED_PROCESS kullanılmaz: konsolsuz PowerShell betiği çalıştırmadan çıkabiliyor (uçtan uca denemede görüldü).
    """
    import base64

    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc]
    base = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    try:
        return subprocess.Popen(args, creationflags=base | breakaway, close_fds=True)
    except OSError:      # iş nesnesi ayrılmaya izin vermiyorsa onsuz
        return subprocess.Popen(args, creationflags=base, close_fds=True)


def last_update_problem() -> str | None:
    """Önceki güncelleme denemesi başarısız olduysa (program hâlâ eski sürümdeyse) kullanıcıya gösterilecek metin."""
    marker = paths.data("guncelleme.json")
    if not marker.exists():
        return None
    try:
        info = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
    marker.unlink(missing_ok=True)
    target = info.get("hedef") or ""
    if not target or _ver(__version__) >= _ver(target):
        return None
    code = ""
    try:
        code = paths.data("guncelleme.sonuc").read_text(encoding="utf-8").strip()
    except OSError:
        pass
    log.warning("Güncelleme %s kurulamadı (kurulum çıkış kodu %s); ayrıntı: %s", target, code or "?",
                paths.data("guncelleme.log"))
    return (f"{target} sürümüne güncelleme kurulamadı (kod {code or '?'}). Yeniden 'Güncelle'ye bas; yine olmazsa "
            f"kurulum dosyasını GitHub'daki Releases sayfasından indirip elle kur.")
