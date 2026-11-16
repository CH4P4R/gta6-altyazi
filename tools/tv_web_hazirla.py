"""LG (webOS) ve Samsung (Tizen) TV uygulamalarının paket klasörlerini hazırlar.

TV arayüzü CouchSubs'tan (AGPL-3.0, Sinan Yorulmaz) alınmıştır; bkz. NOTICE.

    python tools/tv_web_hazirla.py

Çıktı: tv-web/build/webos (ares-package ile .ipk yapılır) ve tv-web/build/tizen
(Samsung sertifikasıyla imzalanıp .wgt yapılır; bunu kasadaki uygulama Tizen Studio ile yapar).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tv-web" / "src"
BUILD = ROOT / "tv-web" / "build"


def main() -> int:
    sys.path.insert(0, str(ROOT / "packaging"))
    from make_assets import badge

    for platform, extra in (("webos", ["appinfo.json", "platform.js"]), ("tizen", ["config.xml", "platform.js"])):
        out = BUILD / platform
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(SRC, out)
        for name in extra:
            shutil.copy(ROOT / "tv-web" / platform / name, out / name)
        # index.html iki simgeyi de kullanır (bekleme ekranı ve panel)
        badge(80).save(out / "icon.png")
        badge(130).save(out / "largeIcon.png")
        if platform == "tizen":
            badge(117).save(out / "icon.png")
        print("hazır:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
