# SPDX-License-Identifier: AGPL-3.0-only
"""Ortak çeviri havuzu istemcisi (sunucusu: sunucu/havuz/havuz_sunucu.py, kendi VPS'imizde).

- Gönderme: yapay zekânın (Claude, Gemini, DeepL) çevirdiği GTA 6 satırları biriktirilir, ~30 sn'de bir toplu ve
  arka planda havuza gider. Giden: İngilizce satır, Türkçesi, hangi yapay zekânın çevirdiği, oyun ve rastgele bir
  kurulum kimliği. Kişisel bilgi, anahtar, ekran görüntüsü gitmez.
- Alma: havuzun paketi ("havuz-gta-6") hazır paketler gibi paket klasörüne iner; değişmediyse yeniden inmez.

Ayarda havuz kapatılırsa hiçbir şey gönderilmez ve indirilmez; adres boşsa varsayılan sunucu kullanılır.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

# GTA6 Altyazı'nın havuz sunucusu (sunucu/havuz, VPS). Ayardaki adres boşsa bu kullanılır.
DEFAULT_URL = "http://87.232.127.103:8787"
SOURCES = {"claude", "gemini", "deepl", "claude-görsel"}
_PACK_ID = re.compile(r"^havuz-[a-z0-9-]{1,40}$")
_LETTER = re.compile(r"[A-Za-z]")


class PoolClient:
    def __init__(self, base: str, client_id: str, game: str = "gta-6", send: bool = True, every: float = 30.0,
                 post: Callable[[str, bytes], int] | None = None, get: Callable[[str], bytes] | None = None):
        self.base = base.rstrip("/")
        self.client, self.game, self.send = client_id, game, send
        self.every = every
        self._post = post or self._http_post
        self._get = get or self._http_get
        self.lock = threading.Lock()
        self.queue: list[dict] = []
        self.sent: set[str] = set()
        self.stop_ev = threading.Event()
        self.thread: threading.Thread | None = None
        self.total = 0

    # ------------------------------------------------------------------ gönderme
    def add(self, en: str, tr: str, source: str) -> bool:
        if not self.send:
            return False
        en, tr = " ".join(en.split()), " ".join(tr.split())
        if source not in SOURCES or not (2 <= len(en) <= 400 and 1 <= len(tr) <= 600) or not _LETTER.search(en) \
                or en == tr:
            return False
        with self.lock:
            if en in self.sent:
                return False
            self.sent.add(en)
            if len(self.sent) > 50000:
                self.sent.clear()
            self.queue.append({"en": en, "tr": tr, "source": source})
            if len(self.queue) > 2000:                    # sunucuya ulaşılamıyorsa bellek şişmesin
                del self.queue[:500]
        self._start()
        return True

    def _start(self) -> None:
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._loop, daemon=True, name="havuz")
            self.thread.start()

    def _loop(self) -> None:
        while not self.stop_ev.wait(self.every):
            self.flush()

    def flush(self) -> int:
        with self.lock:
            batch, self.queue = self.queue[:300], self.queue[300:]
        if not batch:
            return 0
        body = gzip.compress(json.dumps({"client": self.client, "game": self.game, "items": batch},
                                        ensure_ascii=False).encode("utf-8"))
        try:
            got = self._post(self.base + "/v1/satir", body)
            self.total += got
            log.info("Havuz: %d satır gönderildi (%d kabul)", len(batch), got)
            return got
        except Exception as e:  # noqa: BLE001
            log.info("Havuza gönderilemedi (sonra yeniden denenecek): %s", e)
            with self.lock:
                self.queue = batch + self.queue
            return 0

    def close(self) -> None:
        self.stop_ev.set()
        self.flush()

    # ------------------------------------------------------------------ alma
    def update_pack(self, folder: Path) -> Path | None:
        """Havuz paketini indirir (değiştiyse). İndirilen dosyanın yolu, değişiklik yoksa None."""
        cat = json.loads(self._get(self.base + "/v1/packs").decode("utf-8")).get("packs") or []
        wanted = f"havuz-{self.game}"
        info = next((p for p in cat if isinstance(p, dict) and p.get("id") == wanted), None)
        if info is None or not _PACK_ID.match(wanted) or not info.get("entries"):
            return None
        dest = Path(folder) / f"{wanted}.json.gz"
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == str(info.get("sha256", "")).lower():
            return None
        raw = self._get(f"{self.base}/v1/packs/{wanted}")
        if hashlib.sha256(raw).hexdigest() != str(info.get("sha256", "")).lower():
            raise ValueError("havuz paketi doğrulanamadı")
        json.loads(gzip.decompress(raw).decode("utf-8"))      # bozuk dosyayı yazmadan yakala
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(raw)
        tmp.replace(dest)
        log.info("Havuz paketi indi: %s satır", info.get("entries"))
        return dest

    # ------------------------------------------------------------------ HTTP
    @staticmethod
    def _http_post(url: str, body: bytes) -> int:
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json", "Content-Encoding": "gzip", "User-Agent": "gta6-altyazi"})
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (ayardaki havuz adresi)
            return int(json.loads(r.read().decode("utf-8")).get("alinan", 0))

    @staticmethod
    def _http_get(url: str) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "gta6-altyazi"})
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return r.read()
