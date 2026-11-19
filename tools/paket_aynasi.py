"""Hazır çeviri paketlerini kendi GitHub sürümümüze ('paketler') toplar.

    python tools/paket_aynasi.py ÇIKTI_KLASÖRÜ

Kaynaklar: CouchSubs'ın paket sunucusu (GTA 6 dahil; https://github.com/yorulmazsinan/couchsubs, AGPL-3.0) ve
GameTranslator'ın paket deposu (https://gitlab.com/sefflex/GameTranslator). Her paket indirilir, doğrulanır,
.json.gz olarak yazılır ve index.json üretilir. GitHub Actions (paketler.yml) bunu her gün çalıştırıp sürüme yükler.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

COUCHSUBS = "https://couchsubs-packs.enmera.workers.dev/v1/packs"
GAMETRANSLATOR = "https://gitlab.com/sefflex/GameTranslator/-/raw/main/yamalar/"
GT_PACKS = ["gta-v", "red-dead-redemption-2", "mafia-the-old-country", "watch-dogs", "call-of-duty-modern-warfare-2019",
            "assassins-creed-shadows", "elden-ring", "death-stranding-2", "final-fantasy-vii-rebirth",
            "final-fantasy-vii-remake", "marvels-spider-man-2", "death-stranding-directors-cut"]


def get(url: str, tries: int = 3) -> bytes:
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gta6-altyazi-paketler"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except OSError as e:
            if i == tries - 1:
                raise
            print("  tekrar:", url, e)
            time.sleep(5 * (i + 1))
    raise RuntimeError(url)


def entries_of(gz: bytes) -> tuple[str, int]:
    d = json.loads(gzip.decompress(gz).decode("utf-8"))
    n = len(d.get("entries") or {}) + len(d.get("segments") or {})
    return str(d.get("title") or ""), n


def main(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict] = {}
    # 1) CouchSubs (öncelikli: GTA 6 ve güncel sürümler)
    try:
        cat = json.loads(get(COUCHSUBS).decode("utf-8")).get("packs") or []
    except Exception as e:  # noqa: BLE001
        print("CouchSubs listesi alınamadı:", e)
        cat = []
    for p in cat:
        pid = p.get("id", "")
        try:
            raw = get(f"{COUCHSUBS}/{pid}")
            if hashlib.sha256(raw).hexdigest() != str(p.get("sha256", "")).lower():
                print("  SHA tutmadı, atlandı:", pid)
                continue
            gz = raw if raw[:2] == b"\x1f\x8b" else gzip.compress(raw, 9)
            (out / f"{pid}.json.gz").write_bytes(gz)
            index[pid] = {"id": pid, "title": p.get("title") or pid, "entries": int(p.get("entries") or 0),
                          "version": p.get("version", 0), "auto": bool(p.get("auto")), "source": "CouchSubs",
                          "sha256": hashlib.sha256(gz).hexdigest(), "size": len(gz)}
            print("CouchSubs:", pid, index[pid]["entries"])
        except Exception as e:  # noqa: BLE001
            print("  indirilemedi:", pid, e)
    # 2) GameTranslator (CouchSubs'ta olmayanlar)
    for pid in GT_PACKS:
        if pid in index:
            continue
        try:
            raw = get(GAMETRANSLATOR + pid + ".json")
            gz = gzip.compress(raw, 9)
            title, n = entries_of(gz)
            (out / f"{pid}.json.gz").write_bytes(gz)
            index[pid] = {"id": pid, "title": title or pid, "entries": n, "version": 1, "auto": False,
                          "source": "GameTranslator", "sha256": hashlib.sha256(gz).hexdigest(), "size": len(gz)}
            print("GameTranslator:", pid, n)
        except Exception as e:  # noqa: BLE001
            print("  indirilemedi:", pid, e)
    if not index:
        print("Hiç paket alınamadı")
        return 1
    packs = sorted(index.values(), key=lambda p: (p["auto"], p["title"]))
    (out / "index.json").write_text(json.dumps({"updated": int(time.time()), "packs": packs}, ensure_ascii=False,
                                               indent=1), encoding="utf-8")
    print(f"{len(packs)} paket hazır")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "paketler-cikti")))
