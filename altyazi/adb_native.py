# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz:
# windows/src/CouchSubs.TvInstall/Android/AdbConnection.cs and AndroidTvInstaller.cs. Ported to Python.
"""Google'ın adb aracı olmadan Android TV'ye ağ üzerinden (5555) bağlanan küçük ADB istemcisi.

adb.exe'ye göre farkı: arka planda adb sunucusu yok, başka programların (emülatör, telefon aracı) eski adb'siyle
çakışmaz, eşleştirme kodu istemez. TV'de "USB hata ayıklama" açıkken TV 5555'te bekler; ilk bağlantıda TV
"hata ayıklamaya izin verilsin mi?" diye sorar. Protokol: AOSP packages/modules/adb/protocol.txt.
"""

from __future__ import annotations

import base64
import logging
import os
import socket
import struct
import time
from pathlib import Path
from typing import BinaryIO, Callable

log = logging.getLogger(__name__)

CNXN, AUTH, OPEN, OKAY, CLSE, WRTE = 0x4E584E43, 0x48545541, 0x4E45504F, 0x59414B4F, 0x45534C43, 0x45545257
AUTH_TOKEN, AUTH_SIGNATURE, AUTH_RSAPUBLICKEY = 1, 2, 3
VERSION = 0x01000001
MAX_PAYLOAD = 256 * 1024


class AdbError(RuntimeError):
    """kind: unreachable | not_approved | failed"""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


# ----------------------------------------------------------------------------- anahtar
def key_paths() -> list[Path]:
    """Önce Google adb'nin anahtarı (TV onu zaten onayladıysa yeniden sormasın), sonra programın kendi anahtarı."""
    from . import paths

    home = Path(os.environ.get("ANDROID_USER_HOME") or Path.home() / ".android")
    return [home / "adbkey", paths.data("adbkey")]


def load_or_create_key(path: Path | None = None):  # noqa: ANN201
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    candidates = [path] if path else key_paths()
    for p in candidates:
        try:
            key = serialization.load_pem_private_key(p.read_bytes(), password=None)
            if isinstance(key, rsa.RSAPrivateKey) and key.key_size == 2048:
                return key
        except (OSError, ValueError, TypeError):
            continue
    target = path or candidates[-1]
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return key


def sign_token(key, token: bytes) -> bytes:  # noqa: ANN001
    """adb jetonu SHA-1 özeti yerine geçen değer olarak imzalar (RSA_sign NID_sha1); jeton yeniden özetlenmez."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, utils

    return key.sign(token, padding.PKCS1v15(), utils.Prehashed(hashes.SHA1()))


def encode_public_key(key) -> bytes:  # noqa: ANN001
    """Android'in RSA açık anahtar biçimi (libcrypto_utils android_pubkey.c)."""
    words = 64
    pub = key.public_key().public_numbers()
    n, e = pub.n, pub.e
    if n.bit_length() > words * 32:
        raise ValueError("ADB yalnız 2048 bitlik RSA anahtarını kabul eder")
    r32 = 1 << 32
    n0inv = (r32 - pow(n % r32, -1, r32)) % r32
    rr = pow(1 << (words * 32), 2, n)
    return (struct.pack("<II", words, n0inv) + n.to_bytes(words * 4, "little") + rr.to_bytes(words * 4, "little")
            + struct.pack("<I", e))


def public_key_line(key, name: str = "gta6altyazi@GTA6Altyazi") -> bytes:  # noqa: ANN001
    return base64.b64encode(encode_public_key(key)) + b" " + name.encode() + b"\0"


# ----------------------------------------------------------------------------- paket
def encode(command: int, arg0: int, arg1: int, data: bytes = b"") -> bytes:
    return struct.pack("<6I", command, arg0, arg1, len(data), sum(data) & 0xFFFFFFFF, command ^ 0xFFFFFFFF) + data


def _read_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("TV bağlantıyı kapattı")
        buf += chunk
    return bytes(buf)


def read_packet(sock: socket.socket) -> tuple[int, int, int, bytes]:
    command, arg0, arg1, length, _check, magic = struct.unpack("<6I", _read_exact(sock, 24))
    if magic != command ^ 0xFFFFFFFF or length > 1024 * 1024:
        raise ConnectionError("ADB paketi bozuk")
    return command, arg0, arg1, _read_exact(sock, length) if length else b""


# ----------------------------------------------------------------------------- bağlantı
class AdbConnection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.max_payload = 4096
        self.next_id = 1

    @classmethod
    def connect(cls, host: str, port: int = 5555, key=None, on_prompt: Callable[[], None] | None = None,  # noqa: ANN001
                approve_timeout: float = 90.0) -> AdbConnection:
        try:
            sock = socket.create_connection((host, port), timeout=5)
        except OSError as e:
            raise AdbError("unreachable", str(e)) from e
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn = cls(sock)
        try:
            conn._handshake(key or load_or_create_key(), on_prompt, approve_timeout)
        except Exception:
            conn.close()
            raise
        return conn

    def _write(self, command: int, arg0: int, arg1: int, data: bytes = b"") -> None:
        self.sock.sendall(encode(command, arg0, arg1, data))

    def _read(self) -> tuple[int, int, int, bytes]:
        return read_packet(self.sock)

    def _handshake(self, key, on_prompt, approve_timeout: float) -> None:  # noqa: ANN001
        self._write(CNXN, VERSION, MAX_PAYLOAD, b"host::\0")
        signed = waiting = False
        self.sock.settimeout(10)
        while True:
            try:
                command, arg0, arg1, data = self._read()
            except (OSError, ConnectionError) as e:
                # Onay beklenirken bağlantı kapandıysa ya da süre dolduysa kullanıcı izin vermedi
                raise AdbError("not_approved" if waiting else "unreachable", str(e)) from e
            if command == CNXN:
                self.max_payload = min(MAX_PAYLOAD, arg1 or 4096)
                self.sock.settimeout(60)
                return
            if command == AUTH and arg0 == AUTH_TOKEN and not signed:
                signed = True
                self._write(AUTH, AUTH_SIGNATURE, 0, sign_token(key, data))
            elif command == AUTH and arg0 == AUTH_TOKEN:
                # İmza tanınmadı: TV bu anahtarı ilk kez görüyor; açık anahtarı gönderince TV kullanıcıya sorar
                self._write(AUTH, AUTH_RSAPUBLICKEY, 0, public_key_line(key))
                waiting = True
                self.sock.settimeout(approve_timeout)
                if on_prompt:
                    on_prompt()
            else:
                raise AdbError("unreachable", f"beklenmeyen paket {command:08x}")

    def run(self, service: str, stream: BinaryIO | None = None, timeout: float = 60.0) -> str:
        """Bir hizmet aç (shell:…, exec:…), varsa girdiyi gönder, hizmet kapanana kadar çıktıyı topla."""
        local = self.next_id
        self.next_id += 1
        self.sock.settimeout(timeout)
        self._write(OPEN, local, 0, service.encode() + b"\0")
        out = bytearray()
        remote = 0
        closed = False

        def handle(pkt) -> bool:  # noqa: ANN001
            nonlocal remote, closed
            command, arg0, arg1, data = pkt
            if command == OKAY and arg1 == local:
                remote = arg0
                return True
            if command == WRTE and arg1 == local:
                out.extend(data)
                self._write(OKAY, local, arg0)
                return False
            if command == CLSE and arg1 in (local, 0):
                closed = True
                return True
            return False

        try:
            while not handle(self._read()):
                pass
            if closed and remote == 0:
                raise AdbError("failed", f"{service.split(':')[0]} açılamadı")
            if stream is not None and not closed:
                while not closed:
                    chunk = stream.read(self.max_payload)
                    if not chunk:
                        break
                    self._write(WRTE, local, remote, chunk)
                    while True:                 # sonraki parçadan önce TV'nin bunu aldığını bekle
                        pkt = self._read()
                        if pkt[0] == OKAY and pkt[2] == local:
                            break
                        handle(pkt)
                        if closed:
                            break
            while not closed:
                handle(self._read())
        except (OSError, ConnectionError) as e:
            if isinstance(e, AdbError):
                raise
            raise AdbError("failed", str(e)) from e
        try:
            self._write(CLSE, local, remote)
        except OSError:
            pass
        return out.decode("utf-8", "replace")

    def shell(self, cmd: str, timeout: float = 60.0) -> str:
        return self.run("shell:" + cmd, timeout=timeout).strip()

    def install(self, apk: Path, timeout: float = 300.0) -> str:
        """APK'yı TV'ye kopyalamadan doğrudan paket yöneticisine akıt (Android 7+)."""
        size = apk.stat().st_size
        with open(apk, "rb") as f:
            return self.run(f"exec:cmd package install -r -S {size}", f, timeout=timeout).strip()

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> AdbConnection:
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.close()


def wait_ready(host: str, port: int = 5555, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False
