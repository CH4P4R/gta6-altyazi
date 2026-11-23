"""Oyunun İngilizce metni ile okuma düzeltme ("oyun metni").

GTA 6'nın İngilizce metin dökümü (yaklaşık 460 bin farklı satır; kaynak: github.com/psviethoa/gta6-text-en, döküm
CyberLeek) kullanıcı isteyince doğrudan kaynağından indirilir, bilgisayarda küçük bir SQLite (FTS5) dizinine çevrilir.
Program bu metni dağıtmaz ve kuruluma koymaz.

Ekranda okunan satır (OCR) oyunun gerçek satırına çok benziyorsa gerçek satırla değiştirilir: "Get in tbe car, we
got cornpany" → "Get in the car, we got company". Böylece
- hazır paketlerdeki Türkçe (anahtar satırın kendisinden hesaplanır) bir harf hatasında da bulunur,
- yapay zekâya ve yerel çeviriye hatasız İngilizce gider, önbellek aynı satırı bir kez çevirir.

Eşleşme sıkıdır (benzerlik ≥ %88, uzunluk farkı az); emin olunmayan satır olduğu gibi kalır.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

SOURCE = "https://raw.githubusercontent.com/psviethoa/gta6-text-en/main/"
FILES = ("raw_american.tsv", "raw_american_story.tsv", "raw_american_minigame.tsv")
GAME = "Grand Theft Auto VI"

_SEG = re.compile(r"~sl:[0-9.:]+~")                  # altyazı parçası ayırıcısı (her parça ekranda ayrı görünür)
_CODE = re.compile(r"~[^~\s]{1,32}~")                # renk, tuş, emoji, yer tutucu kodları
_TAG = re.compile(r"<[^<>]{0,24}>")
_SPACE = re.compile(r"\s+")
_WORD = re.compile(r"[A-Za-z0-9']{3,}")
MIN_LEN = 8                                          # daha kısa satır düzeltilmez ("Go!", "OK")


def clean(text: str) -> list[str]:
    """Ham satırdan ekranda görünen metin(ler): kodlar atılır, ~sl~ parçaları ayrı satır olur, tamamı da eklenir."""
    text = text.replace("~n~", " ")
    parts = [p for p in (_SPACE.sub(" ", _TAG.sub(" ", _CODE.sub(" ", s))).strip() for s in _SEG.split(text)) if p]
    out = list(parts)
    if len(parts) > 1:
        out.append(" ".join(parts))
    return [p for p in out if len(p) >= MIN_LEN]


def _canon(text: str) -> str:
    from .packs import canon
    return canon(text)


def build(dest: Path, sources: list[Path] | None = None, progress: Callable[[str], None] | None = None,
          fetch: Callable[[str], bytes] | None = None) -> int:
    """Dökümü indirip (ya da verilen dosyalardan) dizini kurar; satır sayısını döndürür. Yarım kalan dosya bırakmaz."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    db = sqlite3.connect(tmp)
    try:
        db.execute("CREATE TABLE satir(id INTEGER PRIMARY KEY, metin TEXT NOT NULL, canon TEXT NOT NULL UNIQUE)")
        db.execute("CREATE VIRTUAL TABLE ara USING fts5(metin, content='satir', content_rowid='id')")
        seen: set[str] = set()
        rows = 0

        def add(text: str) -> None:
            nonlocal rows
            for line in clean(text):
                c = _canon(line)
                if len(c) < MIN_LEN or c in seen:
                    continue
                seen.add(c)
                db.execute("INSERT INTO satir(metin, canon) VALUES (?, ?)", (line, c))
                rows += 1

        names = [str(p) for p in sources] if sources else [SOURCE + f for f in FILES]
        for i, name in enumerate(names, 1):
            if progress:
                progress(f"Oyun metni indiriliyor ({i}/{len(names)})…")
            if sources:
                data = Path(name).read_bytes()
            elif fetch:
                data = fetch(name)
            else:
                with urllib.request.urlopen(name, timeout=60) as r:     # noqa: S310 (sabit https kaynağı)
                    data = r.read()
            lines = data.decode("utf-8", "replace").splitlines()
            for ln in lines[1:]:                     # ilk satır başlık: table, table_offset, idx, hash, text
                cols = ln.split("\t")
                if len(cols) >= 5:
                    add(cols[4])
        if progress:
            progress("Oyun metni dizinleniyor…")
        db.execute("INSERT INTO ara(rowid, metin) SELECT id, metin FROM satir")
        # sözcüklerin kaç satırda geçtiği: aramada yalnız nadir sözcükler kullanılır (hızlı)
        db.execute("CREATE VIRTUAL TABLE sozcuk USING fts5vocab(ara, 'row')")
        db.commit()
    finally:
        db.close()
    tmp.replace(dest)
    log.info("Oyun metni hazır: %d satır (%s)", rows, dest)
    return rows


class ScriptIndex:
    """Oyun metninde en yakın satırı bulur. Her iş parçacığı kendi bağlantısını kullanır."""

    def __init__(self, path: Path, threshold: float = 88.0):
        self.path = Path(path)
        self.threshold = threshold
        self._local = threading.local()
        self._cache: OrderedDict[str, str | None] = OrderedDict()
        self._lock = threading.Lock()
        db = self._db()
        self.count = db.execute("SELECT COUNT(*) FROM satir").fetchone()[0]

    def _db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            self._local.db = db
        return db

    def exact(self, text: str) -> bool:
        return self._db().execute("SELECT 1 FROM satir WHERE canon = ?", (_canon(text),)).fetchone() is not None

    def snap(self, text: str) -> str | None:
        """Okunan satıra çok benzeyen oyun satırı (zaten aynıysa None: değiştirmeye gerek yok)."""
        text = text.strip()
        if len(text) < MIN_LEN:
            return None
        with self._lock:
            if text in self._cache:
                self._cache.move_to_end(text)
                return self._cache[text]
        found = self._snap(text)
        with self._lock:
            self._cache[text] = found
            if len(self._cache) > 4000:
                self._cache.popitem(last=False)
        return found

    def _snap(self, text: str) -> str | None:
        c = _canon(text)
        db = self._db()
        if db.execute("SELECT 1 FROM satir WHERE canon = ?", (c,)).fetchone():
            return None
        words = {w.lower().replace("'", "") for w in _WORD.findall(text)}
        words = {w for w in words if len(w) >= 3}
        if not words:
            return None
        marks = ",".join("?" * len(words))
        freq = dict(db.execute(f"SELECT term, doc FROM sozcuk WHERE term IN ({marks})", tuple(words)).fetchall())
        # okunamayan (dizinde olmayan) sözcükler atlanır; en nadir 3 sözcükle aranır
        rare = sorted((w for w in words if 0 < freq.get(w, 0) < 30000), key=lambda w: freq[w])[:3]
        if not rare:
            return None
        query = " OR ".join('"' + w + '"' for w in rare)
        try:
            rows = db.execute("SELECT s.metin, s.canon FROM ara JOIN satir s ON s.id = ara.rowid WHERE ara MATCH ? "
                              "ORDER BY bm25(ara) LIMIT 40", (query,)).fetchall()
        except sqlite3.Error:
            return None
        from rapidfuzz import fuzz
        best, score = None, 0.0
        for metin, cand in rows:
            if abs(len(cand) - len(c)) > max(4, len(c) * 0.15):
                continue
            s = fuzz.ratio(c, cand)
            if s > score:
                best, score = metin, s
        return best if best is not None and score >= self.threshold else None


def default_path() -> Path:
    from . import paths
    return paths.data("oyun_metni/gta6.sqlite")
