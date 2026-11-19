"""Hazır çeviri paketleri (GameTranslator / topluluk paket biçimiyle uyumlu).

Paket dosyası (düz ya da gzip'li JSON): {"format": 1|2, "id": ..., "title": ..., "entries": {anahtar: Türkçe},
"segments": {anahtar: Türkçe}}. Paketlerde İngilizce metin yoktur; anahtar, ekranda okunan satırın sadeleştirilmiş
halinin SHA-256'sının ilk 8 baytıdır (16 hex). Sadeleştirme: <etiket>'ler boşluk olur, NFKC, küçük harf, NFD ile
aksanlar atılır, harf/rakam dışı her şey tek boşluk olur, baş ve son kırpılır.

Paketler repoda dağıtılmaz; kullanıcı kendi edindiği paket dosyasını programa ekler. Kendi önbelleğimiz de aynı
biçimde dışa aktarılıp arkadaşlarla paylaşılabilir.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_TAG = re.compile(r"<[^<>]{0,40}>")
_SENT = re.compile(r"(?<=[.!?…])\s+")
# Konuşan adı ("FRANKLIN:", "Lamar -") ya da diyalog çizgisi: paketlerde çoğunlukla adsız satır vardır
# (CouchSubs'ın arama sırasından: önce tüm satır, sonra adsız, sonra cümle cümle)
_SPEAKER = re.compile(r"^\s*(?:([A-Z][A-Za-z.'\- ]{0,24}?)\s*:\s+|[-–—]\s*)(?=\S)")


def canon(text: str) -> str:
    s = unicodedata.normalize("NFKC", _TAG.sub(" ", text)).lower()
    out, gap = [], False
    for ch in unicodedata.normalize("NFD", s):
        cat = unicodedata.category(ch)
        if cat in ("Mn", "Mc", "Me"):
            continue
        if cat[0] == "L" or cat in ("Nd", "Nl", "No"):
            if gap and out:
                out.append(" ")
            gap = False
            out.append(ch)
        else:
            gap = True
    return "".join(out)


def key(text: str) -> str | None:
    c = canon(text)
    return hashlib.sha256(c.encode("utf-8")).hexdigest()[:16] if c else None


@dataclass
class Pack:
    id: str
    title: str
    path: Path
    entries: dict[str, str]

    @property
    def count(self) -> int:
        return len(self.entries)


def load(path: Path) -> Pack:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    d = json.loads(raw.decode("utf-8"))
    entries: dict[str, str] = {}
    for section in ("segments", "entries"):     # tam satırlar parçaların üstüne yazsın
        for k, v in (d.get(section) or {}).items():
            if isinstance(v, str) and len(k) == 16:
                entries[k.lower()] = v
    return Pack(id=str(d.get("id") or path.stem), title=str(d.get("title") or path.stem), path=path, entries=entries)


class PackLibrary:
    """Klasördeki tüm paketler. Arama: önce tüm satır, olmazsa cümle cümle (hepsi bulunursa birleştirilir)."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.packs: list[Pack] = []
        self._index: dict[str, tuple[str, str]] = {}
        self.reload()

    def reload(self) -> None:
        self.packs, self._index = [], {}
        self.folder.mkdir(parents=True, exist_ok=True)
        for p in sorted(self.folder.glob("*.json*")):
            if p.suffix == ".tmp":
                continue
            try:
                pack = load(p)
            except Exception as e:  # noqa: BLE001
                log.warning("Paket okunamadı (%s): %s", p.name, e)
                continue
            self.packs.append(pack)
            for k, v in pack.entries.items():
                self._index.setdefault(k, (v, pack.id))
        if self.packs:
            log.info("Çeviri paketleri: %s", ", ".join(f"{p.title} ({p.count})" for p in self.packs))

    def lookup(self, text: str) -> tuple[str, str] | None:
        if not self._index:
            return None
        hit = self._lookup(text)
        if hit:
            return hit
        m = _SPEAKER.match(text)
        if m:
            hit = self._lookup(text[m.end():])
            if hit:
                prefix = f"{m.group(1)}: " if m.group(1) else "- "
                return prefix + hit[0], hit[1]
        return None

    def _lookup(self, text: str) -> tuple[str, str] | None:
        k = key(text)
        if k and k in self._index:
            return self._index[k]
        parts = [p for p in _SENT.split(text.strip()) if p.strip()]
        if len(parts) > 1:
            hits = [self._index.get(key(p) or "") for p in parts]
            if all(hits):
                return " ".join(h[0] for h in hits), hits[0][1]
        return None


def export_cache(db_rows: list[tuple[str, str]], dest: Path, title: str = "GTA6 Altyazı önbelleği") -> int:
    """(İngilizce, Türkçe) satırlarını paket biçiminde yaz. Yazılan satır sayısını döndürür."""
    entries = {}
    for en, tr in db_rows:
        k = key(en)
        if k and tr:
            entries[k] = tr
    data = {"format": 2, "id": "gta6-altyazi-onbellek", "title": title, "source": "GTA6 Altyazı", "entries": entries}
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    dest.write_bytes(gzip.compress(raw) if dest.suffix == ".gz" else raw)
    return len(entries)


# ---------------------------------------------------------------------------------------------- hazır paket kataloğu
# GameTranslator'ın (CouchSubs türevi, AGPL-3.0) herkese açık "yamalar" klasöründeki paketler. Paketler kuruluma
# gömülmez; kullanıcı istediğinde kaynağından indirilir.
CATALOG_BASE = "https://gitlab.com/sefflex/GameTranslator/-/raw/main/yamalar/"
CATALOG: list[tuple[str, str]] = [
    ("gta-v", "Grand Theft Auto V"),
    ("red-dead-redemption-2", "Red Dead Redemption 2"),
    ("mafia-the-old-country", "Mafia: The Old Country"),
    ("watch-dogs", "Watch Dogs"),
    ("call-of-duty-modern-warfare-2019", "Call of Duty: Modern Warfare (2019)"),
    ("assassins-creed-shadows", "Assassin's Creed Shadows"),
    ("elden-ring", "Elden Ring"),
    ("death-stranding-2", "Death Stranding 2"),
    ("final-fantasy-vii-rebirth", "Final Fantasy VII Rebirth"),
    ("marvels-spider-man-2", "Marvel's Spider-Man 2"),
]


def download(pack_id: str, folder: Path, progress=None) -> Pack:  # noqa: ANN001
    """Kataloktaki paketi indir, gzip'leyip klasöre koy ve doğrula."""
    import urllib.request

    if pack_id not in dict(CATALOG):
        raise ValueError(f"Bilinmeyen paket: {pack_id}")
    folder.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CATALOG_BASE + pack_id + ".json", headers={"User-Agent": "gta6-altyazi"})
    chunks, done = [], 0
    with urllib.request.urlopen(req, timeout=30) as r:
        total = int(r.headers.get("Content-Length") or 0)
        while True:
            b = r.read(1 << 16)
            if not b:
                break
            chunks.append(b)
            done += len(b)
            if progress and total:
                progress(done / total)
    raw = b"".join(chunks)
    json.loads(raw.decode("utf-8"))                       # bozuk/yarım indirmeyi yazmadan yakala
    dest = folder / f"{pack_id}.json.gz"
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(gzip.compress(raw, 6))
    tmp.replace(dest)
    return load(dest)


# ---------------------------------------------------------------------------------------------- CouchSubs paketleri
# CouchSubs'ın ücretsiz paket sunucusu (hesap/anahtar yok; https://github.com/yorulmazsinan/couchsubs, server/packs).
# GTA 6 paketi burada dağıtılıyor (oyuncuların gördüğü satırlardan, topluluk katkısıyla). Liste: GET /v1/packs,
# dosya: GET /v1/packs/<id> (.json.gz). İndirilen dosya listedeki SHA-256 ile doğrulanır. Sunucu IP başına saatte
# 60 indirmeye izin verir; program yalnız kullanıcı düğmeye basınca indirir.
COUCHSUBS_PACKS = "https://couchsubs-packs.enmera.workers.dev/v1/packs"
_PACK_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def couchsubs_catalog(timeout: float = 8, fetch=None) -> list[dict]:  # noqa: ANN001
    """[{id, title, entries, sha256, version}] — sunucu yanıt vermezse boş liste."""
    import urllib.request

    try:
        if fetch is None:
            req = urllib.request.Request(COUCHSUBS_PACKS, headers={"User-Agent": "gta6-altyazi"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        else:
            data = fetch(COUCHSUBS_PACKS)
    except Exception as e:  # noqa: BLE001
        log.info("CouchSubs paket listesi alınamadı: %s", e)
        return []
    out = []
    for p in data.get("packs") or []:
        if isinstance(p, dict) and _PACK_ID.match(str(p.get("id", ""))) and p.get("sha256"):
            out.append({"id": p["id"], "title": str(p.get("title") or p["id"]), "entries": int(p.get("entries") or 0),
                        "sha256": str(p["sha256"]).lower(), "version": p.get("version", 0),
                        "auto": bool(p.get("auto"))})
    return out


def download_couchsubs(info: dict, folder: Path, progress=None, fetch=None) -> Pack:  # noqa: ANN001
    import urllib.request

    pid = info["id"]
    if not _PACK_ID.match(pid):
        raise ValueError(f"Geçersiz paket kimliği: {pid}")
    url = f"{COUCHSUBS_PACKS}/{pid}"
    if fetch is None:
        req = urllib.request.Request(url, headers={"User-Agent": "gta6-altyazi"})
        chunks, done = [], 0
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            while True:
                b = r.read(1 << 16)
                if not b:
                    break
                chunks.append(b)
                done += len(b)
                if progress and total:
                    progress(done / total)
        raw = b"".join(chunks)
    else:
        raw = fetch(url)
    if hashlib.sha256(raw).hexdigest() != info["sha256"]:
        raise ValueError("İndirilen paket doğrulanamadı (SHA-256 tutmadı); tekrar dene.")
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{pid}.json.gz"
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(raw if raw[:2] == b"\x1f\x8b" else gzip.compress(raw, 6))
    tmp.replace(dest)
    return load(dest)
