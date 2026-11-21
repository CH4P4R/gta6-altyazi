# SPDX-License-Identifier: AGPL-3.0-only
"""Oyunun menüleri (duraklatma menüsü: "Map / Game / Store / Help", "Retry Checkpoint / Restart Mission").

Nino'nun MenuBlock.swift dosyasından aktarıldı. Menü satırları kısadır, alt alta, sol ya da sağ kenarları hizalı durur.
Türkçesi satırın üstüne değil yanına yazılır: sola yaslı menüde sağına, sağa yaslı menüde soluna.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .metin import Reading, TextBox, TextLine, has_letter, split_where, trim


@dataclass
class Group:
    lines: list[TextLine] = field(default_factory=list)
    # Satırların sağ kenarı hizalı (Türkçesi soluna yazılır).
    right_aligned: bool = False


# En az bu kadar satır alt alta ve hizalıysa menüdür.
MINIMUM_LINES = 3
# Kenar hizası payı (ekran oranı).
EDGE_TOLERANCE = 0.012
# İki menü satırı arasındaki en büyük boşluk (ekran yüksekliği oranı).
MAXIMUM_GAP = 0.13


def groups(reading: Reading) -> list[Group]:
    """Okumadaki menüler (en çok iki: sola ve sağa yaslı). Altyazı ve uzun yazılar menü sayılmaz."""
    candidates = [line for line in reading.lines if is_menu_line(line)]
    used: set[int] = set()
    result: list[Group] = []
    for right_aligned in (False, True):
        def edge(line: TextLine) -> float:
            return line.box.right if right_aligned else line.box.left

        indices = sorted((i for i in range(len(candidates)) if i not in used), key=lambda i: edge(candidates[i]))
        cluster: list[int] = []

        def close() -> None:
            if len(cluster) >= MINIMUM_LINES:
                # Dikeyde ardışık ve sık: aradaki boşluk büyükse menü değil, ekranda ayrı yazılar.
                ordered = sorted(cluster, key=lambda i: candidates[i].box.top)
                run: list[int] = []
                runs: list[list[int]] = []
                for index in ordered:
                    if run and candidates[index].box.top - candidates[run[-1]].box.bottom > MAXIMUM_GAP:
                        runs.append(run)
                        run = []
                    run.append(index)
                runs.append(run)
                for r in runs:
                    if len(r) >= MINIMUM_LINES:
                        used.update(r)
                        result.append(Group([candidates[i] for i in r], right_aligned))
            cluster.clear()

        for index in indices:
            if cluster and edge(candidates[index]) - edge(candidates[cluster[0]]) > EDGE_TOLERANCE:
                close()
            cluster.append(index)
        close()
    return result


_SCREEN_WORDS = frozenset([
    "map", "brief", "progress", "settings", "stats", "gallery", "online", "inventory", "store",
    "help", "photo studio", "game", "journal", "options", "wardrobe", "outfits", "missions",
    # Eşya inceleme ekranı (defter, not, fotoğraf): el yazısı altyazı sanılmasın.
    "show text", "hide text", "flip", "put back", "rotate", "inspect", "examine", "read",
])
# Dükkân ve araç tamiri ekranı: aracın özellik çubukları ("SPEED", "ACCELERATION", "ASPHALT HANDLING", "RATING").
_SHOP_WORDS = frozenset(["speed", "acceleration", "handling", "rating", "upgrade", "performance", "respray", "purchase",
                         "owned", "braking", "armor", "armour"])


def is_menu_screen(reading: Reading) -> bool:
    """Harita, duraklatma ve oyun içi menü ekranı mı: bu sekme/menü sözcüklerinden en az ikisi tek başına satır olarak
    duruyorsa. Bu ekranlarda tuş ipuçları çevrilmez."""
    found: set[str] = set()
    for line in reading.lines:
        text = clean(line.text).lower()
        if text in _SCREEN_WORDS:
            found.add(text)
        for word in split_where(text, lambda c: not c.isalpha()):
            if word in _SHOP_WORDS:
                found.add(word)
        # Sekme şeridi tek satır okunabilir: "JASON & LUCIA MAP BRIEF PROGRESS".
        for word in (w for w in text.split(" ") if w):
            if word in ("map", "brief", "progress"):
                found.add(word)
    return len(found) >= 2


def is_menu_line(line: TextLine) -> bool:
    """Kısa (1-4 sözcük), harfli, bir satırlık yazı."""
    box = line.box
    if box is None or not box.bottom - box.top < 0.07:
        return False
    text = trim(line.text)
    words = [w for w in text.split() if has_letter(w)]
    return 1 <= len(words) <= 4 and len(text) <= 30 and not text.endswith(".") and not text.endswith("?")


def clean(text: str) -> str:
    """Menü satırının yazısı simgelerden arınmış hâliyle ("⊙ Store" → "Store", "ii Map" → "Map")."""
    words = text.split()
    while words and (not has_letter(words[0]) or (len(words[0]) <= 2 and not all(c.isalpha() for c in words[0]))):
        words.pop(0)
    # Simge çoğu zaman küçük harf sanılır ("i Settings", "Il Game"): ardından büyük harfli sözcük gelen 1-2 harflik
    # baştaki küçük harfli parça atılır.
    while (len(words) >= 2 and len(words[0]) <= 2
           and (not any(c.isupper() for c in words[0]) or words[0] == "Il" or words[0] == "II")
           and words[1][:1].isupper()):
        words.pop(0)
    while words and not any(c.isalpha() or c.isnumeric() for c in words[-1]):
        words.pop()
    return " ".join(words)


_TURKISH = {
    "map": "Harita", "game": "Oyun", "store": "Mağaza", "help": "Yardım", "photo studio": "Fotoğraf Stüdyosu",
    "settings": "Ayarlar", "options": "Seçenekler", "resume": "Devam Et", "continue": "Devam Et", "quit": "Çık",
    "quit game": "Oyundan Çık", "exit": "Çık", "back": "Geri", "select": "Seç", "save": "Kaydet", "load": "Yükle",
    "load game": "Oyun Yükle", "new game": "Yeni Oyun", "save game": "Oyunu Kaydet", "inventory": "Envanter",
    "stats": "İstatistikler", "brief": "Özet", "journal": "Günlük", "gallery": "Galeri", "online": "Çevrim İçi",
    "story mode": "Hikâye Modu", "retry checkpoint": "Kontrol Noktasından Tekrar Dene",
    "restart mission": "Görevi Yeniden Başlat",
    "restart": "Yeniden Başlat", "skip": "Atla", "replay mission": "Görevi Tekrar Oyna", "audio": "Ses",
    "display": "Ekran",
    "controls": "Kontroller", "graphics": "Grafik", "accessibility": "Erişilebilirlik", "language": "Dil",
    "credits": "Jenerik",
    "friends": "Arkadaşlar", "messages": "Mesajlar", "contacts": "Kişiler", "phone": "Telefon", "camera": "Kamera",
    "missions": "Görevler", "objectives": "Hedefler", "weapons": "Silahlar", "vehicles": "Araçlar",
    "apparel": "Kıyafet",
    "gone fishing": "Balığa Gitti",
}


def known_turkish(text: str) -> Optional[str]:
    """Sık menü sözcüklerinin oyunlardaki yerleşik Türkçesi ("Settings" → "Ayarlar", "Chapter 3" → "Bölüm 3")."""
    key = trim(text.lower())
    if key in _TURKISH:
        return _TURKISH[key]
    if key.startswith("chapter "):
        number = [w for w in key.split(" ") if w][-1]
        if all(c.isnumeric() for c in number):
            return "Bölüm " + number
    return None


def place_column(group: Group, translations: list[str]) -> list[TextBox]:
    """Menünün bütün satırlarının Türkçesi düzgün bir sütunda: sola yaslı menüde en uzun satırın sağında, sağa yaslı
    menüde en soldaki satırın solunda aynı hizada (TV harf başına ≈ satır yüksekliğinin yarısı; yatay oran 9/16)."""
    gap = 0.03
    if group.right_aligned:
        lefts = [line.box.left for line in group.lines if line.box is not None]
        edge = min(lefts) if lefts else 0.5
    else:
        rights = [line.box.right for line in group.lines if line.box is not None]
        edge = max(rights) if rights else 0.5
    result = []
    for line, translation in zip(group.lines, translations):
        box = line.box
        height = box.bottom - box.top
        width = min(0.42, max(0.05, len(translation) * height * 0.55 * 9 / 16 + 0.02))
        if group.right_aligned:
            right = max(width, edge - gap)
            result.append(TextBox(max(0, right - width), box.top, right, box.bottom))
        else:
            left = min(1 - width, edge + gap)
            result.append(TextBox(left, box.top, min(1, left + width), box.bottom))
    return result


def place_beside(line: TextLine, translation: str, right_aligned: bool) -> TextBox:
    """Tek satırın Türkçesinin yeri: sola yaslı satırın sağında, sağa yaslı satırın solunda."""
    box = line.box
    height = box.bottom - box.top
    width = min(0.45, max(0.06, len(translation) * height * 0.55 * 9 / 16 + 0.02))
    gap = 0.015
    if right_aligned:
        right = max(width, box.left - gap)
        return TextBox(max(0, right - width), box.top, right, box.bottom)
    left = min(1 - width, box.right + gap)
    return TextBox(left, box.top, min(1, left + width), box.bottom)
