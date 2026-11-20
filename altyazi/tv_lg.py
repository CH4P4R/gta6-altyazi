"""LG (webOS) TV'ye TV uygulamasını kurar ve başlatır.

TV'de bir kez: LG Content Store'dan ücretsiz "Developer Mode" uygulamasını kur, LG hesabınla gir,
"Dev Mode Status" ve "Key Server"ı aç, TV'yi yeniden başlat. Developer Mode ekranında TV'nin IP'si ve
6 karakterli bir parola (passphrase) görünür.

Kasa: anahtarı TV'nin Key Server'ından (http://IP:9991/webos_rsa) alır, parolayla açar, SSH (9922, kullanıcı
prisoner) ile bağlanıp .ipk'yı yükler ve LG'nin kurulum servisiyle kurar.

Geliştirici modu en çok 1000 saat açık kalır; süre dolunca LG uygulamayı siler. Kasa her bağlanışta süreyi baştan
başlatır (LG'nin ResetDevModeSession servisi).

Kurulum ayrıntıları (abonelik çıkışını açık tutmak, details.state, kurulumdan sonra sürüm doğrulama, büyük harfli
parola) ve geliştirici modu yenileme CouchSubs'tan (https://github.com/yorulmazsinan/couchsubs, AGPL-3.0, Sinan
Yorulmaz) alınmıştır.
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

APP_ID = "com.gta6altyazi.tv"
SSH_PORT = 9922
KEY_PORT = 9991
REMOTE_DIR = "/media/developer/temp"
DEVMODE_TOKEN = "/var/luna/preferences/devmode_enabled"
DEVMODE_API = "https://developer.lge.com/secure/"
WRONG_PASS = "Anahtar açılamadı: Developer Mode ekranındaki parolayı (Passphrase) doğru yazdığından emin ol."
LOST = "LG TV yanıt vermedi ya da bağlantı koptu. TV açık mı, aynı modemde mi? Yeniden Bağlan'a bas."
# Eski webOS'lar yalnız ssh-rsa (SHA-1) imzasını bilir ve server-sig-algs söylemez (CouchSubs JschShell.kt gibi)
LEGACY_RSA = {"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]}


class LgError(RuntimeError):
    pass


def _open(url: str, timeout: float):  # noqa: ANN202
    """TV'ye giden istekler Windows'un sistem proxy'sinden (VPN/kurumsal) geçmesin."""
    if url.startswith("http://") and not url.startswith("http://localhost"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=timeout)
    return urllib.request.urlopen(url, timeout=timeout)  # noqa: S310


def ipk_path() -> Path | None:
    rel = paths.resource("tv-web/release")
    found = sorted(rel.glob(f"{APP_ID}_*_all.ipk")) if rel.exists() else []
    return found[-1] if found else None


def ipk_version(p: Path) -> str:
    return p.name[len(APP_ID) + 1:].rsplit("_", 1)[0]


def key_file() -> Path:
    return paths.data("lg_webos_rsa")


def fetch_key(host: str) -> bytes:
    """Developer Mode uygulamasının Key Server'ından şifreli SSH anahtarını al."""
    try:
        with _open(f"http://{host}:{KEY_PORT}/webos_rsa", timeout=6) as r:
            data = r.read()
    except OSError as e:
        raise LgError("TV'den anahtar alınamadı. Developer Mode uygulamasında 'Key Server' açık mı, "
                      f"IP doğru mu? ({e})") from e
    if b"PRIVATE KEY" not in data:
        raise LgError("TV'nin verdiği anahtar beklenen biçimde değil.")
    key_file().write_bytes(data)
    return data


def load_key(passphrase: str, data: bytes | None = None):  # noqa: ANN201
    import paramiko

    data = data if data is not None else key_file().read_bytes()
    pw = passphrase.strip()
    # TV parolayı büyük harfle gösterir; küçük yazılmışsa büyük harfle de dene
    for candidate in dict.fromkeys([pw, pw.upper()]):
        try:
            return paramiko.RSAKey.from_private_key(io.StringIO(data.decode()), password=candidate or None)
        except paramiko.SSHException:
            pass
        try:   # PKCS#8 ("BEGIN ENCRYPTED PRIVATE KEY") biçimi: paramiko okuyamaz, cryptography ile aç
            from cryptography.hazmat.primitives import serialization
            key = serialization.load_pem_private_key(data, password=candidate.encode() if candidate else None)
            return paramiko.RSAKey(key=key)
        except Exception:  # noqa: BLE001
            continue
    raise LgError(WRONG_PASS)


class LgTv:
    def __init__(self, host: str, passphrase: str):
        self.host = host
        self.passphrase = passphrase
        self.ssh = None

    def connect(self) -> None:
        import paramiko

        data = key_file().read_bytes() if key_file().exists() else fetch_key(self.host)
        try:
            pkey = load_key(self.passphrase, data)
        except LgError:
            pkey = load_key(self.passphrase, fetch_key(self.host))   # TV anahtarı yenilemiş olabilir
        last: Exception | None = None
        for disabled in (None, LEGACY_RSA):
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                c.connect(self.host, port=SSH_PORT, username="prisoner", pkey=pkey, timeout=8, banner_timeout=8,
                          auth_timeout=8, look_for_keys=False, allow_agent=False, disabled_algorithms=disabled)
                self.ssh = c
                return
            except paramiko.AuthenticationException as e:
                last = e                       # eski TV: bir de yalnız ssh-rsa ile dene
                c.close()
            except Exception as e:  # noqa: BLE001
                c.close()
                log.warning("LG SSH bağlantısı kurulamadı: %s", e)
                raise LgError(f"LG TV'ye bağlanılamadı (SSH {SSH_PORT}). TV'de Developer Mode uygulamasında 'Dev Mode "
                              "Status' açık mı, TV bilgisayarla aynı modemde mi, IP doğru mu?") from e
        log.warning("LG anahtarı reddedildi: %s", last)
        key_file().unlink(missing_ok=True)      # bir sonraki denemede TV'den yeni anahtar alınsın
        raise LgError("TV anahtarı kabul etmedi. Developer Mode'u yeniden açtıysan ekrandaki yeni parolayı yaz, "
                      "'Key Server'ın açık olduğundan emin ol ve yeniden Bağlan'a bas.") from last

    def run(self, cmd: str, timeout: float = 60) -> str:
        try:
            _stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)
            return (stdout.read() + stderr.read()).decode(errors="replace")
        except Exception as e:  # noqa: BLE001  (socket.timeout, SSHException, OSError)
            log.warning("LG komutu başarısız (%s): %r", cmd[:60], e)
            raise LgError(LOST) from e

    def upload(self, ipk: Path, remote: str) -> None:
        """SFTP'siz yükleme (bazı webOS'larda sftp-server yok): cat > dosya. CouchSubs'ın üç istemcisi de böyle yapar."""
        data = ipk.read_bytes()
        try:
            ch = self.ssh.get_transport().open_session()
            ch.settimeout(60)
            ch.exec_command(f"cat > '{remote}'")
            ch.sendall(data)
            ch.shutdown_write()
            rc = ch.recv_exit_status()
            ch.close()
        except Exception as e:  # noqa: BLE001
            log.warning("LG paket yüklenemedi: %r", e)
            raise LgError(LOST) from e
        if rc != 0:
            raise LgError("Paket TV'ye yazılamadı (TV'de yer kalmamış olabilir).")
        size = self.run(f"wc -c < '{remote}'").strip()
        if size.isdigit() and int(size) != len(data):
            raise LgError(f"Paket TV'ye eksik yüklendi ({size}/{len(data)} bayt). Yeniden dene.")

    def install(self, ipk: Path, wait: int = 120) -> None:
        self.run(f"mkdir -p {REMOTE_DIR}; rm -f {REMOTE_DIR}/*.ipk")
        remote = f"{REMOTE_DIR}/{ipk.name}"
        self.upload(ipk, remote)
        # CouchSubs DevModeInstaller.InstallCommand: tek komutta başlat, bekle, sonucu bas, luna-send'i PID ile kapat.
        # sleep'in çıkışları SSH kanalına bağlı değil (2>/dev/null); oturum onu beklemez.
        out = self.run(install_command(remote, wait), timeout=wait + 40)
        result = install_verdict(out) or "cevap yok"
        if result not in ("installed", "cevap yok"):
            self.run(f"rm -f '{remote}'", timeout=10)
        # "installed" dese de TV'deki sürüm gerçekten yenilenene kadar bekle (cevap belirsizse daha uzun)
        want = ipk_version(ipk)
        wait = 30 if result == "installed" else 60
        end = time.time() + wait
        while time.time() < end:
            if self.installed_version() == want:
                return
            if result not in ("installed", "cevap yok"):
                break
            time.sleep(2)
        if "space" in result.lower() or "storage" in result.lower():
            raise LgError("LG TV'ye kurulamadı: TV'de yer kalmamış. Kullanmadığın bir uygulamayı kaldırıp yeniden dene.")
        raise LgError(f"LG TV'ye kurulamadı ({result}). TV'yi kapatıp açıp yeniden Bağlan'a bas.")

    def installed_version(self) -> str | None:
        out = self.run(f"cat /media/developer/apps/usr/palm/applications/{APP_ID}/appinfo.json 2>/dev/null", timeout=15)
        try:
            return json.loads(out).get("version")
        except ValueError:
            return None

    def renew_devmode(self) -> str | None:
        """Geliştirici modu süresini baştan başlat; kalan süreyi ("999:59:59") döndür."""
        token = self.run(f"cat {DEVMODE_TOKEN} 2>/dev/null", timeout=10).strip()
        if not token or " " in token:
            return None
        stamp = paths.data(f"lg_devmode_{self.host.replace(':', '_')}.txt")
        try:      # LG'ye en çok 20 saatte bir sor (CouchSubs gibi)
            if time.time() - float(stamp.read_text()) < 20 * 3600:
                return None
        except (OSError, ValueError):
            pass
        q = urllib.parse.quote(token, safe="")
        try:
            with urllib.request.urlopen(f"{DEVMODE_API}ResetDevModeSession.dev?sessionToken={q}", timeout=10) as r:
                ok = b"success" in r.read().lower()
            with urllib.request.urlopen(f"{DEVMODE_API}CheckDevModeSession.dev?sessionToken={q}", timeout=10) as r:
                left = r.read().decode(errors="replace")
        except OSError as e:
            log.warning("LG geliştirici modu süresi yenilenemedi: %s", e)
            return None
        if ok:
            try:
                stamp.write_text(str(time.time()))
            except OSError:
                pass
        m = re.search(r"\d{1,4}:\d{2}:\d{2}", left)
        log.info("LG geliştirici modu %s; kalan süre %s", "yenilendi" if ok else "yenilenemedi", m.group(0) if m else "?")
        return m.group(0) if m else None

    def launch(self, server: str) -> None:
        params = json.dumps({"id": APP_ID, "params": {"server": f"http://{server}"}})
        out = self.run(f"/usr/bin/luna-send-pub -n 1 'luna://com.webos.applicationManager/launch' '{params}'", timeout=20)
        if '"returnValue":false' in out.replace(" ", ""):
            raise LgError(f"TV uygulaması başlatılamadı: {out.strip()[:300]}")

    def close(self) -> None:
        if self.ssh:
            self.ssh.close()


def install_command(remote: str, wait: int) -> str:
    """CouchSubs DevModeInstaller.InstallCommand'ın birebir karşılığı."""
    log_file = f"{REMOTE_DIR}/kurulum.log"
    params = json.dumps({"id": "com.ares.defaultName", "ipkUrl": remote, "subscribe": True}, separators=(",", ":"))
    return "; ".join([
        f"rm -f {log_file}",
        f"sleep {wait + 30} </dev/null 2>/dev/null | /usr/bin/luna-send-pub -i "
        f"'luna://com.webos.appInstallService/dev/install' '{params}' >{log_file} 2>&1 & L=$!",
        "i=0",
        f"while [ $i -lt {wait} ]; do grep -q -i -e '\"state\" *: *\"installed' -e 'failed' "
        f"-e '\"returnValue\" *: *false' -e '\"state\" *: *\"success' {log_file} 2>/dev/null && break; "
        "kill -0 $L 2>/dev/null || break; sleep 1; i=$((i+1)); done",
        f"cat {log_file}",
        "kill $L 2>/dev/null",
        f"rm -f {log_file}",
    ])


def install_verdict(text: str) -> str | None:
    """Kurulum servisinin çıktısından sonuç: 'installed', hata metni ya da (henüz belli değilse) None."""
    low = text.lower().replace(" ", "")
    if '"state":"installed' in low or '"state":"success' in low:
        return "installed"
    if '"returnvalue":false' in low or "failed" in low:
        m = re.search(r'"errorText"\s*:\s*"([^"]+)"', text)
        return (m.group(1) if m else text.strip()[-300:]) or "hata"
    return None


def _newer(a: str, b: str) -> bool:
    def parts(v: str) -> tuple:
        return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v))
    return parts(a) > parts(b)


def setup(host: str, passphrase: str, server_port: int, force_install: bool = False) -> str:
    from .tv import local_ip

    ipk = ipk_path()
    if ipk is None:
        raise LgError("LG TV paketi (.ipk) bu sürümde yok.")
    tv = LgTv(host, passphrase)
    tv.connect()
    try:
        tv.renew_devmode()
        have = tv.installed_version()
        if force_install or have is None or _newer(ipk_version(ipk), have):
            log.info("LG TV uygulaması kuruluyor (%s)...", ipk.name)
            tv.install(ipk)
            time.sleep(2)
        server = f"{local_ip(host)}:{server_port}"
        tv.launch(server)
        return server
    finally:
        tv.close()
