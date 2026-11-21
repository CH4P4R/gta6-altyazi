# SPDX-License-Identifier: AGPL-3.0-only
"""Okunan yazının satırları ve kutuları: TextBox, TextLine, Reading, ButtonPrompts.

Nino'nun Reading.swift dosyasından aktarıldı (TextMatch.normalize ve
SubtitleStabilizer.endsSentence yardımcıları da burada). Kutular, içinde bulundukları
alanın kenarlarına oranladır (0–1, üstten ve soldan).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional

# ---------------------------------------------------------------------------
# Swift davranışını birebir taklit eden küçük yardımcılar
# ---------------------------------------------------------------------------

# CharacterSet.whitespaces: boşluk ayırıcıları (Zs) ve sekme; satır sonu değil.
_WS = "\t                　"
# CharacterSet.newlines
_NEWLINES = re.compile("[\n\u000b\u000c\r\u0085  ]")


def trim(s: str) -> str:
    """trimmingCharacters(in: .whitespaces): satır sonlarına dokunmaz."""
    return s.strip(_WS)


def swift_round(v: float) -> int:
    """Swift `Int(x.rounded())`: yarım değer sıfırdan uzağa yuvarlanır (Python round bankacı yuvarlaması yapar)."""
    if v >= 0:
        return int(math.floor(v + 0.5))
    return -int(math.floor(-v + 0.5))


def stride_to(start: float, end: float, step: float) -> Iterator[float]:
    """Swift `stride(from:to:by:)` (Double): değerler start + i·step (FMA ile), `end` dahil değil."""
    i = 0
    value = start
    while (value < end) if step > 0 else (value > end):
        yield value
        i += 1
        value = math.fma(float(i), step, start)


def stride_through(start: float, end: float, step: float) -> Iterator[float]:
    """Swift `stride(from:through:by:)` (Double): `end`e tam eşit değer de dahil; kayan nokta payı dahil değil."""
    i = 0
    value = start
    while True:
        if (value >= end) if step > 0 else (value <= end):
            if value == end:
                yield value
            return
        yield value
        i += 1
        value = math.fma(float(i), step, start)


def is_letter(c: str) -> bool:
    return c.isalpha()


def is_number(c: str) -> bool:
    return c.isnumeric()


def is_upper(c: str) -> bool:
    return c.isupper()


def is_lower(c: str) -> bool:
    return c.islower()


def has_letter(s: str) -> bool:
    return any(c.isalpha() for c in s)


def has_lower(s: str) -> bool:
    return any(c.islower() for c in s)


def letter_count(s: str) -> int:
    return sum(1 for c in s if c.isalpha())


def split_spaces(s: str) -> list[str]:
    """Swift `split(separator: " ")`: boş parçalar atılır."""
    return [w for w in s.split(" ") if w]


def split_where(s: str, is_separator: Callable[[str], bool]) -> list[str]:
    """Swift `split(whereSeparator:)`: boş parçalar atılır."""
    parts: list[str] = []
    current: list[str] = []
    for c in s:
        if is_separator(c):
            if current:
                parts.append("".join(current))
                current = []
        else:
            current.append(c)
    if current:
        parts.append("".join(current))
    return parts


def normalize(s: str) -> str:
    """TextMatch.normalize: küçük harf, yalnız harf/rakam, tek boşluk."""
    out = []
    for c in s.lower():
        if c.isalnum() or unicodedata.category(c).startswith("M"):
            out.append(c)
        else:
            out.append(" ")
    return " ".join(w for w in "".join(out).split(" ") if w)


def ends_sentence(raw: str) -> bool:
    """SubtitleStabilizer.endsSentence: satır nokta, ünlem, soru ya da üç noktayla bitiyor mu (kapanan tırnak ve
    parantezler yok sayılır)."""
    closers = {"\"", "'", "”", "’", "»", ")", "]"}
    text = raw.strip()
    while text and text[-1] in closers:
        text = text[:-1]
    return bool(text) and text[-1] in ".!?…"


# ---------------------------------------------------------------------------
# TextBox, TextLine
# ---------------------------------------------------------------------------


@dataclass
class TextBox:
    """Yazının yeri, içinde bulunduğu alanın kenarlarına oranla (0–1, üstten ve soldan)."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def union(self, other: "TextBox") -> "TextBox":
        return TextBox(min(self.left, other.left), min(self.top, other.top),
                       max(self.right, other.right), max(self.bottom, other.bottom))

    def placed(self, area: "TextBox") -> "TextBox":
        """Bu kutu `area` içindeki oranlarsa, aynı yerin `area`'yı içeren çerçevedeki oranları."""
        width = area.right - area.left
        height = area.bottom - area.top
        return TextBox(area.left + self.left * width, area.top + self.top * height,
                       area.left + self.right * width, area.top + self.bottom * height)

    def centered_on_screen(self) -> "TextBox":
        """Ekranın ortasındaki altyazının kutusu ortaya göre simetrik genişletilir; köşedeki yazıya dokunulmaz."""
        middle = (self.left + self.right) / 2
        if not (middle > 0.3 and middle < 0.7):
            return TextBox(self.left, self.top, self.right, self.bottom)
        return TextBox(max(0, min(self.left, 1 - self.right)), self.top,
                       min(1, max(self.right, 1 - self.left)), self.bottom)

    def copy(self) -> "TextBox":
        return TextBox(self.left, self.top, self.right, self.bottom)


@dataclass
class TextLine:
    """Yazı tanımanın bulduğu bir satır. `box`: okunan alana göre yeri; `confidence`: 0–1 güven (yoksa None)."""

    text: str
    box: Optional[TextBox] = None
    confidence: Optional[float] = None


# ---------------------------------------------------------------------------
# ButtonPrompts
# ---------------------------------------------------------------------------


class ButtonPrompts:
    """Oyunların ekranda gösterdiği kumanda ipuçlarını tanır: "R2 Swing", "△ Pick up", "Press ✕ to jump"."""

    # Her zaman kumanda düğmesi olan simgeler ve adlar (yazı tanıma bazen köşeli parantezle okur).
    BUTTONS = frozenset([
        "R1", "R2", "R3", "L1", "L2", "L3", "OPTIONS", "TOUCHPAD",
        "✕", "×", "⨯", "✖", "○", "◯", "●", "□", "▢", "◻", "■", "△", "▲", "⨂",
        # Yazı tanıma PS simgelerini bu karakterlere çeviriyor ("Hold & to …", "hold ® to …").
        "&", "®", "©", "@", "⊗", "Ⓧ", "ⓧ",
        # L1/L2/R1/R2 simgeleri yazı tanımada böyle okunuyor ("Hold LZ to aim", "RZ Shoot").
        "L", "R", "LZ", "RZ", "LI", "RI", "L7", "R7",
        # RDR2'nin ✕ simgesi bazen "*" okunuyor.
        "*",
        # Görüntüden tanınan simgeler: yön tuşları, dokunmatik yüzey, harita işareti.
        "↑", "↓", "←", "→", "✜", "▦", "◆",
    ])
    # Simge yazı tanımada harfe dönüşebilir; yalnız ipucu kalıbında düğme sayılır.
    LOOKALIKES = frozenset(["X", "O"])
    VERBS = frozenset(["press", "hold", "tap", "push", "use", "mash", "release", "double", "pull", "click"])
    BRACKETS = "()[]{}<>「」"

    @staticmethod
    def is_icon(token: str) -> bool:
        """Tek başına bir düğme simgesi mi ("✕", "R2", yazı tanımanın "&" ya da tek "O"/"X" okuduğu simge)."""
        t = token.strip(ButtonPrompts.BRACKETS)
        if ButtonPrompts.is_circled_letter(t):
            return True
        return t.upper() in ButtonPrompts.BUTTONS or t == "O" or t == "X"

    @staticmethod
    def is_circled_letter(t: str) -> bool:
        """Haritadaki görev işareti ("Ⓑ"): görüntüden tanınan renkli dairedeki harf."""
        return len(t) == 1 and 0x24B6 <= ord(t) <= 0x24CF

    @staticmethod
    def display(token: str) -> str:
        """Simgenin TV'de gösterilecek hali."""
        t = token.strip(ButtonPrompts.BRACKETS)
        if ButtonPrompts.is_circled_letter(t) or t in ["↑", "↓", "←", "→", "✜", "▦", "◆"]:
            return t
        u = t.upper()
        if u in ("O", "○", "◯"):
            return "○"
        if u in ("X", "✕", "×", "⨯", "✖", "⊗", "Ⓧ", "*"):
            return "✕"
        if u in ("□", "▢", "◻", "■"):
            return "□"
        if u in ("△", "▲"):
            return "△"
        if u in ("R1", "R2", "R3", "L1", "L2", "L3", "OPTIONS", "TOUCHPAD"):
            return u
        if u == "LZ":
            return "L2"
        if u == "RZ":
            return "R2"
        if u in ("LI", "L7", "L"):
            return "L1"
        if u in ("RI", "R7", "R"):
            return "R1"
        return "●"

    @staticmethod
    def normalized_icons(line: str) -> str:
        """Yuvarlak L3/R3 simgesinin bozuk okunuşları ("13)", "(13", "L3]") düğme adına çevrilir; yan yana tekrar
        okunan aynı simge teke iner."""
        s = line
        s = re.sub(r"(?<![\w])[\(\[]?[1lI|]([123])[\)\]](?=\s|$)", r"L\1", s)
        s = re.sub(r"(?<![\w])[\(\[][1lI|]([123])(?=\s|$)", r"L\1", s)
        s = re.sub(r"(?<![\w])[\(\[]?([LR])([123])[\)\]](?=\s|$)", r"\1\2", s)
        s = re.sub(r"(?<![\w])[\(\[]([LR])([123])(?=\s|$)", r"\1\2", s)
        # "(C1" = L1 simgesi.
        s = re.sub(r"(?<![\w])[\(\[]C([12])[\)\]]?(?=\s|$)", r"L\1", s)
        s = re.sub(r"([✕○△□↑↓←→✜▦◆●Ⓐ-Ⓩ])(?:\s+\1)+", r"\1", s)
        s = re.sub(r"(?<![\w])([LR][123]|OPTIONS|TOUCHPAD)(?:\s+\1)+(?![\w])", r"\1", s)
        return s

    @staticmethod
    def is_prompt(line: str) -> bool:
        separators = set(_WS) | {"+", "/"}
        raw = split_where_keep(line, lambda c: c in separators)
        tokens = [t.strip(ButtonPrompts.BRACKETS) for t in raw]
        tokens = [t for t in tokens if t]
        if not tokens:
            return False
        first = tokens[0]
        # Oyunun menü açıklaması ("PHOTO MODE  SELECT") altyazı değildir.
        if line == line.upper() and "PHOTO MODE" in line.upper():
            return True
        # GTA 6 etkileşim ipucu "△ ⋮ DRINKS": simgeler harf okunuyor ("A e DRINKS").
        if re.search(r"^\s*(\S\s+){1,3}[A-Z][A-Z']{2,}(\s+[A-Z][A-Z']{1,}){0,2}\s*$", line):
            return True

        def is_button(token: str) -> bool:
            return token.upper() in ButtonPrompts.BUTTONS

        words = [t for t in tokens if not is_button(t) and has_letter(t)]
        # "R2 Swing", "△ Pick up", "L1 R1 Spartan Rage"
        if is_button(first):
            return len(words) <= 5
        # "PHOTO MODE L1 + R1": düğme sonda, önünde kısa ve noktalamasız bir eylem adı.
        if is_button(tokens[-1]) and len(words) <= 4 and not ends_sentence(line):
            return True
        # "X Interact", "O Back": ardından kısa, büyük harfle başlayan, noktalamasız bir eylem gelir.
        if (first in ButtonPrompts.LOOKALIKES and 2 <= len(tokens) <= 4
                and tokens[1][:1].isupper() and not ends_sentence(line)):
            return True
        # "Press ✕ to jump", "Hold R2 to aim"
        if first.lower() in ButtonPrompts.VERBS and 2 <= len(tokens) <= 10:
            second = tokens[1]
            if is_button(second) or second in ButtonPrompts.LOOKALIKES:
                return True
            # Simge okunamayınca düşer ("Hold  to see nearby places"); "Hold to …" yine tuş ipucudur.
            if second.lower() == "to" and len(tokens) >= 4:
                return True
        # "Double tap and hold ✕ to ride alongside Dutch"
        if (first.lower() in ButtonPrompts.VERBS and len(tokens) <= 14 and any(is_button(t) for t in tokens)
                and not ends_sentence(line)):
            return True
        return False


def split_where_keep(s: str, is_separator: Callable[[str], bool]) -> list[str]:
    """Swift `components(separatedBy:)`: boş parçalar da kalır."""
    parts: list[str] = []
    current: list[str] = []
    for c in s:
        if is_separator(c):
            parts.append("".join(current))
            current = []
        else:
            current.append(c)
    parts.append("".join(current))
    return parts


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

_NAV_FULL = re.compile(
    r"^[\s\-–—'\"‘’.,·•]*(make\s+an?\s+)?(u-?\s?turn|turn|keep|bear)(\s+(left|right))?"
    r"(\s+(\d+(?:[.,]\d+)?|[Oo])\s*(ft|mi|yd|km|m)\b)*\s*[.!]?$", re.IGNORECASE)
_NAV_MOVE = re.compile(r"^[\s\-–—'\"‘’.,·•]*(u-?\s?turn|turn|keep)\s+(left|right)\b", re.IGNORECASE)
# Mesafe: sayı (okuma hatasıyla "O"/"o" = 0) + birim.
_NAV_DISTANCE = re.compile(r"(\d+(?:[.,]\d+)?|[Oo])\s*(ft|mi|yd|km|m)\b")


@dataclass
class Reading:
    """Bir karenin okunan satırları, yukarıdan aşağı. Boş satırlar atılır."""

    lines: list[TextLine] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.lines = [line for line in self.lines if trim(line.text)]

    # Altyazı satırı ekran yüksekliğinin yaklaşık %2,5-5'i kadardır (en büyük erişilebilirlik ayarında %6).
    MAX_SUBTITLE_LINE_HEIGHT = 0.075
    # Altyazı bloğunun karede kaplayabileceği en çok yükseklik ve satır sayısı.
    MAX_SUBTITLE_BLOCK_HEIGHT = 0.26
    MAX_SUBTITLE_LINES = 5
    # Cümle gibi görünen satır bu kadar yüksekse de atılır (karenin %13'ü).
    MAX_SENTENCE_LINE_HEIGHT = 0.13
    ROW_GAP = 0.05

    @staticmethod
    def empty() -> "Reading":
        return Reading([])

    @staticmethod
    def from_text(text: str) -> "Reading":
        """Satırları ayrı ayrı bilinmeyen eski okuyucular için: her satır sonu bir satırdır."""
        return Reading([TextLine(trim(part)) for part in _NEWLINES.split(text)])

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def box(self) -> Optional[TextBox]:
        """Bütün satırları içine alan kutu; hiçbir satırın yeri bilinmiyorsa None."""
        total: Optional[TextBox] = None
        for line in self.lines:
            if line.box is not None:
                total = line.box.copy() if total is None else total.union(line.box)
        return total

    @property
    def confidence(self) -> Optional[float]:
        values = [line.confidence for line in self.lines if line.confidence is not None]
        if not values:
            return None
        total = 0.0
        for v in values:
            total += v
        return total / len(values)

    def without_button_prompts(self) -> "Reading":
        """Oyunun düğme ipuçları ("R2 Swing", "△ Pick up") çıkarılmış hali; bunlar altyazı değildir."""
        return Reading([line for line in self.lines if not ButtonPrompts.is_prompt(line.text)])

    def without_navigation_hints(self) -> "Reading":
        """Yol tarifi satırları ("Turn Right 405 ft 432 ft") altyazı değildir."""
        return Reading([line for line in self.lines if not Reading.is_navigation_hint(line.text)])

    @staticmethod
    def is_navigation_hint(raw: str) -> bool:
        """Yalnız yön + mesafelerden oluşan satır. Arkasında söz olan cümle ("Turn right at the lights, okay?") altyazıdır."""
        text = trim(raw)
        # Mesafesiz tek komutluk tarif satırları da ("Turn left", "Make a U-turn") tarif sayılır.
        if _NAV_FULL.search(text):
            return True
        move = _NAV_MOVE.search(text)
        if not move:
            return False
        rest = text[move.end():]
        if not _NAV_DISTANCE.search(rest):
            return False
        # Mesafeler çıkınca geriye yalnız okuma kırıntısı (noktalama, tek tük harf) kalmalı.
        leftover = [c for c in _NAV_DISTANCE.sub(" ", rest) if c.isalpha() or c.isnumeric()]
        return len(leftover) <= 2

    def without_item_labels(self) -> "Reading":
        """Eşya, kıyafet, araç etiketleri ve tuş şeritleri altyazı değildir."""
        return Reading([line for line in self.lines if not Reading.is_item_label(line.text)])

    @staticmethod
    def is_item_label(raw: str) -> bool:
        text = trim(raw)
        if re.search(r"\(\d+\s*/\s*\d+\)", text):
            return True
        tokens = text.split()
        if sum(1 for t in tokens if ButtonPrompts.is_icon(t)) >= 2:
            return True
        words = [t for t in tokens if has_letter(t)]
        # Boya kutusu, ürün etiketi, reklam: küçük harfsiz, en çok 6 sözcük. Yalnız 1-2 sözcüklük bağırış kalır.
        if (1 <= len(words) <= 6 and not has_lower(text) and has_letter(text)
                and not (len(words) <= 2 and (text.endswith("!") or text.endswith("?")))):
            return True
        if not (1 <= len(words) <= 4):
            return False
        # Tek sözcüklük, noktalamasız yazı uygulama ya da ekran adıdır ("WhatUp", "Contacts").
        if len(words) == 1 and len(tokens) == 1 and all(c.isalpha() or c == "'" for c in text):
            return True
        # Plaka, tabela, kısa okuma çöpü: küçük harfsiz, en çok 3 sözcük.
        if len(words) <= 3 and not has_lower(text) and not text.endswith("!") and not text.endswith("?"):
            return True
        # Kesme işareti etikette de olur; cümle noktalaması değildir.
        if any(c in ".,!?:;…\"" for c in text):
            return False
        return not has_lower(text)

    def without_clipped_lines(self, margin: float = 0.015) -> "Reading":
        """Okunan alanın hem sol hem sağ kenarına değen satır kesiktir, altyazı değildir."""
        return Reading([line for line in self.lines
                        if line.box is None or not (line.box.left <= margin and line.box.right >= 1 - margin)])

    @staticmethod
    def is_label_like(raw: str) -> bool:
        """Etiket gibi satır: en çok 4 sözcük ve cümle noktalaması yok ("OHM BOY", "YARD SALE")."""
        words = [w for w in raw.split() if has_letter(w)]
        return len(words) <= 4 and not any(c in ".,!?…" for c in raw)

    def without_oversized_lines(self, area: TextBox, limit: float = MAX_SUBTITLE_LINE_HEIGHT) -> "Reading":
        """Dev satırlar atılır, ama temkinli: `limit`ten yüksek satır yalnız etiket gibiyse atılır."""
        scale = area.bottom - area.top
        kept = []
        for line in self.lines:
            box = line.box
            if box is None:
                kept.append(line)
                continue
            height = (box.bottom - box.top) * scale
            if height > max(limit, Reading.MAX_SENTENCE_LINE_HEIGHT):
                continue
            if height > limit and Reading.is_label_like(line.text):
                continue
            kept.append(line)
        return Reading(kept)

    def is_oversized_block(self, area: TextBox) -> bool:
        if len(self.lines) > Reading.MAX_SUBTITLE_LINES:
            return True
        box = self.box
        if box is None:
            return False
        return (box.bottom - box.top) * (area.bottom - area.top) > Reading.MAX_SUBTITLE_BLOCK_HEIGHT

    def joining_rows(self) -> "Reading":
        """Aynı satırda yan yana okunan parçalar soldan sağa tek satır olur."""
        if len(self.lines) <= 1 or not all(line.box is not None for line in self.lines):
            return self
        rows: list[TextLine] = []
        for line in sorted(self.lines, key=lambda ln: ln.box.left):
            box = line.box
            index = next((i for i, row in enumerate(rows) if Reading._same_row(box, row.box)), None)
            if index is not None:
                row = rows[index]
                confidences = [c for c in (row.confidence, line.confidence) if c is not None]
                rows[index] = TextLine(row.text + " " + line.text, row.box.union(box),
                                       min(confidences) if confidences else None)
            else:
                rows.append(line)
        return Reading(sorted(rows, key=lambda ln: ln.box.top))

    @staticmethod
    def _same_row(nxt: TextBox, row: TextBox) -> bool:
        """`nxt` aynı satırda mı: dikeyde küçük yüksekliğin en az %60'ı örtüşür."""
        overlap = min(nxt.bottom, row.bottom) - max(nxt.top, row.top)
        smaller = min(nxt.bottom - nxt.top, row.bottom - row.top)
        if not (smaller > 0 and overlap >= smaller * 0.6):
            return False
        return nxt.left - row.right <= Reading.ROW_GAP

    def subtitle_block(self, area: TextBox) -> "Reading":
        """Alandaki altyazı bloğu: ortalanmış ve menü olmayan en alttaki blok; yoksa en az üç sözcüklü en alttaki blok."""
        if not self.lines or not all(line.box is not None for line in self.lines):
            return self
        blocks: list[list[TextLine]] = []
        for line in sorted(self.lines, key=lambda ln: ln.box.top):
            box = line.box.placed(area)
            index = None
            for i in range(len(blocks) - 1, -1, -1):
                if Reading._belongs(box, blocks[i], area):
                    index = i
                    break
            if index is not None:
                blocks[index].append(line)
            else:
                blocks.append([line])
        candidates = [r for r in (Reading(list(b)) for b in blocks) if not r.is_menu]

        def is_centered(reading: "Reading") -> bool:
            box = reading.box
            if box is None:
                return False
            box = box.placed(area)
            return abs((box.left + box.right) / 2 - 0.5) <= 0.12

        centered = [r for r in candidates if is_centered(r)]
        if centered:
            return max(centered, key=lambda r: r.box.bottom)
        wordy = [r for r in candidates if len(r.text.split()) >= 3]
        if wordy:
            return max(wordy, key=lambda r: r.box.bottom)
        return Reading.empty()

    @staticmethod
    def _belongs(box: TextBox, block: list[TextLine], area: TextBox) -> bool:
        last = block[-1].box.placed(area)
        height = max(box.bottom - box.top, last.bottom - last.top)
        if not (box.top - last.bottom < height * 0.8 and box.top >= last.top):
            return False
        overlap = min(box.right, last.right) - max(box.left, last.left)
        narrower = min(box.right - box.left, last.right - last.left)
        return overlap > 0 and overlap >= narrower * 0.5

    @property
    def is_menu(self) -> bool:
        """Alt alta kısa ve noktalamasız satırlar ("MAP", "HELP", "SOCIAL CLUB") menüdür, konuşma değil."""
        return len(self.lines) >= 3 and all(
            len(line.text.split()) <= 3 and not ends_sentence(line.text) for line in self.lines)

    def placed(self, area: TextBox) -> "Reading":
        """Satır kutularını `area` içindeki oranlardan dış çerçevenin oranlarına taşır."""
        return Reading([TextLine(line.text, line.box.placed(area) if line.box is not None else None, line.confidence)
                        for line in self.lines])
