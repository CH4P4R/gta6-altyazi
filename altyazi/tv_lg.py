"""LG (webOS) TV'ye TV uygulamasını kurar ve başlatır.

TV'de bir kez: LG Content Store'dan ücretsiz "Developer Mode" uygulamasını kur, LG hesabınla gir,
"Dev Mode Status" ve "Key Server"ı aç, TV'yi yeniden başlat. Developer Mode ekranında TV'nin IP'si ve
6 karakterli bir parola (passphrase) görünür.

Kasa: anahtarı TV'nin Key Server'ından (http://IP:9991/webos_rsa) alır, parolayla açar, SSH (9922, kullanıcı
prisoner) ile bağlanıp .ipk'yı yükler ve LG'nin kurulum servisiyle kurar.
"""

from __future__ import annotations

import io
import json
import logging
import time
import urllib.request
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)

APP_ID = "com.gta6altyazi.tv"
SSH_PORT = 9922
KEY_PORT = 9991
REMOTE_DIR = "/media/developer/temp"


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
    try:
        return paramiko.RSAKey.from_private_key(io.StringIO(data.decode()), password=passphrase.strip() or None)
    except paramiko.SSHException as e:
        raise LgError("Anahtar açılamadı: Developer Mode ekranındaki parolayı doğru yazdığından emin ol.") from e


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
        remote = f"{REMOTE_DIR}/{ipk.name}"
        sftp = self.ssh.open_sftp()
        try:
            self.run(f"mkdir -p {REMOTE_DIR}")
            sftp.put(str(ipk), remote)
        finally:
            sftp.close()
        payload = json.dumps({"id": "com.ares.defaultName", "ipkUrl": remote, "subscribe": True})
        try:
            result = self._install_stream(f"/usr/bin/luna-send-pub -i 'luna://com.webos.appInstallService/dev/install' "
                                          f"'{payload}'")
        finally:
            self.run(f"rm -f {remote}")
        if result != "installed":
            # Cevap okunamadıysa TV'deki sürüme bak (kurulum yine de olmuş olabilir)
            if self.installed_version() != ipk_version(ipk):
                raise LgError(f"TV'ye kurulamadı: {result}")

    def installed_version(self) -> str | None:
        out = self.run(f"cat /media/developer/apps/usr/palm/applications/{APP_ID}/appinfo.json 2>/dev/null", timeout=15)
        try:
            return json.loads(out).get("version")
        except ValueError:
            return None

    def _install_stream(self, cmd: str, timeout: float = 90) -> str:
        """Kurulum servisinin cevaplarını satır satır oku: 'installed' ya da hata metni döndür."""
        _stdin, stdout, _stderr = self.ssh.exec_command(cmd, timeout=timeout)
        lines = []
        try:
            for line in iter(stdout.readline, ""):
                lines.append(line.strip())
                low = line.lower().replace(" ", "")
                if '"state":"installed' in low or '"state":"success' in low:
                    return "installed"
                if '"returnvalue":false' in low or "failed" in low:
                    return line.strip()[:300]
        except Exception as e:  # noqa: BLE001  (zaman aşımı)
            return f"zaman aşımı ({e})"
        finally:
            stdout.channel.close()
        return " ".join(lines)[-300:] or "cevap yok"

    def launch(self, server: str) -> None:
        params = json.dumps({"id": APP_ID, "params": {"host": server}})
        out = self.run(f"/usr/bin/luna-send-pub -n 1 'luna://com.webos.applicationManager/launch' '{params}'", timeout=20)
        if '"returnValue":false' in out.replace(" ", ""):
            raise LgError(f"TV uygulaması başlatılamadı: {out.strip()[:300]}")

    def close(self) -> None:
        if self.ssh:
            self.ssh.close()


def setup(host: str, passphrase: str, server_port: int, force_install: bool = False) -> str:
    from .tv import local_ip

    ipk = ipk_path()
    if ipk is None:
        raise LgError("LG TV paketi (.ipk) bu sürümde yok.")
    tv = LgTv(host, passphrase)
    tv.connect()
    try:
        if force_install or tv.installed_version() != ipk_version(ipk):
            log.info("LG TV uygulaması kuruluyor (%s)...", ipk.name)
            tv.install(ipk)
            time.sleep(2)
        server = f"{local_ip(host)}:{server_port}"
        tv.launch(server)
        return server
    finally:
        tv.close()
