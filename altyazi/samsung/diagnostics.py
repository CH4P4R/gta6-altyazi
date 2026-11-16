# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""Samsung kurulumunun hata türleri, Türkçe iletileri ve TV'nin ``vd_appinstall`` çıktısının sınıflandırılması.

TV kurulum başarısız olsa da komutu başarılı bitirir; ne olduğu çıktıdaki ``install failed[118, -12]`` gibi
kodlardan anlaşılır (kodların anlamları Apps2Samsung'un TizenInstallDiagnostics'inden).
"""

from __future__ import annotations

import re

from ..tv_samsung import SamsungError

APP_ID = "GTA6Altyzi.GTA6Altyazi"
PACKAGE_ID = "GTA6Altyzi"

# Hata türleri
UNREACHABLE = "unreachable"
LOGIN_FAILED = "login_failed"
CERTIFICATE_FAILED = "certificate_failed"
TOO_OLD = "too_old"
INSTALL_FAILED = "install_failed"
NOT_ENOUGH_SPACE = "not_enough_space"
CERTIFICATE_MISMATCH = "certificate_mismatch"
CERTIFICATE_REJECTED = "certificate_rejected"
TV_CLOCK_WRONG = "tv_clock_wrong"
PACKAGE_BLOCKED = "package_blocked"
INCOMPATIBLE = "incompatible"
CONNECTION_LOST = "connection_lost"
NO_PACKAGE = "no_package"

MESSAGES = {
    UNREACHABLE: "Samsung TV'ye bağlanılamadı. TV açık ve bu bilgisayarla aynı ağda mı? TV'de Developer mode açık ve "
                 "'Host PC IP' bu bilgisayarın IP'si mi? Ayarı değiştirdiysen TV'yi güç tuşuna 2 sn basılı tutarak "
                 "yeniden başlat.",
    LOGIN_FAILED: "Samsung hesabına giriş tamamlanmadı. Tekrar dene ve tarayıcıda açılan Samsung sayfasında girişi bitir.",
    CERTIFICATE_FAILED: "Samsung imza sertifikasını vermedi. İnternet bağlantını kontrol et, birkaç dakika sonra "
                        "tekrar dene.",
    TOO_OLD: "Bu Samsung TV çok eski; uygulama en az Tizen 2.4 (2016 ve sonrası modeller) ister.",
    INSTALL_FAILED: "Uygulama TV'ye kurulamadı. Tekrar dene; yine olmazsa aşağıdaki sebebi bize gönder.",
    NOT_ENOUGH_SPACE: "TV'de boş yer kalmamış. TV'den kullanmadığın bir uygulamayı sil ve tekrar dene.",
    CERTIFICATE_MISMATCH: "TV'de başka bir bilgisayarda imzalanmış eski bir GTA6 Altyazı var ve kaldırılamadı. TV'de "
                          "Uygulamalar'dan GTA6 Altyazı'yı silip tekrar dene.",
    CERTIFICATE_REJECTED: "TV imza sertifikasını kabul etmedi. TV internete bağlı mı (sertifikayı Samsung'la denetler) "
                          "ve tarihi/saati doğru mu (Ayarlar › Genel › Sistem Yöneticisi › Saat)? Sonra tekrar dene: "
                          "program yeni sertifika alır, Samsung hesabına bir kez daha girersin.",
    TV_CLOCK_WRONG: "TV'nin saati geride; yeni sertifika TV'ye göre henüz geçerli değil. TV'nin tarih ve saatini düzelt "
                    "(Ayarlar › Genel › Sistem Yöneticisi › Saat) ya da birkaç dakika bekleyip tekrar dene.",
    PACKAGE_BLOCKED: "TV, GTA6 Altyazı'yı reddediyor çünkü eski bir kopyası TV'de hâlâ kayıtlı (Tizen hatası 118, -22), "
                     "uygulamalar arasında görünmese bile. Uygulamalar'da varsa silip tekrar dene. Yoksa Smart Hub'ı "
                     "sıfırla (Ayarlar › Destek › Cihaz Bakımı › Kendi Kendine Tanı › Smart Hub'ı Sıfırla; adlar "
                     "modele göre biraz değişir) ve tekrar dene. Smart Hub sıfırlanınca indirdiğin diğer uygulamalar da "
                     "silinir.",
    INCOMPATIBLE: "TV bu paketi desteklemiyor (Tizen hatası 118, -4 / -19): TV'nin yazılımı uygulamanın istediğinden "
                  "eski ya da paket bu TV türüne uygun değil. TV'nin yazılımını güncelleyip tekrar dene.",
    CONNECTION_LOST: "Kurulum sırasında TV bağlantısı koptu. TV'yi açık ve bu bilgisayarla aynı ağda tut, tekrar dene.",
    NO_PACKAGE: "Samsung TV paketi bu sürümde yok (tv-web/build/tizen). Geliştiriciysen önce "
                "'python tools/tv_web_hazirla.py' çalıştır.",
}


class SamsungInstallError(SamsungError):
    """Tizen Studio'suz kurulumun hatası: ``kind`` türü, ``detail`` TV'nin/Samsung'un ham yanıtı (kısaltılmış)."""

    def __init__(self, kind: str, detail: str = "", message: str | None = None):
        self.kind = kind
        self.detail = (detail or "").strip()
        text = message or MESSAGES.get(kind, MESSAGES[INSTALL_FAILED])
        if self.detail:
            text += f" [{self.detail[:300]}]"
        super().__init__(text)


# ----------------------------------------------------------------------------- vd_appinstall çıktısı
NONE = "none"
OTHER = "other"
CERTIFICATE_NOT_YET_VALID = "certificate_not_yet_valid"


def _has(log: str | None, token: str) -> bool:
    return bool(log) and token.lower() in log.lower()


def _connection_lost(log: str | None) -> bool:
    return any(_has(log, t) for t in ("transport connection", "connection reset by peer", "broken pipe"))


def failed(log: str | None) -> bool:
    """Yalın "failed" aranmaz; ilgisiz bir satır başarısızlık sanılmasın."""
    return (_has(log, "install failed") or _has(log, "val[fail]") or _has(log, "not enough space")
            or _has(log, "download failed[116]") or _connection_lost(log))


def classify(log: str | None) -> str:
    """``vd_appinstall`` çıktısından sorun: NONE, OTHER ya da yukarıdaki türlerden biri."""
    if not failed(log):
        return NONE
    if _connection_lost(log):
        return CONNECTION_LOST
    if any(_has(log, f"install failed[{c}]") for c in ("118, -4", "118, -19", "118019")):
        return INCOMPATIBLE
    if _has(log, "download failed[116]") or _has(log, "not enough space"):
        return NOT_ENOUGH_SPACE
    certificate = any(_has(log, f"install failed[{c}]") for c in ("118, -12", "118012", "118, -11", "118011"))
    # [118, -12] iki şey olabilir: TV'de başka sertifikalı kopya (kaldırınca düzelir) ya da TV'nin sertifikayı reddetmesi.
    if certificate and _has(log, "Check certificate error") and not _has(log, "same id and different certificate"):
        return CERTIFICATE_NOT_YET_VALID if _has(log, "not valid yet") else CERTIFICATE_REJECTED
    if certificate or _has(log, "Author certificate not match"):
        return CERTIFICATE_MISMATCH
    if _has(log, "install failed[118, -22]") or _has(log, "install failed[118022]"):
        return PACKAGE_BLOCKED
    return OTHER


def removing_old_copy_may_help(problem: str) -> bool:
    return problem in (CERTIFICATE_MISMATCH, PACKAGE_BLOCKED, OTHER)


def to_error_kind(problem: str) -> str:
    return {
        CONNECTION_LOST: CONNECTION_LOST,
        NOT_ENOUGH_SPACE: NOT_ENOUGH_SPACE,
        CERTIFICATE_MISMATCH: CERTIFICATE_MISMATCH,
        CERTIFICATE_REJECTED: CERTIFICATE_REJECTED,
        CERTIFICATE_NOT_YET_VALID: TV_CLOCK_WRONG,
        PACKAGE_BLOCKED: PACKAGE_BLOCKED,
        INCOMPATIBLE: INCOMPATIBLE,
    }.get(problem, INSTALL_FAILED)


def summary(log: str | None) -> str:
    """Kullanıcıya gösterilecek kısa ayrıntı: TV'nin hata satırları, yoksa çıktının sonu."""
    if not log or not log.strip():
        return "TV yanıt vermedi"
    lines = [ln.strip() for ln in log.split("\n") if ln.strip()]
    key: list[str] = []
    for ln in lines:
        if any(w in ln.lower() for w in ("fail", "error", "reason", "not match", "space")) and ln not in key:
            key.append(ln)
    text = " | ".join(key[:3]) if key else " | ".join(lines[-3:])
    return text if len(text) <= 400 else text[:400] + "…"


def error_for(log: str | None) -> SamsungInstallError | None:
    """Çıktı başarısızsa uygun Türkçe iletili hata; başarılıysa None."""
    problem = classify(log)
    if problem == NONE:
        return None
    return SamsungInstallError(to_error_kind(problem), summary(log))


# ----------------------------------------------------------------------------- sürümler
def _parts(version: str) -> list[int]:
    return [int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", version)]


def is_newer(a: str, b: str) -> bool:
    """Sayısal karşılaştırma: 0.10.0, 0.9.9'dan yenidir."""
    x, y = _parts(a), _parts(b)
    for i in range(max(len(x), len(y))):
        left = x[i] if i < len(x) else 0
        right = y[i] if i < len(y) else 0
        if left != right:
            return left > right
    return False


_FIELD = re.compile(r"^[\s-]*([A-Za-z_]+)\s*=\s*(.*?)[\s-]*$")


def installed_version(listing: str | None, ids: tuple[str, ...] = (APP_ID, PACKAGE_ID)) -> str | None:
    """``0 vd_applist`` çıktısında uygulamamızın sürümü; satırlar ``---- anahtar = değer ----`` biçimindedir."""
    if not listing or not listing.strip():
        return None
    wanted = {i.lower() for i in ids}
    fields: dict[str, str] = {}
    found: str | None = None

    def flush() -> None:
        nonlocal found
        names = [fields.get("app_tizen_id"), fields.get("app_id")]
        version = fields.get("app_version")
        if found is None and version and any(n and n.strip().lower() in wanted for n in names):
            found = version
        fields.clear()

    for raw in listing.replace("\r", "").split("\n"):
        if "=" not in raw and "----" in raw:
            flush()
            continue
        m = _FIELD.match(raw)
        if m:
            fields[m.group(1).lower()] = m.group(2).strip()
    flush()
    return found
