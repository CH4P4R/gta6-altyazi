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
        self._lock = threading.Lock()
        self.frames = 0

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

    # -------------------------------------------------------------------- iş
    def process(self, frame: np.ndarray, t: float) -> None:
        h, w = frame.shape[:2]
        for zcfg, det in self.zones:
            x0, y0, x1, y1 = zone_rect(zcfg, w, h)
            ev = det.process(frame[y0:y1, x0:x1], t)
            if ev is None:
                continue
            if ev.kind == "clear":
                with self._lock:
                    self._seq += 1
                    self._current.pop(zcfg.ad, None)
                self.sink.clear(zcfg.ad)
                continue

            t_ocr = time.perf_counter()
            results = self.rec.recognize([ln.image for ln in ev.lines])
            ocr_ms = (time.perf_counter() - t_ocr) * 1000
            good = [r.text for r in results if r.score >= zcfg.min_skor and r.text]
            text = clean_ocr(" ".join(good))
            if not text or not looks_like_text(text):
                det.reject()
                continue
            with self._lock:
                cur = self._current.get(zcfg.ad)
                if cur and cur[1] == text:
                    continue                      # aynı metin (arka plan oynadı ama yazı değişmedi)
                self._seq += 1
                seq = self._seq
                self._current[zcfg.ad] = (seq, text, 0)

            bx0, by0, bx1, by1 = ev.bbox
            base = DisplayItem(
                zone=zcfg.ad,
                rect=((x0 + bx0) / w, (y0 + by0) / h, (x0 + bx1) / w, (y0 + by1) / h),
                zone_rect=(x0 / w, y0 / h, x1 / w, y1 / h),
                line_h=ev.line_height / h,
                english=text, text="", align=zcfg.hizalama, anchor=zcfg.capa,
                box_opacity=zcfg.kutu_opaklik, font_scale=zcfg.yazi_olcek, ocr_ms=ocr_ms, seq=seq,
            )
            self.engine.submit(text, zcfg.tur, lambda r, b=base, t0=t: self._on_translation(b, t0, r))

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
