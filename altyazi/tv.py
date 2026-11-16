"""Google/Android TV'ye ağ üzerinden TV uygulamasını kurar ve başlatır (Google'ın resmi adb aracıyla).

İki bağlantı yolu desteklenir:
1. Klasik ağ ADB'si (port 5555): Geliştirici seçenekleri > "USB hata ayıklama" açınca çoğu Android TV bunu açar.
   İlk bağlantıda TV "Hata ayıklamaya izin verilsin mi?" diye sorar.
2. Kablosuz hata ayıklama (Android 11+, yeni Google TV'ler): Geliştirici seçenekleri > "Kablosuz hata ayıklama" >
   "Eşleştirme koduyla cihaz eşleştir". Bir kere `tv eslestir IP:PORT KOD` ile eşleştirilir; sonra adres her
   açılışta ağdan (mDNS) kendiliğinden bulunur.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

log = logging.getLogger(__name__)

PACKAGE = "com.gta6altyazi.tv"
ADB_PORT = 5555
ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "tv-android" / "release" / "gta6-altyazi-tv.apk"


class TvError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- ağ
def local_ip(towards: str = "8.8.8.8") -> str:
    """Bu bilgisayarın ev ağındaki adresi (TV'nin bize bağlanacağı adres)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((towards, 9))
        return s.getsockname()[0]
    finally:
        s.close()


def port_open(host: str, port: int = ADB_PORT, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan(port: int = ADB_PORT) -> list[str]:
    """Ev ağında (/24) klasik ADB'si açık cihazları bul."""
    net = ipaddress.ip_network(local_ip() + "/24", strict=False)
    hosts = [str(h) for h in net.hosts()]
    with ThreadPoolExecutor(64) as ex:
        return [h for h, ok in zip(hosts, ex.map(lambda h: port_open(h, port, 0.6), hosts)) if ok]


def apk_version(path: Path = APK) -> int | None:
    try:
        return int(path.with_suffix(".version").read_text().strip())
    except (OSError, ValueError):
        return None


# ----------------------------------------------------------------------------- adb
def find_adb() -> str:
    env = os.environ.get("ALTYAZI_ADB")
    if env:
        return env
    exe = "adb.exe" if sys.platform == "win32" else "adb"
    bundled = ROOT / "tools" / "platform-tools" / exe
    if bundled.exists():
        return str(bundled)
    found = shutil.which("adb")
    if found:
        return found
    raise TvError("adb bulunamadı. kur.bat'ı tekrar çalıştır (platform-tools'u indirir).")


class Adb:
    def __init__(self, adb: str | None = None):
        self.adb = adb or find_adb()

    def run(self, *args: str, timeout: float = 30.0, serial: str | None = None) -> str:
        cmd = [self.adb] + (["-s", serial] if serial else []) + list(args)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=timeout, creationflags=flags)
        except subprocess.TimeoutExpired as e:
            raise TvError(f"adb zaman aşımı: {' '.join(args)}") from e
        return (p.stdout + p.stderr).strip()

    def devices(self) -> dict[str, str]:
        out = self.run("devices")
        res = {}
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                res[parts[0]] = parts[1]
        return res

    def mdns_connect_address(self, host: str) -> str | None:
        """Eşleştirilmiş (kablosuz hata ayıklama) TV'nin o anki bağlantı adresini ağdan bul."""
        out = self.run("mdns", "services", timeout=10)
        for line in out.splitlines():
            if "_adb-tls-connect" in line:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+):(\d+)", line)
                if m and m.group(1) == host:
                    return f"{m.group(1)}:{m.group(2)}"
        return None

    def pair(self, host_port: str, code: str) -> str:
        out = self.run("pair", host_port, code, timeout=30)
        if "Successfully paired" not in out:
            raise TvError(f"Eşleştirme başarısız: {out}")
        return out


class AndroidTv:
    def __init__(self, host: str, adb: Adb | None = None):
        self.host = host
        self.adb = adb or Adb()
        self.serial: str | None = None

    def connect(self, on_prompt=None, approve_timeout: float = 60.0) -> str:  # noqa: ANN001
        """Bağlan; ilk seferde TV'deki onayı bekle. Bağlanılan seri adını döndürür."""
        candidates = []
        if port_open(self.host, ADB_PORT, 1.5):
            candidates.append(f"{self.host}:{ADB_PORT}")
        mdns = self.adb.mdns_connect_address(self.host)
        if mdns:
            candidates.append(mdns)
        if not candidates:
            raise TvError(
                f"{self.host} adresindeki TV'ye ulaşılamıyor. TV açık mı? Geliştirici seçeneklerinde "
                "'USB hata ayıklama' açık mı? Yeni Google TV'lerde 'Kablosuz hata ayıklama'yı açıp "
                "'tv eslestir' komutunu kullan.")
        prompted = False
        for serial in candidates:
            out = self.adb.run("connect", serial, timeout=15)
            if "connected" not in out and "already" not in out:
                log.debug("adb connect %s: %s", serial, out)
                continue
            deadline = time.time() + approve_timeout
            while time.time() < deadline:
                state = self.adb.devices().get(serial)
                if state == "device":
                    self.serial = serial
                    return serial
                if state == "unauthorized" and not prompted:
                    prompted = True
                    if on_prompt:
                        on_prompt()
                time.sleep(1)
            if prompted:
                raise TvError("TV'de 'Hata ayıklamaya izin verilsin mi?' sorusu onaylanmadı.")
        raise TvError(f"TV'ye bağlanılamadı ({', '.join(candidates)}).")

    def sh(self, cmd: str, timeout: float = 30.0) -> str:
        return self.adb.run("shell", cmd, timeout=timeout, serial=self.serial)

    def android_version(self) -> str:
        return self.sh("getprop ro.build.version.release")

    def installed_version(self) -> int | None:
        m = re.search(r"versionCode=(\d+)", self.sh(f"dumpsys package {PACKAGE}"))
        return int(m.group(1)) if m else None

    def install(self, apk: Path = APK) -> None:
        if not apk.exists():
            raise TvError(f"{apk} yok. Depoyu güncelle (git pull).")
        out = self.adb.run("install", "-r", str(apk), timeout=180, serial=self.serial)
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out or "signatures do not match" in out:
            self.adb.run("uninstall", PACKAGE, timeout=60, serial=self.serial)
            out = self.adb.run("install", str(apk), timeout=180, serial=self.serial)
        if "Success" not in out:
            raise TvError(f"TV'ye kurulamadı: {out}")

    def grant_overlay(self) -> None:
        out = self.sh(f"appops set {PACKAGE} SYSTEM_ALERT_WINDOW allow")
        if out:  # bazı sürümlerde izin olarak verilir
            self.sh(f"pm grant {PACKAGE} android.permission.SYSTEM_ALERT_WINDOW")
        state = self.sh(f"appops get {PACKAGE} SYSTEM_ALERT_WINDOW")
        if "allow" not in state:  # "default" + verilmiş izin de olabilir; TV uygulaması eksikse ekranda söyler
            log.warning("TV üstüne çizme izni doğrulanamadı: %s", state)
        self.sh(f"pm grant {PACKAGE} android.permission.POST_NOTIFICATIONS")
        self.sh(f"cmd deviceidle whitelist +{PACKAGE}")   # arka planda öldürülmesin

    def launch(self, server: str) -> None:
        self.sh(f"am start -n {PACKAGE}/.MainActivity --es host {server}")


def setup(host: str, server_port: int, force_install: bool = False, on_prompt=None, adb: Adb | None = None) -> str:  # noqa: ANN001
    """Bağlan, gerekirse kur/güncelle, izni ver ve başlat. TV'nin bağlanacağı adresi döndürür."""
    tv = AndroidTv(host, adb)
    tv.connect(on_prompt)
    log.info("TV bağlandı: %s (Android %s)", tv.serial, tv.android_version())
    have, want = tv.installed_version(), apk_version()
    if force_install or have is None or (want is not None and have < want):
        log.info("TV uygulaması kuruluyor (TV'deki: %s, yeni: %s)...", have, want)
        tv.install()
    tv.grant_overlay()
    server = f"{local_ip(host)}:{server_port}"
    tv.launch(server)
    return server


def setup_in_background(host: str, server_port: int) -> None:
    """Program açılışında TV'yi arka planda hazırla (TV kapalıysa birkaç kez dener, sonra vazgeçer)."""

    def run() -> None:
        for attempt in range(4):
            try:
                server = setup(host, server_port)
                log.info("TV hazır: %s → bu bilgisayar %s", host, server)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("TV'ye bağlanılamadı (%d/4): %s", attempt + 1, e)
            time.sleep(10 * (attempt + 1))

    threading.Thread(target=run, daemon=True, name="tv").start()
