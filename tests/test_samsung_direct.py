"""Tizen Studio'suz Samsung kurulumu (altyazi.samsung): ağ ve gerçek TV olmadan.

Sahte bir sdb sunucusu (yerel TCP), sahte bir Samsung sertifika sunucusu (test CA'sı) ve sahte giriş kullanılır.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import http.client
import io
import json
import re
import socket
import struct
import threading
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import quote, urlencode

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from altyazi import tv_samsung
from altyazi.samsung import certs, diagnostics as diag, installer, login, sdb, signer
from altyazi.samsung.diagnostics import SamsungInstallError

DSIG = "{http://www.w3.org/2000/09/xmldsig#}"
APP = "GTA6Altyzi.GTA6Altyazi"


# ============================================================================ yardımcılar: test CA'sı
def _key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test"), x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(subject: x509.Name, pub, issuer: x509.Name, issuer_key, ca: bool = False, days: int = 365) -> x509.Certificate:
    now = dt.datetime.now(dt.timezone.utc)
    b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(pub)
         .serial_number(x509.random_serial_number())
         .not_valid_before(now - dt.timedelta(hours=1)).not_valid_after(now + dt.timedelta(days=days)))
    if ca:
        b = b.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    return b.sign(issuer_key, hashes.SHA256())


class FakeCA:
    """Kök -> ara sertifika; yaprakları ara sertifika verir (Samsung'un zinciri gibi)."""

    def __init__(self):
        self.root_key = _key()
        self.root = _cert(_name("Test Root"), self.root_key.public_key(), _name("Test Root"), self.root_key, ca=True)
        self.int_key = _key()
        self.intermediate = _cert(_name("Test Intermediate"), self.int_key.public_key(), self.root.subject,
                                  self.root_key, ca=True)

    def issue(self, pub, cn: str = "leaf", days: int = 365) -> x509.Certificate:
        return _cert(_name(cn), pub, self.intermediate.subject, self.int_key, days=days)


@pytest.fixture(scope="module")
def ca() -> FakeCA:
    return FakeCA()


# ============================================================================ sahte sdb sunucusu
class FakeSdb(threading.Thread):
    """Samsung TV'nin sdbd'si gibi davranan küçük sunucu (tek bağlantıyı sırayla işler)."""

    def __init__(self, shell=None, caps=None, auth_key: sdb.AdbKey | None = None, sync_fail: str | None = None):
        super().__init__(daemon=True)
        self.shell_handler = shell or (lambda cmd: "")
        self.caps = caps or {}
        self.auth_key = auth_key
        self.sync_fail = sync_fail
        self.commands: list[str] = []
        self.files: dict[str, bytes] = {}
        self.mtimes: dict[str, int] = {}
        self.auth_ok = None
        self.max_wrte = 0
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        self.error: BaseException | None = None
        self._rid = 1000

    def send(self, c, cmd, a0, a1, payload=b""):
        c.sendall(sdb.encode(cmd, a0, a1, payload))

    def run(self):
        try:
            while True:
                try:
                    c, _ = self.srv.accept()
                except OSError:
                    return
                with c:
                    c.settimeout(10)
                    try:
                        self.serve(c)
                    except sdb.SdbError:
                        pass          # istemci bağlantıyı kapattı
        except BaseException as e:  # noqa: BLE001
            self.error = e

    def serve(self, c):
        cmd, a0, a1, payload = sdb.read_frame(c)
        assert cmd == sdb.CNXN and a0 == 0x01000000 and a1 == 4096 and payload == b"host::sdb-net-client"
        if self.auth_key is not None:
            token = b"0123456789abcdefghij"
            self.send(c, sdb.AUTH, sdb.AUTH_TOKEN, 0, token)
            cmd, a0, _a1, sig = sdb.read_frame(c)
            assert cmd == sdb.AUTH and a0 == sdb.AUTH_SIGNATURE
            try:
                self.auth_key.key.public_key().verify(sig, token, padding.PKCS1v15(), hashes.SHA1())
                self.auth_ok = True
            except InvalidSignature:
                self.auth_ok = False
        self.send(c, sdb.CNXN, 0x01000000, 4096, b"device::fake-tv")
        while True:
            cmd, a0, a1, payload = sdb.read_frame(c)
            if cmd == sdb.OPEN:
                self._rid += 1
                self.channel(c, a0, self._rid, payload.decode())
            # CLSE ve fazladan OKAY'ler yok sayılır

    def send_data(self, c, rid, local, data):
        for off in range(0, len(data), 4096):
            self.send(c, sdb.WRTE, rid, local, data[off:off + 4096])
            cmd, a0, a1, _ = sdb.read_frame(c)
            assert cmd == sdb.OKAY and a0 == local and a1 == rid

    def channel(self, c, local, rid, service):
        self.send(c, sdb.OKAY, rid, local)
        assert service.endswith("\0")
        service = service[:-1]
        if service.startswith("shell:"):
            command = service[6:]
            self.commands.append(command)
            out = self.shell_handler(command).encode()
            self.send_data(c, rid, local, out)
            self.send(c, sdb.CLSE, rid, local)
        elif service == "capability:":
            body = "".join(f"{k}:{v}\n" for k, v in self.caps.items()).encode()
            self.send_data(c, rid, local, struct.pack("<H", len(body)) + body)
            self.send(c, sdb.CLSE, rid, local)
        elif service == "sync:":
            self.sync(c, local, rid)
        else:
            self.send(c, sdb.CLSE, rid, local)

    def sync(self, c, local, rid):
        buf = bytearray()
        path, data = None, bytearray()
        while True:
            cmd, a0, a1, payload = sdb.read_frame(c)
            assert cmd == sdb.WRTE and a0 == local and a1 == rid
            self.max_wrte = max(self.max_wrte, len(payload))
            buf += payload
            self.send(c, sdb.OKAY, rid, local)
            while len(buf) >= 8:
                ident = bytes(buf[:4]).decode()
                (n,) = struct.unpack("<I", buf[4:8])
                if len(buf) < 8 + n:
                    break
                if ident == "DONE":
                    # TizenSdb/CouchSubs biçimi: DONE + uzunluk 4 + mtime (küçük-endian)
                    assert n == 4
                    self.files[path] = bytes(data)
                    self.mtimes[path] = struct.unpack("<I", buf[8:12])[0]
                    del buf[:12]
                    reply = (b"FAIL" + struct.pack("<I", len(self.sync_fail)) + self.sync_fail.encode()
                             if self.sync_fail else b"OKAY" + struct.pack("<I", 0))
                    self.send(c, sdb.WRTE, rid, local, reply)
                    cmd, a0, a1, _ = sdb.read_frame(c)
                    assert cmd == sdb.OKAY
                    return
                chunk = bytes(buf[8:8 + n])
                del buf[:8 + n]
                if ident == "SEND":
                    path = chunk.decode()
                elif ident == "DATA":
                    assert n <= 64 * 1024
                    data += chunk

    def stop(self):
        self.srv.close()


# ============================================================================ sdb
def test_sdb_frame_roundtrip():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(sdb.encode(sdb.WRTE, 7, 9, b"merhaba"))
        assert sdb.read_frame(b) == (sdb.WRTE, 7, 9, b"merhaba")
        raw = bytearray(sdb.encode(sdb.OKAY, 1, 2, b"xy"))
        assert struct.unpack("<6I", raw[:24])[4] == ord("x") + ord("y")
        assert struct.unpack("<6I", raw[:24])[5] == sdb.OKAY ^ 0xFFFFFFFF
        raw[-1] ^= 1                       # bozuk veri: denetim toplamı tutmaz
        a.sendall(bytes(raw))
        with pytest.raises(sdb.SdbError):
            sdb.read_frame(b)


def test_sdb_handshake_shell_capability_and_push():
    key = sdb.AdbKey.generate()
    srv = FakeSdb(shell=lambda cmd: "ABCDEFGH12345678\n" if cmd == "0 getduid" else f"echo:{cmd}" * 1000,
                  caps={"platform_version": "6.5", "sdk_toolpath": "/home/owner/share/tmp/sdk_tools"}, auth_key=key)
    srv.start()
    try:
        with sdb.SdbConnection.connect("127.0.0.1", key, port=srv.port) as conn:
            assert conn.banner == "device::fake-tv" and conn.max_data == 4096
            assert conn.shell("0 getduid").strip() == "ABCDEFGH12345678"
            long = conn.shell("ls")                       # birden çok WRTE parçası
            assert long == "echo:ls" * 1000
            caps = conn.capability()
            assert caps == {"platform_version": "6.5", "sdk_toolpath": "/home/owner/share/tmp/sdk_tools"}
            data = bytes(range(256)) * 700                # 179200 bayt: birden çok DATA (64K) ve WRTE (4K)
            conn.push(data, "/opt/usr/apps/tmp/x.wgt", mtime=1234567)
            assert conn.shell("0 vd_applist").startswith("echo:")   # push sonrası bağlantı hâlâ çalışır
        assert srv.auth_ok is True
        assert srv.files["/opt/usr/apps/tmp/x.wgt"] == data
        assert srv.mtimes["/opt/usr/apps/tmp/x.wgt"] == 1234567
        assert srv.max_wrte <= 4096
        assert srv.commands == ["0 getduid", "ls", "0 vd_applist"]
        assert srv.error is None
    finally:
        srv.stop()


def test_sdb_push_fail_raises():
    srv = FakeSdb(sync_fail="No space left on device")
    srv.start()
    try:
        with sdb.SdbConnection.connect("127.0.0.1", port=srv.port) as conn:
            with pytest.raises(sdb.SdbError, match="No space"):
                conn.push(b"x" * 10, "/tmp/a.wgt")
    finally:
        srv.stop()


def test_sdb_connect_unreachable_retries():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()                                          # kimse dinlemiyor
    with pytest.raises(sdb.SdbError):
        sdb.SdbConnection.connect("127.0.0.1", port=port, timeout=1, attempts=2)


def test_adb_public_key_format():
    key = sdb.AdbKey.generate()
    blob = sdb.encode_public_key(key.key.public_key())
    assert len(blob) == 4 + 4 + 256 + 256 + 4
    words, n0inv = struct.unpack("<II", blob[:8])
    n = key.key.public_key().public_numbers().n
    assert words == 64 and (n * n0inv) % (1 << 32) == (1 << 32) - 1     # n0inv = -1/n mod 2^32
    assert int.from_bytes(blob[8:264], "little") == n
    payload = key.public_key_payload()
    assert payload.endswith(b" gta6altyazi@pc\0") and base64.b64decode(payload.split(b" ")[0]) == blob


# ============================================================================ imza
def _verify_signature_file(xml: bytes, files: dict[str, bytes], cert_chain: list[x509.Certificate],
                           expected_refs: list[str], role: str) -> None:
    text = xml.decode("utf-8")
    # Dosya zaten kanonik yazılmış olmalı (boşluk yok, öznitelikler sıralı, açık kapanışlı öğeler). C14N 2.0 ad alanı
    # bildirimlerini kullanıldıkları öğeye taşıdığından (#prop'taki xmlns:dsp) karşılaştırma Object olmadan yapılır.
    no_obj = re.sub(r"<Object Id=\"prop\">.*?</Object>", "", text)
    assert ET.canonicalize(xml_data=no_obj) == no_obj
    root = ET.fromstring(text)
    assert root.tag == DSIG + "Signature"
    si = root.find(DSIG + "SignedInfo")
    assert si.find(DSIG + "CanonicalizationMethod").get("Algorithm") == "http://www.w3.org/2001/10/xml-exc-c14n#"
    assert si.find(DSIG + "SignatureMethod").get("Algorithm") == "http://www.w3.org/2001/04/xmldsig-more#rsa-sha512"
    refs = si.findall(DSIG + "Reference")
    assert [r.get("URI") for r in refs] == expected_refs + ["#prop"]
    for r in refs[:-1]:
        want = base64.b64encode(hashlib.sha512(files[r.get("URI")]).digest()).decode()
        assert r.find(DSIG + "DigestValue").text == want
        assert r.find(DSIG + "DigestMethod").get("Algorithm") == "http://www.w3.org/2001/04/xmlenc#sha512"
    # #prop nesnesi: C14N 1.1 (kapsayıcı) -> üstten gelen varsayılan ad alanı nesnenin kendisine yazılır.
    obj = re.search(r"<Object Id=\"prop\">.*?</Object>", text).group(0)
    obj_c14n = obj.replace('<Object Id="prop">', '<Object xmlns="http://www.w3.org/2000/09/xmldsig#" Id="prop">', 1)
    assert refs[-1].find(DSIG + "DigestValue").text == base64.b64encode(hashlib.sha512(obj_c14n.encode()).digest()).decode()
    o = root.find(DSIG + "Object")
    props = {p.get("Id"): p for p in o.iter(DSIG + "SignatureProperty")}
    role_el = props["role"][0]
    assert role_el.get("URI") == f"http://www.w3.org/ns/widgets-digsig#role-{role}"
    assert props["profile"].get("Target") == "#" + root.get("Id")
    # Exclusive C14N: SignedInfo alt ağacı, kullandığı varsayılan ad alanıyla birlikte.
    si_text = re.search(r"<SignedInfo>.*?</SignedInfo>", text).group(0)
    si_c14n = si_text.replace("<SignedInfo>", '<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#">', 1)
    sig = base64.b64decode(root.find(DSIG + "SignatureValue").text)
    cert_chain[0].public_key().verify(sig, si_c14n.encode("utf-8"), padding.PKCS1v15(), hashes.SHA512())
    # KeyInfo: yaprak ve ara sertifika (76'lık satırlar)
    xcerts = root.find(DSIG + "KeyInfo").find(DSIG + "X509Data").findall(DSIG + "X509Certificate")
    assert [base64.b64decode(c.text) for c in xcerts] == [c.public_bytes(serialization.Encoding.DER) for c in cert_chain]
    assert all(len(line) <= 76 for c in xcerts for line in c.text.strip().split("\n"))


def test_signer_zip_order_digests_and_rsa(ca, tmp_path):
    key = _key()
    author = ca.issue(key.public_key(), "author")
    dist = ca.issue(key.public_key(), "distributor")
    chain_a = certs.chain(author, [ca.root, ca.intermediate])
    chain_d = certs.chain(dist, [ca.root, ca.intermediate])
    assert chain_a == [author, ca.intermediate]           # kök (kendinden imzalı) zincire konmaz
    app = tmp_path / "app"
    (app / "js").mkdir(parents=True)
    (app / "config.xml").write_text('<widget version="1.2.3"/>')
    (app / "index.html").write_text("<html>merhaba</html>")
    (app / "js" / "app.js").write_bytes(b"console.log(1)\n" * 100)
    (app / "eski.wgt").write_bytes(b"atlanmali")
    entries = signer.folder_entries(app)
    assert [n for n, _ in entries] == ["config.xml", "index.html", "js/app.js"]
    wgt = signer.sign(entries, signer.Signer(key, chain_a), signer.Signer(key, chain_d))
    with zipfile.ZipFile(io.BytesIO(wgt)) as z:
        names = z.namelist()
        files = {n: z.read(n) for n in names}
    assert names == ["author-signature.xml", "signature1.xml", "config.xml", "index.html", "js/app.js"]
    plain = ["config.xml", "index.html", "js/app.js"]
    _verify_signature_file(files["author-signature.xml"], files, chain_a, plain, "author")
    _verify_signature_file(files["signature1.xml"], files, chain_d, ["author-signature.xml", *plain], "distributor")
    assert ET.fromstring(files["author-signature.xml"]).get("Id") == "AuthorSignature"
    assert ET.fromstring(files["signature1.xml"]).get("Id") == "DistributorSignature"
    # yeniden imzalama: eski imza dosyaları atılır
    again = signer.zip_entries(wgt)
    assert [n for n, _ in again] == plain


def test_signature_tamper_detected(ca):
    key = _key()
    leaf = ca.issue(key.public_key())
    files = [("index.html", b"a")]
    xml = signer.signature("AuthorSignature", files, signer.Signer(key, [leaf])).decode()
    tampered = xml.replace(base64.b64encode(hashlib.sha512(b"a").digest()).decode(),
                           base64.b64encode(hashlib.sha512(b"b").digest()).decode())
    si = re.search(r"<SignedInfo>.*?</SignedInfo>", tampered).group(0)
    si = si.replace("<SignedInfo>", '<SignedInfo xmlns="http://www.w3.org/2000/09/xmldsig#">', 1)
    sig = base64.b64decode(re.search(r"<SignatureValue>(.*?)</SignatureValue>", tampered).group(1))
    with pytest.raises(InvalidSignature):
        leaf.public_key().verify(sig, si.encode(), padding.PKCS1v15(), hashes.SHA512())


def test_bundled_samsung_ca_files_load():
    cas = certs.authorities()
    assert len(cas) == 4
    names = {c.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value for c in cas}
    assert "VD DEVELOPER Public CA Class" in names and "Samsung VD Author CA" in names


# ============================================================================ sertifika istekleri
def test_distributor_csr_san_exact_case():
    key = _key()
    duid = "ABCDEFGH12345678XYZ"
    pem = certs.distributor_csr(key, duid, "oyuncu@example.com")
    csr = x509.load_pem_x509_csr(pem)
    assert csr.is_signature_valid
    assert isinstance(csr.signature_hash_algorithm, hashes.SHA256)
    assert csr.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "TizenSDK"
    assert csr.subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)[0].value == "oyuncu@example.com"
    ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
    assert ext.critical is False
    assert ext.value.get_values_for_type(x509.UniformResourceIdentifier) == [
        "URN:tizen:packageid=", f"URN:tizen:deviceid={duid}"]
    der = csr.public_bytes(serialization.Encoding.DER)
    # IA5String, [6] (uniformResourceIdentifier) etiketiyle ve büyük harfler korunarak
    assert b"\x86\x14URN:tizen:packageid=" in der
    assert b"URN:tizen:deviceid=" + duid.encode() in der
    a = x509.load_pem_x509_csr(certs.author_csr(key))
    assert a.is_signature_valid and isinstance(a.signature_hash_algorithm, hashes.SHA256)
    assert a.public_key().public_numbers() == csr.public_key().public_numbers()     # aynı anahtar


def test_distributor_csr_without_email():
    csr = x509.load_pem_x509_csr(certs.distributor_csr(_key(), "DUID1234", ""))
    assert not csr.subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)


def test_multipart_fields():
    acc = certs.SamsungAccount("tok", "uid", "e@x")
    ctype, body = certs.multipart(certs.request_fields(acc, True), "csr", "distributor.csr", b"CSRDATA", boundary="BB")
    assert ctype == "multipart/form-data; boundary=BB"
    text = body.decode()
    for name, value in [("access_token", "tok"), ("user_id", "uid"), ("platform", "VD"),
                        ("privilege_level", "public"), ("developer_type", "Individual")]:
        assert f'name="{name}"\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n{value}\r\n' in text
    assert 'name="csr"; filename="distributor.csr"' in text and text.endswith("CSRDATA\r\n--BB--\r\n")
    _, body = certs.multipart(certs.request_fields(acc, False), "csr", "author.csr", b"X")
    assert b"privilege_level" not in body


def test_server_error_text():
    assert certs.server_error(b'{"code": 401, "message": "invalid token"}') == "code=401, message=invalid token"
    assert certs.server_error(b"  oops  ") == "oops"


def test_profile_validity_and_cache(ca, tmp_path):
    key = _key()
    prof = certs.SigningProfile(tmp_path / "p")
    assert not prof.exists and not prof.is_valid()
    prof.save(key, ca.issue(key.public_key()), ca.issue(key.public_key()), b"<p/>", "DUID1234")
    assert prof.is_valid() and prof.is_for("DUID1234") and not prof.is_for("BASKA")
    assert prof.private_key().public_key().public_numbers() == key.public_key().public_numbers()
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=365)
    assert not prof.is_valid(later)                  # süresi (bir gün payla) dolmuş
    prof.discard()
    assert not prof.exists and list(tmp_path.glob("p.rejected-*"))


# ============================================================================ giriş
def test_login_url():
    url = login.authorize_url()
    assert url == ("https://account.samsung.com/accounts/be1dce529476c1a6d407c4c7578c31bd/signInGate?locale="
                   "&clientId=v285zxnl3h&redirect_uri=http%3A%2F%2Flocalhost%3A4794%2Fsignin%2Fcallback"
                   "&state=accountcheckdogeneratedstatetext&tokenType=TOKEN")


def test_login_callback_parser():
    code = json.dumps({"access_token": "a+b/c=", "userId": "u123", "inputEmailID": "ben@example.com"})
    body = urlencode({"code": code, "state": login.STATE}, quote_via=quote)
    acc = login.parse_callback(body)
    assert acc == certs.SamsungAccount("a+b/c=", "u123", "ben@example.com")
    # tarayıcının form kodlaması (boşluk '+') ve e-postasız yanıt
    body2 = "code=" + quote(json.dumps({"access_token": "t", "userId": "u"})) + "&state=" + login.STATE
    assert login.parse_callback(body2) == certs.SamsungAccount("t", "u", "")
    assert login.parse_callback(body.replace(login.STATE, "baska")) is None
    assert login.parse_callback("code=" + quote(json.dumps({"access_token": "t"})) + "&state=" + login.STATE) is None
    assert login.parse_callback("code=bozuk&state=" + login.STATE) is None
    assert login.parse_callback("") is None
    problem = login.callback_problem("error=access_denied&code=GIZLI&state=x")
    assert "error=access_denied" in problem and "GIZLI" not in problem


def test_login_listener_receives_callback():
    lst = login.Listener(port=0)
    port = lst.socks[0].getsockname()[1]
    replies = []

    def browser():
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("GET", "/favicon.ico")
        replies.append(c.getresponse().status)
        c.close()
        body = urlencode({"code": json.dumps({"access_token": "tok", "userId": "uid", "inputEmailID": "e@x"}),
                          "state": login.STATE})
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.request("POST", "/signin/callback", body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = c.getresponse()
        replies.append((r.status, r.read().decode("utf-8")))
        c.close()

    t = threading.Thread(target=browser)
    t.start()
    acc = lst.wait(10)
    t.join(5)
    assert acc == certs.SamsungAccount("tok", "uid", "e@x")
    assert replies[0] == 404 and replies[1][0] == 200 and "Samsung girişi tamam" in replies[1][1]
    assert lst.socks == []                               # dinleyici kapandı


def test_login_listener_timeout_message():
    lst = login.Listener(port=0)
    with pytest.raises(SamsungInstallError, match="giriş"):
        lst.wait(0.3)


def test_sign_in_opens_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(login.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(login.Listener, "wait", lambda self, timeout, cancel=None: (self.close(), "ok")[1])
    assert login.sign_in(port=0, timeout=1) == "ok"
    assert opened and opened[0].startswith(login.SIGN_IN_GATE)


# ============================================================================ tanı
SUCCESS = f"Push complete.\napp_id[{APP}] installing[100]\nspend time for pkgcmd is [1234]ms\ncmd_ret:0"
MISMATCH = (f"app_id[{APP}] install failed[118, -12]\nreason: Check certificate error : :Package with the same id "
            "and different certificate has been already installed.:<-12>\ncmd_ret:0")
INVALID = (f"app_id[{APP}] install failed[118, -12]\nreason: Check certificate error : :Invalid format of "
           "certificate in signature.:<-2>")


@pytest.mark.parametrize("output, problem, kind", [
    (SUCCESS, diag.NONE, None),
    (MISMATCH, diag.CERTIFICATE_MISMATCH, diag.CERTIFICATE_MISMATCH),
    (f"app_id[{APP}] install failed[118, -11], reason: Author certificate not match :", diag.CERTIFICATE_MISMATCH,
     diag.CERTIFICATE_MISMATCH),
    ("install failed[118012]", diag.CERTIFICATE_MISMATCH, diag.CERTIFICATE_MISMATCH),
    (INVALID, diag.CERTIFICATE_REJECTED, diag.CERTIFICATE_REJECTED),
    ("install failed[118, -12] Check certificate error : :Certificate in signature is expired.:<-6>",
     diag.CERTIFICATE_REJECTED, diag.CERTIFICATE_REJECTED),
    ("install failed[118, -12] Check certificate error : :Certificate in signature is not valid yet.:<-7>",
     diag.CERTIFICATE_NOT_YET_VALID, diag.TV_CLOCK_WRONG),
    (f"app_id[{APP}] install failed[118, -22]\nreason: Security error", diag.PACKAGE_BLOCKED, diag.PACKAGE_BLOCKED),
    ("install failed[118022]", diag.PACKAGE_BLOCKED, diag.PACKAGE_BLOCKED),
    (f"app_id[{APP}] download failed[116]", diag.NOT_ENOUGH_SPACE, diag.NOT_ENOUGH_SPACE),
    ("install failed[118, -4] operation not allowed", diag.INCOMPATIBLE, diag.INCOMPATIBLE),
    ("install failed[118, -19]", diag.INCOMPATIBLE, diag.INCOMPATIBLE),
    ("error: transport connection closed", diag.CONNECTION_LOST, diag.CONNECTION_LOST),
    ("install failed: OSError: Remote closed channel", diag.OTHER, diag.INSTALL_FAILED),
    ("Pull skipped or failed: not found\ninstalling[100]", diag.NONE, None),
])
def test_install_error_mapping(output, problem, kind):
    assert diag.classify(output) == problem
    err = diag.error_for(output)
    if kind is None:
        assert err is None
    else:
        assert err.kind == kind and isinstance(err, tv_samsung.SamsungError)
        assert str(err).startswith(diag.MESSAGES[kind])


def test_turkish_messages():
    assert "saat" in str(SamsungInstallError(diag.TV_CLOCK_WRONG)).lower()
    assert "Host PC IP" in str(SamsungInstallError(diag.UNREACHABLE))
    assert "boş yer" in str(SamsungInstallError(diag.NOT_ENOUGH_SPACE))
    assert "[ayrıntı]" in str(SamsungInstallError(diag.INSTALL_FAILED, "ayrıntı"))


def test_installed_version_and_versions():
    rule = "\t" + "-" * 72
    listing = "\n".join(["\tApplication List for user 5001", rule,
                         "\t-------------app_tizen_id  =  AprZAARz4r.Jellyfin-----------------",
                         "\t-------------app_version  =  1.2.3-----------------------------", rule,
                         f"\t-------------app_tizen_id  =  {APP}----------------",
                         "\t-------------app_version  =  0.4.0-----------------------------", rule,
                         "\tapps count: 2"])
    assert diag.installed_version(listing) == "0.4.0"
    assert diag.installed_version(listing.replace(APP, "Baska.App")) is None
    assert diag.installed_version(None) is None
    assert diag.is_newer("0.10.0", "0.9.9") and not diag.is_newer("0.4.0", "0.4.0")
    assert installer.is_too_old("2.3.1") and not installer.is_too_old("2.4") and not installer.is_too_old("")
    assert installer.needs_device_profile("3.0") and installer.needs_device_profile("4.0.0")
    assert not installer.needs_device_profile("5.0") and not installer.needs_device_profile("")


def test_install_with_recovery():
    outputs = iter([MISMATCH, SUCCESS])
    shell = []
    installer.install_with_recovery(lambda: next(outputs), lambda c: shell.append(c) or "ok")
    assert shell == ["0 vd_appuninstall GTA6Altyzi", f"0 vd_appuninstall {APP}"]
    shell.clear()
    with pytest.raises(SamsungInstallError) as e:
        installer.install_with_recovery(lambda: INVALID, lambda c: shell.append(c) or "")
    assert e.value.kind == diag.CERTIFICATE_REJECTED and shell == []       # kaldırmak işe yaramaz
    with pytest.raises(SamsungInstallError) as e:
        installer.install_with_recovery(lambda: MISMATCH, lambda c: "")
    assert e.value.kind == diag.CERTIFICATE_MISMATCH


# ============================================================================ uçtan uca (sahte TV + sahte Samsung)
class FakeSamsungCA:
    """Samsung'un sertifika sunucusu gibi: CSR'yi alır, test CA'sıyla imzalanmış sertifika döner."""

    def __init__(self, ca: FakeCA, pem: bool = True):
        self.ca = ca
        self.pem = pem
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, content_type, body):
        boundary = content_type.split("boundary=")[1].encode()
        fields = {}
        for part in body.split(b"--" + boundary)[1:-1]:
            head, _, value = part.strip(b"\r\n").partition(b"\r\n\r\n")
            name = re.search(rb'name="([^"]+)"', head).group(1).decode()
            fields[name] = value
        self.calls.append((url, fields))
        if url.endswith("/v1/distributors"):
            return certs.HttpReply(200, "OK", b"<profile duid='x'/>")
        csr = x509.load_pem_x509_csr(fields["csr"])
        cert = self.ca.issue(csr.public_key(), "issued")
        enc = serialization.Encoding.PEM if self.pem else serialization.Encoding.DER
        return certs.HttpReply(200, "OK", cert.public_bytes(enc))


class FakeTv:
    def __init__(self, install_outputs=None, platform="6.0", duid="FAKEDUID0001"):
        self.version = None
        self.duid = duid
        self.outputs = list(install_outputs or [SUCCESS])
        self.server = FakeSdb(shell=self.shell, caps={"platform_version": platform,
                                                      "sdk_toolpath": "/opt/usr/apps/tmp"})

    def shell(self, cmd):
        if cmd == "0 getduid":
            return self.duid + "\n"
        if cmd == "0 vd_applist":
            if not self.version:
                return "\tapps count: 0"
            return f"\t----\n\t---app_tizen_id = {APP}---\n\t---app_version = {self.version}---\n\t----\n"
        if cmd.startswith("0 vd_appinstall"):
            out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
            if diag.classify(out) == diag.NONE:
                self.version = "0.4.0"
            return out
        return "ok"


@pytest.fixture
def app_dir(tmp_path):
    d = tmp_path / "tizen"
    d.mkdir()
    (d / "config.xml").write_text('<widget xmlns="http://www.w3.org/ns/widgets" version="0.4.0"/>')
    (d / "index.html").write_text("<html></html>")
    (d / "app.js").write_text("var a = 1;")
    return d


def test_setup_direct_end_to_end(ca, app_dir, tmp_path, monkeypatch):
    tv = FakeTv(platform="4.0")
    tv.server.start()
    samsung = FakeSamsungCA(ca)
    logins, needed = [], []

    def fake_login():
        logins.append(1)
        return certs.SamsungAccount("tok", "uid", "ben@example.com")

    monkeypatch.setattr(certs, "authorities", lambda: [ca.root, ca.intermediate])
    data = tmp_path / "data"
    try:
        ip = installer.setup_direct("127.0.0.1", needed.append, port=tv.server.port, source=app_dir, data_dir=data,
                                    sign_in=fake_login, http=samsung)
        assert ip == "127.0.0.1"
        assert logins == [1] and needed and needed[0].startswith(login.SIGN_IN_GATE)
        # Samsung'a üç istek: yazar (v3), cihaz profili (v1), dağıtıcı (v3)
        assert [u.rsplit("/apis/", 1)[1] for u, _ in samsung.calls] == ["v3/authors", "v1/distributors",
                                                                         "v3/distributors"]
        a_fields, d_fields = samsung.calls[0][1], samsung.calls[2][1]
        assert a_fields["access_token"] == b"tok" and a_fields["user_id"] == b"uid" and a_fields["platform"] == b"VD"
        assert "privilege_level" not in a_fields and d_fields["privilege_level"] == b"public"
        assert d_fields["developer_type"] == b"Individual"
        dcsr = x509.load_pem_x509_csr(d_fields["csr"])
        assert dcsr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(
            x509.UniformResourceIdentifier)[1] == "URN:tizen:deviceid=FAKEDUID0001"
        # Tizen 4.0: cihaz profili gönderildi; paket gönderildi, kuruldu ve açıldı
        assert tv.server.files["/opt/usr/apps/tmp/device-profile.xml"] == b"<profile duid='x'/>"
        wgts = [p for p in tv.server.files if p.endswith(".wgt")]
        assert len(wgts) == 1 and wgts[0].startswith("/opt/usr/apps/tmp/gta6altyazi-")
        cmds = tv.server.commands
        assert f"0 vd_appinstall {APP} {wgts[0]}" in cmds and cmds[-1] == f"0 was_execute {APP}"
        with zipfile.ZipFile(io.BytesIO(tv.server.files[wgts[0]])) as z:
            names = z.namelist()
            files = {n: z.read(n) for n in names}
        assert names[:2] == ["author-signature.xml", "signature1.xml"]
        prof = certs.SigningProfile(data / "FAKEDUID0001")
        assert prof.is_valid() and prof.is_for("FAKEDUID0001")
        _verify_signature_file(files["signature1.xml"], files, [prof.distributor(), ca.intermediate],
                               ["author-signature.xml", "app.js", "config.xml", "index.html"], "distributor")
        assert certs.SamsungAccount.load(data / "account.json") == certs.SamsungAccount("tok", "uid", "ben@example.com")

        # İkinci kez: kayıtlı sertifika kullanılır, giriş ve Samsung isteği yok; zorlanmazsa yalnız açılır
        tv.server.commands.clear()
        installer.setup_direct("127.0.0.1", port=tv.server.port, source=app_dir, data_dir=data, sign_in=fake_login,
                               http=samsung, force_install=False)
        assert logins == [1] and len(samsung.calls) == 3
        assert tv.server.commands == ["0 vd_applist", f"0 was_execute {APP}"]
        installer.setup_direct("127.0.0.1", port=tv.server.port, source=app_dir, data_dir=data, sign_in=fake_login,
                               http=samsung, force_install=True)
        assert logins == [1] and len(samsung.calls) == 3
        assert tv.server.error is None
    finally:
        tv.server.stop()


def test_setup_direct_reuses_cached_account_then_relogins(ca, app_dir, tmp_path, monkeypatch):
    tv = FakeTv()
    tv.server.start()
    monkeypatch.setattr(certs, "authorities", lambda: [ca.root, ca.intermediate])
    data = tmp_path / "data"
    certs.SamsungAccount("eski", "uid", "").save(data / "account.json")
    good = FakeSamsungCA(ca, pem=False)                   # DER yanıt da okunur

    def http(url, ctype, body):
        if b"eski" in body:
            return certs.HttpReply(401, "Unauthorized", b'{"message": "token expired"}')
        return good(url, ctype, body)

    logins = []
    try:
        installer.setup_direct("127.0.0.1", port=tv.server.port, source=app_dir, data_dir=data,
                               sign_in=lambda: logins.append(1) or certs.SamsungAccount("yeni", "uid", ""), http=http)
        assert logins == [1]
        assert certs.SamsungAccount.load(data / "account.json").access_token == "yeni"
    finally:
        tv.server.stop()


def test_setup_direct_certificate_rejected_discards_profile(ca, app_dir, tmp_path, monkeypatch):
    tv = FakeTv(install_outputs=[INVALID])
    tv.server.start()
    monkeypatch.setattr(certs, "authorities", lambda: [ca.root, ca.intermediate])
    data = tmp_path / "data"
    try:
        with pytest.raises(SamsungInstallError) as e:
            installer.setup_direct("127.0.0.1", port=tv.server.port, source=app_dir, data_dir=data,
                                   sign_in=lambda: certs.SamsungAccount("t", "u", ""), http=FakeSamsungCA(ca))
        assert e.value.kind == diag.CERTIFICATE_REJECTED and "kabul etmedi" in str(e.value)
        assert not (data / "FAKEDUID0001").exists() and list(data.glob("FAKEDUID0001.rejected-*"))
        assert not any(c.startswith("0 vd_appuninstall") for c in tv.server.commands)
    finally:
        tv.server.stop()


def test_setup_direct_errors(app_dir, tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    with pytest.raises(SamsungInstallError) as e:
        installer.setup_direct("127.0.0.1", port=port, source=app_dir, data_dir=tmp_path / "d")
    assert e.value.kind == diag.UNREACHABLE and "Developer mode" in str(e.value)
    with pytest.raises(SamsungInstallError) as e:
        installer.setup_direct("127.0.0.1", port=port, source=tmp_path / "yok", data_dir=tmp_path / "d")
    assert e.value.kind == diag.NO_PACKAGE
    tv = FakeTv(platform="2.3")
    tv.server.start()
    try:
        with pytest.raises(SamsungInstallError) as e:
            installer.setup_direct("127.0.0.1", port=tv.server.port, source=app_dir, data_dir=tmp_path / "d")
        assert e.value.kind == diag.TOO_OLD
    finally:
        tv.server.stop()


def test_package_version_of_real_config():
    cfg = Path(__file__).resolve().parents[1] / "tv-web" / "tizen" / "config.xml"
    assert installer.package_version(cfg.parent)
    root = ET.parse(cfg).getroot()
    app = root.find("{http://tizen.org/ns/widgets}application")
    assert app.get("id") == APP and app.get("package") == diag.PACKAGE_ID


# ============================================================================ uygulamadaki seçim
def test_app_dispatches_samsung_direct_or_tizen_studio(tmp_path, monkeypatch):
    pytest.importorskip("PySide6.QtWidgets")
    import os
    import time
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("ALTYAZI_DATA", str(tmp_path))
    from PySide6.QtWidgets import QApplication

    import altyazi.samsung
    from altyazi import config as config_mod
    from altyazi.app import AppController
    QApplication.instance() or QApplication([])
    monkeypatch.setattr(AppController, "warmup", lambda self: None)
    calls = []

    def fake_direct(host, on_login_needed=None, **kw):
        calls.append(("direct", host, kw["force_install"]))
        on_login_needed("https://example")
        return "10.0.0.2"

    monkeypatch.setattr(altyazi.samsung, "setup_direct", fake_direct)
    monkeypatch.setattr(tv_samsung, "setup", lambda host, profile, root="": calls.append(("studio", host, root))
                        or "10.0.0.3")
    cfg = config_mod.load()
    cfg.sunucu.port = 18789
    cfg.tv.marka = "samsung"
    c = AppController(cfg)
    states = []
    c.tvStatus.connect(lambda s, m: states.append((s, m)))
    try:
        for root in ("", r"C:\tizen-studio"):
            c.cfg.tv.tizen_yolu = root
            n = len(calls)
            c.tv_connect("192.168.1.50", force_install=True)
            deadline = time.time() + 15
            while (len(calls) == n or c.tv_state[0] in ("baglaniyor", "onay")) and time.time() < deadline:
                QApplication.processEvents()
                time.sleep(0.02)
            assert c.tv_state[0] == "bagli", c.tv_state
            for _ in range(10):                 # iş parçacığından gelen sinyaller kuyruktan teslim edilsin
                QApplication.processEvents()
                time.sleep(0.01)
        assert calls == [("direct", "192.168.1.50", True), ("studio", "192.168.1.50", r"C:\tizen-studio")]
        assert any(s == "onay" and "Samsung" in m for s, m in states)
    finally:
        c._src_timer.stop()
        c._ps5_timer.stop()
