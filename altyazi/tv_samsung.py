"""Samsung (Tizen) TV'ye TV uygulamasını Tizen Studio'nun komut satırı araçlarıyla kurar.

Samsung, TV'ye kurulan her uygulamanın o TV'ye özel bir Samsung sertifikasıyla imzalanmasını ister. Bu
sertifika bir kez Tizen Studio'da (Certificate Manager > Samsung) Samsung hesabıyla ve TV'nin DUID'iyle
oluşturulur. Sonrasında bu modül: sdb ile TV'ye bağlanır, uygulamayı o profille imzalar, kurar ve başlatır.

TV'de bir kez: Apps (Uygulamalar) ekranında kumandayla 1-2-3-4-5 yaz, Developer mode'u aç, Host PC IP olarak
bu bilgisayarın IP'sini yaz ve TV'yi güç tuşuna 2 sn basılı tutarak yeniden başlat.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

APP_ID = "GTA6Altyzi.GTA6Altyazi"
SDB_PORT = 26101
CANDIDATES = [r"C:\tizen-studio", r"%USERPROFILE%\tizen-studio", r"D:\tizen-studio", "~/tizen-studio"]


class SamsungError(RuntimeError):
    pass


def find_tizen(configured: str = "") -> tuple[str, str]:
    """(tizen cli, sdb) yolları."""
    roots = ([configured] if configured else []) + CANDIDATES
    for r in roots:
        root = Path(os.path.expanduser(os.path.expandvars(r)))
        for cli in (root / "tools" / "ide" / "bin" / "tizen.bat", root / "tools" / "ide" / "bin" / "tizen"):
            sdb = root / "tools" / ("sdb.exe" if cli.suffix == ".bat" else "sdb")
            if cli.exists() and sdb.exists():
                return str(cli), str(sdb)
    raise SamsungError("Tizen Studio bulunamadı. developer.samsung.com'dan Tizen Studio'yu kur "
                       "(Package Manager'dan 'Samsung Certificate Extension' ile) ya da yerini Ayarlar'dan seç.")


def _run(args: list[str], timeout: float = 180) -> str:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, creationflags=flags)
    except subprocess.TimeoutExpired as e:
        raise SamsungError(f"Zaman aşımı: {' '.join(args[:3])}") from e
    return (p.stdout + p.stderr).strip()


def setup(host: str, profile: str, tizen_root: str = "") -> str:
    cli, sdb = find_tizen(tizen_root)
    serial = f"{host}:{SDB_PORT}"
    out = _run([sdb, "connect", serial], timeout=20)
    if "connected" not in out.lower():
        raise SamsungError("TV'ye bağlanılamadı. TV'de Developer mode açık mı ve 'Host PC IP' bu bilgisayarın IP'si "
                           f"mi? (TV'yi yeniden başlattın mı?) [{out[:200]}]")
    src = paths.resource("tv-web/build/tizen")
    if not (src / "config.xml").exists():
        raise SamsungError("Samsung TV paketi bu sürümde yok.")
    work = Path(tempfile.mkdtemp(prefix="gta6-tizen-"))
    try:
        app = work / "app"
        shutil.copytree(src, app)
        out = _run([cli, "package", "-t", "wgt", "-s", profile, "--", str(app)])
        wgts = list(app.glob("*.wgt"))
        if not wgts:
            hint = (" Sertifika profili bulunamadı: Tizen Studio > Tools > Certificate Manager'da 'Samsung' türünde, "
                    f"TV'nin DUID'iyle '{profile}' adında bir profil oluştur.") if re.search(r"profile|certificate", out, re.I) else ""
            raise SamsungError(f"Uygulama imzalanamadı.{hint} [{out[-300:]}]")
        out = _run([cli, "install", "-n", wgts[0].name, "-s", serial, "--", str(app)])
        if not re.search(r"installed|success|completed", out, re.I):
            raise SamsungError(f"TV'ye kurulamadı. Sertifika bu TV'nin DUID'iyle mi oluşturuldu? [{out[-300:]}]")
        out = _run([cli, "run", "-p", APP_ID, "-s", serial], timeout=60)
        log.info("Samsung TV uygulaması başlatıldı: %s", out[-200:])
    finally:
        shutil.rmtree(work, ignore_errors=True)
    from .tv import local_ip
    return local_ip(host)
