# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""Samsung'dan TV'ye özel imza sertifikası alır ve TV (DUID) başına saklar.

Yazar sertifikası Samsung hesabına, dağıtıcı sertifikası TV'nin DUID'ine bağlıdır; Tizen Studio'nun Certificate
Manager'ının yaptığının aynısı. Uç noktalar ve istek biçimleri Apps2Samsung'dan.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import shutil
import ssl
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .diagnostics import CERTIFICATE_FAILED, SamsungInstallError

log = logging.getLogger(__name__)

AUTHOR_URL = "https://svdca.samsungqbe.com/apis/v3/authors"
DISTRIBUTOR_PROFILE_URL = "https://svdca.samsungqbe.com/apis/v1/distributors"
DISTRIBUTOR_URL = "https://svdca.samsungqbe.com/apis/v3/distributors"
CA_DIR = Path(__file__).resolve().parent / "ca"
CA_NAMES = ("vd_tizen_dev_author_ca", "author_ca", "vd_tizen_dev_public2", "public2")
DAY = dt.timedelta(days=1)


@dataclass
class SamsungAccount:
    """Samsung hesabıyla girişten dönen bilgiler; sertifika istemek için gerekir."""
    access_token: str
    user_id: str
    email: str = ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self)), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SamsungAccount | None:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            if d.get("access_token") and d.get("user_id"):
                return cls(d["access_token"], d["user_id"], d.get("email", ""))
        except (OSError, ValueError, AttributeError):
            pass
        return None


# ----------------------------------------------------------------------------- sertifikalar
def read_certificate(data: bytes) -> x509.Certificate:
    """PEM ya da DER sertifika."""
    if b"-----BEGIN" in data:
        return x509.load_pem_x509_certificate(data)
    return x509.load_der_x509_certificate(data)


_authorities: list[x509.Certificate] | None = None


def authorities() -> list[x509.Certificate]:
    """Samsung'un geliştirici sertifikalarını veren ara sertifikalar (Tizen Studio'dan, değiştirilmeden)."""
    global _authorities
    if _authorities is None:
        out = []
        for name in CA_NAMES:
            try:
                out.append(read_certificate((CA_DIR / f"{name}.pem").read_bytes()))
            except (OSError, ValueError):
                log.warning("Samsung ara sertifikası okunamadı: %s", name)
        _authorities = out
    return _authorities


def chain(leaf: x509.Certificate, cas: list[x509.Certificate] | None = None) -> list[x509.Certificate]:
    """İmzadaki zincir: yaprak ve onu veren Samsung ara sertifikası (kök yok)."""
    for ca in authorities() if cas is None else cas:
        # Ad nesneleri karşılaştırılır (aynı ad farklı ASN.1 dizgi türüyle yazılmış olabilir).
        if _same_name(ca.subject, leaf.issuer) and not _same_name(ca.subject, ca.issuer) and _issued_by(leaf, ca):
            return [leaf, ca]
    return [leaf]


def _issued_by(leaf: x509.Certificate, ca: x509.Certificate) -> bool:
    """Aynı adlı iki Samsung ara sertifikası var (farklı anahtar): imzayı gerçekten atanı seç."""
    try:
        leaf.verify_directly_issued_by(ca)
        return True
    except (ValueError, TypeError, AttributeError):
        return False
    except Exception:  # noqa: BLE001 (InvalidSignature vb.)
        return False


def _same_name(a: x509.Name, b: x509.Name) -> bool:
    return a.rfc4514_string() == b.rfc4514_string()


def _utc(c: x509.Certificate, attr: str) -> dt.datetime:
    v = getattr(c, attr + "_utc", None)
    if v is None:  # eski cryptography
        v = getattr(c, attr).replace(tzinfo=dt.timezone.utc)
    return v


def valid_at(c: x509.Certificate, now: dt.datetime) -> bool:
    """Bir gün pay bırakılarak geçerli mi (bu bilgisayarın saati Samsung'unkinden biraz geride olabilir)."""
    margin = now + DAY
    return _utc(c, "not_valid_before") <= margin <= _utc(c, "not_valid_after")


# ----------------------------------------------------------------------------- CSR
def author_csr(key: rsa.RSAPrivateKey, name: str = "GTA6Altyazi") -> bytes:
    """Yazar sertifikası isteği (CN önemli değil), SHA-256."""
    req = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
           .sign(key, hashes.SHA256()))
    return req.public_bytes(serialization.Encoding.PEM)


def distributor_csr(key: rsa.RSAPrivateKey, duid: str, email: str) -> bytes:
    """Dağıtıcı isteği: CN=TizenSDK (ve hesabın e-postası), SAN'da paket ve TV kimliği. TV imzayı yalnız kendi DUID'i
    sertifikada yazılıysa kabul eder; adlar olduğu gibi (büyük harfle) URI olarak yazılır."""
    attrs = [x509.NameAttribute(NameOID.COMMON_NAME, "TizenSDK")]
    if email.strip():
        attrs.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, email.strip()))
    san = x509.SubjectAlternativeName([x509.UniformResourceIdentifier("URN:tizen:packageid="),
                                       x509.UniformResourceIdentifier(f"URN:tizen:deviceid={duid}")])
    req = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name(attrs))
           .add_extension(san, critical=False)
           .sign(key, hashes.SHA256()))
    return req.public_bytes(serialization.Encoding.PEM)


# ----------------------------------------------------------------------------- HTTP
@dataclass
class HttpReply:
    status: int
    reason: str
    body: bytes


HttpPost = Callable[[str, str, bytes], HttpReply]


def multipart(fields: list[tuple[str, str]], file_field: str, file_name: str, data: bytes,
              boundary: str | None = None) -> tuple[str, bytes]:
    """multipart/form-data gövdesi: (content-type, gövde)."""
    b = boundary or "gta6altyazi-" + uuid.uuid4().hex
    out = bytearray()
    for name, value in fields:
        out += (f'--{b}\r\nContent-Disposition: form-data; name="{name}"\r\n'
                "Content-Type: text/plain; charset=utf-8\r\n\r\n").encode()
        out += value.encode("utf-8") + b"\r\n"
    out += (f'--{b}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n").encode()
    out += data + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return f"multipart/form-data; boundary={b}", bytes(out)


def request_fields(account: SamsungAccount, distributor: bool) -> list[tuple[str, str]]:
    fields = [("access_token", account.access_token), ("user_id", account.user_id), ("platform", "VD")]
    if distributor:
        fields += [("privilege_level", "public"), ("developer_type", "Individual")]
    return fields


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    try:  # paketlenmiş sürümde Windows sertifika deposu yetmezse certifi
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:  # noqa: BLE001
        pass
    return ctx


def urllib_post(url: str, content_type: str, body: bytes) -> HttpReply:
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": content_type, "User-Agent": "GTA6Altyazi"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=_ssl_context()) as r:
            return HttpReply(r.status, r.reason or "", r.read())
    except urllib.error.HTTPError as e:
        return HttpReply(e.code, str(e.reason or ""), e.read() or b"")


def server_error(body: bytes) -> str:
    """Samsung'un hata yanıtı: JSON ise iletisi ve kodu, değilse metnin başı."""
    text = body.decode("utf-8", "replace").strip()
    try:
        d = json.loads(text)
        if isinstance(d, dict):
            parts = [f"{k}={d[k]}" for k in ("code", "errorCode", "error", "message", "errorMessage",
                                              "error_description") if isinstance(d.get(k), (str, int, float))]
            if parts:
                return ", ".join(parts)
    except ValueError:
        pass
    return text if len(text) <= 300 else text[:300] + "…"


# ----------------------------------------------------------------------------- profil
class SigningProfile:
    """Bir TV için imza dosyaları: anahtar (PKCS#8 PEM), sertifikalar (DER), cihaz profili ve DUID."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.key_file = directory / "key.pem"
        self.author_file = directory / "author.cer"
        self.distributor_file = directory / "distributor.cer"
        self.device_profile_file = directory / "device-profile.xml"
        self.duid_file = directory / "duid.txt"

    @property
    def exists(self) -> bool:
        return self.key_file.exists() and self.author_file.exists() and self.distributor_file.exists()

    def private_key(self) -> rsa.RSAPrivateKey:
        key = serialization.load_pem_private_key(self.key_file.read_bytes(), password=None)
        assert isinstance(key, rsa.RSAPrivateKey)
        return key

    def author(self) -> x509.Certificate:
        return read_certificate(self.author_file.read_bytes())

    def distributor(self) -> x509.Certificate:
        return read_certificate(self.distributor_file.read_bytes())

    def is_valid(self, now: dt.datetime | None = None) -> bool:
        if not self.exists:
            return False
        now = now or dt.datetime.now(dt.timezone.utc)
        try:
            return valid_at(self.author(), now) and valid_at(self.distributor(), now)
        except (OSError, ValueError):
            return False

    def is_for(self, duid: str) -> bool:
        try:
            return not self.duid_file.exists() or self.duid_file.read_text().strip() == duid
        except OSError:
            return False

    def describe(self, duid: str) -> str:
        if not self.exists:
            return "yok"
        try:
            a, d = self.author(), self.distributor()
            state = "başka TV'nin" if not self.is_for(duid) else "geçerli" if self.is_valid() else "süresi dolmuş"
            fmt = "%Y-%m-%d"
            return (f"{state}; yazar {_utc(a, 'not_valid_before'):{fmt}}–{_utc(a, 'not_valid_after'):{fmt}}, "
                    f"dağıtıcı {_utc(d, 'not_valid_before'):{fmt}}–{_utc(d, 'not_valid_after'):{fmt}} "
                    f"({d.issuer.rfc4514_string()})")
        except (OSError, ValueError) as e:
            return f"okunamadı ({e})"

    def save(self, key: rsa.RSAPrivateKey, author: x509.Certificate, distributor: x509.Certificate,
             device_profile: bytes, duid: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self.key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()))
        self.author_file.write_bytes(author.public_bytes(serialization.Encoding.DER))
        self.distributor_file.write_bytes(distributor.public_bytes(serialization.Encoding.DER))
        self.device_profile_file.write_bytes(device_profile)
        self.duid_file.write_text(duid)

    def discard(self) -> None:
        """TV'nin reddettiği sertifikayı bir kenara koyar; bir sonraki kurulum Samsung'dan yenisini ister."""
        if not self.directory.exists():
            return
        stamp = time.strftime("%Y%m%d%H%M%S")
        try:
            self.directory.rename(self.directory.with_name(f"{self.directory.name}.rejected-{stamp}"))
        except OSError:
            shutil.rmtree(self.directory, ignore_errors=True)


def safe_name(duid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "_", duid)


# ----------------------------------------------------------------------------- istek
def _post(http: HttpPost, url: str, account: SamsungAccount, csr: bytes, file_name: str, distributor: bool) -> bytes:
    step = url.split("svdca.samsungqbe.com", 1)[-1]
    content_type, body = multipart(request_fields(account, distributor), "csr", file_name, csr)
    try:
        reply = http(url, content_type, body)
    except OSError as e:
        err = SamsungInstallError(CERTIFICATE_FAILED, f"sertifika sunucusuna ulaşılamadı ({step}): {e}")
        err.network = True     # giriş yenilemek işe yaramaz
        raise err from e
    log.info("Samsung sertifika sunucusu %s: %s %s, %d bayt", step, reply.status, reply.reason, len(reply.body))
    if not 200 <= reply.status < 300:
        raise SamsungInstallError(CERTIFICATE_FAILED, f"{step}: {reply.status} {reply.reason} "
                                                      f"{server_error(reply.body)}".strip())
    return reply.body


def _issued(data: bytes, kind: str) -> x509.Certificate:
    """Samsung bazen başarılı yanıtın içinde sertifika yerine hata metni döndürür."""
    try:
        return read_certificate(data)
    except ValueError as e:
        raise SamsungInstallError(CERTIFICATE_FAILED, f"Samsung {kind} sertifikası vermedi: {server_error(data)}") from e


def create(duid: str, account: SamsungAccount, profile: SigningProfile, http: HttpPost = urllib_post) -> SigningProfile:
    """Samsung'dan sertifikaları alır ve ``profile`` klasörüne yazar."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    a_csr = author_csr(key)
    d_csr = distributor_csr(key, duid, account.email)
    author = _issued(_post(http, AUTHOR_URL, account, a_csr, "author.csr", False), "yazar")
    # Eski TV'ler (Tizen 4 ve öncesi) için cihaz profili; yenilerde kullanılmaz ama saklanır.
    device_profile = _post(http, DISTRIBUTOR_PROFILE_URL, account, d_csr, "distributor.csr", True)
    distributor = _issued(_post(http, DISTRIBUTOR_URL, account, d_csr, "distributor.csr", True), "dağıtıcı")
    profile.save(key, author, distributor, device_profile, duid)
    return profile
