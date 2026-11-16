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
