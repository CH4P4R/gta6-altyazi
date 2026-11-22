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
import json
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
from .paths import RESOURCES as ROOT  # noqa: E402

APK = ROOT / "tv-android" / "release" / "gta6-altyazi-tv.apk"


class TvError(RuntimeError):
    pass


class LaunchError(TvError):
    """TV uygulaması kurulu görünüyor ama açılmadı (am start hata verdi)."""


# ----------------------------------------------------------------------------- ağ

# TV uygulamasının (tv-web) bu sürümle gelen sürümü; tv-web/src/app.js APP_VERSION ile aynı tutulur (test denetler)
TV_APP_VERSION = "0.6.0"

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


def local_ips() -> list[str]:
    """Bu bilgisayarın özel ağ (ev ağı) IPv4 adresleri; VPN/Hyper-V gibi ek bağdaştırıcılar varsa hepsi."""
    found: list[str] = []
    try:
        found.append(local_ip())
    except OSError:
        pass
    try:
        for *_, addr in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(addr[0])
    except OSError:
        pass
    out = []
    for ip in found:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.is_private and not a.is_loopback and not a.is_link_local and ip not in out:
            out.append(ip)
    return out


def scan(port: int = ADB_PORT) -> list[str]:
    """Ev ağında (bilgisayarın her özel ağının /24'ü) portu açık cihazları bul. Hata olursa boş liste."""
    hosts: list[str] = []
    mine = set(local_ips())
    for ip in local_ips()[:4]:
        for h in ipaddress.ip_network(ip + "/24", strict=False).hosts():
            if str(h) not in mine and str(h) not in hosts:
                hosts.append(str(h))
    if not hosts:
        return []
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

    def mdns_pairing_address(self, host: str) -> str | None:
        """TV'de 'Eşleştirme koduyla cihaz eşleştir' penceresi açıkken onun adres:port'unu ağdan bul."""
        try:
            out = self.run("mdns", "services", timeout=10)
        except TvError:
            return None
        for line in out.splitlines():
            if "_adb-tls-pairing" in line:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+):(\d+)", line)
                if m and m.group(1) == host:
                    return f"{m.group(1)}:{m.group(2)}"
        return None

    def pair(self, host_port: str, code: str) -> str:
        host_port = host_port.strip().replace(" ", "")
        code = re.sub(r"\D", "", code or "")
        host = host_port.split(":")[0]
        if not host:
            raise TvError("Eşleştirme: TV'nin adresini yaz (ör. 192.168.1.40:37123).")
        if len(code) != 6:
            raise TvError("Eşleştirme kodu 6 haneli olmalı: TV'deki eşleştirme penceresindeki rakamları yaz.")
        # Kablosuz hata ayıklama ana ekranındaki port eşleştirme portu değildir; pencere açıksa doğrusunu bul
        found = self.mdns_pairing_address(host)
        targets = [found] if found else []
        if ":" in host_port and host_port not in targets:
            targets.append(host_port)
        if not targets:
            raise TvError(PAIR_HELP["port"])
        out = ""
        restarted = False
        for target in targets:
            for _attempt in range(2):
                out = self.run("pair", target, code, timeout=30)
                if "Successfully paired" in out:
                    return out
                log.info("adb pair %s: %s", target, out)
                # Başka bir programın (emülatör, telefon aracı) eski adb sunucusu araya girince de "protocol fault"
                # çıkar: adb sunucusunu bir kez baştan başlatıp aynı adresi yeniden dene
                if "protocol fault" in out.lower() and not restarted:
                    restarted = True
                    self.run("kill-server", timeout=10)
                    self.run("start-server", timeout=20)
                    continue
                break
        raise TvError(pair_error(out))


PAIR_HELP = {
    "port": "Eşleştirme olmadı: yazılan port eşleştirme portu değil ya da TV'deki eşleştirme penceresi kapandı. TV'de "
            "Kablosuz hata ayıklama › 'Eşleştirme koduyla cihaz eşleştir'e bas; açılan küçük penceredeki adres:port'u "
            "(ana ekrandaki değil, port farklıdır) ve 6 haneli kodu yaz. Pencere açıkken Eşleştir'e bas.",
    "code": "Eşleştirme kodu yanlış ya da süresi doldu. TV'de pencereyi kapatıp 'Eşleştirme koduyla cihaz eşleştir'e "
            "yeniden bas ve yeni kodu yaz.",
    "unreachable": "TV'ye ulaşılamadı. TV ile bilgisayar aynı modemde mi? Adresi doğru yazdın mı? Eşleştirme penceresi "
                   "açık mı?",
}


def pair_error(out: str) -> str:
    """adb pair çıktısını yapılacak işi söyleyen Türkçe mesaja çevir."""
    low = (out or "").lower()
    if "wrong password" in low or "wrong code" in low:
        msg = PAIR_HELP["code"]
    elif "protocol fault" in low or "couldn't read status" in low or "connection reset" in low:
        msg = PAIR_HELP["port"]
    elif "unable to connect" in low or "failed to connect" in low or "cannot connect" in low or "timed out" in low \
            or "no route" in low or "refused" in low:
        msg = PAIR_HELP["unreachable"]
    else:
        msg = "Eşleştirme olmadı. " + PAIR_HELP["port"].split(": ", 1)[1]
    return f"{msg} (adb: {out.strip()[:160]})" if out.strip() else msg


UNREACHABLE_HELP = (
    "{host} adresindeki TV'ye ulaşılamıyor. TV açık mı, bilgisayarla aynı modemde mi? TV'de Ayarlar › Sistem › "
    "Geliştirici seçenekleri › 'USB hata ayıklama'yı aç ve yeniden Bağlan'a bas. USB hata ayıklama açıkken de "
    "bulunamıyorsa (bazı yeni Google TV'ler buna izin vermez): Gelişmiş › kablosuz eşleştir, sonra adres kutusuna "
    "Kablosuz hata ayıklama ekranındaki IP:PORT'u yaz.")

INSTALL_ERRORS = {
    "INSTALL_FAILED_VERIFICATION_FAILURE": "TV, Play Protect doğrulaması yüzünden kurmadı. TV'de çıkan uyarıda "
                                           "'Yine de yükle'yi seç ve yeniden Bağlan'a bas.",
    "INSTALL_FAILED_USER_RESTRICTED": "TV dışarıdan uygulama kurmayı engelliyor. TV'de Ayarlar › Uygulamalar › "
                                      "Güvenlik › Bilinmeyen kaynaklar'ı aç ve yeniden dene.",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "TV'de yer kalmamış. TV'de kullanmadığın bir uygulamayı kaldırıp yeniden dene.",
    "INSTALL_PARSE_FAILED": "TV uygulama dosyasını okuyamadı. Programı yeniden kurup tekrar dene.",
    "INSTALL_FAILED_OLDER_SDK": "Bu TV'nin Android sürümü çok eski (Android 7 ve üstü gerekir).",
}


def install_error(out: str) -> str:
    for code, msg in INSTALL_ERRORS.items():
        if code in out:
            return f"TV'ye kurulamadı: {msg}"
    return f"TV'ye kurulamadı ({out.strip()[:160]}). TV'yi yeniden başlatıp tekrar dene."


class AndroidTv:
    def __init__(self, host: str, adb: Adb | None = None, port: int | None = None):
        self.host = host
        self.port = port
        self.adb = adb or Adb()
        self.serial: str | None = None

    def connect(self, on_prompt=None, approve_timeout: float = 60.0) -> str:  # noqa: ANN001
        """Bağlan; ilk seferde TV'deki onayı bekle. Bağlanılan seri adını döndürür."""
        candidates = []
        if self.port and self.port != ADB_PORT:
            candidates.append(f"{self.host}:{self.port}")          # Kablosuz hata ayıklama ekranındaki IP:PORT
        if port_open(self.host, ADB_PORT, 1.5):
            candidates.append(f"{self.host}:{ADB_PORT}")
        mdns = None
        for _ in range(5):                                          # eşleştirmeden hemen sonra adres geç görünür
            mdns = self.adb.mdns_connect_address(self.host)
            if mdns or candidates:
                break
            time.sleep(2)
        if mdns and mdns not in candidates:
            candidates.append(mdns)
        if not candidates:
            raise TvError(UNREACHABLE_HELP.format(host=self.host))
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
        out = self.sh(f"dumpsys package {PACKAGE}")
        m = re.search(r"versionCode=(\d+)", out)
        if not m:
            return None
        users = re.findall(r"^\s*User \d+:.*?\binstalled=(true|false)\b", out, re.MULTILINE)
        if users and all(u == "false" for u in users):
            # Kaldırılmış ama kaydı kalmış (ya da Google TV'nin arşivlediği) kopya: temizle, yeniden kurulsun
            log.info("TV'de uygulamanın artık kaydı var (kurulu değil); temizleniyor")
            self.sh(f"pm uninstall {PACKAGE}", timeout=60)
            return None
        return int(m.group(1))

    def install(self, apk: Path = APK) -> None:
        if not apk.exists():
            raise TvError(f"{apk} yok. Depoyu güncelle (git pull).")
        out = self.adb.run("install", "-r", str(apk), timeout=180, serial=self.serial)
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out or "signatures do not match" in out \
                or "INSTALL_FAILED_VERSION_DOWNGRADE" in out:
            self.adb.run("uninstall", PACKAGE, timeout=60, serial=self.serial)
            out = self.adb.run("install", str(apk), timeout=180, serial=self.serial)
        if "Success" not in out:
            raise TvError(install_error(out))

    def grant_overlay(self) -> bool:
        """Üstüne çizme iznini ver. İzin doğrulanabildiyse True."""
        out = self.sh(f"appops set {PACKAGE} SYSTEM_ALERT_WINDOW allow")
        if out:  # bazı sürümlerde izin olarak verilir
            self.sh(f"pm grant {PACKAGE} android.permission.SYSTEM_ALERT_WINDOW")
        state = self.sh(f"appops get {PACKAGE} SYSTEM_ALERT_WINDOW")
        ok = re.search(r"SYSTEM_ALERT_WINDOW: allow\b", state) is not None
        if not ok:
            granted = self.sh(f"dumpsys package {PACKAGE} | grep SYSTEM_ALERT_WINDOW")
            ok = "granted=true" in granted
        if not ok:
            log.warning("TV üstüne çizme iznini vermedi (%s); yedek HDMI modu kullanılacak", state)
        self.sh(f"pm grant {PACKAGE} android.permission.POST_NOTIFICATIONS")
        self.sh(f"cmd deviceidle whitelist +{PACKAGE}")   # arka planda öldürülmesin
        return ok

    def launch(self, server: str, mode: str = "otomatik") -> None:
        """TV uygulamasını bu bilgisayarın adresiyle aç.

        TV uygulaması (CouchSubs'tan) varsayılan olarak HDMI'yı kendi içinde gösterir; görüntü gelmezse ya da TV
        (TCL gibi) HDMI'yı öne alıp uygulamayı arka plana iterse kendiliğinden katman moduna geçer.
        """
        params = json.dumps({"server": f"http://{server}"}, separators=(",", ":"))
        display = "overlay" if mode == "katman" else "inApp"
        # host/mod: eski (0.3.x) TV uygulaması için; yeni APK derlenene kadar o da çalışsın
        old = "katman" if mode in ("katman", "otomatik") else "hdmi"
        self.sh("input keyevent KEYCODE_WAKEUP")       # TV ekran koruyucudaysa uyansın, açılan uygulama görünsün
        out = self.sh(f"am start -n {PACKAGE}/.MainActivity --es params '{params}' --es displayMode {display} "
                      f"--es host {server} --es mod {old}")
        log.info("am start: %s", out.strip()[:200])
        if "Error" in out or "Exception" in out:
            raise LaunchError(out.strip()[:200])


class NativeAndroidTv(AndroidTv):
    """Aynı işler, adb.exe yerine programın kendi ADB istemcisiyle (adb_native; CouchSubs'tan). 5555 açık olmalı."""

    LOST = ("TV yanıt vermedi ya da bağlantı koptu. TV açık mı, bilgisayarla aynı modemde mi? Yeniden Bağlan'a bas.")

    def __init__(self, host: str):
        self.host = host
        self.port = ADB_PORT
        self.serial = f"{host}:{ADB_PORT}"
        self.conn = None

    def connect(self, on_prompt=None, approve_timeout: float = 90.0) -> str:  # noqa: ANN001
        from .adb_native import AdbConnection, AdbError
        try:
            self.conn = AdbConnection.connect(self.host, ADB_PORT, on_prompt=on_prompt, approve_timeout=approve_timeout)
        except AdbError as e:
            if e.kind == "not_approved":
                raise TvError("TV'de 'Hata ayıklamaya izin verilsin mi?' sorusu onaylanmadı. Programda yeniden Bağlan'a "
                              "bas ve TV'de 'Bu bilgisayardan her zaman izin ver'i işaretleyip İzin ver de.") from e
            log.warning("Doğrudan ADB bağlantısı kurulamadı (%s): %s", self.serial, e)
            raise TvError(UNREACHABLE_HELP.format(host=self.host)) from e
        return self.serial

    def sh(self, cmd: str, timeout: float = 30.0) -> str:
        from .adb_native import AdbError
        try:
            return self.conn.shell(cmd, timeout=timeout)
        except AdbError as e:
            log.warning("TV komutu başarısız (%s): %s", cmd[:60], e)
            raise TvError(self.LOST) from e

    def install(self, apk: Path = APK) -> None:
        from .adb_native import AdbError
        if not apk.exists():
            raise TvError(f"{apk} yok. Programı yeniden kur.")
        try:
            out = self.conn.install(apk)
        except AdbError as e:
            log.warning("APK gönderilemedi: %s", e)
            raise TvError(self.LOST) from e
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in out or "signatures do not match" in out \
                or "INSTALL_FAILED_VERSION_DOWNGRADE" in out:
            self.sh(f"pm uninstall {PACKAGE}", timeout=60)
            try:
                out = self.conn.install(apk)
            except AdbError as e:
                raise TvError(self.LOST) from e
        if "Success" not in out:
            raise TvError(install_error(out))

    def close(self) -> None:
        if self.conn:
            self.conn.close()


def _use_native(host: str, adb: Adb | None, port: int | None = None) -> bool:
    """TV 5555'te bekliyorsa programın kendi ADB istemcisi kullanılır (adb.exe yok: sunucu çakışması, eşleştirme yok)."""
    if adb is not None or os.environ.get("ALTYAZI_ADB") or (port and port != ADB_PORT):
        return False
    # Wi-Fi güç tasarrufundaki TV ilk yoklamayı kaçırabilir: birkaç kez dene
    return any(port_open(host, ADB_PORT, 3.0) for _ in range(3))


def setup(host: str, server_port: int, force_install: bool = False, on_prompt=None, adb: Adb | None = None,  # noqa: ANN001
          mode: str = "otomatik", port: int | None = None, progress=None) -> str:  # noqa: ANN001
    """Bağlan, gerekirse kur/güncelle, izni ver ve başlat. TV'nin bağlanacağı adresi döndürür.

    mode: otomatik (uygulama içinde; görüntü gelmezse TV uygulaması kendisi katmana geçer) | katman | hdmi
    port: Kablosuz hata ayıklama ekranındaki bağlantı portu (5555 kapalı TV'ler için)
    """
    if _use_native(host, adb, port):
        tv = NativeAndroidTv(host)
        try:
            return _setup_with(tv, host, server_port, force_install, on_prompt, mode, progress)
        finally:
            tv.close()
    return _setup_with(AndroidTv(host, adb, port), host, server_port, force_install, on_prompt, mode, progress)


def _setup_with(tv: AndroidTv, host: str, server_port: int, force_install: bool, on_prompt,  # noqa: ANN001
                mode: str, progress=None) -> str:  # noqa: ANN001
    say = progress or (lambda _m: None)
    tv.connect(on_prompt)
    log.info("TV bağlandı: %s (Android %s)", tv.serial, tv.android_version())
    have, want = tv.installed_version(), apk_version()
    if force_install or have is None or (want is not None and have < want):
        log.info("TV uygulaması kuruluyor (TV'deki: %s, yeni: %s)...", have, want)
        say("TV uygulaması kuruluyor (1 dk sürebilir). TV'de Play Protect uyarısı çıkarsa 'Yine de yükle'yi seç.")
        tv.install()
    overlay_ok = tv.grant_overlay()
    if not overlay_ok and mode in ("katman", "otomatik"):
        mode = "hdmi"
    server = f"{local_ip(host)}:{server_port}"
    say("TV uygulaması açılıyor...")
    try:
        tv.launch(server, mode)
    except LaunchError as e:
        # Kurulu görünüyor ama açılmadı (bozuk/yarım kalmış kopya): bir kez temiz kurup yeniden dene
        log.warning("TV uygulaması açılamadı (%s); yeniden kuruluyor", e)
        say("TV uygulaması açılamadı, yeniden kuruluyor...")
        tv.sh(f"pm uninstall {PACKAGE}", timeout=60)
        tv.install()
        tv.grant_overlay()
        try:
            tv.launch(server, mode)
        except LaunchError as e2:
            raise TvError(f"TV uygulaması açılamadı: {e2}. TV'yi kapatıp açıp yeniden Bağlan'a bas.") from e2
    log.info("TV uygulaması başlatıldı (%s modu)", mode)
    return server


def setup_in_background(host: str, server_port: int, mode: str = "otomatik") -> None:
    """Program açılışında TV'yi arka planda hazırla (TV kapalıysa birkaç kez dener, sonra vazgeçer)."""

    def run() -> None:
        for attempt in range(4):
            try:
                server = setup(host, server_port, mode=mode)
                log.info("TV hazır: %s → bu bilgisayar %s", host, server)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("TV'ye bağlanılamadı (%d/4): %s", attempt + 1, e)
            time.sleep(10 * (attempt + 1))

    threading.Thread(target=run, daemon=True, name="tv").start()
