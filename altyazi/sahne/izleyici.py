# SPDX-License-Identifier: AGPL-3.0-only
"""Ekrandaki yazıları kendiliğinden çevirir: oyundaki telefon, harita görev kartı, telefona gelen mesaj ve arama kartı.

Nino Game Translator'ın (yunusdemirbag/nino-game-translator, AGPL-3.0) Mac uygulamasındaki watchPhone / showMapCard /
ScreenHints mantığının Python karşılığıdır. Altyazı hattını bekletmez: her şey arka planda, kendi iş parçacığında ve
seyrek (0,6-1,5 sn'de bir) yapılır. Türkçeler TV'ye `screen` olayıyla `overlay` olarak gider (altyazıyı silmez):

- Telefon (sohbet): telefonun yanında dikey mesajlaşma paneli, her mesaj kendi balonunda, oyundaki sırayla.
- Telefon (uygulama: banka, haber): her yazının hemen altında sade Türkçe.
- Harita: seçili görevin kartının Türkçesi kartın hemen altında (yer yoksa üstünde), kart gibi.
- Mesaj kartı: Türkçesi kartın hemen üstünde, gönderenin adıyla, kutusuz; arama kartı: "Paradise Taxi aranıyor…".
"""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import numpy as np

from . import harita, mesaj, telefon
from .ekran import ScreenItem
from .metin import Reading, TextBox, TextLine

log = logging.getLogger(__name__)

MAP_KEYS = {"recenter", "2d view", "3d view", "add marker", "set destination", "close menu"}
CALL_STATUS = {"calling...": "aranıyor…", "calling…": "aranıyor…", "calling": "aranıyor…",
               "incoming call": "arıyor…", "incoming call...": "arıyor…"}
MAP_TERMS = [("KAPALI TUTULMASI", "DEPOSU"), ("Kapalı Tutulması", "Deposu"), ("kapalı tutulması", "deposu"),
             ("işaretli faturaların", "işaretli banknotların"), ("işaretli faturalar", "işaretli banknotlar"),
             ("işaretli fatura", "işaretli banknot"), ("narkotik", "uyuşturucu"), ("NARKOTİK", "UYUŞTURUCU")]
PLACE_WORDS = {"CUSTOMS", "AUTO", "SHOP", "BAR", "CLUB", "MOTORS", "GARAGE", "CARE", "SPEEDWAY", "DINER", "CAFE",
               "GRILL", "MOTEL", "HOTEL", "STORE", "MART", "LOUNGE", "SALOON", "TACKLE", "ANCHOR", "MARINA",
               "AMMU-NATION", "BARBER", "TATTOO", "PAWN"}
BUSINESS = ["distributor", "shop", "store", "dive bar", " bar", "restaurant", "dealer", "club", "diner", "garage",
            "convenience", "wholesaler", "boutique", "salon", "motel", "hotel", "bodega"]
_ICON = re.compile(r"[←-⇿⌀-➿⬀-⯿-]")


def normalize(s: str) -> str:
    """Nino'nun TextMatch.normalize'ı: küçük harf, harf/rakam dışı boşluk, tek boşluk."""
    return " ".join("".join(c if c.isalnum() else " " for c in s.lower()).split())


def without_icons(text: str) -> str:
    return " ".join(_ICON.sub(" ", text).split())


def wrap(text: str, width: float, line: float) -> list[str]:
    """Yazıyı verilen genişliğe (ekran oranı) böler; harf genişliği satır yüksekliğinin ~0,5'i (16:9)."""
    per_line = max(12, int(width / max(0.004, line * 0.5 * 9 / 16)))
    out, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > per_line:
            out.append(cur)
            cur = ""
        cur = word if not cur else cur + " " + word
    if cur:
        out.append(cur)
    return out or [text]


def is_place_name(title: str, description: str = "") -> bool:
    """Kart başlığı dükkân/mekân adıysa ("RIDEOUT CUSTOMS") çevrilmez; "DIŞARIDAN GELEN GÜMRÜK" gibi saçma çıkıyordu."""
    about = description.lower()
    if any(b in about for b in BUSINESS):
        return True
    words = title.upper().split()
    return any(w in PLACE_WORDS for w in words) or (title.upper().startswith("THE ") and len(words) <= 4)


def map_terms(text: str) -> str:
    for a, b in MAP_TERMS:
        text = text.replace(a, b)
    return text


def tr_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


class SceneWatcher:
    """offer(frame) her karede çağrılır (hemen döner). Türkçeler değişince on_items(liste) çağrılır (boş: hepsi kalktı).

    read_lines(img) -> [(metin, (x0, y0, x1, y1) img piksel), ...] ; translate(metin, tür, bağlam) -> Türkçe | None
    """

    PHONE_EVERY, PHONE_EVERY_SHOWN, SCREEN_EVERY, TRACK_EVERY = 0.6, 1.5, 1.5, 0.25
    MESSAGE_STALE = 3.0

    def __init__(self, read_lines: Callable[[np.ndarray], list], translate: Callable[..., str | None],
                 on_items: Callable[[list[ScreenItem]], None], lookup: Callable[[str], str | None] | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.read_lines, self.translate, self.on_items = read_lines, translate, on_items
        self.lookup = lookup or (lambda _t: None)
        self.now = clock
        self.pool = ThreadPoolExecutor(3, thread_name_prefix="sahne")
        self.tr_pool = ThreadPoolExecutor(2, thread_name_prefix="sahne-ceviri")
        self.lock = threading.Lock()
        self.enabled = True
        self.phone_mode = "yan"                       # yan: telefonun yanında mesaj paneli (Nino) | ust: balonların üstünde
        self.tracker = telefon.Tracker()
        # telefon
        self.phone_items: list[ScreenItem] = []
        self.phone_base: tuple[TextBox, list[ScreenItem]] | None = None
        self.phone_key = self.phone_pending = ""
        self.phone_busy = self.track_busy = False
        self.phone_last = self.phone_seen = self.track_last = 0.0
        self.phone_shift = (0.0, 0.0)
        self.phone_shift_seen: tuple[float, float] | None = None
        self.phone_anchors: dict[str, float] = {}
        self.phone_memory: dict[str, str] = {}
        self.phone_texts: list[str] = []
        self.phone_panel_box: TextBox | None = None
        # harita ve mesaj kartı
        self.map_items: list[ScreenItem] = []
        self.map_key = ""
        self.map_memory: dict[str, list[str]] = {}
        self.map_seen_until = 0.0
        self.map_missing = 0
        self.message_items: list[ScreenItem] = []
        self.message_key = self.message_pending = ""
        self.message_seen = 0.0
        self.screen_busy = False
        self.screen_last = 0.0
        self.last_frame: np.ndarray | None = None
        self._sent: list[dict] | None = None

    # ------------------------------------------------------------------ dış arayüz
    @property
    def items(self) -> list[ScreenItem]:
        return self.phone_items + self.map_items + self.message_items

    def phone_box(self) -> TextBox | None:
        """Telefon açıksa ekranı (altyazı hattı telefonun içindeki yazıyı altyazı sanmasın)."""
        return self.phone_panel_box if self.phone_items else None

    def is_phone_text(self, english: str) -> bool:
        """Altyazı okumasında telefondaki yazılardan biri görüldüyse altyazı değildir."""
        if not self.phone_items:
            return False
        key = normalize(english)
        return bool(key) and any(key in normalize(t) or normalize(t) in key for t in self.phone_texts if len(t) > 5)

    def offer(self, frame: np.ndarray) -> None:
        if not self.enabled:
            return
        t = self.now()
        self.last_frame = frame
        if self.message_items and t - self.message_seen > self.MESSAGE_STALE:
            self.message_items = []
            self.message_key = self.message_pending = ""
            self._emit()
        if not self.phone_busy and t - self.phone_last > (self.PHONE_EVERY_SHOWN if self.phone_items else self.PHONE_EVERY):
            self.phone_last, self.phone_busy = t, True
            self.pool.submit(self._guard, self._watch_phone, frame, "phone_busy")
        elif self.phone_items and not self.track_busy and t - self.track_last > self.TRACK_EVERY:
            self.track_last, self.track_busy = t, True
            self.pool.submit(self._guard, self._track_phone, frame, "track_busy")
        if not self.screen_busy and t - self.screen_last > self.SCREEN_EVERY:
            self.screen_last, self.screen_busy = t, True
            self.pool.submit(self._guard, self._watch_screen, frame, "screen_busy")

    def reset(self) -> None:
        self.phone_items, self.map_items, self.message_items = [], [], []
        self.phone_base = None
        self.phone_key = self.phone_pending = self.map_key = self.message_key = self.message_pending = ""
        self._emit()

    def _guard(self, fn, frame, flag: str) -> None:  # noqa: ANN001
        try:
            fn(frame)
        except Exception:  # noqa: BLE001
            log.exception("Ekran yazıları okunamadı")
        finally:
            setattr(self, flag, False)

    def _emit(self) -> None:
        js = [it.to_json() for it in self.items]
        with self.lock:
            if js == self._sent:
                return
            self._sent = js
        try:
            self.on_items(self.items)
        except Exception:  # noqa: BLE001
            log.exception("Ekran yazıları gönderilemedi")

    # ------------------------------------------------------------------ okuma
    def _reading(self, img: np.ndarray, region: TextBox | None = None, max_width: int = 0) -> Reading:
        """Bölgenin yazı satırları, kare koordinatında (0-1)."""
        h, w = img.shape[:2]
        x0 = y0 = 0
        crop = img
        if region is not None:
            x0, y0 = int(max(0, region.left) * w), int(max(0, region.top) * h)
            x1, y1 = int(min(1, region.right) * w), int(min(1, region.bottom) * h)
            if x1 - x0 < 8 or y1 - y0 < 8:
                return Reading([])
            crop = img[y0:y1, x0:x1]
        scale = 1.0
        if max_width and crop.shape[1] > max_width:
            import cv2
            scale = max_width / crop.shape[1]
            crop = cv2.resize(crop, (max_width, int(crop.shape[0] * scale)), interpolation=cv2.INTER_AREA)
        lines = []
        for text, (a, b, c, d) in self.read_lines(np.ascontiguousarray(crop[..., :3])):
            box = TextBox((x0 + a / scale) / w, (y0 + b / scale) / h, (x0 + c / scale) / w, (y0 + d / scale) / h)
            lines.append(TextLine(text, box))
        lines.sort(key=lambda ln: (ln.box.top, ln.box.left))
        return Reading(lines)

    # ------------------------------------------------------------------ telefon
    def _clear_phone(self) -> None:
        self.phone_items = []
        self.phone_base = None
        self.phone_key = self.phone_pending = ""
        self._emit()

    def _watch_phone(self, frame: np.ndarray) -> None:
        if self.now() < self.map_seen_until or self.map_items:
            if self.phone_items:
                self._clear_phone()
            return
        panel = self.tracker.locate(frame)
        if panel is None:
            if self.phone_items and self.now() - self.phone_seen > 1.2:
                self._clear_phone()
            return
        self.phone_panel_box = panel.box
        reading = self._reading(frame, panel.box)
        if any(normalize(ln.text) in MAP_KEYS for ln in reading.lines):
            if self.phone_items:
                self._clear_phone()
            return
        thread = telefon.messages(reading, panel) if telefon.is_thread(reading, panel) else []
        chat = any(telefon.is_sentence(m.text) for m in thread)
        msgs = thread if chat else ([] if telefon.is_message_list(reading) else telefon.app_lines(reading, panel))
        if not msgs:
            if self.phone_items and self.now() - self.phone_seen > 1.2:
                self._clear_phone()
            return
        self.phone_seen = self.now()
        key = "|".join(f"{normalize(m.text)}@{int((m.box.top - panel.box.top) * 60)}" for m in msgs)
        if key == self.phone_key:
            return
        if self.phone_base is not None and self.phone_items:     # sohbet kaydırıldıysa eski Türkçeler hemen kalkar
            now = {normalize(m.text): m.box.top - panel.box.top for m in msgs}
            keys = [normalize(it.source) for it in self.phone_base[1] if not it.backdrop]
            common = [k for k in keys if k in now]
            moved = any(abs(self.phone_anchors.get(k, now[k]) - now[k]) > 0.02 for k in common)
            if moved or len(common) * 2 < len(keys):
                self.phone_items, self.phone_base, self.phone_key = [], None, ""
                self._emit()
        if key != self.phone_pending:                 # aynı okuma iki kez görülünce çevrilir (kaydırma bitsin)
            self.phone_pending = key
            return
        memory = dict(self.phone_memory)

        def remembered(text: str) -> str | None:
            k = normalize(text)
            if len(k.split()) < 5:
                return memory.get(k)
            hits = [(kk, v) for kk, v in memory.items() if kk == k or kk.startswith(k + " ") or kk.endswith(" " + k)]
            return max(hits, key=lambda kv: len(kv[0]))[1] if hits else None

        # Ekranın dibinde cümlesi bitmemiş son mesaj ve üstte baştan kesik ilk mesaj, tamamı görünene kadar çevrilmez
        if chat and msgs and remembered(msgs[-1].text) is None:
            last = msgs[-1]
            if last.box.bottom > panel.box.bottom - 0.06 and last.box.height > last.line_height * 1.8 \
                    and not last.text.rstrip().endswith(tuple(".!?…\")")):
                msgs = msgs[:-1]
        if chat and len(msgs) > 1 and remembered(msgs[0].text) is None and msgs[0].text[:1].islower():
            msgs = msgs[1:]
        if not msgs:
            return
        texts = [telefon.glossary(m.text) or self.lookup(m.text) or remembered(m.text) or "" for m in msgs]
        missing = [i for i, t in enumerate(texts) if not t]
        futures = {i: self.tr_pool.submit(self.translate, msgs[i].text, "mesaj" if chat else "arayuz",
                                          [(m.text, "") for m in msgs[max(0, i - 3):i]] if chat else [])
                   for i in missing}
        for i, fut in futures.items():
            try:
                tr = without_icons(fut.result(timeout=25) or "").strip()
            except Exception:  # noqa: BLE001
                tr = ""
            texts[i] = tr
            if tr:
                self.phone_memory[normalize(msgs[i].text)] = tr
        if len(self.phone_memory) > 600:
            self.phone_memory.clear()
        color = telefon.lifted_sampler(frame, panel)

        def lines(text: str, width: float, line: float) -> tuple[int, int]:
            w = wrap(text, width, line)
            return len(w), max(len(x) for x in w)
        if chat:
            if self.phone_mode == "ust":
                # Telefonun kendi ekranında: her mesajın Türkçesi balonun tam üstünde, balonun renginde (eğik
                # telefonda eğik); TV'de telefon sanki Türkçeymiş gibi görünür
                items = telefon.covers(msgs, texts, panel.angle, color=color)
            else:
                items = telefon.side_bubbles(msgs, texts, panel, chat=True, title=telefon.title_text(reading, panel),
                                             color=color, lines=lines)
        elif self.phone_mode == "ust":
            items = telefon.app_bubbles(msgs, texts, panel, color=color)
        else:
            # Banka, taksi, haber gibi uygulamalar da mesajlar gibi telefonun yanında, telefon boyunda bir panelde:
            # başlık en üstte, her satır telefondaki yerinde ve kendi zemininin renginde.
            head, head_tr = telefon.title_text(reading, panel), None
            if head:
                k = normalize(head)
                for m, t in zip(msgs, texts):
                    if normalize(m.text) == k and t:
                        head_tr = t
                if head_tr is None:
                    head_tr = telefon.glossary(head) or self.lookup(head) or self.phone_memory.get(k)
                if head_tr is None and len(k) > 2:
                    try:
                        head_tr = without_icons(self.translate(head, "arayuz", []) or "").strip() or None
                    except Exception:  # noqa: BLE001
                        head_tr = None
                    if head_tr:
                        self.phone_memory[k] = head_tr
            body = [(m, t) for m, t in zip(msgs, texts) if not head or normalize(m.text) != normalize(head)]
            items = telefon.side_bubbles([m for m, _ in body], [t for _, t in body], panel, chat=False,
                                         title=head_tr or head, color=color, lines=lines) if body else []
            if not items:
                items = telefon.app_bubbles(msgs, texts, panel, color=color)
        anchor = panel.box
        if self.phone_base is not None:              # telefon elde az oynadıysa panel yerinde kalır
            old = self.phone_base[0]
            dx = (panel.box.left + panel.box.right - old.left - old.right) / 2
            dy = (panel.box.top + panel.box.bottom - old.top - old.bottom) / 2
            if abs(dx) < 0.05 and abs(dy) < 0.05:
                items = telefon.shifted(items, -dx, -dy)
                anchor = old
        self.phone_items = items
        self.phone_texts = [m.text for m in msgs]
        self.phone_anchors = {normalize(m.text): m.box.top - panel.box.top for m in msgs}
        self.phone_base = (anchor, items)
        self.phone_shift, self.phone_shift_seen = (0.0, 0.0), None
        self.phone_key, self.phone_pending = key, ""
        shown = [it for it in items if not it.backdrop]
        log.info("telefon: %d yazı%s%s", len(shown),
                 f" ({shown[0].source[:40]} → {shown[0].translation[:40]})" if shown else "", "" if chat else " · uygulama")
        self._emit()

    def _track_phone(self, frame: np.ndarray) -> None:
        """Türkçeler balonların üstündeyken telefon elde sallanır: yalnız telefonun yeri bulunur, örtüler kaydırılır."""
        base = self.phone_base
        if base is None or not self.phone_items:
            return
        found = telefon.find(frame)
        if found is None or self.phone_base is not base:
            return
        b, f = base[0], found.box
        dx = (f.left + f.right - b.left - b.right) / 2
        dy = (f.top + f.bottom - b.top - b.bottom) / 2
        sx, sy = self.phone_shift
        if not (abs(dx - sx) > 0.009 or abs(dy - sy) > 0.012) or abs(dx) >= 0.08 or abs(dy) >= 0.08:
            self.phone_shift_seen = None
            return
        seen = self.phone_shift_seen
        if seen is None or abs(seen[0] - dx) >= 0.008 or abs(seen[1] - dy) >= 0.011:
            self.phone_shift_seen = (dx, dy)
            return
        self.phone_shift_seen = None
        self.phone_shift = ((seen[0] + dx) / 2, (seen[1] + dy) / 2)
        self.phone_items = telefon.shifted(base[1], *self.phone_shift)
        self._emit()

    # ------------------------------------------------------------------ harita ve mesaj kartı
    KEYS_REGION = TextBox(0.80, 0.68, 1.0, 0.97)       # haritanın tuş listesi ("RECENTER", "SET DESTINATION")
    CARD_REGION = TextBox(0.50, 0.40, 1.0, 1.0)        # telefona gelen mesaj/arama kartı (sağ alt)

    def _watch_screen(self, frame: np.ndarray) -> None:
        """Ucuz önce: yalnız haritanın tuş listesinin yeri okunur; harita açıksa bütün ekran (kart için)."""
        keys = self._reading(frame, self.KEYS_REGION)
        map_open = sum(1 for ln in keys.lines if normalize(ln.text) in MAP_KEYS) >= 2 or \
            (self.map_items and self.map_missing == 0 and harita.is_map_screen(keys))
        reading = self._reading(frame, max_width=1280) if map_open else \
            Reading([]) if self.phone_items else self._reading(frame, self.CARD_REGION, max_width=960)
        if map_open and harita.is_map_screen(reading):
            self.map_seen_until = self.now() + 8
            self.map_missing = 0
            card = harita.find(reading)
            if card is not None:
                self._show_map_card(card, frame)
            elif self.map_items:
                self.map_items, self.map_key = [], ""
                self._emit()
            return
        if self.map_items:
            self.map_missing += 1
            if self.map_missing >= 2:                 # sekme geçişinde bir okumada tanınmayabilir
                self.map_items, self.map_key = [], ""
                self._emit()
        if self.phone_items:
            return
        card = Reading([ln for ln in reading.lines if ln.box and ln.box.left > 0.5 and ln.box.top > 0.4])
        if card.lines:
            self._message(card)

    def _show_map_card(self, card, frame: np.ndarray) -> None:  # noqa: ANN001
        whole = " ".join([card.title, *card.sentences])
        if any(c in "ğışĞİŞ" for c in whole) or not card.sentences:
            return                                    # PS5'in kendi Türkçe bildirimi
        if (not card.title and card.box.left > 0.6 and card.box.top < 0.32) or card.box.top < 0.1:
            return                                    # PS5 bildirimi, üstteki sekme şeridi
        key = normalize(whole) + f"@{int(card.box.top * 50)}"
        if key == self.map_key:
            return
        self.map_key = key
        lines = self.map_memory.get(key)
        if lines is None:
            if self.map_items:
                self.map_items = []
                self._emit()
            lines = []
            if card.title:
                tr = without_icons(self.translate(card.title.title(), "arayuz", []) or "").strip()
                if tr:
                    lines.append(tr_upper(tr))
            for s in card.sentences:
                tr = without_icons(self.translate(s, "arayuz", []) or "").strip()
                if tr:
                    lines.append(map_terms(tr))
            if not lines or self.map_key != key:
                return
            self.map_memory[key] = lines
        lines = [map_terms(x) for x in lines]
        if card.title and lines and is_place_name(card.title, " ".join(card.sentences)):
            lines[0] = card.title
        self.map_items = [self._place_map_card(card, lines, frame)]
        log.info("harita kartı: %s → %s", whole[:50], " / ".join(lines)[:80])
        self._emit()

    def _place_map_card(self, card, lines: list[str], frame: np.ndarray) -> ScreenItem:  # noqa: ANN001
        line = min(max(card.line_height, 0.02), 0.032) * 0.85
        fr = None
        try:
            fr = harita.frame(card.box, frame)
        except Exception:  # noqa: BLE001
            fr = None
        if fr is None:
            fr = TextBox(card.box.left - 0.015, card.box.top - 0.02, card.box.right + 0.015, card.box.bottom + 0.02)
        char_w = line * 0.42 * 9 / 16
        longest = max((len(x) for x in lines), default=10)
        width = min(fr.right - fr.left, longest * char_w + 0.035)
        rows = sum(1 if i == 0 else max(1, int(np.ceil(len(t) * char_w / max(0.01, width - 0.03))))
                   for i, t in enumerate(lines))
        height = line * rows * 1.32 + 0.022
        below, above = 0.97 - (fr.bottom + 0.012), fr.top - 0.012 - 0.02
        top = fr.bottom + 0.012
        if height > below:
            if height <= above or above > below:
                if height > above:
                    line *= (above - 0.022) / (height - 0.022)
                    height = above
                top = fr.top - 0.012 - height
            else:
                line *= (below - 0.022) / (height - 0.022)
                height = below
        left = max(fr.left, card.box.left - 0.014)
        return ScreenItem(source=" ".join([card.title, *card.sentences]), translation="\n".join(lines),
                          box=TextBox(left, top, left + width, top + height), line_height=line, card=True)

    def _message(self, card: Reading) -> None:
        call = mesaj.call(card)
        if call is not None:
            self.message_seen = self.now()
            name, status = call
            key = "arama:" + name + status
            if key == self.message_key:
                return
            self.message_key, self.message_pending = key, ""
            tr = CALL_STATUS.get(status.lower().strip(), status) if status else ""
            self.message_items = [self._call_item(name, tr, [ln.box for ln in card.lines if ln.box])] if tr else []
            self._emit()
            return
        if mesaj.is_list(card) or not mesaj.is_card(card):
            return
        self.message_seen = self.now()
        name, body = mesaj.parts(card)
        key = normalize(body)
        if not key or key == self.message_key:
            return
        if key != self.message_pending:
            self.message_pending = key
            return
        self.message_key = key
        tr = without_icons(self.lookup(body) or self.translate(body, "mesaj", []) or "").strip()
        if not tr:
            return
        self.message_items = [self._message_item(name, body, tr, [ln.box for ln in card.lines if ln.box])]
        log.info("mesaj: %s: %s → %s", name, body[:40], tr[:40])
        self._emit()

    @staticmethod
    def _message_item(name: str, body: str, tr: str, boxes: list[TextBox]) -> ScreenItem:
        left = min((b.left for b in boxes), default=0.5)
        right = max((b.right for b in boxes), default=0.9)
        top = min((b.top for b in boxes), default=0.7)
        line = min(boxes[1].height if len(boxes) > 1 else 0.03, 0.032) * 0.8
        wrapped = wrap(tr, max(0.2, right - left), line)
        height = line * (len(wrapped) + 1) * 1.3
        it_top = max(0.0, top - height - 0.02)
        return ScreenItem(source=body, translation="\n".join([name, *wrapped]),
                          box=TextBox(left, it_top, max(right, left + 0.2), it_top + height), line_height=line, plain=True)

    @staticmethod
    def _call_item(name: str, status: str, boxes: list[TextBox]) -> ScreenItem:
        left = min((b.left for b in boxes), default=0.1)
        right = max((b.right for b in boxes), default=0.4)
        top = min((b.top for b in boxes), default=0.8)
        line = min(boxes[0].height if boxes else 0.03, 0.032) * 0.8
        height = line * 1.3
        it_top = max(0.0, top - height - 0.035)
        return ScreenItem(source=name, translation=f"{name} {status}",
                          box=TextBox(left, it_top, max(right, left + 0.2), it_top + height), line_height=line,
                          plain=True, italic=True)
