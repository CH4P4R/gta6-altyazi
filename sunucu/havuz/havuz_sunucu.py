# SPDX-License-Identifier: AGPL-3.0-only
"""GTA6 Altyazı ortak çeviri havuzu sunucusu (kendi VPS'imizde çalışır).

Oyuncuların yapay zekâyla (Claude, Gemini, DeepL) çevirdiği satırlar buraya gelir; aynı satırın aynı Türkçesini
yeterince farklı kurulum gönderince (varsayılan 2) satır havuz paketine girer ve herkese ücretsiz dağıtılır. Uygulama
havuz paketini hazır paketler gibi indirir (CouchSubs paket sunucusunun /v1/packs biçimi).

Yalnız Python 3.9+ standart kütüphanesi gerekir (kurulum yok). Kişisel bilgi tutulmaz: istek gönderen IP yalnız
bellekte, her gün değişen tuzla özetlenip hız sınırı için kullanılır; kurulum kimliği rastgele bir sayıdır.

    python3 havuz_sunucu.py                      # sunucuyu başlat (HAVUZ_* ortam değişkenleri aşağıda)
    python3 havuz_sunucu.py istatistik           # satır/oy sayıları
    python3 havuz_sunucu.py sil "English line"   # bir satırı havuzdan sil (kötü çeviri)
    python3 havuz_sunucu.py engelle KURULUM_ID   # bir kurulumun bütün gönderdiklerini sil ve engelle

Uç noktalar:
    POST /v1/satir              {"client": 32 onaltılık, "game": "gta-6", "items": [{"en", "tr", "source"}]}
    GET  /v1/packs              {"packs": [{"id", "title", "entries", "sha256", "version", "auto"}]}
    GET  /v1/packs/<id>         paket (.json.gz): {"id", "title", "version", "entries": {anahtar: Türkçe}}
    GET  /v1/saglik             {"ok": true, "satir": .., "oy": .., "paket": ..}
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import unicodedata
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

log = logging.getLogger("havuz")

HOST = os.environ.get("HAVUZ_HOST", "127.0.0.1")          # Caddy önündeyse 127.0.0.1; doğrudan açıksa 0.0.0.0
PORT = int(os.environ.get("HAVUZ_PORT", "8787"))
DB_PATH = Path(os.environ.get("HAVUZ_VERI", "/var/lib/gta6-havuz/havuz.sqlite"))
MIN_VOTES = max(1, int(os.environ.get("HAVUZ_MIN_OY", "2")))   # paketine girmek için gereken farklı kurulum
GAMES = {g.strip(): g.strip() for g in os.environ.get("HAVUZ_OYUNLAR", "gta-6").split(",") if g.strip()}
TITLES = {"gta-6": "Grand Theft Auto VI"}
REBUILD_EVERY = int(os.environ.get("HAVUZ_YENILE_SN", "300"))
TRUST_PROXY = os.environ.get("HAVUZ_VEKIL", "1") == "1"        # X-Forwarded-For (Caddy) okunur

MAX_BODY = 256 * 1024
MAX_ITEMS = 300
MAX_EN, MAX_TR = 400, 600
RATE_ITEMS_HOUR = int(os.environ.get("HAVUZ_SAAT_SINIRI", "3000"))   # bir IP'den saatte en çok satır
RATE_REQ_MINUTE = 30
_CLIENT = re.compile(r"^[0-9a-f]{32}$")
_GAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
_SOURCES = {"claude", "gemini", "deepl", "claude-görsel"}


# ------------------------------------------------------------------ satır anahtarı (altyazi/packs.py ile aynı)
_TAG = re.compile(r"<[^<>]{0,40}>")


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


# ------------------------------------------------------------------ satır denetimi
_LETTER = re.compile(r"[A-Za-z]")
_BAD = re.compile(r"https?://|www\.|<script|\{\{|\bAPI\b key", re.I)
_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
_EN_WORDS = {"the", "and", "you", "your", "with", "this", "that", "what", "are", "for", "have", "get"}


def acceptable(en: str, tr: str) -> bool:
    """Saçma, boş ya da kötü niyetli satır havuza girmez. Emin olunamayanı geri çevirmek yeterli: aynı satırı
    başka oyuncular da gönderecek."""
    if not (2 <= len(en) <= MAX_EN and 1 <= len(tr) <= MAX_TR):
        return False
    if not _LETTER.search(en) or _BAD.search(en) or _BAD.search(tr):
        return False
    ce, ct = canon(en), canon(tr)
    if not ce or not ct or ce == ct and len(ce.split()) > 2:          # çevrilmemiş (ad ve kısa sözcük olabilir)
        return False
    if len(tr) > 4 * len(en) + 20 or len(en) > 6 * len(tr) + 20:       # uydurma ya da yarım
        return False
    words = ct.split()
    if len(words) >= 5 and not (_TR_CHARS & set(tr)) and sum(w in _EN_WORDS for w in words) * 3 >= len(words):
        return False                                                    # Türkçe değil, İngilizce
    return True


# ------------------------------------------------------------------ veri
class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self.write = threading.Lock()
        db = self.db()
        db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS oy(
                game TEXT NOT NULL, key TEXT NOT NULL, en TEXT NOT NULL, tr TEXT NOT NULL,
                client TEXT NOT NULL, source TEXT NOT NULL, t INTEGER NOT NULL,
                PRIMARY KEY(game, key, client));
            CREATE INDEX IF NOT EXISTS oy_tr ON oy(game, key, tr);
            CREATE TABLE IF NOT EXISTS engel(client TEXT PRIMARY KEY, t INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS silinen(game TEXT NOT NULL, key TEXT NOT NULL, PRIMARY KEY(game, key));
        """)
        db.commit()

    def db(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            self._local.db = db
        return db

    def blocked(self, client: str) -> bool:
        return self.db().execute("SELECT 1 FROM engel WHERE client=?", (client,)).fetchone() is not None

    def add(self, game: str, client: str, items: list[tuple[str, str, str, str]]) -> int:
        """items: (anahtar, en, tr, kaynak). Aynı kurulumun aynı satıra ikinci oyu öncekini değiştirir."""
        now = int(time.time())
        with self.write:
            db = self.db()
            db.executemany("INSERT INTO oy(game, key, en, tr, client, source, t) VALUES (?, ?, ?, ?, ?, ?, ?) "
                           "ON CONFLICT(game, key, client) DO UPDATE SET tr=excluded.tr, source=excluded.source, "
                           "t=excluded.t", [(game, k, en, tr, client, src, now) for k, en, tr, src in items])
            db.commit()
        return len(items)

    def best(self, game: str, min_votes: int) -> dict[str, str]:
        """Her satırın en çok oy alan Türkçesi (eşitlikte en yenisi); yeterli oyu olmayan ve silinen satır yok."""
        rows = self.db().execute(
            "SELECT key, tr, COUNT(*) AS n, MAX(t) FROM oy WHERE game=? AND key NOT IN "
            "(SELECT key FROM silinen WHERE game=?) GROUP BY key, tr HAVING n >= ? ORDER BY key, n, MAX(t)",
            (game, game, min_votes)).fetchall()
        out: dict[str, str] = {}
        for k, tr, _n, _t in rows:                      # sıralı: her anahtarın son satırı en iyisi
            out[k] = tr
        return out

    def stats(self) -> dict:
        db = self.db()
        return {"oy": db.execute("SELECT COUNT(*) FROM oy").fetchone()[0],
                "satir": db.execute("SELECT COUNT(DISTINCT game || key) FROM oy").fetchone()[0],
                "kurulum": db.execute("SELECT COUNT(DISTINCT client) FROM oy").fetchone()[0]}

    def remove(self, game: str, english: str) -> int:
        k = key(english)
        with self.write:
            db = self.db()
            n = db.execute("DELETE FROM oy WHERE game=? AND key=?", (game, k)).rowcount
            db.execute("INSERT OR IGNORE INTO silinen(game, key) VALUES (?, ?)", (game, k))
            db.commit()
        return n

    def block(self, client: str) -> int:
        with self.write:
            db = self.db()
            n = db.execute("DELETE FROM oy WHERE client=?", (client,)).rowcount
            db.execute("INSERT OR IGNORE INTO engel(client, t) VALUES (?, ?)", (client, int(time.time())))
            db.commit()
        return n


class Packs:
    """Havuz paketleri bellekte hazır tutulur; REBUILD_EVERY saniyede bir yeniden kurulur."""

    def __init__(self, store: Store, min_votes: int = MIN_VOTES):
        self.store, self.min_votes = store, min_votes
        self.lock = threading.Lock()
        self.items: dict[str, tuple[dict, bytes]] = {}

    def rebuild(self) -> None:
        fresh = {}
        for game in GAMES:
            entries = self.store.best(game, self.min_votes)
            pid = f"havuz-{game}"
            title = f"{TITLES.get(game, game)} (GTA6 Altyazı havuzu)"
            version = int(time.time())
            body = json.dumps({"id": pid, "title": title, "version": version, "entries": entries},
                              ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            gz = gzip.compress(body, 9, mtime=0)
            info = {"id": pid, "title": title, "entries": len(entries), "sha256": hashlib.sha256(gz).hexdigest(),
                    "version": version, "auto": True, "size": len(gz)}
            fresh[pid] = (info, gz)
        with self.lock:
            # Satırlar değişmediyse sürüm ve özet aynı kalır (uygulama boşuna indirmesin).
            for pid, (info, gz) in list(fresh.items()):
                old = self.items.get(pid)
                if old and old[0]["entries"] == info["entries"] and \
                        json.loads(gzip.decompress(old[1]))["entries"] == json.loads(gzip.decompress(gz))["entries"]:
                    fresh[pid] = old
            self.items = fresh

    def catalog(self) -> list[dict]:
        with self.lock:
            return [info for info, _ in self.items.values()]

    def get(self, pid: str) -> bytes | None:
        with self.lock:
            hit = self.items.get(pid)
        return hit[1] if hit else None


class RateLimit:
    def __init__(self):
        self.lock = threading.Lock()
        self.salt = secrets.token_bytes(16)
        self.day = time.strftime("%Y%m%d")
        self.reqs: dict[str, deque] = defaultdict(deque)
        self.items: dict[str, deque] = defaultdict(deque)

    def _who(self, ip: str) -> str:
        today = time.strftime("%Y%m%d")
        if today != self.day:                         # her gün yeni tuz: IP özetleri günden güne bağlanamaz
            self.day, self.salt = today, secrets.token_bytes(16)
            self.reqs.clear()
            self.items.clear()
        return hashlib.sha256(self.salt + ip.encode()).hexdigest()[:16]

    def allow(self, ip: str, count: int) -> bool:
        now = time.monotonic()
        with self.lock:
            who = self._who(ip)
            r, it = self.reqs[who], self.items[who]
            while r and now - r[0] > 60:
                r.popleft()
            while it and now - it[0][0] > 3600:
                it.popleft()
            if len(r) >= RATE_REQ_MINUTE or sum(n for _, n in it) + count > RATE_ITEMS_HOUR:
                return False
            r.append(now)
            it.append((now, count))
            return True


# ------------------------------------------------------------------ HTTP
def make_handler(store: Store, packs: Packs, limit: RateLimit):
    class Handler(BaseHTTPRequestHandler):
        server_version = "gta6-havuz/1"
        sys_version = ""

        def log_message(self, fmt, *args):  # noqa: ANN001, ANN002
            log.debug("%s", fmt % args)

        def _ip(self) -> str:
            if TRUST_PROXY:
                fwd = self.headers.get("X-Forwarded-For", "")
                if fwd:
                    return fwd.split(",")[0].strip()
            return self.client_address[0]

        def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8",
                  extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code: int, data: dict) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/v1/packs":
                self._json(200, {"packs": packs.catalog()})
            elif path.startswith("/v1/packs/"):
                gz = packs.get(path[len("/v1/packs/"):])
                if gz is None:
                    self._json(404, {"hata": "paket yok"})
                else:
                    self._send(200, gz, "application/gzip", {"Cache-Control": "public, max-age=300"})
            elif path in ("/v1/saglik", "/saglik", ""):
                self._json(200, {"ok": True, **store.stats(), "paket": packs.catalog()})
            else:
                self._json(404, {"hata": "yok"})

        do_HEAD = do_GET

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0].rstrip("/") != "/v1/satir":
                self._json(404, {"hata": "yok"})
                return
            try:
                size = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                size = 0
            if not 0 < size <= MAX_BODY:
                self._json(413, {"hata": "istek çok büyük"})
                return
            raw = self.rfile.read(size)
            try:
                if self.headers.get("Content-Encoding", "").lower() == "gzip":
                    raw = gzip.decompress(raw)
                    if len(raw) > MAX_BODY * 4:
                        raise ValueError("büyük")
                data = json.loads(raw.decode("utf-8"))
                client = str(data.get("client", ""))
                game = str(data.get("game", ""))
                items = data.get("items") or []
                if not _CLIENT.match(client) or not _GAME.match(game) or game not in GAMES \
                        or not isinstance(items, list) or len(items) > MAX_ITEMS:
                    raise ValueError("biçim")
            except Exception:  # noqa: BLE001
                self._json(400, {"hata": "geçersiz istek"})
                return
            if not limit.allow(self._ip(), len(items)):
                self._json(429, {"hata": "çok sık"}, )
                return
            if store.blocked(client):
                self._json(200, {"alinan": 0})              # engellenen kuruluma belli etmeden
                return
            rows, seen = [], set()
            for it in items:
                if not isinstance(it, dict):
                    continue
                en = " ".join(str(it.get("en", "")).split())
                tr = " ".join(str(it.get("tr", "")).split())
                src = str(it.get("source", ""))[:20]
                k = key(en) if en else None
                if not k or k in seen or src not in _SOURCES or not acceptable(en, tr):
                    continue
                seen.add(k)
                rows.append((k, en, tr, src))
            n = store.add(game, client, rows) if rows else 0
            self._json(200, {"alinan": n})

    return Handler


def serve() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    store = Store(DB_PATH)
    packs = Packs(store)
    packs.rebuild()

    def rebuild_loop() -> None:
        while True:
            time.sleep(REBUILD_EVERY)
            try:
                packs.rebuild()
            except Exception:  # noqa: BLE001
                log.exception("Paket kurulamadı")

    threading.Thread(target=rebuild_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), make_handler(store, packs, RateLimit()))
    log.info("Havuz %s:%d (en az %d oy, oyunlar: %s, veri: %s)", HOST, PORT, MIN_VOTES, ",".join(GAMES), DB_PATH)
    httpd.serve_forever()


def main(argv: list[str]) -> int:
    if not argv:
        serve()
        return 0
    store = Store(DB_PATH)
    cmd = argv[0]
    if cmd == "istatistik":
        print(json.dumps({**store.stats(), "paket": {g: len(store.best(g, MIN_VOTES)) for g in GAMES}},
                         ensure_ascii=False, indent=1))
    elif cmd == "sil" and len(argv) >= 2:
        print(store.remove(argv[2] if len(argv) > 2 else "gta-6", argv[1]), "oy silindi")
    elif cmd == "engelle" and len(argv) == 2 and _CLIENT.match(argv[1]):
        print(store.block(argv[1]), "oy silindi; kurulum engellendi")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
