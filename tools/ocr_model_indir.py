"""İngilizceye özel OCR tanıma modellerini indirir (RapidOCR'ın yayınladığı PP-OCR ONNX modelleri).

    python tools/ocr_model_indir.py

Adresler ve SHA256 özetleri rapidocr 3.10.0 paketinin default_models.yaml dosyasından alındı.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0"
FILES = [
    ("en_PP-OCRv5_rec_mobile.onnx", f"{BASE}/onnx/PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx",
     "c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8"),
    ("en_PP-OCRv4_rec_mobile.onnx", f"{BASE}/onnx/PP-OCRv4/rec/en_PP-OCRv4_rec_mobile.onnx",
     "e8770c967605983d1570cdf5352041dfb68fa0c21664f49f47b155abd3e0e318"),
    ("en_dict.txt", f"{BASE}/paddle/PP-OCRv4/rec/en_PP-OCRv4_rec_mobile/en_dict.txt", None),
]


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "models/ocr")
    out.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, url, sha in FILES:
        dest = out / name
        if dest.exists() and (sha is None or hashlib.sha256(dest.read_bytes()).hexdigest() == sha):
            print("var:", name)
            continue
        print("indiriliyor:", name)
        req = urllib.request.Request(url, headers={"User-Agent": "gta6-altyazi"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if sha and hashlib.sha256(data).hexdigest() != sha:
            print(f"HATA: {name} doğrulanamadı (SHA256 uyuşmuyor)")
            ok = False
            continue
        dest.write_bytes(data)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
