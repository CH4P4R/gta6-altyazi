# SPDX-License-Identifier: AGPL-3.0-only
# Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz; sdb/signing
# originally from TizenSdb (MIT, PatrickSt1991/tizen-sdb) and Apps2Samsung (MIT). Modified for GTA6 Altyazı.
"""Samsung (Tizen) TV'ye TV uygulamasını Tizen Studio olmadan, saf Python ile kurar.

Adımlar: sdb (TCP 26101) ile TV'ye bağlan, DUID'i oku, gerekirse Samsung hesabıyla girip o TV'ye özel imza
sertifikası al, paketi (.wgt) W3C widget imzasıyla imzala, TV'ye gönder, kur ve aç.

- ``sdb``: sdb (ADB'nin Tizen'deki karşılığı) istemcisi
- ``signer``: author-signature.xml / signature1.xml imzaları
- ``certs``: Samsung'dan yazar ve dağıtıcı sertifikası alma, TV başına önbellek
- ``login``: Samsung hesabıyla tarayıcıda giriş (localhost:4794 dinleyicisi)
- ``diagnostics``: ``vd_appinstall`` çıktısının sınıflandırılması ve Türkçe hata iletileri
- ``installer``: hepsini bir araya getiren ``setup_direct``
"""

from .diagnostics import SamsungInstallError
from .installer import setup_direct

__all__ = ["SamsungInstallError", "setup_direct"]
