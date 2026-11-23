# SPDX-License-Identifier: AGPL-3.0-only
"""Oyundaki telefonun ekranı (GTA 6: dikey, beyaz, büyük dikdörtgen) ve içindeki sohbet / uygulama yazıları.

Nino'nun PhonePanel.swift dosyasından aktarıldı (PhonePanel ve PhoneThread). Telefon açıkken içindeki yazılar altyazı
değildir: siyah altyazı kutusunda değil, mesaj balonunun üstünde ya da telefonun yanındaki panelde gösterilir.

Kareler HxWx3 (BGR) ya da HxWx4 (BGRA) uint8 numpy dizileridir; örnekleyiciler (r, g, b) döndürür (RGB sırası).
"""

from __future__ import annotations

import math
import os
import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, NamedTuple, Optional, Sequence

import cv2
import numpy as np

from . import mesaj
from .ekran import ScreenItem
from .metin import (Reading, TextBox, TextLine, has_letter, letter_count, normalize, split_spaces, stride_through,
                    stride_to, swift_round, trim)


class RGB(NamedTuple):
    r: int
    g: int
    b: int


Color = Callable[[float, float], Optional[Sequence[int]]]


class Column(NamedTuple):
    left: float
    right: float


@dataclass
class Panel:
    """Bulunan ekran. Yaya hâlde telefon eğik tutulur: ekran bir paralelkenardır, aşağı indikçe sola ya da sağa kayar."""

    # Ekranı çevreleyen dikdörtgen (0–1, kareye göre).
    box: TextBox
    # Üst kenarda ekranın sol kenarı (x).
    top_left: float
    # Eğim: bir kare yüksekliği aşağı inince sol kenarın x olarak kayması (dik telefonda 0).
    lean: float
    # Ekranın genişliği (her satırda aynı).
    width: float

    @property
    def angle(self) -> float:
        """Telefonun dönme açısı (derece, saat yönü artı; kare 16:9)."""
        return math.atan(-self.lean * 16 / 9) * 180 / math.pi

    def left(self, y: float) -> float:
        """`y` yüksekliğinde ekranın sol kenarı."""
        return self.top_left + self.lean * (y - self.box.top)

    def center(self, y: float) -> float:
        return self.left(y) + self.width / 2


@dataclass
class Message:
    text: str
    box: TextBox
    line_height: float


# ---------------------------------------------------------------------------
# PhonePanel: ekranı bulma
# ---------------------------------------------------------------------------

# Koyu ekranın satırlarının en az bu kadarında beyaz yazı noktası olmalı.
DARK_TEXT_SHARE = 0.15
# Küçültülmüş karede koyu ekrandaki yazının noktası (bulanıklaşmış beyaz): en parlak kanalı en az bu kadar.
DARK_TEXT_FLOOR = 110
# Koyu temalı ekran: en parlak kanal bundan koyu.
DARK_SCREEN_CEILING = 75
# Koyu ekranın çevresindeki gövde ekrandan belirgin açıktır: en parlak kanalı en az bu kadar.
BEZEL_FLOOR = 85
# Telefon ekranında uyan iki satır arasındaki en uzun boşluk (küçültülmüş karede satır).
MAX_ROW_GAP = 10
# Bir renk kanalı en az bu kadar parlaksa (ve üçü birbirine yakınsa) nokta beyaz sayılır. Gece ekran kısılır ve
# sarımsı olur (araçta ≈185–225, yaya gece ≈130–175); gündüz 250'dir. Asıl ayırt edici şekil ve siyah çerçevedir.
WHITE_FLOOR = 118
# Telefonun siyah çerçevesi: ekranın hemen solu ve sağı bundan koyu olmalı.
DARK_CEILING = 90
# Telefon ekranının genişliği (kare genişliğine oranla).
WIDTH_RANGE = (0.12, 0.30)
# Telefon ekranının ortasının durabileceği yer (x; yaya ≈0.48, araçta ≈0.69).
CENTER_RANGE = (0.30, 0.80)
# Telefon ekranının yüksekliği (kare yüksekliğine oranla).
HEIGHT_RANGE = (0.38, 0.86)


def _quot(a: int, b: int) -> int:
    """Swift tamsayı bölmesi (sıfıra doğru kırpar)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _rgb(frame, width: int, height: int) -> Optional[np.ndarray]:
    """Kare `width`×`height` boyutuna küçültülür; RGB, HxWx3 uint8. Swift kareyi CGContext'e orta kaliteyle çizer;
    Nino'nun gerçek kare örneklerinde (koyu Rydeme ekranı dahil) aynı sonucu veren OpenCV süzgeci bikübiktir (alan
    ortalaması ince çerçeveyi bulanıklaştırıp koyu ekranı kaçırıyordu)."""
    if frame is None:
        return None
    img = np.asarray(frame)
    if img.size == 0:
        return None
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = img[:, :, :3]
    elif img.ndim != 3 or img.shape[2] != 3:
        return None
    if img.shape[0] != height or img.shape[1] != width:
        img = cv2.resize(np.ascontiguousarray(img), (width, height), interpolation=cv2.INTER_CUBIC)
    return np.ascontiguousarray(img[:, :, ::-1])


def find(frame) -> Optional[Panel]:
    """Karede telefonun beyaz ekranı; yoksa None.

    Kare küçültülür ve her satırda en uzun beyaz şerit aranır. Telefonun ekranı çok sayıda satırda aynı genişlikte,
    kenarları bir doğru üzerinde duran şerit verir; hemen iki yanında telefonun siyah çerçevesi vardır."""
    width, height = 240, 135
    pixels = _rgb(frame, width, height)
    if pixels is None:
        return None
    px = pixels.astype(np.int32)
    low = px.min(axis=2)
    spread = px.max(axis=2) - low
    white = ((low >= WHITE_FLOOR) & (spread <= 45)).tolist()
    dark = (low < DARK_CEILING).tolist()
    light = _find_grid(width, height, white, dark)
    if light is not None:
        return light
    # Telefon elde bir süre dokunulmadan durunca ekranı kararıyor (gece beyaz ekran ≈70). Kare karanlıksa ortasındaki
    # en aydınlık kısım beyaza çekilip beyaz ekran yeniden aranır (köşelerdeki parlak HUD yazıları sayılmaz).
    middle = np.sort(low[height // 10:height * 9 // 10:2, width * 15 // 100:width * 85 // 100:2].ravel())
    bright = 0 if middle.size == 0 else int(middle[middle.size * 95 // 100])
    if 40 <= bright < WHITE_FLOOR:
        gain = 225.0 / float(bright)
        lifted_low = (low.astype(np.float64) * gain).astype(np.int64)
        lifted_spread = (spread.astype(np.float64) * gain).astype(np.int64)
        dim = _find_grid(width, height,
                         ((lifted_low >= WHITE_FLOOR) & (lifted_spread <= 45)).tolist(),
                         (lifted_low < DARK_CEILING).tolist())
        if dim is not None:
            return dim
    # Koyu temalı uygulama (GTA 6 Rydeme): ekran koyu, çevresindeki gövde açık. Aynı şekil sınamaları tersine
    # çevrilmiş renklerle.
    high = low + spread
    found = _find_grid(width, height,
                       ((high <= DARK_SCREEN_CEILING) & (spread <= 40)).tolist(),
                       (high >= BEZEL_FLOOR).tolist())
    if found is None or not found.box.bottom <= 0.96:
        return None
    # Koyu kıyafet ya da gölge de koyu dikdörtgen verebiliyor: koyu ekranın satırlarının belirgin bir kısmında beyaz
    # yazı noktaları olmalı.
    top = int(found.box.top * height)
    bottom = int(found.box.bottom * height)
    highs = high.tolist()
    texty = 0
    for y in range(top, max(top + 1, bottom)):
        start = int(found.left(y / height) * width) + 2
        end = start + int(found.width * width) - 4
        if not end > start:
            continue
        row = highs[y]
        count = sum(1 for x in range(start, end + 1) if row[min(width - 1, max(0, x))] >= DARK_TEXT_FLOOR)
        if count >= 2 and count <= (end - start + 1) * 0.6:
            texty += 1
    return found if texty >= max(1, bottom - top) * DARK_TEXT_SHARE else None


def find_map(width: int, height: int, is_white: Callable[[int, int], bool],
             is_dark: Callable[[int, int], bool]) -> Optional[Panel]:
    """Beyaz/koyu nokta haritasında telefonun ekranı (sınama için ayrı; Swift `find(width:height:isWhite:isDark:)`)."""
    white = [[bool(is_white(x, y)) for x in range(width)] for y in range(height)]
    dark = [[bool(is_dark(x, y)) for x in range(width)] for y in range(height)]
    return _find_grid(width, height, white, dark)


def _find_grid(width: int, height: int, white: list[list[bool]], dark: list[list[bool]]) -> Optional[Panel]:
    def is_white(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and white[y][x]

    def is_dark(x: int, y: int) -> bool:
        return 0 <= x < width and 0 <= y < height and dark[y][x]

    # Her satırın telefon genişliğindeki beyaz şeritleri. Yazının ince çizgileri şeridi bölmez (≤3 nokta).
    runs: list[list[tuple[int, int]]] = [[] for _ in range(height)]
    min_run = int(width * WIDTH_RANGE[0])
    max_run = int(width * WIDTH_RANGE[1])
    for y in range(height):
        row = white[y]
        x = 0
        while x < width:
            if not row[x]:
                x += 1
                continue
            end = x
            probe = x + 1
            while probe < width and probe - end <= 4:
                if row[probe]:
                    end = probe
                probe += 1
            # Gümüş çerçevenin 1-2 noktalık parlak çizgisi ekranın şeridine ekleniyor ve kenarı kaydırıyordu; şeridin
            # başındaki ve sonundaki böyle kırıntılar atılır.
            start, finish = x, end
            while finish - start > 6:
                head = 0
                p = start
                while start <= p <= finish and row[p]:
                    head += 1
                    p += 1
                if not (head <= 2 and not row[start + head] and not row[start + head + 1]):
                    break
                start += head
                while start < finish and not row[start]:
                    start += 1
            while finish - start > 6:
                tail = 0
                p = finish
                while start <= p <= finish and row[p]:
                    tail += 1
                    p -= 1
                if not (tail <= 2 and not row[finish - tail] and not row[finish - tail - 1]):
                    break
                finish -= tail
                while finish > start and not row[finish]:
                    finish -= 1
            length = finish - start + 1
            if min_run <= length <= max_run:
                runs[y].append((start, finish))
            x = end + 1
    # Sol kenar bir doğrudur: başlangıç = a + eğim·satır. Her eğim için en çok satırın paylaştığı (a, genişlik) aranır;
    # her eğimin en güçlü birkaç adayı, en çok oy alandan başlanarak sınanır.
    candidates: list[tuple[int, float, int]] = []
    slopes = [0.0] + [v for k in range(1, 16) for v in (k * 0.02, k * -0.02)]
    for slope in slopes:
        votes: dict[int, int] = {}
        for y, row_runs in enumerate(runs):
            for run_start, run_end in row_runs:
                intercept = swift_round(run_start - slope * y)
                key = _quot(intercept + 400, 2) * 1000 + _quot(run_end - run_start, 2)
                votes[key] = votes.get(key, 0) + 1
        for key, count in sorted(votes.items(), key=lambda kv: -kv[1])[:3]:
            if count >= 8:
                candidates.append((count, slope, key))
    # Eşitlikte dik telefon (eğim 0, listede önce) öne geçer: sıralama kararlıdır.
    candidates.sort(key=lambda c: -c[0])

    def attempt(best: tuple[int, float, int]) -> Optional[Panel]:
        _, slope, key = best
        guess = float(_quot(key, 1000) * 2 - 400)
        span = key % 1000 * 2

        def left_edge(y: int, intercept: float) -> float:
            return intercept + slope * y

        # Her satırda ekrana uyan şerit (varsa).
        fit: dict[int, tuple[int, int]] = {}
        for y, row_runs in enumerate(runs):
            for run in row_runs:
                if abs(run[0] - left_edge(y, guess)) <= 3.5 and abs(run[1] - run[0] - span) <= 4:
                    fit[y] = run
                    break
        rows = sorted(fit)
        # Telefonun üstündeki aydınlık pencere de aynı hizada beyaz verebiliyor: uyan satırlar uzun boşluklarla
        # parçalara ayrılır; başka parça varken karenin üst ya da alt kenarına değen parça atılır.
        clusters: list[list[int]] = []
        for y in rows:
            if clusters and y - clusters[-1][-1] <= MAX_ROW_GAP:
                clusters[-1].append(y)
            else:
                clusters.append([y])
        inner = [c for c in clusters if c[0] > 1 and c[-1] < height - 2]
        if len(clusters) > 1 and inner:
            rows = [y for c in inner for y in c]
        if len(rows) < 8:
            return None
        intercepts = sorted(fit[y][0] - slope * y for y in rows)
        intercept = intercepts[len(intercepts) // 2]
        widths = sorted(fit[y][1] - fit[y][0] for y in rows)
        run_width = widths[len(widths) // 2]

        def left(y: int) -> int:
            return swift_round(left_edge(y, intercept))

        # Siyah çerçeve: satırların çoğunda ekranın hemen solu ve sağı koyu. Gümüş telefonda koyu kısım kenardaki 1-2
        # noktalık çizgidir; koyu nokta kenarın 1-4 nokta yakınında aranır.
        framed = [y for y in rows
                  if any(is_dark(max(0, left(y) - d), y) for d in range(1, 5))
                  and any(is_dark(min(width - 1, left(y) + run_width + d), y) for d in range(1, 5))]
        # Gündüz telefonun bir yanı güneşli tahta olabiliyor: satırların çoğunda iki yanı beyaz olmayan ve en az üçte
        # birinde koyu çerçeveli beyaz şerit de telefondur.
        edged = [y for y in rows
                 if any(not is_white(max(0, left(y) - d), y) for d in range(1, 5))
                 and any(not is_white(min(width - 1, left(y) + run_width + d), y) for d in range(1, 5))]
        if not (len(framed) >= len(rows) * 0.7
                or (len(edged) >= len(rows) * 0.85 and len(framed) >= len(rows) * 0.35)):
            return None

        # Üst ve alt kenar: şeridin yarıdan çoğu beyaz olduğu sürece ekrandır.
        def bright(y: int) -> bool:
            lo = max(0, left(y))
            hi = min(width - 1, left(y) + run_width)
            if not hi > lo:
                return False
            return sum(1 for x in range(lo, hi + 1) if is_white(x, y)) >= (hi - lo + 1) * 0.5

        first, last = rows[0], rows[-1]
        while first > 0 and bright(first - 1):
            first -= 1
        while last < height - 1 and bright(last + 1):
            last += 1
        rows = [y for y in rows if first <= y <= last]
        tall = (last - first + 1) / height
        # Ekranın en az dörtte biri baştan sona beyaz olmalı (fotoğraflı sohbette resim satırları beyaz değildir).
        if not (HEIGHT_RANGE[0] <= tall <= HEIGHT_RANGE[1] and len(rows) >= (last - first + 1) * 0.25):
            return None
        # Dikey dikdörtgen (nokta olarak yükseklik/genişlik; kare 16:9).
        shape = (tall * 9) / ((run_width + 1) / width * 16)
        if not (1.2 <= shape <= 2.6):
            return None
        w, h = float(width), float(height)
        top_left = left_edge(first, intercept)
        bottom_left = left_edge(last, intercept)
        box = TextBox(max(0.0, min(top_left, bottom_left)) / w, first / h,
                      min(w, max(top_left, bottom_left) + (run_width + 1)) / w, (last + 1) / h)
        # Telefon ekranın ortasında (yaya) ya da sağ yarısında (araçta) durur ve kenarlara değmez. Eğilip aşağı
        # indirilen telefon ekranın alt kenarından taşar; üstü ekranın ortalarındaysa telefondur.
        if not (CENTER_RANGE[0] <= (box.left + box.right) / 2 <= CENTER_RANGE[1] and box.top >= 0.04
                and (box.bottom <= 0.96 or box.top >= 0.2)):
            return None
        # Eğim: nokta/satır → kare genişliği / kare yüksekliği.
        return Panel(box, top_left / w, slope * h / w, (run_width + 1) / w)

    # Aynı beyaz alan birkaç eğimde de aday çıkar; telefonun sırası gelsin diye yeterince aday sınanır.
    if os.environ.get("NINO_TESHIS") is not None:
        for best in candidates[:16]:
            found = attempt(best)
            print("ADAY", best[0], best[1], found.box if found else None)
    for best in candidates[:16]:
        panel = attempt(best)
        if panel is not None:
            return panel
    return None


def sampler(frame, width: int = 960, height: int = 540) -> Color:
    """Karedeki bir noktanın rengi (0–1 kesirlerle x, y; çevresindeki 3×3 noktanın ortalaması). Kare bir kez küçültülür."""
    pixels = _rgb(frame, width, height)
    if pixels is None:
        return lambda x, y: None
    px = pixels.astype(np.int32)
    # 3×3 toplam önceden hesaplanır (Swift her noktada toplar; sonuç aynıdır).
    sums = np.zeros_like(px)
    sums[1:-1, 1:-1] = sum(px[1 + dy:height - 1 + dy, 1 + dx:width - 1 + dx]
                           for dy in (-1, 0, 1) for dx in (-1, 0, 1))
    averages = sums // 9

    def color(x: float, y: float) -> Optional[RGB]:
        cx = swift_round(x * width)
        cy = swift_round(y * height)
        if not (cx >= 1 and cy >= 1 and cx < width - 1 and cy < height - 1):
            return None
        a = averages[cy, cx]
        return RGB(int(a[0]), int(a[1]), int(a[2]))

    return color


def lifted_sampler(frame, panel: Panel) -> Color:
    """Telefonun ekranı kararmışsa (dokunulmadan duran telefon) renkler aydınlatılarak okunur: ekranın en aydınlık
    kısmı (zemin) beyaza çekilir. Koyu temalı uygulamanın (Rydeme) ekranı aydınlatılmaz."""
    base = sampler(frame)
    colors: list[Sequence[int]] = []
    for y in stride_to(panel.box.top + 0.03, panel.box.bottom - 0.02, 0.02):
        for share in stride_through(0.05, 0.95, 0.1):
            c = base(panel.left(y) + panel.width * share, y)
            if c is not None:
                colors.append(c)
    colors.sort(key=lambda c: max(c[0], c[1], c[2]))
    lights = [max(c[0], c[1], c[2]) for c in colors]
    if not lights:
        return base
    screen = lights[len(lights) * 8 // 10]
    # Açık ekranda noktaların çoğu zemindir (ortanca en aydınlık kısma yakın); koyu temada çoğu koyudur.
    middle = lights[len(lights) // 2]
    # Kararmış beyaz ekran gri kalır (renk payı az); koyu temanın laciverti renklidir.
    zone = colors[len(colors) * 8 // 10]
    gray = min(zone[0], zone[1], zone[2]) / max(1, max(zone[0], zone[1], zone[2]))
    # Koyu temada beyaz yazı zeminden çok aydınlıktır; kararmış açık ekranda en aydınlık nokta zemine yakındır.
    brightest = lights[-1]
    if not (40 <= screen < 232 and middle >= screen * 0.8 and gray >= 0.8 and brightest <= screen * 1.3):
        return base
    gain = 238.0 / screen

    def color(x: float, y: float) -> Optional[RGB]:
        c = base(x, y)
        if c is None:
            return None
        return RGB(min(255, int(c[0] * gain)), min(255, int(c[1] * gain)), min(255, int(c[2] * gain)))

    return color


def guess(boxes: Sequence[TextBox]) -> Panel:
    """Telefon uygulamasının yazılarından telefon ekranının tahmini yeri: elde tutulan GTA 6 telefonu ≈ 0,21 genişlik,
    ekranın 0,20–0,82'si; yazılar bu tahminin dışına taşıyorsa kutu onları da içine alır."""
    min_left = min((b.left for b in boxes), default=0.6)
    max_right = max((b.right for b in boxes), default=0.78)
    left = max(0.02, min_left - 0.015)
    right = min(0.98, max(max_right + 0.015, left + 0.21))
    top = min(0.2, min((b.top for b in boxes), default=0.3) - 0.02)
    bottom = min(0.95, max(0.82, max((b.bottom for b in boxes), default=0.8) + 0.03))
    return Panel(TextBox(left, max(0.04, top), right, bottom), left, 0.0, right - left)


def screen_share(panel: Panel, frame, dark: bool) -> float:
    """Ekranın içindeki noktaların ne kadarı koyu (`dark`) ya da beyaz ekran rengi."""
    sample = sampler(frame, width=480, height=270)
    hits = 0
    total = 0
    for row in range(1, 15):
        y = panel.box.top + (panel.box.bottom - panel.box.top) * row / 15
        for column in range(1, 8):
            c = sample(panel.left(y) + panel.width * column / 8, y)
            if c is None:
                continue
            total += 1
            high = max(c[0], c[1], c[2])
            low = min(c[0], c[1], c[2])
            if (high <= DARK_SCREEN_CEILING + 10) if dark else (low >= WHITE_FLOOR and high - low <= 45):
                hits += 1
    return 0.0 if total == 0 else hits / total


class Tracker:
    """Bir kez bulunan telefonu takip eder. Koyu temalı uygulamada kartlar ve alt pencere ekranı böldüğünden telefon
    her karede baştan bulunamıyordu. Bulunamayan karede, son bulunan yerde hâlâ aynı tür ekran (koyu ya da beyaz)
    duruyorsa telefon orada sayılır. Takip en son gerçek bulunuştan `max_age` saniye sürer."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last: Optional[Panel] = None
        self._dark = False
        self._last_seen = float("-inf")
        self.max_age = 20.0

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def adopt(self, boxes: Sequence[TextBox], frame) -> None:
        """Telefon uygulamasının sözcükleri görüldü ama telefon bulunamadı: telefonun yeri bu yazıların yerinden
        tahmin edilip takip oradan başlar."""
        if not boxes:
            return
        with self._lock:
            if not (self._last is None or self._now() - self._last_seen > 2):
                return
        guessed = guess(boxes)
        is_dark = screen_share(guessed, frame, dark=True) >= 0.45
        with self._lock:
            self._last = guessed
            self._dark = is_dark
            self._last_seen = self._now()

    def locate(self, frame) -> Optional[Panel]:
        found = find(frame)
        if found is not None:
            is_dark = screen_share(found, frame, dark=True) >= 0.5
            with self._lock:
                self._last = found
                self._dark = is_dark
                self._last_seen = self._now()
            return found
        with self._lock:
            if self._now() - self._last_seen < self.max_age and self._last is not None:
                previous, was_dark = self._last, self._dark
            else:
                return None
        if not screen_share(previous, frame, dark=was_dark) >= 0.45:
            with self._lock:
                self._last = None
            return None
        return previous


# ---------------------------------------------------------------------------
# PhoneThread: sohbet ekranının mesajları
# ---------------------------------------------------------------------------

# Telefon ekranının en üstündeki başlık şeridi (ekran yüksekliğine oranla).
HEADER_SHARE = 0.07
# Başlık şeridinin hemen altında bu kadar (kare yüksekliğine oranla) içinde başlayan satır kesiktir.
CLIPPED_TOP = 0.012
# Yazının kenarından balonun içine doğru: rengin okunduğu yer (karede ≈ balonun iç payının yarısı).
BUBBLE_INSET = 0.0045
# Örtünün yazıdan taşması: İngilizcenin harf uçları görünmesin, balonun kenarına da varmasın.
COVER_PAD_X = 0.0035
COVER_PAD_Y = 0.004
# Panelin genişliği (kare genişliğine oranla), balonların ve zeminin saydamlığı.
SIDE_WIDTH = 0.27
SIDE_ALPHA = 0.95
BACKDROP_ALPHA = 0.6
# Açık (gündüz) sohbette panel telefon ekranının buzlu bir kopyası gibi süt beyazı ve daha az saydamdır.
LIGHT_BACKDROP_ALPHA = 0.88
# Panelin sağ altında GTA6 Altyazı rozetine bırakılan yer (kare yüksekliğine oranla).
BADGE_SPACE = 0.03


def is_thread(reading: Reading, panel: Panel) -> bool:
    """Telefon ekranındaki okuma (`reading`, kareye göre yerleşmiş) bir sohbet mi: en üstte, ekranın ortasında kişinin
    adı durur. Mesaj listesinde en üstteki yazı sola yaslıdır; liste çevrilmez."""
    return title(reading, panel) is not None


def title_text(reading: Reading, panel: Panel) -> Optional[str]:
    """Sohbetin başlığındaki ad ("Lucia", "Fleeca, Laguna Lane")."""
    box = title(reading, panel)
    if box is None:
        return None
    for line in reading.lines:
        if line.box == box:
            return trim(line.text)
    return None


_NAV_BUTTONS = ("back", "geri", "done", "close", "cancel", "edit")


def title(reading: Reading, panel: Panel) -> Optional[TextBox]:
    """Sohbetin başlığı (kişinin adı) olan satırın kutusu: başlık şeridinde ya da ekrandaki en üst satır."""
    height = panel.box.bottom - panel.box.top
    boxes = [line.box for line in reading.lines if line.box is not None]
    topmost = min((b.top for b in boxes), default=0)
    for line in reading.lines:
        box = line.box
        if box is None or not (box.top < panel.box.top + height * HEADER_SHARE or box.top <= topmost + 0.002):
            continue
        text = trim(line.text)
        middle = (box.top + box.bottom) / 2
        # Başlık kişi ya da yer adıdır; yer adında virgül, nokta, kesme ve & olabilir ("Fleeca, Laguna Lane").
        name_like = (len(text) >= 2 and len(split_spaces(text)) <= 5
                     and all(c.isalpha() or c in " ,.'’&-" for c in text) and has_letter(text))
        # Gezinme düğmesi ("Back", "< Back") kişi adı değildir.
        if text.lower().strip("<‹ ") in _NAV_BUTTONS:
            continue
        if not ((mesaj.is_name(text) or name_like)
                and abs((box.left + box.right) / 2 - panel.center(middle)) < panel.width * 0.12):
            continue
        # Listede adın hemen altında, aynı hizada önizleme satırı durur; sohbet başlığının altında yoktur.
        indent = box.left - panel.left(box.top)
        if not any(other.top > box.top + 0.008 and other.top < box.top + 0.05
                   and abs(other.left - panel.left(other.top) - indent) < 0.015 for other in boxes):
            return box
    return None


def messages(reading: Reading, panel: Panel) -> list[Message]:
    """Sohbet ekranındaki mesajlar, yukarıdan aşağı. Başlık, "New message", yer/eşya etiketleri ve harfsiz satırlar
    mesaj değildir."""
    found = panel
    box_p = found.box
    panel_height = box_p.bottom - box_p.top
    # Başlık şeridinin alt kenarı: şerit ya da (ekran yukarıda bulunduysa) başlığın kendisi hangisi aşağıdaysa.
    head_box = title(reading, found)
    header = max(box_p.top + panel_height * HEADER_SHARE, head_box.bottom if head_box is not None else 0)
    # Satırın ortasındaki emoji satırı ikiye bölüyor; aynı satırdaki parçalar önce birleşir.
    lines: list[tuple[str, TextBox]] = []
    for line in joining_pieces(reading).lines:
        box = line.box
        if box is None:
            continue
        text = trim(line.text)
        if letter_count(text) < 2:
            continue
        # En üstteki başlık şeridi: kişinin adı ve geri oku.
        if not box.top > header:
            continue
        # Başlığın hemen altında yarısı kesik satır (sohbet kaydırılmış) her okumada başka okunuyordu.
        if not box.top > header + CLIPPED_TOP:
            continue
        # Ekranın alt kenarında yarısı görünen satır okunamaz.
        if not box.bottom < box_p.bottom - 0.01:
            continue
        lines.append((text, box))
    lines.sort(key=lambda ln: ln[1].top)
    # Satır aralığı: art arda iki satırın üst kenarları arasındaki en küçük fark. Eğik telefonda kutular şişer; paragraf
    # satır aralığıyla ayrılır.
    steps = [b[1].top - a[1].top for a, b in zip(lines, lines[1:])]
    steps = [s for s in steps if 0.012 <= s <= 0.04]
    if steps:
        pitch = min(steps)
    else:
        pitch = (min(ln[1].bottom - ln[1].top for ln in lines) if lines else 0.025) * 1.2
    groups: list[list[tuple[str, TextBox]]] = []
    for ln in lines:
        # Eğik telefonda paragrafın satırları aşağı indikçe yana kayar: sol kenar ekranın kenarına göre ölçülür.
        indent = ln[1].left - found.left(ln[1].top)
        if groups:
            last = groups[-1][-1]
            head = groups[-1][0]
            if (ln[1].top - last[1].top < pitch * 1.6
                    and abs(indent - (head[1].left - found.left(head[1].top))) < 0.02):
                groups[-1].append(ln)
                continue
        groups.append([ln])
    result = []
    for group in groups:
        text = " ".join(ln[0] for ln in group)
        if is_label(text):
            continue
        box = group[0][1].copy()
        for ln in group[1:]:
            box = box.union(ln[1])
        result.append(Message(text, box, pitch * 0.85))
    return result


def joining_pieces(reading: Reading) -> Reading:
    """Aynı satırda, aralarında küçük boşlukla (emoji) yan yana okunan parçalar tek satır olur."""
    rows: list[TextLine] = []
    for line in sorted(reading.lines, key=lambda ln: ln.box.left if ln.box is not None else 0):
        box = line.box
        if box is None:
            rows.append(line)
            continue
        index = None
        for i, row in enumerate(rows):
            other = row.box
            if other is None:
                continue
            overlap = min(box.bottom, other.bottom) - max(box.top, other.top)
            smaller = min(box.bottom - box.top, other.bottom - other.top)
            if (smaller > 0 and overlap >= smaller * 0.75 and box.left - other.right <= 0.03
                    and box.left > other.right - 0.005):
                index = i
                break
        if index is not None:
            other = rows[index].box
            rows[index] = TextLine(rows[index].text + " " + line.text, other.union(box), rows[index].confidence)
        else:
            rows.append(line)
    return Reading(rows)


_LABELS = {"new message", "new messages", "typing", "delivered", "read", "today", "yesterday", "messages encrypted"}


def is_label(text: str) -> bool:
    """Mesaj olmayan satır: "New message", "Typing...", ek olarak gönderilen yer ya da eşyanın adı (her sözcüğü büyük
    harfle başlar, cümle noktalaması yoktur)."""
    lowered = text.lower().strip(".…• ")
    if lowered in _LABELS:
        return True
    # Kilit simgesi harf sanılıyor ("A Messages encrypted").
    if lowered.endswith("messages encrypted") or lowered.endswith("message encrypted"):
        return True
    # Mesaja eklenen uygulama bağlantısının kartı ("BuckMe") mesaj değildir.
    if normalize(text) in PHONE_APP_NAMES:
        return True
    words = split_spaces(text)
    if not (len(words) >= 2 and not any(c in ".,!?…" for c in text)):
        return False
    return all(w[0].isupper() or w.lower() in ("del", "de", "la", "of", "the", "&") for w in words)


def column(panel: Panel, max_width: float = 0.30) -> Column:
    """Türkçelerin duracağı sütun: telefonun boş kalan (geniş) yanında, en çok `max_width` genişliğinde."""
    box = panel.box
    gap = 0.035
    if (box.left + box.right) / 2 > 0.5:
        right = box.left - gap
        return Column(max(0.02, right - max_width), right)
    left = box.right + gap
    return Column(left, min(0.98, left + max_width))


def boxes(messages: Sequence[Message], line_counts: Sequence[int], line_heights: Sequence[float],
          column: Sequence[float]) -> list[TextBox]:
    """Her çevirinin kutusu: mesajın hizasında, sütunun içinde; üst üste binmesinler diye gerekirse aşağı kayar."""
    col_left, col_right = column[0], column[1]
    result = []
    floor = 0.0
    for index, message in enumerate(messages):
        height = line_heights[index] * max(1, line_counts[index]) * 1.3
        top = min(max(message.box.top, floor), max(0, 0.98 - height))
        result.append(TextBox(col_left, top, col_right, top + height))
        floor = top + height + line_heights[index] * 0.6
    return result


def _hex(r: int, g: int, b: int) -> str:
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def _fill_rgb(fill: Optional[str]) -> Optional[tuple[int, int, int]]:
    value = _parse_hex(fill)
    return None if value is None else ((value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff)


def _parse_hex(fill: Optional[str]) -> Optional[int]:
    if fill is None or len(fill) != 7:
        return None
    digits = fill[1:]
    if not all(c in "0123456789abcdefABCDEF" for c in digits):
        return None
    return int(digits, 16)


def covers(messages: Sequence[Message], translations: Sequence[str], angle: float = 0.0, *,
           color: Color) -> list[ScreenItem]:
    """Mesajların Türkçesi her mesaj balonunun tam üstünde, balonun kendi rengiyle ve koyu yazıyla durur. Balonun rengi
    yazının hemen solundan (balonun iç payı) ve balonun içinden okunur."""
    def luminance(c: Sequence[int]) -> int:
        return c[0] * 299 + c[1] * 587 + c[2] * 114

    items = []
    for message, turkish in zip(messages, translations):
        text = turkish.strip()
        # Ek kartının adı ("BuckMe" bağlantısı) "BuckMe mi?" diye soruya çevrilip mesaj gibi çıkıyordu.
        if not text or not worth_showing(message.text, text):
            continue
        box = message.box
        # Yazının solundaki iç paydan birkaç noktada okunur; en aydınlığı alınır.
        points = [(box.left - inset, box.top + (box.bottom - box.top) * share)
                  for share in (0.15, 0.35, 0.5, 0.65, 0.85) for inset in (BUBBLE_INSET, BUBBLE_INSET * 0.6)]
        # Eğik telefonda yazının solu balonun dışına düşüyor: balonun içinden de okunur (aydınlık yarı; ortancası).
        inside = []
        for y in stride_through(0.15, 0.85, 0.1):
            for x in stride_through(0.1, 0.9, 0.1):
                c = color(box.left + (box.right - box.left) * x, box.top + (box.bottom - box.top) * y)
                if c is not None:
                    inside.append(c)
        inside.sort(key=luminance)
        ground = inside[len(inside) - len(inside) * 4 // 10:] if len(inside) >= 10 else []
        edge_colors = [c for c in (color(px, py) for px, py in points) if c is not None]
        edge = max(edge_colors, key=luminance) if edge_colors else (233, 233, 236)
        # İçerisi harf kadar koyuysa (kutu yazıyı sıkı sarıyor) yazının solundaki pay kullanılır.
        if not ground or luminance(ground[len(ground) // 2]) * 4 < luminance(edge) * 3:
            fill = edge
        else:
            fill = ground[len(ground) // 2]
        light = (fill[0] * 299 + fill[1] * 587 + fill[2] * 114) // 1000 > 140
        item = ScreenItem(message.text, text,
                          TextBox(box.left - COVER_PAD_X, box.top - COVER_PAD_Y,
                                  box.right + COVER_PAD_X, box.bottom + COVER_PAD_Y),
                          message.line_height)
        item.fill = _hex(fill[0], fill[1], fill[2])
        item.ink = "#2c2c2e" if light else "#f5f5f7"
        item.angle = angle
        items.append(item)
    return items


def shifted(items: Sequence[ScreenItem], dx: float, dy: float) -> list[ScreenItem]:
    """Telefon kaydıysa (el sallanıyor) örtüler de aynı kadar kaydırılır; yazı yeniden okunmaz."""
    return [replace(item, box=TextBox(item.box.left + dx, item.box.top + dy, item.box.right + dx, item.box.bottom + dy))
            for item in items]


def side_bubbles(messages: Sequence[Message], translations: Sequence[str], panel: Panel, chat: bool = True,
                 title: Optional[str] = None, *, color: Color,
                 lines: Callable[[str, float, float], tuple[int, int]]) -> list[ScreenItem]:
    """Mesajların Türkçesi telefonun yanında, telefon boyunda dikey bir mesajlaşma panelinde: gelen mesajlar solda,
    giden mesajlar sağda, her biri kendi balonunun renginde ve mesajın hizasında. İlk öğe panelin zeminidir.
    `lines(text, width, line)` Türkçenin o genişlikte kaç satır tuttuğunu ve en uzun satırın harf sayısını verir."""
    cover_items = covers(messages, translations, color=color)
    if not cover_items:
        return []
    kept = []
    for cover in cover_items:
        match = next((m for m in messages if m.text == cover.source), None)
        if match is not None:
            kept.append(match)
    col = column(panel, max_width=SIDE_WIDTH)
    inset = 0.012
    gap = 0.012
    inner = Column(col.left + inset, col.right - inset)
    bubble_max = (inner.right - inner.left) * 0.82
    pad = 0.012
    counts: list[int] = []
    longest: list[int] = []
    heights: list[float] = []
    for index, cover in enumerate(cover_items):
        # Türkçe telefondaki yazıya yakın boyda (panel telefon ekranının kopyası gibi okunsun).
        line = min(max(kept[index].line_height, 0.018), 0.028) * 1.08
        count, long = lines(cover.translation, bubble_max - pad, line)
        counts.append(count)
        longest.append(long)
        heights.append(line)
    placed = boxes(kept, counts, heights, (inner.left, inner.right))
    # Panel telefonun boyundadır; balonlar sığmazsa yukarı doğru sıkışır. Panelin sağ altında GTA6 Altyazı rozeti durur.
    bottom = panel.box.bottom - gap - BADGE_SPACE
    if placed and placed[-1].bottom > bottom:
        shift = placed[-1].bottom - bottom
        placed = [TextBox(b.left, b.top - shift, b.right, b.bottom - shift) for b in placed]
    # Giden mesaj: telefonda sağa yaslı ya da aynı sohbetin en gri balonundan belirgin mavi (renk karşılaştırmayla).
    blueness = [blue_shift(c.fill) for c in cover_items]
    grayest = min(blueness, default=0)
    # Sohbetteki en soldaki mesajlara göre belirgin içeride başlayıp en sağdakilerle aynı yerde biten mesaj sağa yaslıdır.
    indents = [m.box.left - panel.left(m.box.top) for m in kept]
    rights = [m.box.right - panel.left(m.box.top) for m in kept]
    leftmost = min(indents, default=0)
    rightmost = max(rights, default=0)
    right_aligned = [indents[i] - leftmost > panel.width * 0.1 and rightmost - rights[i] < panel.width * 0.08
                     for i in range(len(kept))]
    outgoing = [chat and (is_outgoing(kept[i], panel) or right_aligned[i] or blueness[i] - grayest >= 14)
                for i in range(len(cover_items))]
    items: list[ScreenItem] = []
    # Zemin: sohbetin zemini balonların arasından (gelen balonların sağındaki boşluk) okunur.
    samples = []
    for m in kept:
        if is_outgoing(m, panel):
            continue
        # Eğik telefonda kutunun sağ kenarı ekranın dışına düşer; ekranın o yükseklikteki sağ kenarına göre okunur.
        y = (m.box.top + m.box.bottom) / 2
        c = color(panel.left(y) + panel.width - 0.012, y)
        if c is not None:
            samples.append(c)
    ordered = sorted(samples, key=lambda c: c[0] + c[1] + c[2])
    ground = ordered[len(samples) // 2] if ordered else (226, 228, 233)
    backdrop = ScreenItem("", "", TextBox(col.left, panel.box.top, col.right, panel.box.bottom), 0.02)

    def lum(c: Sequence[int]) -> int:
        return (c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000

    # Açık sohbette zemin beyaza yaklaşır, gelen balon beyazlaşır, giden balonun mavisi belirginleşir. Zemin örneği
    # telefonun koyu çerçevesine ya da başparmağa denk gelebilir: gelen balonlar açıksa sohbet de açık sayılır.
    incoming = sorted(lum(c) for c in (_fill_rgb(cover_items[i].fill) for i in range(len(cover_items)) if not outgoing[i])
                      if c is not None)
    light_bubbles = bool(incoming) and incoming[len(incoming) // 2] > 150
    light_chat = chat and (lum(ground) > 150 or light_bubbles)
    if light_chat and lum(ground) <= 150:
        ground = (236, 236, 240)
    to_white = 0.6 if light_chat else 0.0

    def lift(v: int) -> int:
        return int(float(v) + (255 - float(v)) * to_white)

    backdrop.fill = _hex(lift(ground[0]), lift(ground[1]), lift(ground[2]))
    backdrop.alpha = LIGHT_BACKDROP_ALPHA if light_chat else BACKDROP_ALPHA
    backdrop.backdrop = True
    # Panelin en üstünde ortada gönderenin adı (TV başlık olarak çizer; ad çevrilmez).
    if chat and title:
        backdrop.translation = title
        backdrop.line_height = min(max(max((m.line_height for m in kept), default=0.022), 0.02), 0.028)
    items.append(backdrop)
    for index in range(len(cover_items)):
        box = placed[index].copy()
        width = min(bubble_max, longest[index] * heights[index] * 0.5 * 9 / 16 + pad + 0.012)
        if not chat:
            # Uygulama ekranı: her satır telefondaki yatay yerine ve genişliğine göre (ölçeklenerek) durur.
            message = kept[index]
            scale = (inner.right - inner.left) / panel.width
            left = message.box.left - panel.left(message.box.top)
            box.left = inner.left + max(0, left) * scale - pad / 2
            box.right = min(inner.right, box.left + max(width, (message.box.right - message.box.left) * scale + pad))
        elif outgoing[index]:
            box.left = inner.right - width
            box.right = inner.right
        else:
            box.left = inner.left
            box.right = inner.left + width
        box.bottom += heights[index] * 0.3
        item = replace(cover_items[index])
        value = _parse_hex(item.fill) if light_chat else None
        if value is not None:
            r = float((value >> 16) & 0xff)
            g = float((value >> 8) & 0xff)
            b = float(value & 0xff)
            if outgoing[index]:
                tuned = (r * 0.86, g * 0.93, min(255, b * 1.04))
            else:
                tuned = (r + (255 - r) * 0.7, g + (255 - g) * 0.7, b + (255 - b) * 0.7)
            item.fill = _hex(int(tuned[0]), int(tuned[1]), int(tuned[2]))
        item.box = box
        item.line_height = heights[index]
        item.angle = None
        item.alpha = SIDE_ALPHA
        item.side = True
        items.append(item)
    return items


def blue_shift(fill: Optional[str]) -> int:
    """Rengin maviliği: mavi kanalın kırmızı ve yeşilin ortalamasından farkı."""
    value = _parse_hex(fill)
    if value is None:
        return 0
    r, g, b = (value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff
    return b - (r + g) // 2


def is_outgoing(message: Message, panel: Panel) -> bool:
    """Giden mesaj: telefonda sağa yaslı balon (sol kenarı ekranın içinde epey içeride başlar)."""
    return message.box.left - panel.left(message.box.top) > panel.width * 0.2


def app_lines(reading: Reading, panel: Panel) -> list[Message]:
    """Sohbet olmayan telefon uygulaması (BuckMe bankası): her yazı satırı ayrı çevrilir. Harfsiz satırlar ($500),
    üstteki başlık şeridi ve alt kenarda yarısı görünen satır alınmaz."""
    box_p = panel.box
    panel_height = box_p.bottom - box_p.top
    lines: list[Message] = []
    for line in reading.lines:
        box = line.box
        if box is None:
            continue
        # Satırın başındaki simge ("◆ Checking Account") çevrilmez.
        text = trim(line.text)
        i = 0
        while i < len(text) and not (text[i].isalpha() or text[i].isnumeric() or text[i] in "$€£"):
            i += 1
        text = trim(text[i:])
        # Boş sohbetin "Messages encrypted" yazısı uygulama yazısı değildir.
        lowered = text.lower()
        if lowered.endswith("messages encrypted") or lowered.endswith("message encrypted"):
            continue
        if not (letter_count(text) >= 3 and box.top > box_p.top + panel_height * HEADER_SHARE
                and box.bottom < box_p.bottom - 0.01):
            continue
        lines.append(Message(text, box, (box.bottom - box.top) * 0.85))
    lines.sort(key=lambda m: m.box.top)
    # Alt alta devam eden satırlar tek cümledir (haber başlığı): sonraki satır küçük harfle başlıyorsa ya da önceki
    # satır noktalamasız ve en az üç sözcüklüyse. Ayrı etiketler ("Muscle - High" / "Body Fat - Low") ayrı kalır.
    merged: list[Message] = []
    for line in lines:
        if merged:
            last = merged[-1]
            gap = line.box.top - last.box.bottom
            height = line.box.bottom - line.box.top
            words = len([w for w in split_spaces(last.text) if has_letter(w)])
            ended = bool(last.text) and last.text[-1] in ".!?:"
            # Yazar satırı ("By Rusty Travers") paragrafa katılmaz.
            byline = last.text.lower().startswith("by ") and words <= 4
            continues = not byline and (line.text[:1].islower() or (not ended and words >= 3))
            if gap < height * 0.6 and abs(line.box.left - last.box.left) < 0.02 and continues:
                merged[-1] = Message(last.text + " " + line.text, last.box.union(line.box), last.line_height)
                continue
        merged.append(line)
    return merged


def is_dark_on_light(box: TextBox, color: Color) -> bool:
    """Kutudaki yazı açık zeminde koyu yazı mı (telefon ekranı, mesaj balonu): zemin (ortanca parlaklık) yazının
    noktalarından aydınlıktır. Altyazı ise koyu sahnede (ya da siyah kutuda) beyaz yazıdır."""
    values = []
    for y in stride_through(box.top, box.bottom, max((box.bottom - box.top) / 6, 0.001)):
        for share in stride_through(0.02, 0.98, 0.03):
            c = color(box.left + (box.right - box.left) * share, y)
            if c is not None:
                values.append((c[0] * 299 + c[1] * 587 + c[2] * 114) // 1000)
    if len(values) < 20:
        return False
    values.sort()
    darkest = values[len(values) // 20]
    middle = values[len(values) // 2]
    brightest = values[len(values) * 19 // 20]
    # Zemin yazıdan belirgin aydınlık ve yazı zeminden koyu: koyu yazı.
    return middle - darkest >= 25 and middle - darkest > (brightest - middle) * 2


def worth_showing(source: str, translation: str) -> bool:
    """Çevrilecek yazı mı: çevirisi boş değil, aslının aynısı değil ve tek sözcüklü aslını olduğu gibi içermiyor
    ("buckme" → "BuckMe mi?": marka adı çevrilmez)."""
    a = normalize(source)
    b = normalize(translation)
    return bool(b) and a != b and not (a in b and " " not in a)


def glossary(text: str) -> Optional[str]:
    """Oyun telefonunun arayüz yazıları için sabit Türkçe ("Checking Account" → "Vadesiz Hesap")."""
    key = normalize(text)
    if key in GLOSSARY_TERMS:
        return GLOSSARY_TERMS[key]
    # "Book Ryde ($82)" → "Ryde Çağır ($82)": parantez içindeki tutar korunur.
    open_at = text.find("(")
    if open_at >= 0 and text.endswith(")"):
        fixed = GLOSSARY_TERMS.get(normalize(text[:open_at]))
        if fixed is not None:
            return fixed + " " + text[open_at:]
    # "Muscle - High" → "Kas - Yüksek"
    parts = text.split(" - ")
    if len(parts) == 2:
        left = STAT_NAMES.get(normalize(parts[0]))
        right = STAT_LEVELS.get(normalize(parts[1]))
        if left is not None and right is not None:
            return left + " - " + right
    # Tanıma tireyi düşürebiliyor ("Muscle High").
    words = split_spaces(key)
    if len(words) >= 2:
        right = STAT_LEVELS.get(words[-1])
        left = STAT_NAMES.get(" ".join(words[:-1]))
        if right is not None and left is not None:
            return left + " - " + right
    # "Level 3/4" → "Seviye 3/4"
    if key.startswith("level "):
        rest = split_spaces(text)[1:2]
        if rest and "/" in rest[0]:
            return "Seviye " + rest[0]
    # "$4,900 to next goal" → "Sonraki hedefe $4.900"
    if key.endswith(" to next goal"):
        amount = split_spaces(text)[:1]
        if amount and any(c.isnumeric() for c in amount[0]):
            return "Sonraki hedefe " + amount[0].replace(",", ".")
    return None


def is_message_list(reading: Reading) -> bool:
    """Telefonun mesaj listesi mi: "…" ile kesilmiş önizlemeler var. Büyük harfle başlayan arayüz satırları tek başına
    liste değildir."""
    return mesaj.is_list(reading) and any(
        trim(line.text).endswith("...") or trim(line.text).endswith("…") for line in reading.lines)


def is_sentence(text: str) -> bool:
    """Cümle mi (sohbet mesajı): cümle noktalaması ya da küçük harfle başlayan sözcüğü var."""
    words = [w for w in split_spaces(text) if has_letter(w)]
    # Cümle sonu noktalaması (sayı içindeki nokta değil: "1.74 mi"); en az iki sözcüklü yazıda.
    stripped = trim(text)
    if len(words) >= 2 and stripped and stripped[-1] in ".!?":
        return True
    if any(c in "!?" for c in text) and len(words) >= 2:
        return True
    return len(words) >= 3 and any(w[0].islower() for w in words[1:])


def is_phone_ui(text: str) -> bool:
    """Oyun telefonunun uygulamalarına özgü sözcükler: telefon o karede bulunamasa da altyazı, mesaj kartı ya da ipucu
    sayılmaz."""
    # Kök olarak aranır: yazı tanıma bir harfi yanlış okusa da ("Destinatior") tanınsın.
    key = " " + normalize(text)
    if any(" " + w in key for w in PHONE_UI_WORDS):
        return True
    # Uygulama adları tam sözcük olarak ("Ryde", "Rydeme"; "Rydell" değil).
    if set(split_spaces(key)) & PHONE_APP_NAMES:
        return True
    bare = normalize(re.sub(r"\(.*\)", "", text))
    if bare in GLOSSARY_TERMS:
        return True
    # Sözlüğün kalıplarıyla çevrilen yazı da telefondadır; tek sözcükler diyalogda da geçebilir, sayılmaz.
    return len(split_spaces(text)) >= 2 and glossary(text) is not None


def app_bubbles(lines: Sequence[Message], translations: Sequence[str], panel: Panel, color: Color) -> list[ScreenItem]:
    """Sohbet olmayan uygulamada (BuckMe) Türkçe, telefonun yanındaki boşlukta uygulamanın kendi renginde baloncuklar
    olarak, her yazının hizasında ve telefona yakın kenara yaslı durur. Zemin paneli yoktur."""
    kept = [(line, turkish) for line, turkish in zip(lines, translations) if worth_showing(line.text, turkish)]
    if not kept:
        return []
    # Uygulamanın rengi: önce üst başlık şeridi, yoksa yazıların hemen çevresi. Renk bulunamazsa (beyaz haber
    # uygulaması) baloncuk ekranın baskın arka planı ve yazı rengiyle çizilir.
    accent: Sequence[int] = (58, 58, 60)

    def strongest(points: list[tuple[float, float]]) -> Optional[Sequence[int]]:
        best = 60
        found = None
        for x, y in points:
            c = color(x, y)
            if c is None:
                continue
            saturation = max(c[0], c[1], c[2]) - min(c[0], c[1], c[2])
            # Yeterince aydınlık olmalı (koyu ekrandaki koyu lacivert uygulamanın rengi değildir).
            if saturation > best and max(c[0], c[1], c[2]) >= 120:
                best = saturation
                found = c
        return found

    header = [(panel.left(y) + panel.width * s, y)
              for y in stride_to(panel.box.top - 0.04, panel.box.top + 0.06, 0.01)
              for s in stride_through(0.1, 0.9, 0.1)]
    around: list[tuple[float, float]] = []
    for line, _ in kept:
        middle = (line.box.top + line.box.bottom) / 2
        around += [(line.box.left - 0.006, middle), (line.box.right + 0.006, middle),
                   ((line.box.left + line.box.right) / 2, line.box.top - 0.006),
                   ((line.box.left + line.box.right) / 2, line.box.bottom + 0.006)]
    ink = "#ffffff"
    found = strongest(header)
    if found is None:
        found = strongest(around)
    if found is not None:
        accent = found
    else:
        def light(c: Sequence[int]) -> int:
            return c[0] * 299 + c[1] * 587 + c[2] * 114

        # Arka plan: telefon ekranında en çok görülen renk (16'lık kümeler; en kalabalık kümenin ortalaması).
        bins: dict[int, list[Sequence[int]]] = {}
        for y in stride_to(panel.box.top + 0.02, panel.box.bottom - 0.01, 0.01):
            for share in stride_through(0.05, 0.95, 0.05):
                c = color(panel.left(y) + panel.width * share, y)
                if c is None:
                    continue
                bins.setdefault((c[0] // 16) << 8 | (c[1] // 16) << 4 | (c[2] // 16), []).append(c)
        if bins:
            crowd = max(bins.values(), key=len)
            back = (sum(c[0] for c in crowd) // len(crowd), sum(c[1] for c in crowd) // len(crowd),
                    sum(c[2] for c in crowd) // len(crowd))

            def distance(c: Sequence[int]) -> int:
                return abs(c[0] - back[0]) + abs(c[1] - back[1]) + abs(c[2] - back[2])

            # Yazı rengi: satırların içinde arka plandan en uzak nokta (arka plana göre koyulaştırılır ya da açılır).
            strokes = []
            for line, _ in kept:
                for y in stride_through(line.box.top, line.box.bottom, max((line.box.bottom - line.box.top) / 8, 0.002)):
                    for s in stride_through(0.02, 0.98, 0.02):
                        c = color(line.box.left + (line.box.right - line.box.left) * s, y)
                        if c is not None:
                            strokes.append(c)
            accent = back
            light_back = light(back) > 128_000
            text_color = max(strokes, key=distance) if strokes else None
            if text_color is not None and distance(text_color) >= 90:
                k = 0.6 if light_back else 1.0
                if light_back:
                    ink = _hex(int(text_color[0] * k), int(text_color[1] * k), int(text_color[2] * k))
                else:
                    ink = _hex(255 - (255 - text_color[0]) // 2, 255 - (255 - text_color[1]) // 2,
                               255 - (255 - text_color[2]) // 2)
            else:
                ink = "#1c1c1e" if light_back else "#ffffff"
    col = column(panel, max_width=SIDE_WIDTH)
    on_left = col.right <= panel.box.left
    floor = 0.0
    # Bütün baloncuklarda aynı yazı boyu (ortanca satır yüksekliği).
    heights = sorted(line.line_height / 0.85 for line, _ in kept)
    size = min(max(heights[len(heights) // 2], 0.018), 0.028) * 0.95
    items = []
    for line, turkish in kept:
        text = turkish.strip()
        # Uzun yazı (haber paragrafı) sütun genişliğinde alt satırlara kaydırılır.
        char_width = size * 0.5 * 9 / 16
        room = col.right - col.left
        per_line = max(8, int((room - 0.03) / (char_width * 0.85)))
        rows = max(1, math.ceil(len(text) / per_line))
        width = room if rows > 1 else min(room, len(text) * char_width + 0.03)
        height = size * (1.22 * rows + 0.45) if rows > 1 else size * 1.55
        wanted = line.box.top if rows > 1 else (line.box.top + line.box.bottom) / 2 - height / 2
        top = min(max(wanted, floor), max(0, 0.98 - height))
        floor = top + height + size * 0.4
        left = col.right - width if on_left else col.left
        item = ScreenItem(line.text, text, TextBox(left, top, left + width, top + height), size)
        item.fill = _hex(accent[0], accent[1], accent[2])
        item.ink = ink
        item.alpha = SIDE_ALPHA
        item.side = True
        items.append(item)
    return items


# Uygulama adları ve uygulamaya özgü sözcükler (tek başına geçince yeter).
PHONE_UI_WORDS = ["trip detail", "change destinat", "destinatio", "messages encrypt",
                  "map pin expir", "checking accoun", "family saving",
                  # Fitness uygulaması (tek sözcük değil kalıp: diyalogdaki "workout" altyazı kalsın)
                  "workout window", "strength workout", "cardio workout", "calorie balanc", "maintain weight",
                  "gain weight", "lose weight"]
PHONE_APP_NAMES = frozenset(["ryde", "rydeme", "buckme"])

STAT_NAMES = {"muscle": "Kas", "body fat": "Vücut Yağı", "stamina": "Dayanıklılık", "strength": "Güç", "fat": "Yağ"}
STAT_LEVELS = {"high": "Yüksek", "low": "Düşük", "medium": "Orta", "average": "Ortalama",
               "very high": "Çok Yüksek", "very low": "Çok Düşük"}

GLOSSARY_TERMS = {
    # Gazete adları çevrilmez (aynısı döner, baloncuk gösterilmez).
    "vice city horn": "Vice City Horn", "the leonida journal": "The Leonida Journal",
    "leonida journal": "Leonida Journal",
    "ripped": "Kaslı", "toned": "Sıkı", "average": "Ortalama", "body & nutrition": "Vücut ve Beslenme",
    "body nutrition": "Vücut ve Beslenme",
    "strength workout": "Güç Antrenmanı", "cardio workout": "Kardiyo Antrenmanı", "workout window": "Antrenman zamanı",
    "focus": "Odak", "fitness": "Fitness", "calorie balance": "Kalori Dengesi",
    "you will maintain weight": "Kilonu koruyacaksın",
    "you will gain weight": "Kilo alacaksın", "you will lose weight": "Kilo vereceksin", "hungry": "Aç", "full": "Tok",
    "trip details": "Yolculuk Bilgileri", "cost": "Ücret", "choose ryde": "Ryde Seç", "standard ryde": "Standart Ryde",
    "change destination": "Varış Noktasını Değiştir", "book ryde": "Ryde Çağır", "cancel ryde": "Ryde'ı İptal Et",
    "checking account": "Vadesiz Hesap", "savings account": "Birikim Hesabı", "family savings": "Aile Birikimi",
    "family savings video": "Aile Birikimi Videosu", "atm finder": "ATM Bulucu", "faqs": "SSS",
    "savings": "Birikim", "balance": "Bakiye", "deposit": "Para Yatır", "withdraw": "Para Çek", "transfer": "Transfer",
    "transactions": "Hesap Hareketleri", "recent transactions": "Son Hareketler", "set a goal": "Hedef Belirle",
    "messages encrypted": "Mesajlar şifreli", "new message": "Yeni mesaj", "all contacts": "Tüm Kişiler",
    "suggested": "Önerilenler", "messages": "Mesajlar", "map pin expired": "Konum süresi doldu",
}
