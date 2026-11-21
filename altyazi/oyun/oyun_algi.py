# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın GameSense.swift, RunningGame.swift ve GameChoice.swift dosyalarından taşındı.

Oynanan oyun. PS5'in keşif yanıtı çalışan oyunu çoğu zaman bildirmiyor (running-app-titleid boş); oyun dört yoldan
bilinir, öncelik sırasıyla: PS5'in bildirdiği (`set_console`), kullanıcının elle seçtiği (`choose`), okunan satırların
art arda aynı hazır paketten gelmesi (son 20 satırın en az 5'i yalnız o pakette bulunan satırsa, `note_line`) ve
ekrandan tanınan (`set_seen`). Elle seçim paket çoğunluğunun önüne geçer: paketi olmayan oyunda ortak satırlar başka
oyunun paketinden gelip oyunu değiştirmesin.

Paket eşlemesi (`pack_for_game`): Nino'da başlık kimliği → paket tablosu yoktur. Oyun pakete ADIYLA bağlanır
(`game_key`: "Grand Theft Auto V", "GTA 5" ve paket kimliği "gta-v" aynı anahtara, "gta 5"e iner). Tek kimlik
eşlemesi ortak havuzun otomatik paketleridir: "pool-ppsa01234" ↔ PPSA01234, "pool-cusa00419-00" ↔ CUSA00419_00.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable

log = logging.getLogger(__name__)

GENERAL_PACK = "pool-genel"      # oyunu bilinmeyen satırların ortak paketi: bir oyun değildir
MAX_NAME = 120


# ------------------------------------------------------------------------------------------------- RunningGame
def normalized_title_id(value: str | None) -> str | None:
    """Dört harf, beş rakam, isteğe bağlı "_00" eki (büyük harfe çevrilir); biçim tutmazsa None."""
    if value is None:
        return None
    tid = value.strip().upper()
    if re.fullmatch(r"[A-Z]{4}[0-9]{5}(?:_[0-9]{2})?", tid):
        return tid
    return None


def normalized_name(value: str | None) -> str | None:
    """Denetim karakterleri ve fazla boşluk atılır, en çok 120 karakter; boşsa None."""
    if value is None:
        return None
    cleaned = "".join(" " if unicodedata.category(ch) in ("Cc", "Cf") else ch for ch in value)
    trimmed = " ".join(cleaned.split())[:MAX_NAME].strip()
    return trimmed or None


@dataclass(frozen=True)
class RunningGame:
    """PS5'te o an çalışan oyun: başlık kimliği ("PPSA01234", "CUSA00419_00") ve adı. Oyun paketten ya da kullanıcının
    seçiminden geldiyse kimlik çoğu zaman yoktur."""
    title_id: str | None
    name: str | None

    @classmethod
    def from_console(cls, title_id: str | None, name: str | None) -> RunningGame | None:
        """PS5'in bildirdiği oyun; kimlik PS5 biçiminde değilse None (ana ekran ya da sistem uygulaması)."""
        tid = normalized_title_id(title_id)
        return cls(tid, normalized_name(name)) if tid else None

    @classmethod
    def named(cls, name: str | None, title_id: str | None = None) -> RunningGame | None:
        """Yalnız adıyla bilinen oyun; ad boşsa None. Kimlik geçerliyse o da tutulur."""
        n = normalized_name(name)
        return cls(normalized_title_id(title_id), n) if n else None


def running_game_from_console(info) -> RunningGame | None:  # noqa: ANN001
    """remoteplay.discover()'un ConsoleInfo'sundan (title_id, app_name) çalışan oyun."""
    return RunningGame.from_console(getattr(info, "title_id", None), getattr(info, "app_name", None))


# ------------------------------------------------------------------------------------------------- GameName
_ALIASES = [("grand theft auto", "gta"), ("call of duty", "cod"), ("red dead redemption", "rdr"),
            ("ea sports fc", "fc"), ("ea sports", "")]
_ROMAN = {"ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8", "ix": "9", "x": "10",
          "xi": "11", "xii": "12", "xiii": "13", "xiv": "14", "xv": "15", "xvi": "16"}


def _alnum(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "LN"


def game_key(value: str) -> str:
    """Oyun adının karşılaştırma anahtarı (GameName.key): küçük harf, aksansız, noktalama yok, Roma rakamı sayıya,
    bilinen uzun adlar kısaltmaya. "Grand Theft Auto VI", "GTA 6" ve "gta6" → "gta 6"."""
    marks = re.sub("[™®©]", " ", value)              # NFKD "™"yi "TM" yapar; önce atılır
    text: list[str] = []
    previous: str | None = None
    for ch in unicodedata.normalize("NFKD", marks).lower():
        if unicodedata.category(ch) in ("Mn", "Mc", "Me") or ch in "'’`":
            continue
        if ch == "ı":
            ch = "i"
        if ch == "&":
            text.append(" and ")
            previous = " "
            continue
        alnum = _alnum(ch)
        if not alnum:
            ch = " "
        # "gta6" → "gta 6" (harf ve rakam ayrılır)
        if previous is not None and alnum:
            pl, pn = unicodedata.category(previous)[0] == "L", unicodedata.category(previous)[0] == "N"
            cl, cn = unicodedata.category(ch)[0] == "L", unicodedata.category(ch)[0] == "N"
            if (pl and cn) or (pn and cl):
                text.append(" ")
        text.append(ch)
        previous = ch
    words = [_ROMAN.get(w, w) for w in "".join(text).split()]
    if len(words) > 1 and words[0] == "the":
        words.pop(0)
    joined = " " + " ".join(words) + " "
    for long, short in _ALIASES:
        joined = joined.replace(f" {long} ", f" {short} " if short else " ")
    return " ".join(joined.split())[:80].strip()


# ------------------------------------------------------------------------------------------------- paket eşlemesi
def title_id_from_pack(pack_id: str) -> str | None:
    """Kimliğiyle toplanmış otomatik paket ("pool-ppsa01234", "pool-cusa00419-00") oyunun kimliğini taşır."""
    if not pack_id.startswith("pool-"):
        return None
    return normalized_title_id(pack_id[5:].replace("-", "_"))


def pool_pack_id(title_id: str) -> str | None:
    """Başlık kimliğinin otomatik paket kimliği: "PPSA01234" → "pool-ppsa01234", "CUSA00419_00" → "pool-cusa00419-00"."""
    tid = normalized_title_id(title_id)
    return f"pool-{tid.lower().replace('_', '-')}" if tid else None


def _id_title(pack) -> tuple[str, str]:  # noqa: ANN001
    if isinstance(pack, tuple):
        return str(pack[0]), str(pack[1])
    return str(pack.id), str(getattr(pack, "title", "") or pack.id)


def pack_for_game(game: RunningGame | str | None, packs: Iterable) -> str | None:
    """Oyunun paket kimliği; yoksa None. `packs`: Pack nesneleri (id, title) ya da (id, title) ikilileri.
    1. Başlık kimliği varsa o kimliğin otomatik paketi ("pool-ppsa01234").
    2. Adının anahtarı paketin başlığının ya da kimliğinin anahtarıyla aynı olan SON paket (Nino: resolveLimit;
       sonradan yüklenen, ör. kullanıcının indirdiği paket kazanır). Ortak havuz paketi bir oyun değildir."""
    if game is None:
        return None
    if isinstance(game, str):
        game = RunningGame.named(game)
        if game is None:
            return None
    items = [_id_title(p) for p in packs]
    if game.title_id:
        pool = pool_pack_id(game.title_id)
        if any(pid == pool for pid, _ in items):
            return pool
    wanted = game_key(game.name) if game.name else ""
    if not wanted:
        return None
    found = None
    for pid, title in items:
        if pid != GENERAL_PACK and (game_key(title) == wanted or game_key(pid) == wanted):
            found = pid
    return found


def distinctive_pack(library, text: str) -> str | None:  # noqa: ANN001
    """Satır yalnız TEK bir pakette bulunuyorsa o paketin kimliği (Nino: takeDistinctiveHit); birkaç pakette ortak
    satırlar ("Okay.", "Let's go.") sayılmaz. `library`: altyazi.packs.PackLibrary (her Pack'in `entries` sözlüğü).
    Sıra PackLibrary.lookup'la aynı: tüm satır, konuşan etiketi olmadan, cümle cümle."""
    from ..packs import _SENT, _SPEAKER, key

    packs = list(getattr(library, "packs", []) or [])
    if not packs:
        return None
    candidates = [text]
    m = _SPEAKER.match(text)
    if m:
        candidates.append(text[m.end():])
    for cand in list(candidates):
        parts = [p for p in _SENT.split(cand.strip()) if p.strip()]
        if len(parts) > 1:
            candidates += parts
    for cand in candidates:
        k = key(cand)
        if not k:
            continue
        owners = [p for p in packs if k in p.entries]
        if len(owners) == 1:
            return owners[0].id
        if owners:
            return None              # bulundu ama ortak: oy sayılmaz
    return None


# ------------------------------------------------------------------------------------------------- GameSense
class Source(str, Enum):
    CONSOLE = "console"
    PACK = "pack"
    USER = "user"
    SCREEN = "screen"


class GameSense:
    WINDOW = 20          # bakılan son satır sayısı
    THRESHOLD = 5        # tanımak için aynı paketten gelmesi gereken satır sayısı
    ASK_AFTER = 120.0    # çeviri başladıktan bu kadar saniye sonra oyun hâlâ bilinmiyorsa sorulur

    def __init__(self):
        self._lock = threading.Lock()
        self._recent: list[str | None] = []
        self._titles: dict[str, str] = {}
        self._console: RunningGame | None = None
        self._pack: RunningGame | None = None
        self._pack_id: str | None = None
        self._chosen: RunningGame | None = None
        self._seen: RunningGame | None = None
        self._asked = False

    @property
    def current(self) -> RunningGame | None:
        """Havuza giden oyun: PS5'in bildirdiği, yoksa kullanıcının seçtiği, yoksa paketten tanınan, yoksa ekrandan."""
        with self._lock:
            return self._console or self._chosen or self._pack or self._seen

    @property
    def is_sure(self) -> bool:
        """Oyun kesin biliniyor mu (PS5, kullanıcı ya da ekran); paketten tahmin kesin sayılmaz."""
        with self._lock:
            return self._console is not None or self._chosen is not None or self._seen is not None

    @property
    def source(self) -> Source | None:
        with self._lock:
            if self._console is not None:
                return Source.CONSOLE
            if self._chosen is not None:
                return Source.USER
            if self._pack is not None:
                return Source.PACK
            if self._seen is not None:
                return Source.SCREEN
            return None

    @property
    def pack_limit(self) -> str | None:
        """Paket aramasının sınırlanacağı oyunun adı: kullanıcı seçtiyse ve PS5 bir oyun bildirmiyorsa; yoksa None."""
        with self._lock:
            return self._chosen.name if self._console is None and self._chosen is not None else None

    @property
    def chosen_name(self) -> str | None:
        with self._lock:
            return self._chosen.name if self._chosen else None

    @property
    def pack_id(self) -> str | None:
        """Satır çoğunluğundan tanınan paketin kimliği (Swift'te gizli alan; altyazı yeri anahtarı için açıldı)."""
        with self._lock:
            return self._pack_id

    def note_line(self, pack_id: str | None = None, title: str | None = None) -> bool:
        """Bir satır gösterildi. `pack_id`/`title`: satır yalnız tek bir pakette bulunduysa o paket (bkz.
        `distinctive_pack`); motorla çevrildiyse ya da ortaksa None. Oyun bu satırla yeni tanındıysa True."""
        with self._lock:
            pid = None if pack_id == GENERAL_PACK else pack_id
            self._recent.append(pid)
            if len(self._recent) > self.WINDOW:
                del self._recent[:len(self._recent) - self.WINDOW]
            if pid is None:
                return False
            if title:
                self._titles[pid] = title
            if pid == self._pack_id or self._recent.count(pid) < self.THRESHOLD:
                return False
            game = RunningGame.named(self._titles.get(pid, pid), title_id_from_pack(pid))
            if game is None:
                return False
            self._pack, self._pack_id = game, pid
            return True

    def set_console(self, game: RunningGame | None) -> None:
        """PS5'in bildirdiği oyun (bilinmiyorsa None). PS5 elle seçilenden başka bir oyun bildirirse elle seçim eskimiştir
        ve silinir: yoksa PS5 bildirmeyi bırakınca eski oyun geri gelirdi."""
        with self._lock:
            self._console = game
            if game and game.name and self._chosen and self._chosen.name \
                    and game_key(game.name) != game_key(self._chosen.name):
                self._chosen = None

    def set_seen(self, name: str | None) -> None:
        """Ekrandan tanınan oyun (paketi olmayan yeni oyunda tek kaynak)."""
        with self._lock:
            self._seen = RunningGame.named(name) if name else None

    def choose(self, name: str | None) -> None:
        """Kullanıcının seçimi ("Hangi oyunu oynuyorsunuz?" ya da "Değiştir"); None seçimi siler."""
        with self._lock:
            self._chosen = RunningGame.named(name)
            self._asked = True

    def start_session(self) -> None:
        """Yeni çeviri oturumu: paket penceresi ve soru sıfırlanır; kullanıcının seçimi uygulama açık kaldıkça kalır."""
        with self._lock:
            self._recent.clear()
            self._pack = None
            self._pack_id = None
            self._console = None
            self._asked = False

    def should_ask(self, running_for: float, enabled: bool) -> bool:
        """Kart gösterilmeli mi: ayar açık, bu oturumda sorulmadı, oyun hiçbir yoldan bilinmiyor ve iki dakikadır çeviri."""
        with self._lock:
            return (enabled and not self._asked and self._console is None and self._pack is None
                    and self._chosen is None and self._seen is None and running_for >= self.ASK_AFTER)

    def mark_asked(self) -> None:
        """Kart gösterildi ya da "Sorma"ya basıldı: bu oturumda bir daha sorulmaz."""
        with self._lock:
            self._asked = True


# ------------------------------------------------------------------------------------------------- GameCatalog
POPULAR = [
    "Grand Theft Auto VI", "Grand Theft Auto V", "Red Dead Redemption 2", "Ghost of Yōtei", "Marvel's Spider-Man 2",
    "Death Stranding 2: On the Beach", "Elden Ring", "Elden Ring Nightreign", "Assassin's Creed Shadows",
    "Call of Duty: Black Ops 7", "Call of Duty: Black Ops 6", "Battlefield 6", "EA Sports FC 26",
    "Mafia: The Old Country", "The Last of Us Part II Remastered", "God of War Ragnarök", "Cyberpunk 2077",
    "Hogwarts Legacy", "Resident Evil Requiem", "Silent Hill f", "Metal Gear Solid Delta: Snake Eater", "Borderlands 4",
    "Kingdom Come: Deliverance II", "Clair Obscur: Expedition 33", "Final Fantasy VII Rebirth", "Stellar Blade",
    "Black Myth: Wukong", "Baldur's Gate 3", "Horizon Forbidden West", "Alan Wake 2",
    "Indiana Jones and the Great Circle", "Dying Light: The Beast", "Ghost of Tsushima", "Star Wars Outlaws",
    "The Witcher 3: Wild Hunt", "Monster Hunter Wilds", "Split Fiction", "Hollow Knight: Silksong",
]


def suggestions(query: str, packs: list[str], last: str | None, limit: int = 8) -> list[str]:
    """Kartın önerileri: önce son oynanan, sonra paketlerin oyunları, sonra popüler oyunlar; aynı oyun bir kez.
    Arama yazılmışsa anahtarı aramayı içerenler, aramayla başlayanlar önde."""
    seen, all_ = set(), []
    for name in ([last] if last else []) + list(packs) + POPULAR:
        k = game_key(name)
        if not k or k in seen:
            continue
        seen.add(k)
        all_.append(name)
    wanted = game_key(query)
    if not wanted:
        return all_[:limit]
    found = [n for n in all_ if wanted in game_key(n)]
    first = [n for n in found if game_key(n).startswith(wanted)]
    return (first + [n for n in found if not game_key(n).startswith(wanted)])[:limit]


def pack_games(packs: Iterable) -> list[str]:
    """Paket listesinden oyun adları (ortak havuz paketi bir oyun değildir)."""
    return [title for pid, title in map(_id_title, packs) if pid != GENERAL_PACK]


# ------------------------------------------------------------------------------------------------- GameChoice
class GameChoice:
    """Uygulamanın "oynanan oyun" durumu (GameSense üzerine): "Oynanan oyun: X · Değiştir", iki dakika sonra çıkan
    "Hangi oyunu oynuyorsunuz?" kartı ve kullanıcının seçimi. Seçim PS5'in adıyla saklanır; aynı PS5'te sonraki
    oturumda kartın ilk önerisi olur. Swift'teki zamanlayıcı yerine uygulama `tick()`'i ~15 sn'de bir çağırır."""

    CHECK_INTERVAL = 15.0
    REMEMBERED_KEY = "lastGames"

    def __init__(self, store_path: Path | str | None = None, clock: Callable[[], float] = time.monotonic):
        self.sense = GameSense()
        self.game: RunningGame | None = None
        self.source: Source | None = None
        self.asking = False
        self.on_change: Callable[[RunningGame | None], None] = lambda _game: None
        self.on_ask: Callable[[], None] = lambda: None             # kart açılmalı (arayüz)
        self.on_limit: Callable[[str | None], None] = lambda _name: None   # paket araması bu oyunla sınırlansın
        self.pack_titles: Callable[[], list[str]] = list
        self._store = Path(store_path) if store_path else None
        self._clock = clock
        self._console: str | None = None
        self._started: float | None = None
        self._enabled: Callable[[], bool] = lambda: False
        self._limit: object = object()

    def start(self, console: str | None, enabled: Callable[[], bool]) -> None:
        """Çeviri başladı. `console`: PS5'in adı (son oyun bununla hatırlanır); `enabled`: soru ayarı açık mı."""
        self.sense.start_session()
        self._console = console
        self._enabled = enabled
        self._started = self._clock()
        self._publish()

    def tick(self) -> bool:
        """Kart açılmalı mı diye bakar (Swift: 15 sn'lik zamanlayıcı). Kart bu çağrıda açıldıysa True."""
        if self._started is None:
            return False
        if self.sense.should_ask(self._clock() - self._started, bool(self._enabled())):
            self.sense.mark_asked()
            self._started = None     # zamanlayıcı biter
            self.asking = True
            self.on_ask()
            return True
        return False

    def stop(self) -> None:
        """Çeviri durdu: kart kapanır."""
        self._started = None
        self.asking = False

    def note_line(self, pack_id: str | None, title: str | None = None) -> None:
        """Ekrana bir satır geldi; `pack_id`: satır yalnız tek pakette bulunduysa o paket (`distinctive_pack`)."""
        if not self.sense.note_line(pack_id, title):
            return
        self.asking = False
        self._publish()

    def console_reported(self, game: RunningGame | None) -> None:
        """PS5'in keşif yanıtındaki oyun (yoksa None)."""
        self.sense.set_console(game)
        self._publish()

    def seen(self, name: str) -> None:
        """Oyun ekrandan tanındı; sorulacak soru gereksizleşir."""
        self.sense.set_seen(name)
        self.asking = False
        self._publish()

    def choose(self, name: str) -> None:
        """Kullanıcı bir oyun seçti ya da adını yazdı."""
        name = name.strip()
        if not name:
            return
        self.sense.choose(name)
        if self._console:
            saved = self._remembered()
            game = RunningGame.named(name)
            if game:
                saved[self._console] = game.name
                self._save(saved)
        self.asking = False
        self._publish()

    def automatic(self) -> None:
        """Kullanıcının seçimini bırak: oyun yine paketten / PS5'ten kendiliğinden anlaşılsın."""
        with self.sense._lock:
            self.sense._chosen = None
        self.asking = False
        self._publish()

    def ask(self) -> None:
        """"Değiştir": kart elle açılır."""
        self.sense.mark_asked()
        self.asking = True

    def dismiss(self) -> None:
        """"Sorma": bu oturumda bir daha sorulmaz."""
        self.sense.mark_asked()
        self.asking = False

    @property
    def last_played(self) -> str | None:
        """Bu PS5'te son seçilen oyun."""
        return self._remembered().get(self._console) if self._console else None

    def suggestions(self, query: str) -> list[str]:
        return suggestions(query, self.pack_titles(), self.last_played)

    def _remembered(self) -> dict[str, str]:
        if not self._store or not self._store.is_file():
            return {}
        try:
            data = json.loads(self._store.read_text("utf-8")).get(self.REMEMBERED_KEY) or {}
            return {str(k): str(v) for k, v in data.items()}
        except (OSError, ValueError, AttributeError):
            return {}

    def _save(self, saved: dict[str, str]) -> None:
        if not self._store:
            return
        try:
            data = {}
            if self._store.is_file():
                try:
                    data = json.loads(self._store.read_text("utf-8"))
                except ValueError:
                    data = {}
            data[self.REMEMBERED_KEY] = saved
            self._store.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._store.with_name(self._store.name + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
            os.replace(tmp, self._store)
        except OSError as e:
            log.debug("Son oyun yazılamadı: %s", e)

    def _publish(self) -> None:
        limit = self.sense.pack_limit
        if limit != self._limit:
            self._limit = limit
            self.on_limit(limit)
        current = self.sense.current
        self.source = self.sense.source
        if current == self.game:
            return
        self.game = current
        self.on_change(current)
