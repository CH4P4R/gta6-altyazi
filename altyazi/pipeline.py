"""Kare → bölge tespiti → OCR → çeviri → ekran.

Yakalama iş parçacığı sadece en son kareyi bırakır (eski kareler atılır, kuyruk
birikmez). İşçi iş parçacığı en yeni kareyi alır. Çeviri ayrı havuzlarda
çalıştığı için yavaş bir çeviri yeni altyazının tespitini asla bekletmez.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Protocol

import numpy as np

from .config import BolgeCfg, Config
from .detector import ZoneDetector, zone_rect
from .translate import Result, TranslationEngine

log = logging.getLogger(__name__)


@dataclass
class DisplayItem:
    zone: str
    rect: tuple[float, float, float, float]   # İngilizce metnin kare içindeki yeri (oran)
    zone_rect: tuple[float, float, float, float]
    line_h: float                              # satır yüksekliği (kare yüksekliğine oran)
    english: str
    text: str
    align: str
    anchor: str
    box_opacity: int
    font_scale: float
    source: str = ""
    quality: int = 0
    latency_ms: float = 0.0                    # karenin yakalanmasından çevirinin gelmesine kadar
    ocr_ms: float = 0.0
    mt_ms: float = 0.0
    seq: int = 0


class Sink(Protocol):
    def show(self, item: DisplayItem) -> None: ...
    def clear(self, zone: str) -> None: ...


class MultiSink:
    def __init__(self, *sinks):
        self.sinks = [s for s in sinks if s is not None]

    def add(self, sink) -> None:  # noqa: ANN001
        """Çeviri sürerken sonradan açılan yerel sunucuyu (TV akışı) ekle."""
        if sink is not None and sink not in self.sinks:
            self.sinks.append(sink)

    def show(self, item: DisplayItem) -> None:
        for s in self.sinks:
            s.show(item)

    def clear(self, zone: str) -> None:
        for s in self.sinks:
            s.clear(zone)

    def overlay(self, items: list[dict]) -> None:
        """Ekran yazılarının Türkçeleri (telefon, harita kartı, mesaj): yalnız destekleyen çıkışlara (TV sunucusu)."""
        for s in self.sinks:
            fn = getattr(s, "set_overlay", None)
            if fn:
                fn(items)


_LETTER = re.compile(r"[A-Za-z]")


def clean_ocr(text: str) -> str:
    text = text.replace("|", "I").replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    text = re.sub(r"(?<=\w)'\s+(t|s|ll|re|ve|d|m)\b", r"'\1", text)   # "can' t" -> "can't"
    return re.sub(r"\s+", " ", text).strip()


def looks_like_text(text: str) -> bool:
    letters = len(_LETTER.findall(text))
    return letters >= 2 and letters >= 0.5 * len(text.replace(" ", ""))


_TOKEN = re.compile(r"[\w']+")


def _real_words(text: str) -> int:
    return sum(1 for t in _TOKEN.findall(text) if t.replace("'", "").isalpha())
_MEANING = re.compile(r"\b(not|no|never|don't|can't|won't|isn't|aren't|didn't)\b|\b\d+(st|nd|rd|th)?\b", re.IGNORECASE)


def worse_reread(old: str, new: str) -> bool:
    """Ekrandaki satırın daha kötü okunmuş hali mi (aynı cümle, daha az gerçek kelime)?

    Parlak arka planda OCR bir kelimeyi kaçırınca çeviri bozulup geri düzelerek titriyordu. Yeni okuma bir olumsuzluk
    ya da sayı ekliyorsa anlam değişmiş olabilir, atlanmaz. (Fikir CouchSubs'ın SubtitleStabilizer'ından.)
    """
    from rapidfuzz import fuzz

    if not old or fuzz.ratio(old.lower(), new.lower()) < 85:
        return False
    if len(_MEANING.findall(new)) > len(_MEANING.findall(old)):
        return False
    return _real_words(new) < _real_words(old)


_SENT_END = re.compile(r"[.!?…:\"')\]]\s*$")


def rows_of(boxes: list[tuple[int, int, int, int]], texts: list[str]) -> list[tuple[str, tuple[int, int, int, int]]]:
    """OCR parçalarını satırlara topla (dikeyde örtüşen parçalar aynı satır, soldan sağa): [(metin, kutu)]."""
    items = [(b, t) for b, t in zip(boxes, texts) if t]
    items.sort(key=lambda bt: (bt[0][1], bt[0][0]))
    rows: list[list] = []
    for b, t in items:
        if rows:
            rb = rows[-1][0]
            overlap = min(rb[3], b[3]) - max(rb[1], b[1])
            if overlap > 0.5 * min(rb[3] - rb[1], b[3] - b[1]):
                rows[-1][0] = (min(rb[0], b[0]), min(rb[1], b[1]), max(rb[2], b[2]), max(rb[3], b[3]))
                rows[-1][1].append((b[0], t))
                continue
        rows.append([b, [(b[0], t)]])
    return [(" ".join(t for _, t in sorted(parts)), rb) for rb, parts in rows]


def blocks_of(rows: list[tuple[str, tuple[int, int, int, int]]], line_h: float, gap_ratio: float = 0.45,
              separate: set[int] | None = None) -> list[tuple[str, tuple[int, int, int, int], int]]:
    """Satırları paragraflara ayır: [(metin, kutu, satır sayısı)], yukarıdan aşağı.

    GTA'da görev yazısı ("Arabaya git") altta dururken diyalog altyazısı onun üstüne çıkar. İkisi tek metin gibi
    çevrilirse anlamsız bir cümle çıkıyordu. Satırlar arası boşluk büyükse ayrı paragraf sayılır. 'separate'teki
    satırlar (ekranda sabit duran görev/HUD satırları) her zaman kendi paragrafıdır.
    Kutular OCR için yazının çevresine lh/4 pay eklenmiş hâldedir; boşluk bu payla birlikte ölçülür.
    """
    separate = separate or set()
    blocks: list[list] = []
    prev_sep = False
    for i, (text, rb) in enumerate(rows):
        gap = rb[1] - blocks[-1][1][3] if blocks else 0
        # Cümle bitmeden satır kırıldıysa ("Hurry up, they are right" / "behind us!") boşluk biraz geniş olsa da
        # aynı paragraftır; görev yazısı hep bitmiş bir cümlenin altında durur
        unfinished = bool(blocks) and not _SENT_END.search(blocks[-1][0])
        sep = i in separate
        if blocks and not sep and not prev_sep and (gap <= gap_ratio * line_h or (unfinished and gap <= 1.2 * line_h)):
            bb = blocks[-1][1]
            blocks[-1][0] += " " + text
            blocks[-1][1] = (min(bb[0], rb[0]), bb[1], max(bb[2], rb[2]), max(bb[3], rb[3]))
            blocks[-1][2] += 1
        else:
            blocks.append([text, rb, 1])
        prev_sep = sep
    return [(t, b, n) for t, b, n in blocks]


def group_blocks(boxes: list[tuple[int, int, int, int]], texts: list[str], line_h: float,
                 gap_ratio: float = 0.45) -> list[tuple[str, tuple[int, int, int, int]]]:
    return [(t, b) for t, b, _n in blocks_of(rows_of(boxes, texts), line_h, gap_ratio)]


# --------------------------------------------------------------------- GTA 6'da görülen ve çevrilmemesi gerekenler
# (CouchSubs'ın GTA 6 oynanırken bulduğu düzeltmelerden: #424 tuş ipuçları, #406 kısa HUD yazıları, #394 sabit görev
# satırı. https://github.com/yorulmazsinan/couchsubs, AGPL-3.0, Sinan Yorulmaz)
_PROMPT_VERBS = {"press", "hold", "tap", "use", "mash", "release", "push", "click", "toggle", "pull"}
_KEY_NAMES = {"rb", "lb", "rt", "lt", "r1", "r2", "r3", "l1", "l2", "l3", "x", "a", "b", "y", "options", "touchpad",
              "share", "space", "enter", "esc", "tab", "shift", "ctrl", "alt", "lmb", "rmb", "mmb"}
_REAL_UPPER = {"ON", "UP", "IT", "IN", "OF", "TO", "AT", "OR", "AND", "GO", "NO", "OK", "MY", "ME", "US", "BE", "DO",
               "SO", "AN", "IS", "THE", "YOU", "HIM", "HER"}
_DETERMINERS = {"your", "the", "my", "his", "her", "our", "their", "its", "it", "me", "him", "us", "them", "a", "an",
                "this", "that", "you"}


_KEY_TOKEN = re.compile(r"^[\[(<{]?([A-Z]|[RL][123]|[RL][BT]|OPTIONS|TOUCHPAD|SHARE|SPACE|ENTER|ESC|TAB|SHIFT|CTRL|ALT|"
                        r"LMB|RMB|MMB)[\])>}]?[.,]?$", re.IGNORECASE)


def _clean_key(w: str) -> bool:
    return bool(_KEY_TOKEN.match(w)) and not (w.isalpha() and w.upper() in _REAL_UPPER)


def _crop_jpeg(zone_img: np.ndarray, box: tuple[int, int, int, int], line_h: float) -> bytes | None:
    """Satırın (tuş simgesiyle) küçük resmi: biraz pay, küçükse büyütülmüş JPEG."""
    import cv2
    h, w = zone_img.shape[:2]
    pad = int(max(4, line_h * 0.6))
    x0, y0, x1, y1 = box
    crop = zone_img[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)]
    if crop.size == 0:
        return None
    if crop.shape[0] < 64:
        f = 64 / crop.shape[0]
        crop = cv2.resize(crop, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes() if ok else None


def is_button_prompt(text: str) -> bool:
    """"Press [△] to take cover" gibi, tuş simgesi OKUNAMAMIŞ tuş ipucu mu? Simge resim olduğu için OCR ya hiç okumuyor
    ("Press to threaten the teller") ya da kalıntı okuyor ("Press @ to", "Hold I LI to"). Bunları çevirip üstünü
    kapatırsak hangi tuşa basılacağı kayboluyordu; çevrilmez, oyunun kendi yazısı simgesiyle görünür kalır.
    Tuş adı düzgün okunduysa ("Press E to enter", "Hold [RB] to aim") çevrilir: Claude tuş adını aynen korur."""
    t = text.strip()
    if not t or any(c in t for c in "!?\"“”:"):
        return False
    words = t.split()
    if len(words) < 3 or words[0].lower().strip(",") not in _PROMPT_VERBS:
        return False
    idx = next((i for i in range(1, min(len(words), 5)) if words[i].lower() == "to"), None)
    if idx is None or idx + 1 >= len(words):
        return False
    residue = [w for w in words[1:idx] if w.lower() not in ("and", "or")]
    if residue and all(_clean_key(w) for w in residue):
        return False                             # tuş adı okunmuş: normal çevrilsin
    for w in residue:
        core = w.strip("[]()<>{}.,")
        if not any(ch.isalpha() for ch in w) or len(core) <= 1 or core.lower() in _KEY_NAMES:
            continue
        if core.isupper() and len(core) <= 3 and core not in _REAL_UPPER:
            continue
        return False                             # gerçek bir sözcük: ipucu değil ("Use the car to escape")
    if not residue and words[idx + 1].lower().strip(",.") in _DETERMINERS:
        return False                             # "Hold to your course" konuşmadır
    return True


def is_short_hud(text: str) -> bool:
    """Tek satır, en çok üç sözcük, hiç küçük harf yok, cümle sonu noktalaması yok: "TAKE AMMO PACK (0/3)", "SIT",
    "• ADD TO TRUNK". Bunlar etkileşim/HUD yazısıdır, altyazı değil ("OKAY.", "WHAT?" altyazıdır)."""
    t = text.strip()
    letters = [ch for ch in t if ch.isalpha()]
    if not letters or any(ch.islower() for ch in letters) or _SENT_END_STRICT.search(t):
        return False
    return sum(1 for w in t.split() if any(ch.isalpha() for ch in w)) <= 3


_PLATE_TOKEN = re.compile(r"[A-Z0-9]{2,8}")
_PLATE_WORDS = {"LEONIDA", "SAN ANDREAS", "VICE CITY", "LIBERTY CITY", "LOS SANTOS", "SUNSHINE STATE"}


def is_plate_or_name(text: str, names: set[str] | None = None) -> bool:
    """Araç plakası ("46EEK572", "5ABC 123", "LUCIA1") ya da plakadaki eyalet yazısı ("LEONIDA") gibi çevrilmemesi
    gereken yazı mı? Yalnız özel adlardan oluşan satır ("Vice City", "Jason") da çevrilmez: çevirisi kendisiyle aynı."""
    t = text.strip().strip(".,·-")
    if not t:
        return False
    up = re.sub(r"\s+", " ", t.upper())
    if up in _PLATE_WORDS:
        return True
    toks = t.split()
    if 1 <= len(toks) <= 2 and all(_PLATE_TOKEN.fullmatch(x) for x in toks):
        alnum = sum(len(x) for x in toks)
        if 4 <= alnum <= 10 and any(ch.isdigit() for ch in t) and any(ch.isalpha() for ch in t):
            return True                          # plaka: büyük harf + rakam, 1-2 parça, kısa ("WASTED" plaka değil)
    if names:
        low = {n.lower() for n in names}
        if t.lower() in low:
            return True
    return False


_SENT_END_STRICT = re.compile(r"[.!?…]\W*$")


class StickyRows:
    """Konuşma değişirken ekranda sabit duran satırı (GTA 6'da konuşmanın hemen altında dakikalarca duran görev yazısı)
    bulur. En az 6 sn ekranda kalan ve yanında ondan en az 3 sn sonra gelmiş başka satır bulunan satır sabittir.
    Sabit satır diyalogla birleştirilmez, kendi paragrafı olarak bir kez çevrilir ve yerinde kalır."""

    STICKY_S = 6.0
    YOUNGER_S = 3.0

    def __init__(self):
        self.rows: list[dict] = []

    def reset(self) -> None:
        self.rows = []

    def update(self, texts: list[str], now: float) -> set[int]:
        from rapidfuzz import fuzz

        used: set[int] = set()
        matched: list[dict | None] = []
        for text in texts:
            key = normalize_text(text)
            if len(key) < 3:
                matched.append(None)
                continue
            row = None
            for j, r in enumerate(self.rows):
                if j not in used and fuzz.ratio(key, r["key"]) >= 85:
                    row = r
                    used.add(j)
                    break
            if row is None:
                row = {"key": key, "since": now, "sticky": False}
                self.rows.append(row)
                used.add(len(self.rows) - 1)
            matched.append(row)
        present = [r for r in matched if r is not None]
        for r in present:
            if not r["sticky"] and now - r["since"] >= self.STICKY_S and \
                    any(o["since"] - r["since"] >= self.YOUNGER_S for o in present):
                r["sticky"] = True
        # Her okuma bölgenin tamamıdır: bu okumada olmayan satır ekrandan kalkmıştır
        self.rows = present
        return {i for i, r in enumerate(matched) if r is not None and r["sticky"]}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w']+", " ", text.lower())).strip()


def match_keys(zone: str, prev: dict[str, tuple[int, int]], spans: list[tuple[int, int]]) -> list[str]:
    """Her paragrafa bölge içinde kalıcı bir ad ver: önceki karede dikeyde örtüştüğü paragrafın adı, yoksa yeni ad
    (ilk paragraf bölgenin adını alır, sonrakiler "altyazi.2", "altyazi.3"...)."""
    keys: list[str] = []
    free = dict(prev)
    for y0, y1 in spans:
        best, best_ov = None, 0.0
        for k, (p0, p1) in free.items():
            ov = (min(y1, p1) - max(y0, p0)) / max(1, min(y1 - y0, p1 - p0))
            if ov > best_ov:
                best, best_ov = k, ov
        if best is not None and best_ov >= 0.5:
            keys.append(best)
            free.pop(best)
            continue
        used = set(keys) | set(free)
        name, n = zone, 2
        while name in used:
            name, n = f"{zone}.{n}", n + 1
        keys.append(name)
    return keys


def _ocr_clean(text: str) -> str:
    """Nino OcrNoise: süslü/solan yazıda okunan çöp sözcükler ("ou$3e") satır birleşmeden önce atılır."""
    try:
        from .kalite.ocr_gurultu import clean
        return clean(text)
    except Exception:  # noqa: BLE001
        return text


def _reread(newer: str, older: str) -> bool:
    """Nino Rereads: yeni okuma eskinin yarım ya da bozuk tekrarı mı (çevirmene ikinci kez gitmesin)."""
    try:
        from .oyun.yeniden_okuma import is_reread_of
        return is_reread_of(newer, older)
    except Exception:  # noqa: BLE001
        return False


class Pipeline:
    def __init__(self, cfg: Config, sink: Sink, recognizer, engine: TranslationEngine, source=None,
                 frame_sink=None):
        self.cfg = cfg
        self.sink = sink
        self.rec = recognizer
        self.engine = engine
        self.source = source
        self.frame_sink = frame_sink          # "pencere" gösterim modunda her kareyi alır
        self.zones: list[tuple[BolgeCfg, ZoneDetector]] = [(z, ZoneDetector(z)) for z in cfg.bolgeler
                                                           if getattr(z, "aktif", True)]
        self._last_read: dict[str, float] = {}
        self._cond = threading.Condition()
        self._latest: tuple[np.ndarray, float] | None = None
        self._running = False
        self._stopped = False      # stop() çağrıldı: geç gelen çeviriler yok sayılır
        self._seq = 0
        self._current: dict[str, tuple[int, str, int]] = {}   # bölge -> (seq, ingilizce, gösterilen kalite)
        self._blocks: dict[str, dict[str, tuple[int, int]]] = {}   # bölge -> {paragraf adı: (y0, y1)}
        self._sticky: dict[str, StickyRows] = {}                     # bölge -> sabit (görev/HUD) satır izleyici
        self._lock = threading.Lock()
        self.frames = 0
        self.last_frame: np.ndarray | None = None
        self.paused = False
        self.notice = None                     # arayüze kısa bilgi mesajı: notice(str)
        self._fs_reader = None
        self._fs_request = False
        self._fs_zones: list[str] = []
        self._fs_until = 0.0
        self._fs_busy = False
        self.layout_top = None                 # öğrenilen altyazı şeridinin üstü (oyun/altyazi_yeri.py): () -> float | None
        self.scene = None                      # ekran yazıları: telefon, harita kartı, mesaj kartı (sahne/izleyici.py)
        if getattr(cfg.ceviri, "ekran_yazilari", False) and hasattr(engine, "translate_now"):
            try:
                self.scene = self._make_scene()
            except Exception:  # noqa: BLE001
                log.exception("Ekran yazıları izleyicisi açılamadı")

    def _make_scene(self):  # noqa: ANN202
        from .sahne.izleyici import SceneWatcher
        holder: dict = {}

        def read_lines(img):  # noqa: ANN001, ANN202
            if "r" not in holder:                    # ilk kullanımda (model yüklemesi altyazıyı bekletmesin)
                from .fullscreen import FullScreenReader
                holder["r"] = FullScreenReader(min_score=0.5, motor=getattr(self.cfg.ocr, "motor", "otomatik"))
            return holder["r"].read_lines(img)

        def on_items(items) -> None:  # noqa: ANN001
            if self._stopped:
                return
            overlay = getattr(self.sink, "overlay", None)
            if overlay:
                overlay([it.to_json() for it in items])

        w = SceneWatcher(read_lines, self.engine.translate_now, on_items, lookup=self.engine.lookup)
        w.phone_mode = getattr(self.cfg.ceviri, "telefon_yeri", "yan")
        return w

    # ------------------------------------------------------------------ yaşam döngüsü
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="isci")
        self._thread.start()
        if self.source is not None:
            self.source.start(self.on_frame)

    def stop(self) -> None:
        self._running = False
        self._stopped = True
        with self._lock:          # durdurulduktan sonra gelen geç çeviriler ekrana basılmasın (TV'de takılı kalırdı)
            self._current.clear()
            self._seq += 1
        if self.scene is not None:
            self.scene.enabled = False
            overlay = getattr(self.sink, "overlay", None)
            if overlay:
                overlay([])
        if self.source is not None:
            self.source.stop()
        with self._cond:
            self._cond.notify_all()

    def on_frame(self, frame: np.ndarray, t: float) -> None:
        self.frames += 1
        self.last_frame = frame
        if self.frame_sink is not None:
            self.frame_sink(frame, t)
        with self._cond:
            self._latest = (frame, t)
            self._cond.notify()

    def _worker(self) -> None:
        while self._running:
            with self._cond:
                while self._latest is None and self._running:
                    self._cond.wait(0.5)
                item, self._latest = self._latest, None
            if item is not None:
                try:
                    self.process(*item)
                except Exception:  # noqa: BLE001
                    log.exception("Kare işlenirken hata")

    # ------------------------------------------------------------- komutlar
    def _say(self, msg: str) -> None:
        log.info(msg)
        if self.notice:
            self.notice(msg)

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        if self.paused:
            self._clear_all()
            self._say("Çeviri duraklatıldı")
        else:
            for _, det in self.zones:
                det.reject()
            self._say("Çeviri devam ediyor")
        return self.paused

    def request_fullscreen(self) -> None:
        """Ekrandaki her şeyi çevir. Zaten açıksa kapatır."""
        if self._fs_zones:
            self._clear_fullscreen()
            self._say("Tam ekran çeviri kapatıldı")
        elif not self._fs_busy:
            self._fs_request = True

    def _clear_all(self) -> None:
        self._blocks.clear()
        self._sticky.clear()
        with self._lock:
            zones = list(self._current)
            self._current.clear()
            self._seq += 1
        for z in zones:
            self.sink.clear(z)
        self._fs_zones = []

    def _clear_fullscreen(self) -> None:
        with self._lock:
            zones, self._fs_zones = self._fs_zones, []
            for z in zones:
                self._current.pop(z, None)
            self._seq += 1
        for z in zones:
            self.sink.clear(z)

    def _show_fullscreen(self, blocks: list, t: float, quick: bool) -> None:
        """Tam ekran blokları göster. quick=True: yerel çeviri (görsel okuma birazdan geliyorsa)."""
        zones = []
        for i, b in enumerate(blocks):
            name = f"tam{i}"
            zones.append(name)
            with self._lock:
                self._seq += 1
                seq = self._seq
                self._current[name] = (seq, b.text, 0)
            base = DisplayItem(zone=name, rect=b.rect, zone_rect=b.rect, line_h=b.line_h, english=b.text,
                               text="", align="sol", anchor="ust", box_opacity=255, font_scale=1.0, seq=seq)
            self.engine.submit(b.text, "arayuz", lambda r, bb=base, t0=t: self._on_translation(bb, t0, r),
                               refine=not quick)
        self._fs_zones = zones
        self._fs_until = time.time() + self.cfg.kisayol.tam_ekran_sure

    def _run_fullscreen(self, frame: np.ndarray, t: float) -> None:
        self._fs_busy = True
        try:
            self._say("Ekran çevriliyor...")
            if self._fs_reader is None:
                from .fullscreen import FullScreenReader
                self._fs_reader = FullScreenReader(motor=getattr(self.cfg.ocr, "motor", "otomatik"))
            blocks = self._fs_reader.read(frame)
            names = set(self.cfg.ceviri.sozluk)
            blocks = [b for b in blocks if not is_plate_or_name(b.text, names)]   # plakalar, yalnız özel adlar
            vision = getattr(self.engine, "can_read_screen", False) and self.cfg.kisayol.tam_ekran_gorsel
            if blocks:
                self._show_fullscreen(blocks, t, quick=vision)
            if vision:
                self._say(f"{getattr(self.engine.refine, 'name', 'yapay zekâ').capitalize()} ekranı okuyor...")
                items = self._vision(frame, blocks, t)
                if items:
                    self._say(f"Ekrandaki {len(items)} yazı Claude ile çevrildi")
                    return
            if blocks:
                self._say(f"Ekrandaki {len(blocks)} yazı çevrildi")
            else:
                self._say("Ekranda çevrilecek yazı bulunamadı")
        except Exception:  # noqa: BLE001
            log.exception("Tam ekran çeviri hatası")
        finally:
            self._fs_busy = False

    def _vision(self, frame: np.ndarray, blocks: list, t: float) -> list:
        """Ekran görüntüsünü (OCR kutuları numaralı) Claude'a gönder; sonuçları OCR konumlarıyla göster."""
        import cv2

        from .translate import REFINED
        img = np.ascontiguousarray(frame[..., :3]).copy()
        h, w = img.shape[:2]
        for i, b in enumerate(blocks):
            x0, y0, x1, y1 = (int(b.rect[0] * w), int(b.rect[1] * h), int(b.rect[2] * w), int(b.rect[3] * h))
            cv2.rectangle(img, (x0, y0), (x1, y1), (60, 220, 255), 2)
            cv2.putText(img, str(i), (x0, max(14, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 220, 255), 2)
        scale = min(1.0, 1568 / max(w, h))   # Claude'un önerdiği en büyük kenar
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return []
        try:
            items = self.engine.refine.read_screen(jpg.tobytes(), [(i, b.text) for i, b in enumerate(blocks)])
        except Exception as e:  # noqa: BLE001
            log.warning("Claude görsel okuma hatası: %s", e)
            return []
        from .fullscreen import Block
        shown = []
        for it in items:
            en, tr = (it.get("english") or "").strip(), (it.get("turkish") or "").strip()
            if not en or not tr:
                continue
            i = it.get("id", -1)
            if isinstance(i, int) and 0 <= i < len(blocks):
                b = blocks[i]
                rect, lh = b.rect, b.line_h
            else:
                box = it.get("box") or []
                if len(box) != 4 or box[2] <= box[0] or box[3] <= box[1]:
                    continue
                rect = tuple(min(1.0, max(0.0, v / 1000)) for v in box)
                lh = min(0.04, rect[3] - rect[1])
            shown.append((Block(en, rect, lh), tr))
            self.engine.cache.put(en, tr, REFINED, "claude-görsel")
        if not shown:
            return []
        self._clear_fullscreen()
        zones = []
        for k, (b, tr) in enumerate(shown):
            name = f"tam{k}"
            zones.append(name)
            with self._lock:
                self._seq += 1
                seq = self._seq
                self._current[name] = (seq, b.text, REFINED)
            item = DisplayItem(zone=name, rect=b.rect, zone_rect=b.rect, line_h=b.line_h, english=b.text, text=tr,
                               align="sol", anchor="ust", box_opacity=255, font_scale=1.0, source="claude-görsel",
                               quality=REFINED, latency_ms=(time.perf_counter() - t) * 1000, seq=seq)
            self.sink.show(item)
        self._fs_zones = zones
        self._fs_until = time.time() + self.cfg.kisayol.tam_ekran_sure
        return shown

    # -------------------------------------------------------------------- iş
    def process(self, frame: np.ndarray, t: float) -> None:
        if self._fs_request:
            self._fs_request = False
            threading.Thread(target=self._run_fullscreen, args=(frame.copy(), t), daemon=True).start()
        if self._fs_zones and time.time() > self._fs_until:
            self._clear_fullscreen()
        if self.paused:
            return
        if self.scene is not None:
            self.scene.offer(frame)
        h, w = frame.shape[:2]
        learned = self.layout_top() if self.layout_top else None
        for zcfg, det in self.zones:
            x0, y0, x1, y1 = zone_rect(zcfg, w, h)
            if learned and zcfg.tur == "altyazi" and y0 / h < learned < y1 / h - 0.06:
                y0 = int(learned * h)             # altyazının yeri öğrenildi: yalnız o şerit okunur (hızlı, HUD karışmaz)
            if getattr(self.cfg.ocr, "sik_oku", False) and det.shown_sig is not None \
                    and t - self._last_read.get(zcfg.ad, 0.0) > 1.0:
                det.reject()                      # değişmeyen alanı da saniyede bir yeniden oku (CouchSubs)
                self._last_read[zcfg.ad] = t
            ev = det.process(frame[y0:y1, x0:x1], t)
            if ev is None:
                continue
            self._last_read[zcfg.ad] = t
            if ev.kind == "clear":
                self._sticky.pop(zcfg.ad, None)
                self._drop_keys(list(self._blocks.pop(zcfg.ad, {}) or [zcfg.ad]))
                continue

            t_ocr = time.perf_counter()
            results = self.rec.recognize([ln.image for ln in ev.lines])
            ocr_ms = (time.perf_counter() - t_ocr) * 1000
            texts = [_ocr_clean(r.text) if (r.score >= zcfg.min_skor and r.text) else "" for r in results]
            rows = [(clean_ocr(tx), b) for tx, b in rows_of([ln.box for ln in ev.lines], texts)]
            names = set(self.cfg.ceviri.sozluk)
            # Tuş simgesi okunamamış ipuçları: Claude varsa satırın resmi okunup simgeyle çevrilir, yoksa atlanır
            vision = getattr(self.engine, "can_read_images", False)
            prompts = {tx for tx, _ in rows if tx and is_button_prompt(tx)}
            rows = [(tx, b) for tx, b in rows
                    if tx and (vision or tx not in prompts) and not is_plate_or_name(tx, names)]
            sticky = self._sticky.setdefault(zcfg.ad, StickyRows()).update([tx for tx, _ in rows], t)
            blocks = [(tx, b) for tx, b, n in blocks_of(rows, ev.line_height, zcfg.paragraf_boslugu, sticky)
                      if tx and looks_like_text(tx) and not (zcfg.tur == "altyazi" and n == 1 and is_short_hud(tx))]
            if not blocks:
                det.reject()
                continue
            prev = self._blocks.get(zcfg.ad, {})
            keys = match_keys(zcfg.ad, prev, [(b[1], b[3]) for _, b in blocks])
            self._blocks[zcfg.ad] = {k: (b[1], b[3]) for k, (_, b) in zip(keys, blocks)}
            self._drop_keys([k for k in prev if k not in keys])
            phone = self.scene.phone_box() if self.scene is not None else None
            for key, (text, (bx0, by0, bx1, by1)) in zip(keys, blocks):
                if phone is not None and (self.scene.is_phone_text(text) or (
                        phone.left < (x0 + bx1) / w and (x0 + bx0) / w < phone.right
                        and phone.top < (y0 + by1) / h and (y0 + by0) / h < phone.bottom)):
                    continue                      # telefondaki yazı altyazı değil: telefonun yanında çevriliyor
                with self._lock:
                    cur = self._current.get(key)
                    if cur and (cur[1] == text or worse_reread(cur[1], text) or _reread(text, cur[1])):
                        continue                  # aynı metin ya da aynı satırın daha kötü / yarım okunuşu
                    self._seq += 1
                    seq = self._seq
                    self._current[key] = (seq, text, 0)
                base = DisplayItem(
                    zone=key,
                    rect=((x0 + bx0) / w, (y0 + by0) / h, (x0 + bx1) / w, (y0 + by1) / h),
                    zone_rect=(x0 / w, y0 / h, x1 / w, y1 / h),
                    line_h=ev.line_height / h,
                    english=text, text="", align=zcfg.hizalama, anchor=zcfg.capa,
                    box_opacity=zcfg.kutu_opaklik, font_scale=zcfg.yazi_olcek, ocr_ms=ocr_ms, seq=seq,
                )
                cb = (lambda r, b=base, t0=t: self._on_translation(b, t0, r))
                if prompts and any(p in text for p in prompts):
                    jpeg = _crop_jpeg(frame[y0:y1, x0:x1], (bx0, by0, bx1, by1), ev.line_height)
                    if jpeg:
                        self.engine.submit_image(text, jpeg, zcfg.tur, cb)
                        continue
                self.engine.submit(text, zcfg.tur, cb)

    def _drop_keys(self, keys: list[str]) -> None:
        if not keys:
            return
        with self._lock:
            self._seq += 1
            for k in keys:
                self._current.pop(k, None)
        for k in keys:
            self.sink.clear(k)

    def _on_translation(self, base: DisplayItem, t_frame: float, r: Result) -> None:
        if self._stopped:
            return
        with self._lock:
            cur = self._current.get(base.zone)
            if not cur or cur[0] != base.seq or r.quality < cur[2]:
                return                            # bu arada yeni metin geldi ya da daha iyisi zaten ekranda
            self._current[base.zone] = (cur[0], cur[1], r.quality)
        text = r.text
        if not getattr(self.cfg.ceviri, "konusan_goster", True):
            from .kalite import konusan
            text = konusan.present(text, base.english, False)     # "LUCIA: Gitmeliyiz." → "Gitmeliyiz."
        item = replace(base, text=text, source=r.source, quality=r.quality, mt_ms=r.ms,
                       latency_ms=(time.perf_counter() - t_frame) * 1000)
        log.info("[%s] %4.0f ms (OCR %.0f, %s %.0f) %s → %s", item.zone, item.latency_ms, item.ocr_ms,
                 item.source, item.mt_ms, item.english, item.text)
        self.sink.show(item)
