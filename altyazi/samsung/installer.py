# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""GTA6 Altyazı'nın Samsung TV uygulamasını geliştirici modu açık TV'ye Tizen Studio olmadan kurar.

TV'nin DUID'ini okur, gerekirse Samsung hesabıyla TV'ye özel sertifika alır, paketi imzalar, kurar ve açar.

TV'de bir kez: Uygulamalar ekranında kumandayla 1-2-3-4-5 yaz, Developer mode'u aç, Host PC IP olarak bu
bilgisayarın IP'sini yaz ve TV'yi güç tuşuna 2 sn basılı tutarak yeniden başlat.
"""

from __future__ import annotations

import logging
import re
import secrets
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable

from .. import paths
from . import certs, diagnostics as diag, login, sdb, signer
from .diagnostics import APP_ID, PACKAGE_ID, SamsungInstallError

log = logging.getLogger(__name__)

MINIMUM_TIZEN = "2.4"          # config.xml'deki required_version
DEVICE_PROFILE_UP_TO = "4.0"   # bu sürüme kadar (dahil) TV kurulumdan önce device-profile.xml ister
DEFAULT_TOOLPATH = "/opt/usr/apps/tmp"
_DUID = re.compile(r"^[A-Za-z0-9_\-+=/]{8,}$")


def is_too_old(platform: str) -> bool:
    return bool(platform) and diag.is_newer(MINIMUM_TIZEN, platform)


def needs_device_profile(platform: str) -> bool:
    return bool(platform) and not is_too_old(platform) and not diag.is_newer(platform, DEVICE_PROFILE_UP_TO)


def is_duid(text: str) -> bool:
    return bool(_DUID.match(text))


def package_version(folder: Path) -> str | None:
    try:
        return ET.parse(folder / "config.xml").getroot().get("version")
    except (OSError, ET.ParseError):
        return None


def read_duid(conn: sdb.SdbConnection, attempts: int = 3, delay: float = 0.5) -> str:
    """Yavaş TV'lerde ilk yanıt boş gelebiliyor; birkaç kez denenir."""
    last = ""
    for i in range(attempts):
        last = conn.shell("0 getduid")
        duid = last.split("\n")[0].strip()
        if is_duid(duid):
            return duid
        if i < attempts - 1:
            time.sleep(delay)
    raise SamsungInstallError(diag.UNREACHABLE, f"TV kimliği (DUID) okunamadı; TV'nin yanıtı: {last.strip() or 'boş'}")


def install_with_recovery(install: Callable[[], str], shell: Callable[[str], str],
                          progress: Callable[[str], None] = lambda s: None) -> None:
    """Kurar; TV başka sertifikayla kurulmuş eski kopya ya da paket kimliği yüzünden reddederse eski kopyayı kaldırıp
    bir kez daha dener. Sonuç yine başarısızsa TV'nin söylediği sebeple SamsungInstallError atar."""
    out = install()
    log.info("vd_appinstall çıktısı:\n%s", out.strip())
    problem = diag.classify(out)
    if problem == diag.NONE:
        return
    log.warning("Samsung kurulumu başarısız: %s", problem)
    if not diag.removing_old_copy_may_help(problem):
        raise SamsungInstallError(diag.to_error_kind(problem), diag.summary(out))
    progress("TV'deki eski kopya kaldırılıp yeniden kuruluyor...")
    for app in (PACKAGE_ID, APP_ID):
        try:
            log.info("vd_appuninstall %s: %s", app, shell(f"0 vd_appuninstall {app}").strip())
        except OSError as e:
            log.info("vd_appuninstall %s: %s", app, e)
    retry = install()
    log.info("İkinci deneme vd_appinstall çıktısı:\n%s", retry.strip())
    problem = diag.classify(retry)
    if problem != diag.NONE:
        raise SamsungInstallError(diag.to_error_kind(problem), diag.summary(retry))


class _Installer:
    def __init__(self, host: str, port: int, data_dir: Path, source: Path,
                 sign_in: Callable[[], certs.SamsungAccount], http: certs.HttpPost,
                 progress: Callable[[str], None], on_login_needed: Callable[[str], object] | None):
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.source = source
        self.sign_in = sign_in
        self.http = http
        self.progress = progress
        self.on_login_needed = on_login_needed

    # ------------------------------------------------------------------ yardımcılar
    def connect(self) -> sdb.SdbConnection:
        key = sdb.AdbKey.load_or_create(self.data_dir / "sdb_key.pem")
        try:
            conn = sdb.SdbConnection.connect(self.host, key, port=self.port)
        except OSError as e:
            raise SamsungInstallError(diag.UNREACHABLE, f"sdb {self.host}:{self.port}: {e}") from e
        log.info("sdb bağlantısı kuruldu (%s:%s) %s", self.host, self.port, conn.banner)
        return conn

    def installed(self, conn: sdb.SdbConnection) -> str | None:
        try:
            listing = conn.shell("0 vd_applist")
        except OSError as e:
            log.info("vd_applist okunamadı: %s", e)
            return None
        v = diag.installed_version(listing)
        log.info("vd_applist: %s", f"GTA6 Altyazı {v}" if v else "GTA6 Altyazı yok")
        return v

    def launch(self, conn: sdb.SdbConnection) -> None:
        """Uygulamayı açar; açılmasa da kurulum başarılıdır."""
        self.progress("TV uygulaması açılıyor...")
        try:
            log.info("was_execute: %s", conn.shell(f"0 was_execute {APP_ID}").strip())
        except OSError as e:
            log.warning("Uygulama açılamadı (kurulum yine tamam): %s", e)

    def profile(self, duid: str) -> certs.SigningProfile:
        return certs.SigningProfile(self.data_dir / certs.safe_name(duid))

    def obtain_certificates(self, duid: str, profile: certs.SigningProfile) -> certs.SigningProfile:
        """Önce kayıtlı Samsung oturumuyla dener; Samsung reddederse (jeton eskimiş) tarayıcıda yeniden girilir."""
        account_file = self.data_dir / "account.json"
        account = certs.SamsungAccount.load(account_file)
        if account is not None:
            self.progress("Samsung'dan bu TV'ye özel imza sertifikası alınıyor...")
            try:
                return certs.create(duid, account, profile, self.http)
            except SamsungInstallError as e:
                if e.network:
                    raise
                log.info("Kayıtlı Samsung oturumuyla sertifika alınamadı, yeniden giriş gerekiyor: %s", e.detail)
                account_file.unlink(missing_ok=True)
        if self.on_login_needed is not None:
            # Çağıran girişi reddedebilir (ör. kendiliğinden bağlanırken habersiz tarayıcı açılmasın): hata yükselir
            self.on_login_needed(login.authorize_url())
        self.progress("Tarayıcıda açılan Samsung sayfasında hesabına gir (yalnız ilk sefer, 5 dk içinde)...")
        account = self.sign_in()
        account.save(account_file)
        self.progress("Samsung girişi tamam; imza sertifikası alınıyor...")
        return certs.create(duid, account, profile, self.http)

    # ------------------------------------------------------------------ akış
    def run(self, force_install: bool) -> None:
        if not (self.source / "config.xml").exists():
            raise SamsungInstallError(diag.NO_PACKAGE)
        version = package_version(self.source)
        self.progress(f"Samsung TV'ye bağlanılıyor ({self.host})...")
        conn = self.connect()
        try:
            self._run(conn, version, force_install)
        except SamsungInstallError:
            raise
        except OSError as e:
            # Adımların arasında TV bağlantıyı kapattı ya da yanıt vermedi.
            raise SamsungInstallError(diag.CONNECTION_LOST, str(e) or type(e).__name__) from e
        finally:
            conn.close()

    def _run(self, conn: sdb.SdbConnection, version: str | None, force_install: bool) -> None:
        caps = conn.capability()
        platform = caps.get("platform_version", "").strip()
        tool_path = caps.get("sdk_toolpath", "").strip() or DEFAULT_TOOLPATH
        log.info("Samsung TV: Tizen %s, sdk_toolpath %s", platform or "?", tool_path)
        if is_too_old(platform):
            raise SamsungInstallError(diag.TOO_OLD, f"Tizen {platform}")

        on_tv = self.installed(conn)
        if not force_install and version and on_tv and not diag.is_newer(version, on_tv):
            self.launch(conn)
            return

        duid = read_duid(conn)
        log.info("DUID: %s", duid)
        profile = self.profile(duid)
        log.info("Kayıtlı sertifika: %s", profile.describe(duid))
        if not profile.is_valid() or not profile.is_for(duid):
            profile = self.obtain_certificates(duid, profile)
            log.info("Yeni sertifika: %s", profile.describe(duid))

        if needs_device_profile(platform) and profile.device_profile_file.exists():
            remote = f"{tool_path}/device-profile.xml"
            try:
                conn.push(profile.device_profile_file.read_bytes(), remote)
                log.info("Cihaz profili gönderildi: %s", remote)
            except OSError as e:
                log.warning("Cihaz profili gönderilemedi (%s): %s", remote, e)

        self.progress("Uygulama imzalanıyor...")
        key = profile.private_key()
        signed = signer.sign(signer.folder_entries(self.source),
                             signer.Signer(key, certs.chain(profile.author())),
                             signer.Signer(key, certs.chain(profile.distributor())))
        log.info("Paket imzalandı (%d bayt).", len(signed))

        remote = f"{tool_path}/gta6altyazi-{secrets.token_hex(4)}.wgt"

        def install() -> str:
            # TizenSdb'deki gibi hata da çıktıya yazılır; tanı çıktıdan yapılır.
            out = ""
            try:
                conn.push(signed, remote)
                out = "Push complete.\n"
                out += conn.shell(f"0 vd_appinstall {APP_ID} {remote}")
            except Exception as e:  # noqa: BLE001
                out += f"\ninstall failed: {type(e).__name__}: {e}\n"
            return out

        self.progress("Uygulama TV'ye gönderilip kuruluyor...")
        try:
            install_with_recovery(install, conn.shell, self.progress)
        except SamsungInstallError as e:
            if e.kind == diag.CERTIFICATE_REJECTED:
                # TV bu sertifikayı kabul etmiyor; bir sonraki denemede Samsung'dan yenisi istensin.
                profile.discard()
                log.info("Kayıtlı sertifika bırakıldı; bir sonraki denemede yenisi alınacak.")
            raise
        after = self.installed(conn)
        if version and after and diag.is_newer(version, after):
            raise SamsungInstallError(diag.INSTALL_FAILED, f"TV kurulumu bitirdi ama TV'de hâlâ {after} sürümü var "
                                                           f"({version} kurulmalıydı)")
        self.launch(conn)


def setup_direct(host: str, on_login_needed: Callable[[str], object] | None = None, *,
                 force_install: bool = True, progress: Callable[[str], None] | None = None,
                 port: int = sdb.PORT, source: Path | None = None, data_dir: Path | None = None,
                 sign_in: Callable[[], certs.SamsungAccount] | None = None, http: certs.HttpPost | None = None,
                 cancel: threading.Event | None = None, login_timeout: float = 300) -> str:
    """Samsung TV'ye GTA6 Altyazı'yı kurar ve açar; bu bilgisayarın ev ağındaki adresini döner.

    ``on_login_needed(url)``: Samsung girişi gerektiğinde, tarayıcı açılmadan hemen önce çağrılır.
    ``force_install`` False ise TV'deki sürüm paketinkinden eski değilse kurmadan yalnız açar.
    Hata durumunda Türkçe iletili ``SamsungInstallError`` (``tv_samsung.SamsungError`` alt sınıfı) atar.
    """
    inst = _Installer(
        host=host, port=port,
        data_dir=data_dir or paths.data("samsung"),
        source=source or paths.resource("tv-web/build/tizen"),
        sign_in=sign_in or (lambda: login.sign_in(None, login_timeout, cancel=cancel)),
        http=http or certs.urllib_post,
        progress=progress or (lambda s: log.info("%s", s)),
        on_login_needed=on_login_needed,
    )
    inst.run(force_install)
    from ..tv import local_ip
    return local_ip(host)
