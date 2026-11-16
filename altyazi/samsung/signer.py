# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""Tizen web uygulaması paketini (.wgt) imzalar.

W3C Widget Signature biçimi: ``author-signature.xml`` (paketin dosyaları) ve ``signature1.xml`` (dağıtıcı; önce
yazar imzası, sonra dosyalar). Özet SHA-512, imza RSA-SHA512.

XML imza kütüphanesi kullanılmaz: imzalanan iki parça (SignedInfo ve ``#prop`` nesnesi) bu modülün yazdığı, yapısı
sabit XML olduğundan kanonik biçimleri doğrudan üretilir: SignedInfo exclusive C14N, nesne C14N 1.1 ile (boşluk yok,
öznitelikler sıralı, öğeler açık kapanışlı). Dosyaya da aynı metin yazılır; TV kendi kanonikleştirdiğinde aynı
baytları bulur.
"""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

DSIG = "http://www.w3.org/2000/09/xmldsig#"
DSP = "http://www.w3.org/2009/xmldsig-properties"
RSA_SHA512 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha512"
SHA512 = "http://www.w3.org/2001/04/xmlenc#sha512"
EXC_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
C14N11 = "http://www.w3.org/2006/12/xml-c14n11"

AUTHOR_FILE = "author-signature.xml"
DISTRIBUTOR_FILE = "signature1.xml"


@dataclass
class Signer:
    """İmza için anahtar ve sertifika zinciri (yaprak önce, kök yok)."""
    key: rsa.RSAPrivateKey
    chain: list[x509.Certificate]


Entry = tuple[str, bytes]


def folder_entries(folder: Path) -> list[Entry]:
    """Klasördeki dosyalar (paket içi adlarıyla, sıralı); eski imza dosyaları ve .wgt'ler atılır."""
    out: list[Entry] = []
    for p in sorted(folder.rglob("*")):
        if not p.is_file():
            continue
        name = p.relative_to(folder).as_posix()
        low = name.lower()
        if low.endswith(AUTHOR_FILE) or low.endswith(DISTRIBUTOR_FILE) or low.endswith(".wgt"):
            continue
        out.append((name, p.read_bytes()))
    return out


def zip_entries(wgt: bytes) -> list[Entry]:
    """İmzasız ya da imzalı paketin dosyaları; eski imza dosyaları atılır, sıra korunur."""
    out: list[Entry] = []
    with zipfile.ZipFile(io.BytesIO(wgt)) as z:
        for info in z.infolist():
            low = info.filename.lower()
            if info.is_dir() or low.endswith(AUTHOR_FILE) or low.endswith(DISTRIBUTOR_FILE):
                continue
            out.append((info.filename, z.read(info)))
    return out


def sign(files: list[Entry], author: Signer, distributor: Signer) -> bytes:
    """İmzalı .wgt: önce author-signature.xml, sonra signature1.xml, sonra dosyalar."""
    author_sig = (AUTHOR_FILE, signature("AuthorSignature", files, author))
    dist_sig = (DISTRIBUTOR_FILE, signature("DistributorSignature", [author_sig, *files], distributor))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in [author_sig, dist_sig, *files]:
            z.writestr(name, data)
    return buf.getvalue()


def digest(data: bytes) -> str:
    return base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


def attr(value: str) -> str:
    """Kanonik XML'deki öznitelik kaçışları."""
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
            .replace("\t", "&#x9;").replace("\n", "&#xA;").replace("\r", "&#xD;"))


def prop_object(sig_id: str, canonical: bool) -> str:
    """``<Object Id="prop">``: profil, rol ve boş tanımlayıcı. Kanonik biçimde (C14N 1.1) üst öğeden gelen
    varsayılan ad alanı nesnenin kendisinde yazılır."""
    role = "author" if sig_id == "AuthorSignature" else "distributor"
    target = attr("#" + sig_id)

    def prop(name: str, child: str, uri: str | None) -> str:
        u = f' URI="{attr(uri)}"' if uri else ""
        return f'<SignatureProperty Id="{name}" Target="{target}"><dsp:{child}{u}></dsp:{child}></SignatureProperty>'

    head = f'<Object xmlns="{DSIG}" Id="prop">' if canonical else '<Object Id="prop">'
    return (head + f'<SignatureProperties xmlns:dsp="{DSP}">'
            + prop("profile", "Profile", "http://www.w3.org/ns/widgets-digsig#profile")
            + prop("role", "Role", f"http://www.w3.org/ns/widgets-digsig#role-{role}")
            + prop("identifier", "Identifier", None)
            + "</SignatureProperties></Object>")


def signed_info(files: list[Entry], prop_digest: str) -> str:
    """Dosyadaki SignedInfo (ad alanı üst öğeden gelir)."""
    parts = ["<SignedInfo>",
             f'<CanonicalizationMethod Algorithm="{EXC_C14N}"></CanonicalizationMethod>',
             f'<SignatureMethod Algorithm="{RSA_SHA512}"></SignatureMethod>']
    for name, data in files:
        parts.append(f'<Reference URI="{attr(name)}"><DigestMethod Algorithm="{SHA512}"></DigestMethod>'
                     f"<DigestValue>{digest(data)}</DigestValue></Reference>")
    parts.append(f'<Reference URI="#prop"><Transforms><Transform Algorithm="{C14N11}"></Transform></Transforms>'
                 f'<DigestMethod Algorithm="{SHA512}"></DigestMethod><DigestValue>{prop_digest}</DigestValue>'
                 "</Reference>")
    parts.append("</SignedInfo>")
    return "".join(parts)


def canonical_signed_info(si: str) -> str:
    """Exclusive C14N: kullanılan varsayılan ad alanı kök öğede yazılır."""
    return f'<SignedInfo xmlns="{DSIG}">' + si[len("<SignedInfo>"):]


def _wrap76(text: str) -> str:
    return "\n".join(text[i:i + 76] for i in range(0, len(text), 76))


def signature(sig_id: str, files: list[Entry], signer: Signer) -> bytes:
    """Bir imza dosyası (``<Signature Id="…">``), XML bildirimi ve girinti olmadan."""
    si = signed_info(files, digest(prop_object(sig_id, canonical=True).encode("utf-8")))
    value = signer.key.sign(canonical_signed_info(si).encode("utf-8"), padding.PKCS1v15(), hashes.SHA512())
    xml = [f'<Signature xmlns="{DSIG}" Id="{attr(sig_id)}">', si,
           f"<SignatureValue>{base64.b64encode(value).decode('ascii')}</SignatureValue>",
           "<KeyInfo><X509Data>"]
    for cert in signer.chain:
        der = cert.public_bytes(serialization.Encoding.DER)
        xml.append(f"<X509Certificate>\n{_wrap76(base64.b64encode(der).decode('ascii'))}\n</X509Certificate>")
    xml.append("</X509Data></KeyInfo>")
    xml.append(prop_object(sig_id, canonical=False))
    xml.append("</Signature>")
    return "".join(xml).encode("utf-8")
