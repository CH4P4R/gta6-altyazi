# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""Samsung hesabıyla giriş.

Sayfa tarayıcıda açılır; Samsung'un SignInGate sayfası jetonu bu bilgisayardaki küçük bir dinleyiciye
(``http://localhost:4794/signin/callback``) POST eder. Tizen Studio'nun sertifika eklentisi de aynı yolu kullanır.
Tarayıcı ``localhost``'u ``::1``'e de çözebildiği için IPv4 ve IPv6 geri döngü adresleri birlikte dinlenir.
"""

from __future__ import annotations

import json
import logging
import select
import socket
import threading
import time
import webbrowser
from typing import Callable
from urllib.parse import quote, unquote, unquote_plus

from .certs import SamsungAccount
from .diagnostics import LOGIN_FAILED, SamsungInstallError

log = logging.getLogger(__name__)

SIGN_IN_GATE = "https://account.samsung.com/accounts/be1dce529476c1a6d407c4c7578c31bd/signInGate"
CLIENT_ID = "v285zxnl3h"
STATE = "accountcheckdogeneratedstatetext"
CALLBACK_PORT = 4794
CALLBACK_PATH = "/signin/callback"


def authorize_url(port: int = CALLBACK_PORT) -> str:
    redirect = quote(f"http://localhost:{port}{CALLBACK_PATH}", safe="")
    return f"{SIGN_IN_GATE}?locale=&clientId={CLIENT_ID}&redirect_uri={redirect}&state={STATE}&tokenType=TOKEN"


def parse_callback(body: str) -> SamsungAccount | None:
    """Gövde: ``code=<urlencoded JSON>&state=…``. JSON'da access_token, userId ve inputEmailID bulunur."""
    state = code = None
    for part in body.split("&"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name == "state":
            state = unquote_plus(value)
        elif name == "code":
            code = value
    if state != STATE or not code or not code.strip():
        return None
    d = None
    # Önce yalnız %XX çözülür; jetonda olabilecek '+' boşluğa çevrilmez (CouchSubs'taki gibi). JSON bozuk çıkarsa
    # (tarayıcı formu boşlukları '+' yapmış) form kodlamasıyla bir daha denenir.
    for decode in (unquote, unquote_plus):
        try:
            d = json.loads(decode(code))
            break
        except ValueError:
            continue
    if not isinstance(d, dict):
        return None
    token, user, email = d.get("access_token"), d.get("userId"), d.get("inputEmailID")
    if isinstance(token, str) and token and isinstance(user, str) and user:
        return SamsungAccount(token, user, email if isinstance(email, str) else "")
    return None


def callback_problem(body: str) -> str:
    """Geri dönüşte jeton neden yok: alan adları ve Samsung'un hata alanları (jetonun kendisi yazılmaz)."""
    parts = []
    for part in body.split("&"):
        if not part:
            continue
        name, _, value = part.partition("=")
        name = unquote_plus(name)
        parts.append(f"{name}={unquote_plus(value)}" if name in ("error", "error_description", "error_code", "state")
                     else name)
    return ", ".join(parts)[:200]


def read_request(conn: socket.socket) -> tuple[str, str, str]:
    """Ham HTTP isteği: (yöntem, yol, gövde)."""
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(16384)
        if not chunk or len(data) > 1024 * 1024:
            return "", "", ""
        data += chunk
    end = data.index(b"\r\n\r\n")
    lines = data[:end].decode("latin-1").split("\r\n")
    req = lines[0].split(" ")
    length = 0
    for ln in lines[1:]:
        if ln.lower().startswith("content-length:"):
            try:
                length = int(ln[15:].strip())
            except ValueError:
                pass
    body = bytearray(data[end + 4:])
    while len(body) < length:
        chunk = conn.recv(16384)
        if not chunk:
            break
        body += chunk
    return (req[0] if req else ""), (req[1] if len(req) > 1 else ""), body.decode("utf-8", "replace")


PAGE_OK = ("<!doctype html><html lang=tr><meta charset=utf-8><meta name=viewport content=\"width=device-width\">"
           "<title>GTA6 Altyazı</title><body style=\"font-family:system-ui,sans-serif;padding:3em;background:#111;"
           "color:#eee\"><h2>Samsung girişi tamam ✓</h2><p>Bu sekmeyi kapatıp GTA6 Altyazı'ya dönebilirsin. "
           "Program şimdi TV'ye özel imza sertifikasını alıp uygulamayı kuruyor.</p></body></html>")
PAGE_BAD = ("<!doctype html><html lang=tr><meta charset=utf-8><title>GTA6 Altyazı</title>"
            "<body style=\"font-family:system-ui,sans-serif;padding:3em\"><h2>Samsung girişinden hesap bilgisi "
            "gelmedi</h2><p>GTA6 Altyazı'ya dönüp tekrar dene.</p></body></html>")


def _respond(conn: socket.socket, status: int, page: str) -> None:
    reason = {200: "OK", 400: "Bad Request"}.get(status, "Not Found")
    body = page.encode("utf-8")
    conn.sendall(f"HTTP/1.1 {status} {reason}\r\nContent-Type: text/html; charset=utf-8\r\n"
                 f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii") + body)


class Listener:
    """Geri dönüşü bekleyen dinleyici; yalnız bu bilgisayarın içinden (127.0.0.1 ve ::1) bağlanılır."""

    def __init__(self, port: int = CALLBACK_PORT):
        self.port = port
        self.socks: list[socket.socket] = []
        errors = []
        for family, addr in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
            s = None
            try:
                s = socket.socket(family, socket.SOCK_STREAM)
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                else:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if family == socket.AF_INET6 and hasattr(socket, "IPV6_V6ONLY"):
                    s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                s.bind((addr, port))
                s.listen(8)
                self.socks.append(s)
            except OSError as e:
                errors.append(f"{addr}: {e}")
                if s is not None:
                    s.close()
        if not any(s.family == socket.AF_INET for s in self.socks):
            self.close()
            raise SamsungInstallError(LOGIN_FAILED, f"giriş dönüşü için localhost:{port} açılamadı (program iki kez "
                                                    f"mi açık?): {'; '.join(errors)}")

    def wait(self, timeout: float, cancel: threading.Event | None = None) -> SamsungAccount:
        deadline = time.monotonic() + timeout
        rejected = None
        try:
            while True:
                left = deadline - time.monotonic()
                if left <= 0 or (cancel is not None and cancel.is_set()):
                    break
                ready, _, _ = select.select(self.socks, [], [], min(left, 0.5))
                for s in ready:
                    try:
                        conn, _addr = s.accept()
                    except OSError:
                        continue
                    with conn:
                        conn.settimeout(10)
                        try:
                            method, path, body = read_request(conn)
                        except OSError:
                            continue
                        is_cb = method == "POST" and path.startswith(CALLBACK_PATH)
                        account = parse_callback(body) if is_cb else None
                        if is_cb and account is None:
                            rejected = callback_problem(body)
                        try:
                            _respond(conn, 200 if account else 400 if is_cb else 404,
                                     PAGE_OK if account else PAGE_BAD if is_cb else "Not found")
                        except OSError:
                            pass
                        if account:
                            return account
        finally:
            self.close()
        if cancel is not None and cancel.is_set():
            raise SamsungInstallError(LOGIN_FAILED, "giriş iptal edildi")
        extra = f"; Samsung'un geri dönüşünde hesap bilgisi yoktu ({rejected})" if rejected else ""
        raise SamsungInstallError(LOGIN_FAILED, f"giriş {round(timeout / 60)} dakika içinde tamamlanmadı{extra}")

    def close(self) -> None:
        for s in self.socks:
            try:
                s.close()
            except OSError:
                pass
        self.socks = []


def sign_in(open_browser: Callable[[str], object] | None = None, timeout: float = 300,
            port: int = CALLBACK_PORT, cancel: threading.Event | None = None) -> SamsungAccount:
    """Dinleyiciyi açar, sayfayı tarayıcıda açtırır ve girişi bekler (en çok ``timeout`` sn)."""
    # Windows'ta kapanan dinleyicinin portu bir süre (TIME_WAIT) yeniden açılamayabilir: ikinci girişte biraz bekle
    deadline = time.monotonic() + 30
    while True:
        try:
            listener = Listener(port)
            break
        except SamsungInstallError:
            if time.monotonic() > deadline or (cancel is not None and cancel.is_set()):
                raise
            time.sleep(2)
    url = authorize_url(port)
    log.info("Samsung girişi tarayıcıda açılıyor: %s", url)
    try:
        (open_browser or webbrowser.open)(url)
    except Exception as e:  # noqa: BLE001
        listener.close()
        raise SamsungInstallError(LOGIN_FAILED, f"tarayıcı açılamadı: {e}. Şu adresi tarayıcıda aç: {url}") from e
    return listener.wait(timeout, cancel)
