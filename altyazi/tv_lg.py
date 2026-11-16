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


class LgError(RuntimeError):
    pass


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
        with urllib.request.urlopen(f"http://{host}:{KEY_PORT}/webos_rsa", timeout=6) as r:
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
            continue
    raise LgError("Anahtar açılamadı: Developer Mode ekranındaki parolayı doğru yazdığından emin ol.")


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
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(self.host, port=SSH_PORT, username="prisoner", pkey=pkey, timeout=8, banner_timeout=8,
                      auth_timeout=8, look_for_keys=False, allow_agent=False)
        except Exception as e:  # noqa: BLE001
            raise LgError(f"TV'ye bağlanılamadı (SSH {SSH_PORT}). Developer Mode açık ve TV aynı ağda mı? ({e})") from e
        self.ssh = c

    def run(self, cmd: str, timeout: float = 60) -> str:
        _stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)
        return (stdout.read() + stderr.read()).decode(errors="replace")

    def install(self, ipk: Path) -> None:
        self.run(f"mkdir -p {REMOTE_DIR}; rm -f {REMOTE_DIR}/*.ipk")
        remote = f"{REMOTE_DIR}/{ipk.name}"
        sftp = self.ssh.open_sftp()
        try:
            sftp.put(str(ipk), remote)
        finally:
            sftp.close()
        size = self.run(f"wc -c < {remote}").strip()
        if size and size.isdigit() and int(size) != ipk.stat().st_size:
            raise LgError(f"Paket TV'ye eksik yüklendi ({size}/{ipk.stat().st_size} bayt).")
        payload = json.dumps({"id": "com.ares.defaultName", "ipkUrl": remote, "subscribe": True})
        log_file = f"{REMOTE_DIR}/kurulum.log"
        # Bazı webOS sürümleri, girişi kapanan luna-send aboneliğinde kurulumu yarıda keser: giriş 'sleep' ile açık
        # tutulur, çıktı dosyaya yazılır ve dosya izlenir.
        self.run(f"rm -f {log_file}; (sleep 120 </dev/null | /usr/bin/luna-send-pub -i "
                 f"'luna://com.webos.appInstallService/dev/install' '{payload}' > {log_file} 2>&1 &)", timeout=15)
        result, deadline = "cevap yok", time.time() + 120
        try:
            while time.time() < deadline:
                time.sleep(1)
                verdict = install_verdict(self.run(f"cat {log_file} 2>/dev/null", timeout=10))
                if verdict:
                    result = verdict
                    break
        finally:
            self.run(f"pkill -f 'appInstallService/dev/install' ; rm -f {remote} {log_file}", timeout=10)
        # "installed" dese de TV'deki sürüm gerçekten yenilenene kadar bekle (cevap belirsizse daha uzun)
        want = ipk_version(ipk)
        wait = 30 if result == "installed" else 60
        end = time.time() + wait
        while time.time() < end:
            if self.installed_version() == want:
                return
            if result not in ("installed", "cevap yok") and not result.startswith("zaman"):
                break
            time.sleep(2)
        raise LgError(f"TV'ye kurulamadı: {result}")

    def installed_version(self) -> str | None:
        out = self.run(f"cat /media/developer/apps/usr/palm/applications/{APP_ID}/appinfo.json 2>/dev/null", timeout=15)
        try:
            return json.loads(out).get("version")
        except ValueError:
            return None

    def renew_devmode(self) -> str | None:
        """Geliştirici modu süresini baştan başlat; kalan süreyi ("999:59:59") döndür."""
        token = self.run(f"cat {DEVMODE_TOKEN} 2>/dev/null", timeout=10).strip()
        if not token:
            return None
        try:
            with urllib.request.urlopen(f"{DEVMODE_API}ResetDevModeSession.dev?sessionToken={token}", timeout=10) as r:
                ok = b"success" in r.read().lower()
            with urllib.request.urlopen(f"{DEVMODE_API}CheckDevModeSession.dev?sessionToken={token}", timeout=10) as r:
                left = r.read().decode(errors="replace")
        except OSError as e:
            log.warning("LG geliştirici modu süresi yenilenemedi: %s", e)
            return None
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


def install_verdict(text: str) -> str | None:
    """Kurulum servisinin çıktısından sonuç: 'installed', hata metni ya da (henüz belli değilse) None."""
    low = text.lower().replace(" ", "")
    if '"state":"installed' in low or '"state":"success' in low:
        return "installed"
    if '"returnvalue":false' in low or "failed" in low:
        m = re.search(r'"errorText"\s*:\s*"([^"]+)"', text)
        return (m.group(1) if m else text.strip()[-300:]) or "hata"
    return None


def setup(host: str, passphrase: str, server_port: int, force_install: bool = False) -> str:
    from .tv import local_ip

    ipk = ipk_path()
    if ipk is None:
        raise LgError("LG TV paketi (.ipk) bu sürümde yok.")
    tv = LgTv(host, passphrase)
    tv.connect()
    try:
        tv.renew_devmode()
        if force_install or tv.installed_version() != ipk_version(ipk):
            log.info("LG TV uygulaması kuruluyor (%s)...", ipk.name)
            tv.install(ipk)
            time.sleep(2)
        server = f"{local_ip(host)}:{server_port}"
        tv.launch(server)
        return server
    finally:
        tv.close()
