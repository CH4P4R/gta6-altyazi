# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""sdb (ADB'nin Tizen'deki karşılığı) istemcisi, TCP 26101 üzerinden.

Çerçeve: 24 baytlık küçük-endian başlık (komut, arg0, arg1, uzunluk, bayt toplamı, komut ^ 0xFFFFFFFF) ve veri.
Kurulum komutları sırayla çalıştığı için bir anda tek kanal açıktır ve çerçeveler çağıranın iş parçacığında okunur.
"""

from __future__ import annotations

import base64
import socket
import struct
import time
from collections import deque
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

PORT = 26101
VERSION = 0x01000000
MAX_DATA = 4096
SYNC_MAX_DATA = 64 * 1024
BANNER = b"host::sdb-net-client"

CNXN = 0x4E584E43
AUTH = 0x48545541
OPEN = 0x4E45504F
OKAY = 0x59414B4F
WRTE = 0x45545257
CLSE = 0x45534C43
HEADER = 24

AUTH_TOKEN = 1
AUTH_SIGNATURE = 2
AUTH_PUBLICKEY = 3


class SdbError(OSError):
    pass


# ----------------------------------------------------------------------------- çerçeve
def checksum(payload: bytes) -> int:
    return sum(payload) & 0xFFFFFFFF


def encode(command: int, arg0: int, arg1: int, payload: bytes = b"") -> bytes:
    return struct.pack("<6I", command, arg0 & 0xFFFFFFFF, arg1 & 0xFFFFFFFF, len(payload), checksum(payload),
                       command ^ 0xFFFFFFFF) + payload


def _read_exactly(sock: socket.socket, size: int) -> bytes:
    buf = bytearray()
    while len(buf) < size:
        chunk = sock.recv(size - len(buf))
        if not chunk:
            raise SdbError("TV bağlantıyı kapattı")
        buf += chunk
    return bytes(buf)


def read_frame(sock: socket.socket) -> tuple[int, int, int, bytes]:
    """Bir çerçeve okur; başlık ya da toplam bozuksa SdbError."""
    command, arg0, arg1, length, total, magic = struct.unpack("<6I", _read_exactly(sock, HEADER))
    if length > 16 * 1024 * 1024:
        raise SdbError(f"sdb: geçersiz uzunluk {length}")
    payload = _read_exactly(sock, length) if length else b""
    if magic != command ^ 0xFFFFFFFF:
        raise SdbError(f"sdb: geçersiz çerçeve (komut {command:08X})")
    if total != checksum(payload):
        raise SdbError("sdb: denetim toplamı tutmuyor")
    return command, arg0, arg1, payload


def sync_packet(ident: str, payload: bytes) -> bytes:
    """sync: alt protokolünün paketi: 4 harfli kimlik, küçük-endian uzunluk, veri."""
    return ident.encode("ascii") + struct.pack("<I", len(payload)) + payload


def parse_capability(data: bytes) -> dict[str, str]:
    """``capability:`` yanıtı: ilk iki bayt uzunluk, sonra ``anahtar:değer`` satırları."""
    if len(data) < 2:
        return {}
    out: dict[str, str] = {}
    for line in data[2:].decode("utf-8", "replace").split("\n"):
        parts = [p for p in line.split(":") if p]
        if len(parts) == 2 and parts[0] not in out:
            out[parts[0]] = parts[1]
    return out


# ----------------------------------------------------------------------------- kimlik anahtarı
class AdbKey:
    """sdb'nin (ADB gibi) kimlik doğrulama anahtarı: 2048 bit RSA. Çoğu Samsung TV istemez."""

    def __init__(self, key: rsa.RSAPrivateKey):
        self.key = key

    @classmethod
    def generate(cls) -> AdbKey:
        return cls(rsa.generate_private_key(public_exponent=65537, key_size=2048))

    @classmethod
    def load_or_create(cls, path: Path) -> AdbKey:
        try:
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            if isinstance(key, rsa.RSAPrivateKey):
                return cls(key)
        except (OSError, ValueError):
            pass
        k = cls.generate()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(k.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))
        return k

    def sign(self, token: bytes) -> bytes:
        """TV'nin jetonunu imzalar (TizenSdb: RSA-SHA1, PKCS#1 v1.5)."""
        return self.key.sign(token, padding.PKCS1v15(), hashes.SHA1())

    def public_key_payload(self, name: str = "gta6altyazi@pc") -> bytes:
        return (base64.b64encode(encode_public_key(self.key.public_key())).decode() + " " + name + "\0").encode()


def encode_public_key(pub: rsa.RSAPublicKey) -> bytes:
    """Android'in RSAPublicKey yapısı: sözcük sayısı, n0inv, modül ve R² (küçük-endian 256 bayt), üs."""
    size = 256
    nums = pub.public_numbers()
    n = nums.n
    r32 = 1 << 32
    n0inv = (r32 - pow(n % r32, -1, r32)) % r32
    rr = pow(1 << (size * 8), 2, n)
    return (struct.pack("<II", size // 4, n0inv) + n.to_bytes(size, "little") + rr.to_bytes(size, "little")
            + struct.pack("<I", nums.e))


# ----------------------------------------------------------------------------- bağlantı
class Channel:
    """Açık bir sdb kanalı."""

    def __init__(self, conn: SdbConnection, local_id: int, service: str):
        self.conn = conn
        self.local_id = local_id
        self.service = service
        self.remote_id = 0
        self.pending: deque[bytes] = deque()
        self.acked = False
        self.closed = False

    def pump(self) -> None:
        """Bir çerçeve okur ve bu kanala göre işler."""
        conn = self.conn
        cmd, arg0, arg1, payload = read_frame(conn.sock)
        if cmd == OKAY:
            if arg1 == self.local_id:
                if self.remote_id == 0:
                    self.remote_id = arg0
                else:
                    self.acked = True
        elif cmd == WRTE:
            if arg1 == self.local_id:
                # TV kanal açılmadan önce de yazabilir (TizenSdb'deki not); veri saklanır.
                if self.remote_id == 0:
                    self.remote_id = arg0
                self.pending.append(payload)
                conn.send(OKAY, self.local_id, arg0)
            else:
                conn.send(CLSE, arg1, arg0)
        elif cmd == CLSE:
            if arg1 == self.local_id:
                self.closed = True
                try:
                    conn.send(CLSE, self.local_id, arg0)
                except OSError:
                    pass
        elif cmd == OPEN:
            conn.send(CLSE, arg1, arg0)

    def read(self) -> bytes | None:
        """TV'nin gönderdiği bir sonraki parça; kanal kapandıysa None."""
        while not self.pending:
            if self.closed:
                return None
            self.pump()
        return self.pending.popleft()

    def read_all(self) -> bytes:
        out = bytearray()
        while (chunk := self.read()) is not None:
            out += chunk
        return bytes(out)

    def read_exactly(self, size: int) -> bytes:
        out = bytearray()
        while len(out) < size:
            chunk = self.read()
            if chunk is None:
                raise SdbError("sdb: kanal erken kapandı")
            need = size - len(out)
            out += chunk[:need]
            if len(chunk) > need:
                self.pending.appendleft(chunk[need:])
        return bytes(out)

    def write(self, data: bytes) -> None:
        """Veriyi max_data'lık parçalarla yazar; TV her parçayı OKAY ile onaylar."""
        offset = 0
        while offset < len(data):
            if self.closed:
                raise SdbError("sdb: TV kanalı kapattı")
            part = data[offset:offset + self.conn.max_data]
            self.acked = False
            self.conn.send(WRTE, self.local_id, self.remote_id, part)
            while not self.acked:
                if self.closed:
                    raise SdbError("sdb: TV kanalı kapattı")
                self.pump()
            offset += len(part)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self.conn.send(CLSE, self.local_id, self.remote_id)
        except OSError:
            pass

    def __enter__(self) -> Channel:
        return self

    def __exit__(self, *_exc) -> None:  # noqa: ANN002
        self.close()


class SdbConnection:
    def __init__(self, sock: socket.socket, key: AdbKey | None = None):
        self.sock = sock
        self.key = key
        self.max_data = MAX_DATA
        self.banner = ""
        self._next_id = ord("a")

    @classmethod
    def connect(cls, host: str, key: AdbKey | None = None, port: int = PORT, timeout: float = 10.0,
                attempts: int = 3) -> SdbConnection:
        """Bağlanır. Samsung'un sdbd'si yeni bağlantıyı el sıkışmanın ortasında bazen kapatır; üç kez denenir."""
        last: Exception | None = None
        for attempt in range(attempts):
            sock = None
            try:
                sock = socket.create_connection((host, port), timeout=timeout)
                sock.settimeout(120)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                conn = cls(sock, key)
                conn.handshake()
                return conn
            except OSError as e:
                last = e
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                if attempt < attempts - 1:
                    time.sleep(0.4)
        raise SdbError(str(last) if last else "sdb bağlantısı kurulamadı")

    def send(self, command: int, arg0: int, arg1: int, payload: bytes = b"") -> None:
        self.sock.sendall(encode(command, arg0, arg1, payload))

    def handshake(self) -> None:
        self.send(CNXN, VERSION, self.max_data, BANNER)
        while True:
            cmd, arg0, arg1, payload = read_frame(self.sock)
            if cmd == CNXN:
                if arg1 > 0:
                    self.max_data = min(self.max_data, arg1)
                self.banner = payload.decode("utf-8", "replace")
                return
            if cmd == AUTH:
                if self.key is None:
                    self.key = AdbKey.generate()
                if arg0 == AUTH_TOKEN:
                    self.send(AUTH, AUTH_SIGNATURE, 0, self.key.sign(payload))
                elif arg0 == AUTH_PUBLICKEY:
                    self.send(AUTH, AUTH_PUBLICKEY, 0, self.key.public_key_payload())
                else:
                    raise SdbError(f"sdb: bilinmeyen AUTH türü {arg0}")
                continue
            raise SdbError("sdb: CNXN ya da AUTH bekleniyordu")

    def open(self, service: str) -> Channel:
        """Kanal açar ve TV'nin onayını (OKAY) bekler."""
        self._next_id += 1
        ch = Channel(self, self._next_id, service)
        self.send(OPEN, ch.local_id, 0, service.encode("utf-8"))
        while ch.remote_id == 0:
            if ch.closed:
                raise SdbError(f"sdb: TV kanalı açmadı ({service.rstrip(chr(0))})")
            ch.pump()
        return ch

    def shell(self, command: str) -> str:
        with self.open(f"shell:{command}\0") as ch:
            return ch.read_all().decode("utf-8", "replace")

    def capability(self) -> dict[str, str]:
        with self.open("capability:\0") as ch:
            return parse_capability(ch.read_all())

    def push(self, data: bytes, remote_path: str, mtime: int | None = None) -> None:
        """Dosyayı TV'ye gönderir (sync: SEND, DATA…, DONE; TV OKAY ya da FAIL döner)."""
        with self.open("sync:\0") as ch:
            ch.write(sync_packet("SEND", remote_path.encode("utf-8")))
            for off in range(0, len(data), SYNC_MAX_DATA):
                ch.write(sync_packet("DATA", data[off:off + SYNC_MAX_DATA]))
            # TizenSdb'deki (ve CouchSubs'taki) gibi mtime DONE paketinin verisi olarak gönderilir (AOSP adb'de
            # uzunluk alanının kendisidir); Samsung TV'lerde bu biçim çalışıyor.
            ch.write(sync_packet("DONE", struct.pack("<I", int(time.time() if mtime is None else mtime) & 0xFFFFFFFF)))
            while True:
                head = ch.read_exactly(8)
                ident = head[:4].decode("ascii", "replace")
                (length,) = struct.unpack("<I", head[4:])
                payload = ch.read_exactly(length) if length else b""
                if ident == "OKAY":
                    return
                if ident == "FAIL":
                    raise SdbError("sdb sync: FAIL: " + (payload.decode("utf-8", "replace") or "unknown"))

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self) -> SdbConnection:
        return self

    def __exit__(self, *_exc) -> None:  # noqa: ANN002
        self.close()
