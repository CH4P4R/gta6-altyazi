"""Google/Android TV'ye ağ üzerinden (ADB, port 5555) TV uygulamasını kurar ve başlatır.

TV'de bir kez: Ayarlar > Sistem > Hakkında > "Android TV OS derlemesi"ne 7 kez bas (geliştirici modu),
sonra Ayarlar > Sistem > Geliştirici seçenekleri > "USB hata ayıklama"yı aç. İlk bağlantıda TV
"Hata ayıklamaya izin verilsin mi?" diye sorar: "Bu bilgisayardan her zaman izin ver" + İzin ver.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

log = logging.getLogger(__name__)

PACKAGE = "com.gta6altyazi.tv"
ADB_PORT = 5555
ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "tv-android" / "release" / "gta6-altyazi-tv.apk"
KEY = ROOT / ".adb" / "adbkey"


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
    """Ev ağında (/24) ADB'si açık cihazları bul."""
    net = ipaddress.ip_network(local_ip() + "/24", strict=False)
    hosts = [str(h) for h in net.hosts()]
    with ThreadPoolExecutor(64) as ex:
        found = [h for h, ok in zip(hosts, ex.map(lambda h: port_open(h, port, 0.6), hosts)) if ok]
    return found


def apk_version(path: Path = APK) -> int | None:
    """Depodaki APK'nın versionCode'u (yanına yazılan .version dosyasından)."""
    v = path.with_suffix(".version")
    try:
        return int(v.read_text().strip())
    except (OSError, ValueError):
        return None


class AndroidTv:
    def __init__(self, host: str, port: int = ADB_PORT):
        from adb_shell.adb_device import AdbDeviceTcp

        self.host = host
        self.dev = AdbDeviceTcp(host, port, default_transport_timeout_s=10.0)

    def connect(self, on_prompt=None) -> None:  # noqa: ANN001
        from adb_shell.auth.keygen import keygen
        from adb_shell.auth.sign_pythonrsa import PythonRSASigner

        if not KEY.exists():
            KEY.parent.mkdir(parents=True, exist_ok=True)
            keygen(str(KEY))
        signer = PythonRSASigner(KEY.with_suffix(".pub").read_text(), KEY.read_text())
        if on_prompt:
            on_prompt()
        # İlk seferde TV'de onay beklenir: 60 sn süre tanı
        self.dev.connect(rsa_keys=[signer], auth_timeout_s=60.0)

    def sh(self, cmd: str, timeout: float = 30.0) -> str:
        return (self.dev.shell(cmd, read_timeout_s=timeout, timeout_s=timeout) or "").strip()

    def installed_version(self) -> int | None:
        out = self.sh(f"dumpsys package {PACKAGE} | grep versionCode")
        m = re.search(r"versionCode=(\d+)", out)
        return int(m.group(1)) if m else None

    def install(self, apk: Path = APK) -> None:
        if not apk.exists():
            raise FileNotFoundError(f"{apk} yok. Depoyu güncelle (git pull) ya da GitHub Actions derlemesini bekle.")
        remote = "/data/local/tmp/gta6-altyazi-tv.apk"
        self.dev.push(str(apk), remote, read_timeout_s=60.0)
        out = self.sh(f"pm install -r {remote}", timeout=120)
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out or "signatures do not match" in out:
            self.sh(f"pm uninstall {PACKAGE}")
            out = self.sh(f"pm install {remote}", timeout=120)
        self.sh(f"rm {remote}")
        if "Success" not in out:
            raise RuntimeError(f"TV'ye kurulamadı: {out}")

    def grant_overlay(self) -> None:
        out = self.sh(f"appops set {PACKAGE} SYSTEM_ALERT_WINDOW allow")
        if out:  # bazı sürümlerde izin olarak verilir
            self.sh(f"pm grant {PACKAGE} android.permission.SYSTEM_ALERT_WINDOW")
        # Android 13+: ön plan servisinin bildirimi için (yoksa da çalışır)
        self.sh(f"pm grant {PACKAGE} android.permission.POST_NOTIFICATIONS 2>/dev/null")
        # TV'nin pil/arka plan kısıtlamaları servisi öldürmesin
        self.sh(f"cmd deviceidle whitelist +{PACKAGE} 2>/dev/null")

    def launch(self, server: str) -> None:
        self.sh(f"am start -n {PACKAGE}/.MainActivity --es host {server}")

    def close(self) -> None:
        try:
            self.dev.close()
        except Exception:  # noqa: BLE001
            pass


def setup(host: str, server_port: int, force_install: bool = False, on_prompt=None) -> str:  # noqa: ANN001
    """Bağlan, gerekirse kur/güncelle, izni ver ve başlat. TV'nin bağlanacağı adresi döndürür."""
    tv = AndroidTv(host)
    try:
        tv.connect(on_prompt)
        have, want = tv.installed_version(), apk_version()
        if force_install or have is None or (want is not None and have < want):
            log.info("TV uygulaması kuruluyor (TV'deki: %s, yeni: %s)...", have, want)
            tv.install()
        tv.grant_overlay()
        server = f"{local_ip(host)}:{server_port}"
        tv.launch(server)
        return server
    finally:
        tv.close()


def setup_in_background(host: str, server_port: int) -> None:
    """Uygulama açılışında TV'yi arka planda hazırla (TV kapalıysa sessizce vazgeç)."""
    import threading

    def run() -> None:
        for attempt in range(3):
            if port_open(host, timeout=1.0):
                try:
                    server = setup(host, server_port)
                    log.info("TV hazır: %s → bu bilgisayar %s", host, server)
                    return
                except Exception as e:  # noqa: BLE001
                    log.warning("TV'ye bağlanılamadı: %s", e)
            time.sleep(5 * (attempt + 1))
        log.warning("TV (%s) bulunamadı. TV açık mı, geliştirici modunda USB hata ayıklama açık mı?", host)

    threading.Thread(target=run, daemon=True, name="tv").start()
