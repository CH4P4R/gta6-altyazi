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

    def show(self, item: DisplayItem) -> None:
        for s in self.sinks:
            s.show(item)

    def clear(self, zone: str) -> None:
        for s in self.sinks:
            s.clear(zone)


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


def group_blocks(boxes: list[tuple[int, int, int, int]], texts: list[str], line_h: float,
                 gap_ratio: float = 0.45) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Satırları paragraflara ayır: [(metin, kutu)], yukarıdan aşağı.

    GTA'da görev yazısı ("Arabaya git") altta dururken diyalog altyazısı onun üstüne çıkar. İkisi tek metin gibi
    çevrilirse anlamsız bir cümle çıkıyordu. Satırlar arası boşluk büyükse ayrı paragraf sayılır.
    Kutular OCR için yazının çevresine lh/4 pay eklenmiş hâldedir; boşluk bu payla birlikte ölçülür.
    """
    items = [(b, t) for b, t in zip(boxes, texts) if t]
    items.sort(key=lambda bt: (bt[0][1], bt[0][0]))
    # aynı satırdaki parçalar (dikeyde örtüşen) tek satır
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
    blocks: list[list] = []
    for rb, parts in rows:
        text = " ".join(t for _, t in sorted(parts))
        gap = rb[1] - blocks[-1][1][3] if blocks else 0
        # Cümle bitmeden satır kırıldıysa ("Hurry up, they are right" / "behind us!") boşluk biraz geniş olsa da
        # aynı paragraftır; görev yazısı hep bitmiş bir cümlenin altında durur
        unfinished = bool(blocks) and not _SENT_END.search(blocks[-1][0])
        if blocks and (gap <= gap_ratio * line_h or (unfinished and gap <= 1.2 * line_h)):
            bb = blocks[-1][1]
            blocks[-1][0] += " " + text
            blocks[-1][1] = (min(bb[0], rb[0]), bb[1], max(bb[2], rb[2]), max(bb[3], rb[3]))
        else:
            blocks.append([text, rb])
    return [(t, b) for t, b in blocks]


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


class Pipeline:
    def __init__(self, cfg: Config, sink: Sink, recognizer, engine: TranslationEngine, source=None,
                 frame_sink=None):
        self.cfg = cfg
        self.sink = sink
        self.rec = recognizer
        self.engine = engine
        self.source = source
        self.frame_sink = frame_sink          # "pencere" gösterim modunda her kareyi alır
        self.zones: list[tuple[BolgeCfg, ZoneDetector]] = [(z, ZoneDetector(z)) for z in cfg.bolgeler]
        self._cond = threading.Condition()
        self._latest: tuple[np.ndarray, float] | None = None
        self._running = False
        self._seq = 0
        self._current: dict[str, tuple[int, str, int]] = {}   # bölge -> (seq, ingilizce, gösterilen kalite)
        self._blocks: dict[str, dict[str, tuple[int, int]]] = {}   # bölge -> {paragraf adı: (y0, y1)}
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

    # ------------------------------------------------------------------ yaşam döngüsü
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True, name="isci")
        self._thread.start()
        if self.source is not None:
            self.source.start(self.on_frame)

    def stop(self) -> None:
        self._running = False
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
                self._fs_reader = FullScreenReader()
            blocks = self._fs_reader.read(frame)
            vision = getattr(self.engine, "can_read_screen", False) and self.cfg.kisayol.tam_ekran_gorsel
            if blocks:
                self._show_fullscreen(blocks, t, quick=vision)
            if vision:
                self._say("Claude ekranı okuyor...")
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
        h, w = frame.shape[:2]
        for zcfg, det in self.zones:
            x0, y0, x1, y1 = zone_rect(zcfg, w, h)
            ev = det.process(frame[y0:y1, x0:x1], t)
            if ev is None:
                continue
            if ev.kind == "clear":
                self._drop_keys(list(self._blocks.pop(zcfg.ad, {}) or [zcfg.ad]))
                continue

            t_ocr = time.perf_counter()
            results = self.rec.recognize([ln.image for ln in ev.lines])
            ocr_ms = (time.perf_counter() - t_ocr) * 1000
            texts = [r.text if (r.score >= zcfg.min_skor and r.text) else "" for r in results]
            blocks = [(clean_ocr(tx), b) for tx, b in group_blocks([ln.box for ln in ev.lines], texts,
                                                                    ev.line_height, zcfg.paragraf_boslugu)]
            blocks = [(tx, b) for tx, b in blocks if tx and looks_like_text(tx)]
            if not blocks:
                det.reject()
                continue
            prev = self._blocks.get(zcfg.ad, {})
            keys = match_keys(zcfg.ad, prev, [(b[1], b[3]) for _, b in blocks])
            self._blocks[zcfg.ad] = {k: (b[1], b[3]) for k, (_, b) in zip(keys, blocks)}
            self._drop_keys([k for k in prev if k not in keys])
            for key, (text, (bx0, by0, bx1, by1)) in zip(keys, blocks):
                with self._lock:
                    cur = self._current.get(key)
                    if cur and (cur[1] == text or worse_reread(cur[1], text)):
                        continue                  # aynı metin ya da aynı satırın daha kötü okunuşu
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
                self.engine.submit(text, zcfg.tur, lambda r, b=base, t0=t: self._on_translation(b, t0, r))

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
        with self._lock:
            cur = self._current.get(base.zone)
            if not cur or cur[0] != base.seq or r.quality < cur[2]:
                return                            # bu arada yeni metin geldi ya da daha iyisi zaten ekranda
            self._current[base.zone] = (cur[0], cur[1], r.quality)
        item = replace(base, text=r.text, source=r.source, quality=r.quality, mt_ms=r.ms,
                       latency_ms=(time.perf_counter() - t_frame) * 1000)
        log.info("[%s] %4.0f ms (OCR %.0f, %s %.0f) %s → %s", item.zone, item.latency_ms, item.ocr_ms,
                 item.source, item.mt_ms, item.english, item.text)
        self.sink.show(item)
