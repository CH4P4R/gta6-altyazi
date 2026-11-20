"""LG (webOS) ve Samsung (Tizen) TV uygulamalarının paket klasörlerini hazırlar.

TV arayüzü CouchSubs'tan (AGPL-3.0, Sinan Yorulmaz) alınmıştır; bkz. NOTICE.

    python tools/tv_web_hazirla.py

Çıktı: tv-web/build/webos (ares-package ile .ipk yapılır) ve tv-web/build/tizen
(Samsung sertifikasıyla imzalanıp .wgt yapılır; bunu kasadaki uygulama Tizen Studio ile yapar).
"""

from __future__ import annotations

import json
import re
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
        # Sürüm her derlemede programınkiyle aynı: TV'deki eski uygulama "yeni sürüm var" diye güncellenir
        sys.path.insert(0, str(ROOT))
        import altyazi
        js = (out / "app.js").read_text(encoding="utf-8")
        js = re.sub(r"var APP_VERSION = '[^']*';", f"var APP_VERSION = '{altyazi.__version__}';", js, count=1)
        (out / "app.js").write_text(js, encoding="utf-8")
        if platform == "webos":
            info = json.loads((out / "appinfo.json").read_text(encoding="utf-8"))
            info["version"] = altyazi.__version__
            # webOS 25 oyunun üstüne ekran koruyucu açmasın (CouchSubs #230)
            info.setdefault("screenSaverProperties", {"preferredType": 2})
            (out / "appinfo.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        # index.html iki simgeyi de kullanır (bekleme ekranı ve panel)
        badge(80).save(out / "icon.png")
        badge(130).save(out / "largeIcon.png")
        if platform == "tizen":
            badge(117).save(out / "icon.png")
            # Samsung'un webapis.js'i (ekran koruyucuyu kapatmak için; CouchSubs package-tizen.sh gibi)
            html = (out / "index.html").read_text(encoding="utf-8")
            tag = '<script src="platform.js"></script>'
            if "webapis.js" not in html and tag in html:
                html = html.replace(tag, '<script src="$WEBAPIS/webapis/webapis.js"></script>\n  ' + tag)
                (out / "index.html").write_text(html, encoding="utf-8")
            xml = (out / "config.xml").read_text(encoding="utf-8")
            xml = re.sub(r'(<widget[^>]*\sversion=")[^"]+(")', rf"\g<1>{altyazi.__version__}\g<2>", xml, count=1)
            (out / "config.xml").write_text(xml, encoding="utf-8")
        print("hazır:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
