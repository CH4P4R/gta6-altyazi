"""Programın kendi ADB istemcisi (adb_native): gerçek bir Android TV'nin adbd'sini taklit eden sunucuyla."""

import os
import socket
import struct
import threading

import pytest

from altyazi import adb_native as A


def decode_android_pubkey(blob: bytes):
    """android_pubkey biçimini çöz ve iç tutarlılığını doğrula (TV'nin yaptığı gibi)."""
    words, n0inv = struct.unpack_from("<II", blob)
    assert words == 64 and len(blob) == 8 + 64 * 4 * 2 + 4
    n = int.from_bytes(blob[8:8 + 256], "little")
    rr = int.from_bytes(blob[8 + 256:8 + 512], "little")
    e = struct.unpack_from("<I", blob, 8 + 512)[0]
    assert (n * n0inv) % (1 << 32) == (1 << 32) - 1          # n0inv = -1/n mod 2^32
    assert rr == pow(1 << 2048, 2, n)
    return n, e


def verify(n: int, e: int, token: bytes, sig: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
    pub = rsa.RSAPublicNumbers(e, n).public_key()
    try:
        pub.verify(sig, token, padding.PKCS1v15(), utils.Prehashed(hashes.SHA1()))
        return True
    except InvalidSignature:
        return False


class FakeAdbd:
    """Tek TV: yetkili anahtarlar, kurulu sürüm, gelen komutlar."""

    def __init__(self, approve=True, installed=None, incompatible=False):
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        self.authorized: list[tuple[int, int]] = []
        self.approve = approve
        self.installed = installed
        self.incompatible = incompatible
        self.commands: list[str] = []
        self.received = 0
        self.prompts = 0
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(c,), daemon=True).start()

    def _send(self, c, cmd, a0, a1, data=b""):
        c.sendall(A.encode(cmd, a0, a1, data))

    def _client(self, c):
        try:
            cmd, _, _, data = A.read_packet(c)
            assert cmd == A.CNXN and data.startswith(b"host::")
            token = os.urandom(20)
            self._send(c, A.AUTH, A.AUTH_TOKEN, 0, token)
            while True:
                cmd, a0, _, data = A.read_packet(c)
                assert cmd == A.AUTH
                if a0 == A.AUTH_SIGNATURE:
                    if any(verify(n, e, token, data) for n, e in self.authorized):
                        break
                    token = os.urandom(20)
                    self._send(c, A.AUTH, A.AUTH_TOKEN, 0, token)
                elif a0 == A.AUTH_RSAPUBLICKEY:
                    self.prompts += 1
                    if not self.approve:
                        c.close()
                        return
                    b64 = data.rstrip(b"\0").split(b" ")[0]
                    import base64
                    self.authorized.append(decode_android_pubkey(base64.b64decode(b64)))
                    break
            self._send(c, A.CNXN, A.VERSION, 4096, b"device::ro.product.name=tcl;\0")
            while True:
                cmd, a0, a1, data = A.read_packet(c)
                if cmd != A.OPEN:
                    continue
                service = data.rstrip(b"\0").decode()
                self.commands.append(service)
                local, remote = a0, 77
                self._send(c, A.OKAY, remote, local)
                out = self._run(c, service, local, remote)
                if out:
                    self._send(c, A.WRTE, remote, local, out.encode())
                    A.read_packet(c)                                  # istemcinin OKAY'i
                self._send(c, A.CLSE, remote, local)
                A.read_packet(c)                                      # istemcinin CLSE'si
        except (OSError, ConnectionError, struct.error):
            pass

    def _run(self, c, service, local, remote):
        if service.startswith("exec:cmd package install"):
            size = int(service.rsplit(" ", 1)[1])
            got = 0
            while got < size:
                cmd, _, _, data = A.read_packet(c)
                assert cmd == A.WRTE
                got += len(data)
                self._send(c, A.OKAY, remote, local)
            self.received = got
            if self.incompatible and self.installed is not None:
                return "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]\n"
            self.installed = 99
            return "Success\n"
        if service == "shell:getprop ro.build.version.release":
            return "12\n"
        if service.startswith("shell:dumpsys package com.gta6altyazi.tv"):
            if "grep" in service:
                return ""
            return f"    versionCode={self.installed} minSdk=24\n" if self.installed is not None else ""
        if service.startswith("shell:pm uninstall"):
            self.installed = None
            self.incompatible = False
            return "Success\n"
        if service.startswith("shell:appops get"):
            return "SYSTEM_ALERT_WINDOW: allow\n"
        if service.startswith("shell:am start"):
            return "Starting: Intent { cmp=com.gta6altyazi.tv/.MainActivity }\n"
        return ""


@pytest.fixture
def key(tmp_path):
    return A.load_or_create_key(tmp_path / "adbkey")


def test_first_connection_asks_tv_then_remembers(key):
    tv = FakeAdbd()
    prompts = []
    with A.AdbConnection.connect("127.0.0.1", tv.port, key, on_prompt=lambda: prompts.append(1)) as c:
        assert c.shell("getprop ro.build.version.release") == "12"
    assert prompts == [1] and tv.prompts == 1                 # ilk sefer TV sordu
    with A.AdbConnection.connect("127.0.0.1", tv.port, key, on_prompt=lambda: prompts.append(1)) as c:
        assert c.shell("getprop ro.build.version.release") == "12"
    assert prompts == [1] and tv.prompts == 1                 # ikinci sefer imza tanındı, soru yok


def test_refused_approval_is_reported(key):
    tv = FakeAdbd(approve=False)
    with pytest.raises(A.AdbError) as e:
        A.AdbConnection.connect("127.0.0.1", tv.port, key, approve_timeout=5)
    assert e.value.kind == "not_approved"


def test_unreachable(key):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(A.AdbError) as e:
        A.AdbConnection.connect("127.0.0.1", port, key)
    assert e.value.kind == "unreachable"


def test_stream_install(key, tmp_path):
    tv = FakeAdbd()
    apk = tmp_path / "app.apk"
    apk.write_bytes(os.urandom(700_000))                      # birden çok parça
    with A.AdbConnection.connect("127.0.0.1", tv.port, key) as c:
        assert c.install(apk) == "Success"
    assert tv.received == 700_000


def test_key_is_reused_and_adb_key_preferred(tmp_path, monkeypatch):
    from cryptography.hazmat.primitives import serialization
    k1 = A.load_or_create_key(tmp_path / "k")
    k2 = A.load_or_create_key(tmp_path / "k")
    pem = lambda k: k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,  # noqa: E731
                                    serialization.NoEncryption())
    assert pem(k1) == pem(k2)
    # Google adb'nin anahtarı varsa o kullanılır (TV onu zaten onayladıysa yeniden sormaz)
    monkeypatch.setenv("ANDROID_USER_HOME", str(tmp_path / "android"))
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path / "data"))
    (tmp_path / "android").mkdir()
    (tmp_path / "android" / "adbkey").write_bytes(pem(k1))
    assert pem(A.load_or_create_key()) == pem(k1)


def test_tv_setup_uses_native_client_without_adb_exe(tmp_path, monkeypatch):
    """Tam akış: 5555 açık TV'ye adb.exe olmadan bağlan, kur, izin ver, başlat."""
    from altyazi import tv as T
    monkeypatch.delenv("ALTYAZI_ADB", raising=False)
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    monkeypatch.setenv("ANDROID_USER_HOME", str(tmp_path / "android"))
    monkeypatch.setattr(T, "find_adb", lambda: (_ for _ in ()).throw(AssertionError("adb.exe kullanılmamalı")))
    fake = FakeAdbd(installed=1, incompatible=True)
    monkeypatch.setattr(T, "ADB_PORT", fake.port)
    apk = tmp_path / "tv.apk"
    apk.write_bytes(b"x" * 5000)
    monkeypatch.setattr(T, "APK", apk)
    monkeypatch.setattr(T.AndroidTv.install, "__defaults__", (apk,))
    monkeypatch.setattr(T.NativeAndroidTv.install, "__defaults__", (apk,))
    prompts = []
    server = T.setup("127.0.0.1", 8787, force_install=True, on_prompt=lambda: prompts.append(1))
    assert prompts == [1] and server.endswith(":8787")
    assert fake.installed == 99 and fake.received == 5000
    assert any(c.startswith("shell:pm uninstall") for c in fake.commands)     # imza farkı: kaldırıp yeniden kur
    assert any(c.startswith("shell:appops set com.gta6altyazi.tv SYSTEM_ALERT_WINDOW allow") for c in fake.commands)
    assert any(c.startswith("shell:am start -n com.gta6altyazi.tv/.MainActivity") and "displayMode inApp" in c
               for c in fake.commands)
