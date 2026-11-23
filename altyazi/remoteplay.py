"""Yerleşik PS5 Remote Play: chiaki-ng penceresi olmadan PS5 görüntüsünü arka planda alır.

Oyun TV'de, HDMI'dan, gecikmesiz oynanır. Bilgisayar PS5'e ikinci bir PSN hesabıyla Remote Play üzerinden bağlanır ve
görüntüyü yalnız altyazıyı okumak için kullanır (ses ve kol girdisi kapalı). Kendi hesabınla bağlanılsaydı Remote Play
kolunu kapatırdı; ikinci hesapla oyunun kesilmez.

Yerel kütüphane: native/couchsubs_native.c (CouchSubs'tan; libchiaki + FFmpeg, AGPL-3.0). Bu dosya onun Python
karşılığıdır; yeniden bağlanma, uyandırma, görüntü takılma ve 720p'ye düşme kuralları CouchSubs'ın Windows
uygulamasındakiyle (StreamSession.cs) aynıdır.
"""

from __future__ import annotations

import base64
import ctypes
import logging
import os
import queue
import re
import sys
import threading
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------------- yerel kütüphane
_LIB_NAME = {"win32": "couchsubs_native.dll", "darwin": "couchsubs_native.dylib"}.get(sys.platform,
                                                                                       "couchsubs_native.so")
LOG_CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
CONSOLE_EX_CB = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                                 ctypes.c_char_p, ctypes.c_void_p)
FRAME_CB = ctypes.CFUNCTYPE(None, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_int, ctypes.c_int,
                            ctypes.c_void_p)
EVENT_CB = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)

EVENT_CONNECTED, EVENT_QUIT, EVENT_LOGIN_PIN = 0, 1, 2
QUIT_STOPPED, QUIT_IN_USE, QUIT_REFUSED, QUIT_NETWORK, QUIT_OTHER, QUIT_RP_CRASHED, QUIT_PSN_REGIST_FAILED = range(7)
QUIT_CONSOLE_CLOSED = 7      # PS5 akışı kendisi kapattı (kullanıcı PS5'te hesap değiştirdi): ağ kopması değil


class _Registered(ctypes.Structure):
    _fields_ = [("nickname", ctypes.c_char * 0x20), ("regist_key", ctypes.c_uint8 * 0x10),
                ("morning", ctypes.c_uint8 * 0x10)]


_lib = None
_lib_lock = threading.Lock()


def library_candidates() -> list[Path]:
    here = Path(__file__).resolve().parent
    out = []
    if os.environ.get("GTA6_RP_LIB"):
        out.append(Path(os.environ["GTA6_RP_LIB"]))
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        out += [base / _LIB_NAME, base / "native" / _LIB_NAME, Path(sys.executable).parent / _LIB_NAME]
    out += [here.parent / "native" / "bin" / _LIB_NAME, here.parent / "native" / "build" / _LIB_NAME]
    return out


def available() -> bool:
    try:
        lib()
        return True
    except OSError:
        return False


def lib():  # noqa: ANN201
    global _lib
    with _lib_lock:
        if _lib is not None:
            return _lib
        errors = []
        for path in library_candidates():
            if not path.exists():
                continue
            try:
                handle = ctypes.CDLL(str(path))
            except OSError as e:
                errors.append(f"{path}: {e}")
                continue
            _declare(handle)
            if handle.cs_init() != 0:
                raise OSError("Remote Play kütüphanesi başlatılamadı (cs_init)")
            log.info("Remote Play kütüphanesi: %s", path)
            _lib = handle
            return _lib
        raise OSError("Remote Play kütüphanesi bulunamadı" + (": " + "; ".join(errors) if errors else ""))


def _declare(h) -> None:  # noqa: ANN001
    c = ctypes
    h.cs_init.restype = c.c_int
    h.cs_discover_ex.argtypes = [c.POINTER(c.c_char_p), c.c_int, c.c_int, CONSOLE_EX_CB, c.c_void_p]
    h.cs_discover_ex.restype = c.c_int
    h.cs_wake.argtypes = [c.c_char_p, c.c_uint64]
    h.cs_wake.restype = c.c_int
    h.cs_register.argtypes = [c.c_char_p, c.POINTER(c.c_uint8), c.c_uint32, c.POINTER(_Registered),
                              c.POINTER(c.c_uint32), LOG_CB, c.c_void_p]
    h.cs_register.restype = c.c_int
    h.cs_session_start_ex.argtypes = [c.c_char_p, c.POINTER(c.c_uint8), c.POINTER(c.c_uint8), c.POINTER(c.c_uint8),
                                      c.c_int, c.c_int, FRAME_CB, EVENT_CB, LOG_CB, c.c_void_p]
    h.cs_session_start_ex.restype = c.c_void_p
    h.cs_session_set_login_pin.argtypes = [c.c_void_p, c.POINTER(c.c_uint8), c.c_size_t]
    h.cs_session_set_login_pin.restype = c.c_int
    h.cs_session_stop.argtypes = [c.c_void_p]
    h.cs_session_stop.restype = None


def _bytes(data: bytes, n: int):  # noqa: ANN202
    buf = (ctypes.c_uint8 * n)()
    for i, b in enumerate(data[:n]):
        buf[i] = b
    return buf


def _text(p: bytes | None) -> str | None:
    return p.decode("utf-8", "replace") if p else None


_LEVEL = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
rp_log = logging.getLogger("altyazi.remoteplay.chiaki")


# ----------------------------------------------------------------------------------------- PS5 bilgileri
@dataclass
class ConsoleInfo:
    host: str
    name: str
    awake: bool
    title_id: str | None = None
    app_name: str | None = None


@dataclass
class RegisteredConsole:
    host: str
    name: str
    regist_key: bytes        # 16 bayt (ASCII onaltılık, sıfırla doldurulmuş)
    morning: bytes           # 16 bayt

    @property
    def wake_credential(self) -> int | None:
        text = self.regist_key.split(b"\0", 1)[0].decode("ascii", "replace")
        try:
            return int(text, 16)
        except ValueError:
            return None

    def to_cfg(self) -> dict:
        return {"ip": self.host, "ad": self.name, "anahtar": self.regist_key.hex(), "morning": self.morning.hex()}

    @classmethod
    def from_cfg(cls, c) -> RegisteredConsole | None:  # noqa: ANN001
        try:
            key, morning = bytes.fromhex(c.anahtar or ""), bytes.fromhex(c.morning or "")
        except ValueError:
            return None
        if not c.ip or len(key) != 16 or len(morning) != 16:
            return None
        return cls(c.ip, c.ad or "", key, morning)


def local_targets() -> list[str]:
    """Bağlı ev ağlarındaki bütün adresler ve genel yayın (genel yayına PS5 her ağda yanıt vermiyor)."""
    from .tv import local_ips
    out = []
    for ip in local_ips():
        prefix = ip.rsplit(".", 1)[0]
        out += [f"{prefix}.{i}" for i in range(1, 255) if f"{prefix}.{i}" != ip]
    out.append("255.255.255.255")
    return list(dict.fromkeys(out))


def discover(host: str | None = None, timeout: float = 3.0) -> list[ConsoleInfo]:
    """Ağdaki PS5'ler (host verilirse yalnız o adres). Bloklar."""
    h = lib()
    targets = [host] if host else local_targets()
    arr = (ctypes.c_char_p * len(targets))(*[t.encode() for t in targets])
    found: dict[str, ConsoleInfo] = {}
    lock = threading.Lock()

    @CONSOLE_EX_CB
    def on_console(addr, name, awake, title, app, _user):  # noqa: ANN001
        try:
            a = _text(addr)
            if a:
                with lock:
                    found[a] = ConsoleInfo(a, _text(name) or "PS5", bool(awake), _text(title), _text(app))
        except Exception:  # noqa: BLE001
            pass

    h.cs_discover_ex(arr, len(targets), int(timeout * 1000), on_console, None)
    with lock:
        return sorted(found.values(), key=lambda c: c.host)


def wake(console: RegisteredConsole) -> None:
    cred = console.wake_credential
    if cred is None:
        raise RuntimeError("Eşleme anahtarı PS5'i uyandırmaya uygun değil; PS5'i yeniden eşle")
    if lib().cs_wake(console.host.encode(), cred) != 0:
        raise RuntimeError("PS5'e uyandırma isteği gönderilemedi")


# ----------------------------------------------------------------------------------------- eşleme (PIN)
REG_MESSAGES = {
    "WrongAccount": "PS5 bu PSN hesabını tanımadı. İkinci hesap PS5'te kullanıcı olarak ekli olmalı ve PS5'te bu "
                    "hesapla en az bir kez oturum açılmış olmalı.",
    "WrongCode": "Kod yanlış ya da süresi dolmuş. PS5'te yeni kod al ve hemen yaz.",
    "InUse": "PS5'te Uzaktan Oynatma şu an başka bir cihazda açık (telefon, PS Portal, chiaki-ng). Onu kapatıp yeniden dene.",
    "VersionMismatch": "PS5'in sistem yazılımı güncel değil. PS5'i güncelleyip yeniden dene.",
    "ConsoleCrashed": "PS5'teki Uzaktan Oynatma takıldı. PS5'i tamamen kapatıp aç (dinlenme modu değil), yeniden dene.",
    "BadAddress": "PS5'in adresi geçersiz.",
    "NoFreePort": "Bilgisayarda boş ağ portu kalmadı. Bilgisayarı yeniden başlatıp dene.",
    "PairingClosed": "PS5'te eşleştirme ekranı açık değil. PS5'te Ayarlar › Sistem › Uzaktan Oynatma › Cihazı Eşleştir'i aç.",
    "ConnectFailed": "PS5 yanıt verdi ama bağlantı açılamadı. Güvenlik duvarını ve aynı ağda olduğunuzu denetle.",
    "NoAnswer": "PS5 yanıt vermedi. PS5 açık mı, adres doğru mu, eşleştirme ekranı açık mı?",
    "NoReply": "PS5 kodu aldı ama yanıt vermedi. PS5'te yeni kod alıp yeniden dene.",
    "Failed": "PS5 eşlemesi başarısız.",
}


class RegistrationError(RuntimeError):
    def __init__(self, kind: str, detail: str | None = None):
        self.kind, self.detail = kind, detail
        super().__init__(REG_MESSAGES.get(kind, REG_MESSAGES["Failed"]) + (f" ({detail})" if detail else ""))


def parse_pin(text: str | None) -> int | None:
    """PS5'in 'Cihazı Eşleştir' ekranındaki 8 haneli kod; boşluk, tire, nokta atlanır."""
    if text is None:
        return None
    digits = []
    for ch in text:
        if ch.isspace() or ch in "-–._":
            continue
        if unicodedata.category(ch) != "Nd":
            return None
        digits.append(str(unicodedata.digit(ch)))
    return int("".join(digits)) if len(digits) == 8 else None


_REASON = re.compile(r"Reported Application Reason: (0x)?([0-9a-fA-F]+)")


def registration_failure(reason: int | None, errors: list[str]) -> str:
    def has(*needles: str) -> bool:
        return any(n in line for line in errors for n in needles)
    if reason == 0x80108B02:
        return "WrongAccount"
    if reason == 0x80108B09:
        return "WrongCode"
    if reason == 0x80108B10:
        return "InUse"
    if reason == 0x80108B11:
        return "VersionMismatch"
    if reason == 0x80108B15:
        return "ConsoleCrashed"
    if reason is None:
        if has("getaddrinfo"):
            return "BadAddress"
        if has("send search", "for search", "Regist connect failed", "search response") and \
                has("assign requested address", "No buffer space", "Too many open files", "WSA error 10049",
                    "WSA error 10055", "WSA error 10024"):
            return "NoFreePort"
        if has("search response") and has("Connection refused", "WSA error 10054"):
            return "PairingClosed"
        if has("connect for request"):
            return "ConnectFailed"
        if has("search response", "connect for search", "send search", "Regist search failed", "Regist connect failed"):
            return "NoAnswer"
        if has("response HTTP header", "receiving response content", "receive response content"):
            return "NoReply"
    return "Failed"


def register(host: str, account_id: bytes, pin: int) -> RegisteredConsole:
    """PS5'i 8 haneli kodla eşler (en çok ~30 sn bloklar). Başarısızlıkta RegistrationError."""
    if len(account_id) != 8:
        raise ValueError("PSN hesap kimliği 8 bayt olmalı")
    h = lib()
    log.info("PS5 eşlemesi başlıyor: %s", host)
    for attempt in range(1, 4):
        errors: list[str] = []

        @LOG_CB
        def on_log(level, message, _user):  # noqa: ANN001
            text = _text(message) or ""
            rp_log.log(_LEVEL.get(level, logging.DEBUG), text)
            if level == 0:
                errors.append(text)

        out = _Registered()
        reason = ctypes.c_uint32(0)
        result = h.cs_register(host.encode(), _bytes(account_id, 8), pin, ctypes.byref(out), ctypes.byref(reason),
                               on_log, None)
        if result == 0:
            name = out.nickname.split(b"\0", 1)[0].decode("utf-8", "replace")
            log.info("PS5 eşlendi: %s (%s)", name, host)
            return RegisteredConsole(host, name, bytes(out.regist_key), bytes(out.morning))
        reported = reason.value if result == 1 and reason.value else None
        kind = registration_failure(reported, errors) if result == 1 else ("NoReply" if result == 2 else "Failed")
        detail = next((m.group(0).split(": ", 1)[1] for e in errors for m in [_REASON.search(e)] if m), None) or \
            (errors[0] if errors else None)
        log.warning("PS5 eşlemesi başarısız (%s, deneme %d): %s %s", host, attempt, kind, detail)
        if not (kind == "NoAnswer" and attempt < 3):
            raise RegistrationError(kind, detail)
        time.sleep(0.5)
    raise RegistrationError("Failed")


# ----------------------------------------------------------------------------------------- PSN girişi
PSN_CLIENT_ID = "ba495a24-818c-472b-b12d-ff231c1b5745"       # chiaki-ng'nin Remote Play istemcisi
PSN_CLIENT_SECRET = "mvaiZkRsAsI1IBkY"
PSN_TOKEN_URL = "https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/token"
PSN_SCOPE = ("psn:clientapp referenceDataService:countryConfig.read pushNotification:webSocket.desktop.connect "
             "sessionManager:remotePlaySession.system.update")
PSN_REDIRECT = "https://remoteplay.dl.playstation.net/remoteplay/redirect"


def _q(items: list[tuple[str, str]]) -> str:
    return "&".join(urllib.parse.quote(k, safe="-._~:/?@!$'()*,;") + "=" +
                    urllib.parse.quote(v, safe="-._~:/?@!$'()*,;") for k, v in items)


PSN_LOGIN_URL = "https://auth.api.sonyentertainmentnetwork.com/2.0/oauth/authorize?" + _q([
    ("service_entity", "urn:service-entity:psn"), ("response_type", "code"), ("client_id", PSN_CLIENT_ID),
    ("redirect_uri", PSN_REDIRECT), ("scope", PSN_SCOPE), ("request_locale", "en_US"), ("ui", "pr"),
    ("service_logo", "ps"), ("layout_type", "popup"), ("smcid", "remoteplay"), ("prompt", "always"),
    ("PlatformPrivacyWs1", "minimal")])


class PsnError(RuntimeError):
    pass


def redirect_from_text(text: str | None) -> str | None:
    """Kullanıcının tarayıcıdan kopyalayıp yapıştırdığı metindeki yönlendirme adresi (kod ya da Sony hatası içeren)."""
    if not text:
        return None
    i = text.lower().find(PSN_REDIRECT)
    if i < 0:
        return None
    j = i
    while j < len(text) and not text[j].isspace() and text[j] not in "\"'<>":
        j += 1
    url = text[i:j]
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    return url if q.get("code") or q.get("error") else None


def _sony_error(data: dict) -> str | None:
    err = data.get("error")
    if not err:
        return None
    desc, code = data.get("error_description"), data.get("error_code")
    return str(err) + (f": {desc}" if desc else "") + (f" ({code})" if code else "")


def account_id_from_redirect(url: str, session=None) -> bytes:  # noqa: ANN001
    """Sony girişinin yönlendirdiği adresten PSN hesap kimliği (8 bayt). Token saklanmaz."""
    import requests
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    code = (q.get("code") or [""])[0]
    if not code:
        err = (q.get("error") or [""])[0]
        if err:
            desc = (q.get("error_description") or [""])[0].replace("+", " ")
            raise PsnError(f"Sony girişi tamamlamadı: {err}" + (f": {desc}" if desc else ""))
        raise PsnError("Yapıştırılan adreste giriş kodu yok. Girişten sonra adres çubuğundaki adresin tamamını kopyala.")
    s = session or requests.Session()
    auth = (PSN_CLIENT_ID, PSN_CLIENT_SECRET)
    try:
        r = s.post(PSN_TOKEN_URL, auth=auth, timeout=30, data=_q([
            ("grant_type", "authorization_code"), ("code", code), ("scope", PSN_SCOPE), ("redirect_uri", PSN_REDIRECT)]),
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        data = _json(r)
        token = data.get("access_token")
        if not token:
            raise PsnError("Sony giriş kodunu kabul etmedi: " + (_sony_error(data) or "yanıt anlaşılamadı") +
                           ". Kod tek kullanımlık ve birkaç dakikada eskir; yeniden giriş yap.")
        r = s.get(f"{PSN_TOKEN_URL}/{urllib.parse.quote(token, safe='')}", auth=auth, timeout=30)
        info = _json(r)
    except requests.RequestException as e:
        raise PsnError(f"Sony'ye ulaşılamadı: {e}") from e
    uid = info.get("user_id")
    try:
        return int(str(uid)).to_bytes(8, "little")
    except (TypeError, ValueError, OverflowError):
        raise PsnError("Sony'nin yanıtında hesap kimliği yok") from None


def _json(r) -> dict:  # noqa: ANN001
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        err = _sony_error(data) if isinstance(data, dict) else None
        if r.status_code == 429 or "too many" in (err or "").lower():
            raise PsnError("Sony çok fazla deneme dedi; birkaç dakika bekleyip yeniden giriş yap.")
        raise PsnError(f"Sony girişi reddetti (HTTP {r.status_code}" + (f", {err}" if err else "") +
                       "). Kod tek kullanımlık ve birkaç dakikada eskir; yeniden giriş yap.")
    return data if isinstance(data, dict) else {}


def account_b64(account_id: bytes) -> str:
    return base64.b64encode(account_id).decode()


def account_from_b64(text: str) -> bytes | None:
    try:
        b = base64.b64decode(text or "", validate=True)
    except ValueError:
        return None
    return b if len(b) == 8 else None


# ----------------------------------------------------------------------------------------- oturum kuralları
class WakePolicy:
    """Dinlenmedeki PS5 yalnız çeviri başlarken uyandırılır; akış bir kez kurulduysa (oyuncu PS5'i kapattıysa)
    yeniden açılmaz, açılması beklenir."""

    def __init__(self) -> None:
        self.streamed = False

    def decide(self, awake: bool | None) -> str:
        if awake is not False:
            return "connect"
        return "wait" if self.streamed else "wake"


class ReconnectPolicy:
    """2, 4, 8, 16, 32, en çok 60 sn; bağlı oturum düşünce en az 8 sn; 5 dk süren oturumdan sonra baştan."""
    STABLE_AFTER = 300.0

    def __init__(self) -> None:
        self.attempt = 0
        self.connected_at: float | None = None

    def next_delay(self, in_use: bool = False) -> int:
        if in_use:
            self.attempt = max(self.attempt, 2)
        delay = min(60, 2 << self.attempt)
        self.attempt = min(self.attempt + 1, 5)
        return delay

    def reset(self) -> None:
        self.attempt, self.connected_at = 0, None

    def connected(self, now: float) -> None:
        self.connected_at = now

    def ended(self, now: float) -> None:
        if self.connected_at is not None:
            if now - self.connected_at >= self.STABLE_AFTER:
                self.attempt = 0
            self.attempt = max(self.attempt, 2)
        self.connected_at = None


class ReconnectLimit:
    """Yeniden bağlanma sınırı (CouchSubs 8f82f3c4, GitHub #353): PS5 akışı kendisi kapattıysa en çok 1, ağ kopmasında
    art arda en çok 5 kez yeniden denenir; sonra durulur, nedeni ve Yeniden bağlan gösterilir. Eskiden sınırsız
    deneniyor, PS5'te durmadan "uzaktan oynatma bağlandı / koptu" bildirimi çıkıp oyun bölünüyordu. Sayaçlar çeviri
    başlayınca, Yeniden bağlan'da ve 2 dk süren oturumdan sonra sıfırlanır."""
    MAX_CONSOLE_CLOSED = 1
    MAX_NETWORK = 5
    STABLE_AFTER = 120.0

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.console_closed = 0
        self.network = 0
        self.connected_at: float | None = None

    def connected(self, now: float) -> None:
        self.connected_at = now

    def ended(self, kind: str, now: float) -> str | None:
        """Yeniden denenecekse None, durulacaksa gösterilecek neden ("console_closed_repeatedly" / "gave_up")."""
        if self.connected_at is not None and now - self.connected_at >= self.STABLE_AFTER:
            self.console_closed = self.network = 0
        self.connected_at = None
        if kind == "console_closed":
            self.console_closed += 1
            return "console_closed_repeatedly" if self.console_closed > self.MAX_CONSOLE_CLOSED else None
        if kind in ("network", "not_found", "refused", "other"):
            self.network += 1
            return "gave_up" if self.network > self.MAX_NETWORK else None
        return None


class QualityFallback:
    """10 dk içinde 2 kopma olursa bu çeviri boyunca 720p (kablosuz ağda PS5 akışı kopuyordu)."""

    def __init__(self) -> None:
        self.drops: list[float] = []
        self.lowered = False

    def dropped(self, now: float) -> bool:
        if self.lowered:
            return False
        self.drops = [t for t in self.drops if now - t <= 600] + [now]
        if len(self.drops) >= 2:
            self.lowered = True
            return True
        return False


class StreamStats:
    """Sistem sağlığı için: son bir dakikadaki görüntü hızı, donmalar (0.5 sn'den uzun boşluk) ve kopmalar."""
    WINDOW, FREEZE = 60.0, 0.5

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.frames: list[float] = []
        self.freezes: list[float] = []
        self.drops: list[float] = []

    def frame(self, now: float) -> None:
        with self._lock:
            if self.frames and now - self.frames[-1] > self.FREEZE:
                self.freezes.append(now)
            self.frames.append(now)
            if len(self.frames) > 4000:
                self.frames = self.frames[-2000:]

    def drop(self, now: float) -> None:
        with self._lock:
            self.drops.append(now)

    def summary(self, now: float) -> dict:
        with self._lock:
            recent = [t for t in self.frames if now - t <= self.WINDOW]
            span = min(self.WINDOW, now - recent[0]) if recent else 0.0
            fps = len(recent) / span if span >= 2 else 0.0
            per_min = 60.0 / max(span, 1.0) if span else 0.0
            freezes = sum(1 for t in self.freezes if now - t <= self.WINDOW) * per_min
            drops = sum(1 for t in self.drops if now - t <= 600)
            last = now - self.frames[-1] if self.frames else None
        return {"fps": round(fps, 1), "donma_dk": round(freezes, 1), "kopma_10dk": drops,
                "son_kare_sn": None if last is None else round(last, 1)}


class PictureWatchdog:
    """Bağlıyken görüntü 15 sn (ilk görüntü 8 sn) gelmezse oturum yeniden kurulur."""
    STALL_AFTER, FIRST_AFTER = 15.0, 8.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.since: float | None = None
        self.has_picture = False

    def connected(self, now: float) -> None:
        with self._lock:
            self.since, self.has_picture = now, False

    def picture(self, now: float) -> None:
        with self._lock:
            if self.since is not None:
                self.since, self.has_picture = now, True

    def ended(self) -> None:
        with self._lock:
            self.since = None

    def stalled(self, now: float) -> float | None:
        with self._lock:
            if self.since is None:
                return None
            gap = now - self.since
            return gap if gap >= (self.STALL_AFTER if self.has_picture else self.FIRST_AFTER) else None


REGIST_REJECTED = {0x80108B09, 0x80108B02, 0x80108B26}
REMOTE_PLAY_DISABLED = 0x80108B12
_UNREACHABLE = ("Session request connect failed eventually", "Failed to send session request",
                "Failed to receive session request response")


@dataclass
class Disconnect:
    kind: str            # stopped|in_use|refused|network|not_found|asleep|crashed|regist|login_pin|login_wrong|rejected|
    #                      console_closed|console_closed_repeatedly|gave_up|other
    detail: str | None = None

    def message(self, host: str = "") -> str:
        k = self.kind
        if k == "in_use":
            return ("PS5'te Uzaktan Oynatma başka bir cihazda açık (telefon, PS Portal ya da chiaki-ng). Onu kapat; "
                    "kapanınca kendiliğinden bağlanır.")
        if k in ("network", "refused", "not_found"):
            return (f"PS5'e ulaşılamıyor{f' ({host})' if host else ''}. PS5 açık ve bilgisayarla aynı ağda mı? "
                    "Yeniden deneniyor.")
        if k == "asleep":
            return "PS5 dinlenme modunda. Açılınca kendiliğinden bağlanılacak."
        if k == "crashed":
            return "PS5'teki Uzaktan Oynatma takıldı. PS5'i tamamen kapatıp aç (dinlenme modu değil)."
        if k == "regist":
            return "PS5 eşlemesi geçersiz (PS5'te silinmiş ya da PS5 sıfırlanmış). Ayarlar › PS5'ten yeniden eşle."
        if k == "login_pin":
            return "PS5 bu hesap için giriş şifresi istiyor. Ayarlar › PS5'e PS5 giriş şifresini (4 hane) yaz."
        if k == "login_wrong":
            return "PS5 giriş şifresi yanlış. Ayarlar › PS5'ten düzelt."
        if k == "rejected":
            if self.detail == f"0x{REMOTE_PLAY_DISABLED:08x}":
                return ("PS5'te Uzaktan Oynatma kapalı: PS5'te Ayarlar › Sistem › Uzaktan Oynatma › Uzaktan "
                        "Oynatmayı Etkinleştir'i aç.")
            return f"PS5 bağlantıyı kabul etmedi{f' ({self.detail})' if self.detail else ''}. Yeniden deneniyor."
        if k == "stopped":
            return "PS5 bağlantısı kapandı."
        if k == "console_closed":
            return "PS5 Uzaktan Oynatma'yı kendisi kapattı (PS5'te kullanıcı değişmiş olabilir). Bir kez yeniden deneniyor."
        if k == "console_closed_repeatedly":
            return ("PS5 bağlantıyı yine kapattı. PS5'te programın giriş yaptığı ikinci hesapla oynuyorsun; kolu açınca "
                    "kendi (ana) hesabını seç. Hazır olunca fişi çekip yeniden tak (ya da Durdur, sonra Başlat).")
        if k == "gave_up":
            return ("PS5'e art arda bağlanılamadı; denemeler durduruldu. PS5 açık ve aynı ağda mı? Hazır olunca "
                    "fişi çekip yeniden tak (ya da Durdur, sonra Başlat).")
        return f"PS5 bağlantısı koptu{f': {self.detail}' if self.detail else ''}. Yeniden deneniyor."


def from_native(quit_reason: int, text: str | None, hint: Disconnect | None = None) -> Disconnect:
    if quit_reason == QUIT_OTHER and text == "Unknown Session Request Error":
        return hint or Disconnect("rejected")
    return {QUIT_STOPPED: Disconnect("stopped"), QUIT_IN_USE: Disconnect("in_use"), QUIT_REFUSED: Disconnect("refused"),
            QUIT_NETWORK: Disconnect("network"), QUIT_RP_CRASHED: Disconnect("crashed"),
            QUIT_PSN_REGIST_FAILED: Disconnect("regist"),
            QUIT_CONSOLE_CLOSED: Disconnect("console_closed", text)}.get(quit_reason, Disconnect("other", text))


def session_request_hint(line: str | None) -> Disconnect | None:
    if not line:
        return None
    m = _REASON.search(line)
    if m:
        try:
            code = int(m.group(2), 16)
        except ValueError:
            return None
        return Disconnect("regist") if code in REGIST_REJECTED else Disconnect("rejected", f"0x{code:08x}")
    return Disconnect("network") if any(u in line for u in _UNREACHABLE) else None


def normalized_passcode(value: str | None) -> str | None:
    v = (value or "").strip()
    return v if len(v) == 4 and v.isdigit() else None


# ----------------------------------------------------------------------------------------- oturum
class _Box:
    """Tek bir yerel oturum ve onun geri çağrıları (oturum kapanana kadar canlı tutulur)."""

    def __init__(self, owner: StreamSession, generation: int):
        self.owner, self.generation = owner, generation
        self.native: int | None = None
        self.hint: Disconnect | None = None
        self._lock = threading.Lock()

        @FRAME_CB
        def on_frame(ptr, w, h, stride, _u):  # noqa: ANN001
            try:
                owner._frame(ptr, w, h, stride)
            except Exception:  # noqa: BLE001
                log.exception("Remote Play karesi işlenemedi")

        @EVENT_CB
        def on_event(event, quit_reason, text, _u):  # noqa: ANN001
            try:
                owner._event(self, event, quit_reason, _text(text))
            except Exception:  # noqa: BLE001
                log.exception("Remote Play olayı işlenemedi")

        @LOG_CB
        def on_log(level, message, _u):  # noqa: ANN001
            line = _text(message) or ""
            rp_log.log(_LEVEL.get(level, logging.DEBUG), line)
            h = session_request_hint(line)
            if h is not None:
                self.hint = h

        self.cbs = (on_frame, on_event, on_log)

    def start(self, console: RegisteredConsole, account: bytes, height: int, max_fps: int) -> None:
        self.native = lib().cs_session_start_ex(console.host.encode(), _bytes(console.regist_key, 16),
                                                _bytes(console.morning, 16), _bytes(account, 8), max_fps, height,
                                                *self.cbs, None)

    def stop(self) -> None:
        with self._lock:
            if self.native:
                lib().cs_session_stop(self.native)
                self.native = None

    def set_pin(self, pin: bytes) -> None:
        with self._lock:
            if self.native:
                lib().cs_session_set_login_pin(self.native, _bytes(pin, len(pin)), len(pin))


class StreamSession:
    """PS5'e ikinci hesapla bağlanır, görüntüyü kare kare verir; koparsa kendiliğinden yeniden bağlanır.

    on_frame(bgra, zaman) oturumun iş parçacığında; on_state(durum, mesaj) kuyruğun iş parçacığında çağrılır.
    durum: baglaniyor | bagli | kopuk | durdu
    """
    MAX_FPS = 20

    def __init__(self, console: RegisteredConsole, account: bytes, passcode: str | None = None,
                 on_frame: Callable[[np.ndarray, float], None] | None = None,
                 on_state: Callable[[str, str], None] | None = None,
                 on_moved: Callable[[RegisteredConsole], None] | None = None):
        self.console, self.account, self.passcode = console, account, normalized_passcode(passcode)
        self.on_frame, self.on_state, self.on_moved = on_frame, on_state, on_moved
        self.state = ("durdu", "")
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._running = False
        self._gen = 0
        self._box: _Box | None = None
        self._policy, self._wake, self._quality = ReconnectPolicy(), WakePolicy(), QualityFallback()
        self._limit = ReconnectLimit()
        self._watchdog = PictureWatchdog()
        self._crashes = 0
        self._streaming = False
        self._search_answered = True
        self._next_relocate = 0.0
        self._last_frame = 0.0
        self.stats = StreamStats()
        self._thread = threading.Thread(target=self._run, daemon=True, name="remoteplay")
        self._thread.start()

    # --------------------------------------------------------------- dış arayüz
    def start(self) -> None:
        gen = self._bump(True)

        def go() -> None:
            self._policy.reset()
            self._limit.reset()
            self._wake = WakePolicy()
            self._crashes = 0
            self._connect(gen)
        self._post(go)

    def stop(self) -> None:
        self._bump(False)
        self._post(self._close_box)

    def reconnect_now(self) -> None:
        if not self._running and self._limit.console_closed == 0 and self._limit.network == 0:
            return                          # hiç başlamamış oturum (denemeler durdurulduysa yeniden açılır)
        gen = self._bump(True)

        def go() -> None:
            self._close_box()
            self._policy.reset()
            self._limit.reset()
            self._crashes = 0
            self._connect(gen)
        self._post(go)

    @property
    def streaming(self) -> bool:
        return self.state[0] == "bagli"

    # --------------------------------------------------------------- kuyruk
    def _run(self) -> None:
        while True:
            fn = self._q.get()
            try:
                fn()
            except Exception:  # noqa: BLE001
                log.exception("Remote Play oturum kuyruğu")

    def _post(self, fn: Callable[[], None]) -> None:
        self._q.put(fn)

    def _post_after(self, delay: float, fn: Callable[[], None]) -> None:
        t = threading.Timer(delay, lambda: self._post(fn))
        t.daemon = True
        t.start()

    def _bump(self, running: bool) -> int:
        with self._lock:
            self._running = running
            self._gen += 1
            return self._gen

    def _current(self, gen: int) -> bool:
        with self._lock:
            return self._running and self._gen == gen

    def _emit(self, state: str, msg: str = "") -> None:
        if (state, msg) != self.state:
            log.info("PS5 oturumu: %s %s", state, msg)
        self.state = (state, msg)
        if self.on_state:
            try:
                self.on_state(state, msg)
            except Exception:  # noqa: BLE001
                log.exception("on_state")

    # --------------------------------------------------------------- bağlanma (hepsi kuyrukta)
    def _connect(self, gen: int) -> None:
        if not self._current(gen) or self._box is not None:
            return
        self._emit("baglaniyor", f"PS5'e bağlanılıyor ({self.console.host})...")
        at_host = next(iter(_safe_discover(self.console.host, 2.0)), None)
        if at_host is not None and (not self.console.name or at_host.name == self.console.name):
            info = at_host
        else:
            info = self._relocate() or at_host
        self._search_answered = info is not None
        action = self._wake.decide(info.awake if info else None)
        if action == "wake":
            self._emit("baglaniyor", "PS5 dinlenme modunda; uyandırılıyor...")
            try:
                wake(self.console)
            except Exception as e:  # noqa: BLE001
                log.warning("PS5 uyandırılamadı: %s", e)
            self._wait_wake(gen, time.monotonic() + 20)
        elif action == "wait":
            self._schedule(gen, Disconnect("asleep"))
        else:
            self._open(gen)

    def _relocate(self) -> ConsoleInfo | None:
        """Kayıtlı adreste PS5 yoksa (modem adresi değiştirmiş olabilir) ağda adıyla arar."""
        if time.monotonic() < self._next_relocate:
            return None
        self._next_relocate = time.monotonic() + 30
        named = [c for c in _safe_discover(None, 3.0) if c.name == self.console.name]
        if len(named) != 1 or named[0].host == self.console.host:
            return None
        log.warning("PS5 yeni adreste: %s -> %s", self.console.host, named[0].host)
        self.console = RegisteredConsole(named[0].host, self.console.name, self.console.regist_key, self.console.morning)
        if self.on_moved:
            try:
                self.on_moved(self.console)
            except Exception:  # noqa: BLE001
                log.exception("on_moved")
        return named[0]

    def _wait_wake(self, gen: int, deadline: float) -> None:
        def check() -> None:
            if not self._current(gen):
                return
            if any(c.awake for c in _safe_discover(self.console.host, 2.0)):
                self._open(gen)
            elif time.monotonic() < deadline:
                self._wait_wake(gen, deadline)
            else:
                self._schedule(gen, Disconnect("asleep"))
        self._post_after(2.0, check)

    def _open(self, gen: int) -> None:
        if not self._current(gen) or self._box is not None:
            return
        box = _Box(self, gen)
        try:
            box.start(self.console, self.account, 720 if self._quality.lowered else 1080, self.MAX_FPS)
        except Exception as e:  # noqa: BLE001
            box.native = None
            log.warning("PS5 oturumu başlatılamadı: %s", e)
        if not box.native:
            self._schedule(gen, Disconnect("other", "oturum başlatılamadı"))
            return
        self._box = box

    def _close_box(self) -> None:
        self._streaming = False
        self._watchdog.ended()
        box, self._box = self._box, None
        if box is not None:
            threading.Thread(target=box.stop, daemon=True, name="remoteplay-kapat").start()

    def _schedule(self, gen: int, reason: Disconnect) -> None:
        if not self._search_answered and reason.kind in ("network", "other"):
            reason = Disconnect("not_found", self.console.host)
        if self._current(gen):
            stop = self._limit.ended(reason.kind, time.monotonic())
            if stop is not None:            # sınırsız döngü yerine dur; Yeniden bağlan'la sayaç sıfırlanır (#353)
                log.warning("PS5 oturumu: yeniden bağlanma durduruldu (%s; PS5 kapattı %d, ağ %d kez)", stop,
                            self._limit.console_closed, self._limit.network)
                self._bump(False)
                self._emit("kopuk", Disconnect(stop).message(self.console.host))
                return
        self._emit("kopuk", reason.message(self.console.host))
        if not self._current(gen):
            return
        delay = self._policy.next_delay(in_use=reason.kind == "in_use")
        self._post_after(delay, lambda: self._connect(gen))

    def _watch(self, gen: int) -> None:
        def check() -> None:
            if self._box is None or self._box.generation != gen or not self._current(gen):
                return
            gap = self._watchdog.stalled(time.monotonic())
            if gap is None:
                self._watch(gen)
                return
            log.warning("PS5'ten %d sn'dir görüntü gelmiyor; oturum yeniden kuruluyor", gap)
            self._close_box()
            self._policy.ended(time.monotonic())
            self._note_drop()
            self._schedule(gen, Disconnect("other", "PS5'ten görüntü gelmiyor"))
        self._post_after(1.0, check)

    def _note_drop(self) -> None:
        self.stats.drop(time.monotonic())
        if self._quality.dropped(time.monotonic()):
            log.warning("PS5 bağlantısı 10 dk içinde 2 kez koptu; görüntü 720p'ye düşürülüyor (PS5'i modeme kabloyla "
                        "bağlamak kalıcı çözüm)")

    # --------------------------------------------------------------- yerel geri çağrılar
    def _frame(self, ptr, w: int, h: int, stride: int) -> None:  # noqa: ANN001
        now = time.monotonic()
        self._watchdog.picture(now)
        self._last_frame = now
        self.stats.frame(now)
        if not self.on_frame:
            return
        flat = np.ctypeslib.as_array(ptr, shape=(h * stride,))
        frame = np.array(flat.reshape(h, stride // 4, 4)[:, :w], copy=True)
        self.on_frame(frame, time.perf_counter())

    def _event(self, box: _Box, event: int, quit_reason: int, text: str | None) -> None:
        gen = box.generation
        if event == EVENT_CONNECTED:
            def connected() -> None:
                if self._box is not box or not self._current(gen):
                    return
                now = time.monotonic()
                self._policy.connected(now)
                self._limit.connected(now)
                self._wake.streamed = True
                self._crashes = 0
                self._streaming = True
                self._watchdog.connected(now)
                self._emit("bagli", f"PS5'e bağlı ({self.console.name or self.console.host})")
                self._watch(gen)
            self._post(connected)
        elif event == EVENT_LOGIN_PIN:
            incorrect = quit_reason == 1

            def pin() -> None:
                if self._box is not box or not self._current(gen):
                    return
                if not incorrect and self.passcode:
                    log.info("PS5 giriş şifresi istedi; kayıtlı şifre gönderiliyor")
                    box.set_pin(self.passcode.encode("ascii"))
                    return
                self._bump(False)
                self._close_box()
                self._emit("kopuk", Disconnect("login_wrong" if incorrect else "login_pin").message())
            self._post(pin)
        elif event == EVENT_QUIT:
            reason = from_native(quit_reason, text, box.hint)
            log.info("PS5 oturumu kapandı: %s (%s) %s", quit_reason, reason.kind, text or "")

            def quit_() -> None:
                if self._box is not box or not self._current(gen):
                    return
                was = self._streaming
                self._close_box()
                self._policy.ended(time.monotonic())
                if was and reason.kind in ("network", "other"):
                    self._note_drop()
                if reason.kind == "regist":
                    self._bump(False)
                    self._emit("kopuk", reason.message())
                    return
                if reason.kind == "crashed":
                    self._crashes += 1
                    if self._crashes > 2:
                        self._bump(False)
                        self._emit("kopuk", reason.message())
                        return
                if reason.kind == "refused":
                    self._next_relocate = 0.0
                self._schedule(gen, reason)
            self._post(quit_)


def _safe_discover(host: str | None, timeout: float) -> list[ConsoleInfo]:
    try:
        return discover(host, timeout)
    except Exception as e:  # noqa: BLE001
        log.warning("PS5 araması başarısız: %s", e)
        return []
