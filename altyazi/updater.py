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
        asset = next((a for a in r.get("assets") or [] if a.get("name") == SETUP_NAME), None)
        if not asset:
            continue
        if best is None or _ver(tag) > _ver("v" + best["version"]):
            best = {"version": tag[1:], "url": asset["browser_download_url"], "size": asset.get("size", 0),
                    "notes": r.get("body") or ""}
    return best


def newer_than_current(rel: dict | None, current: str = __version__) -> bool:
    return bool(rel) and _ver("v" + rel["version"]) > _ver("v" + current)


def download_setup(rel: dict, progress=None) -> Path:  # noqa: ANN001
    dest = Path(tempfile.gettempdir()) / f"GTA6Altyazi-Setup-{rel['version']}.exe"
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


def run_setup(setup: Path) -> None:
    """Sessiz kur; kurulum bitince uygulamayı kendisi açar (installer.iss: WizardSilent)."""
    if sys.platform != "win32":
        raise RuntimeError("Güncelleme yalnız Windows'ta kurulabilir.")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                     creationflags=flags, close_fds=True)
