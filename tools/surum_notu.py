"""Releases sayfasındaki sürüm notunu CHANGELOG.md'den üretir.

    python tools/surum_notu.py 0.4.6 notlar.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def section(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(rf"^## {re.escape(version)}\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def notes(version: str, sha: str = "") -> str:
    body = section(version) or "Hata düzeltmeleri ve iyileştirmeler."
    return f"""## GTA6 Altyazı {version}

{body}

### Kurulum
1. Aşağıdaki **GTA6Altyazi-Setup.exe**'yi indir ve çalıştır (yönetici izni istemez).
2. "Windows kişisel bilgisayarınızı korudu" uyarısında **Ek bilgi › Yine de çalıştır**.
3. İlk açılışta resimli kurulum sihirbazı adım adım yol gösterir. Takıldığın yerde uygulamadaki **Rehber** sayfasına bak.

Eski sürümün üstüne kurabilirsin; ayarların korunur. · [Bütün sürüm notları](https://github.com/CH4P4R/gta6-altyazi/blob/HEAD/CHANGELOG.md) · [Rehber](https://github.com/CH4P4R/gta6-altyazi#-adım-adım-rehber)
{f"<sub>derleme {sha}</sub>" if sha else ""}
"""


if __name__ == "__main__":
    v = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    sha = sys.argv[3] if len(sys.argv) > 3 else ""
    text = notes(v, sha)
    if out:
        out.write_text(text, encoding="utf-8")
    else:
        print(text)
