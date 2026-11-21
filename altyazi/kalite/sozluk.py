# SPDX-License-Identifier: AGPL-3.0-only
"""Yerel çevirinin terim sözlüğü.

Nino Game Translator'ın Glossary.swift dosyasından taşındı (core/Sources/CouchSubsCore/Glossary.swift; Windows:
CouchSubs.Core/Glossary.cs, aynı biçim ve kurallar). Yerleşik sözlük Nino'nun Resources/glossary-en-tr.json
dosyasıdır (aşağıda `BUILT_IN_JSON`, içerik aynen).

Dosya biçimi: `{ "game": "God of War", "terms": { "Leviathan Axe": "Leviathan Baltası" }, "keep": ["Kratos"] }`.
- `terms` İngilizce terimi verilen Türkçeyle değiştirir, `keep` adları olduğu gibi bırakır. Eşleşme büyük/küçük harfe
  bakmaz, yalnız tam sözcüklerde olur, uzun terim önce gelir ("Leviathan Axe", "Axe"dan önce).
- `keepExact` da adları bırakır ama yalnız yazıldığı gibi (büyük/küçük harf aynı) geçince: aynı zamanda sıradan bir
  sözcük olan adlar için ("Soul" kahramanın adıyken "soul" ruh demek).
- `phrases` çeviriden önce oyun argosunu düz İngilizceye çevirir (anahtar düzenli ifade, tam sözcük, büyük/küçük harfe
  bakmaz: "toss a smoke" → "throw a smoke grenade").
- `lines` kısa ünlem satırlarının hazır Türkçesidir ("Reloading!" → "Şarjör değiştiriyorum!"): satır baştaki/sondaki
  noktalama ve büyük/küçük harf yok sayılarak birebir eşleşirse motora hiç gitmez.
Genel sözlüğün üstüne kullanıcının klasöründeki `*.json` dosyaları eklenir (ad sırasıyla; aynı terimde sonraki kazanır).

Python farkları: `TermMatch.start/length` UTF-16 değil Python dizin (kod noktası) birimindedir; JSON5 desteklenmez
(yalnız düz JSON); `phrases` anahtarları ICU yerine Python `re` sözdizimiyle derlenir (derlenemeyen anahtar atlanır).
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ._harf import bosluk_satir_kirp, harf_rakam_mi, harf_var, utf16_uzunluk


@dataclass(frozen=True)
class TermMatch:
    """Metinde bulunan terim: konumu (Python dizini), sözlükteki İngilizcesi ve Türkçesi."""
    start: int
    length: int
    english: str
    turkish: str


@dataclass(frozen=True)
class _Term:
    """Sözlükte yazıldığı gibi İngilizce, Türkçe; `exact` ise yalnız aynı büyük/küçük harfle eşleşir."""
    english: str
    turkish: str
    exact: bool = False


class ParseError(ValueError):
    """Sözlük dosyasının kökü bir JSON nesnesi değil."""


_ENDINGS = frozenset(".!?…")


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


class Glossary:
    """Terim sözlüğü. Doğrudan değil `parse`, `merge`, `load`, `empty()` ya da `built_in()` ile kurulur."""

    def __init__(self, terms: dict[str, _Term] | None = None, phrases: dict[str, str] | None = None,
                 lines: dict[str, str] | None = None):
        # Küçük harfli İngilizce → terim.
        self._terms: dict[str, _Term] = dict(terms or {})
        # Düzenli ifade → düz İngilizce; anahtar (UTF-8 bayt) sırasıyla uygulanır.
        self._phrases: dict[str, str] = dict(phrases or {})
        # `line_key` → Türkçe.
        self._lines: dict[str, str] = dict(lines or {})
        self._phrase_patterns: list[tuple[re.Pattern, str]] = []
        for key in sorted(self._phrases, key=_utf8):
            try:
                self._phrase_patterns.append((re.compile(r"\b(?:" + key + r")\b", re.IGNORECASE), self._phrases[key]))
            except re.error:
                continue
        # Uzundan kısaya terimler; arama bu sırayla yapılır.
        self._ordered: list[_Term] = sorted(self._terms.values(), key=lambda t: (-utf16_uzunluk(t.english), t.english))
        self._search = {t.english: re.compile(re.escape(t.english), re.IGNORECASE) for t in self._ordered if not t.exact}
        words: set[str] = set()
        # `keepExact` adları sıradan sözcük de olduğundan büyük harfe çevrilmez ("I SOLD MY SOUL" → "soul").
        for term in self._ordered:
            if not term.exact and any(c.isupper() for c in term.english):
                # Sözlükte büyük harfle yazılmış terimler ad sayılır: tümü büyük harfli cümlede de büyük harfle kalır.
                words.update(w.lower() for w in term.english.split(" ") if len(w) >= 2)
        # Büyük harfle kalması gereken sözcükler (küçük harfle); `normalize_case`'e ad olarak verilir.
        self.capital_words: frozenset[str] = frozenset(words)
        # Sözlüğün içeriğinden kısa bir iz; terim içeren satırların önbellek anahtarına girer.
        self.fingerprint: str = _make_fingerprint(self._ordered, self._phrases, self._lines)

    # ------------------------------------------------------------------ kurucular
    @classmethod
    def empty(cls) -> Glossary:
        return _empty()

    @classmethod
    def built_in(cls) -> Glossary:
        """Uygulamayla gelen genel oyun terimleri (Nino'nun glossary-en-tr.json'u)."""
        return _built_in()

    @classmethod
    def parse(cls, data: bytes | str) -> Glossary:
        """JSON sözlük metnini okur; JSON bozuksa `json.JSONDecodeError`, kök nesne değilse `ParseError` atar
        (ikisi de `ValueError`)."""
        root = json.loads(data)
        if not isinstance(root, dict):
            raise ParseError("sözlük kökü bir JSON nesnesi değil")
        return cls.from_dict(root)

    @classmethod
    def from_dict(cls, root: dict[str, Any]) -> Glossary:
        """Okunmuş JSON nesnesinden (ya da elle kurulmuş sözlükten: `{"terms": {...}, "keep": [...]}`) sözlük."""
        terms: dict[str, _Term] = {}
        mapping = root.get("terms")
        if isinstance(mapping, dict):
            # Sözlük sırası JSON'da tanımsız; aynı sonucu vermek için anahtar sırasıyla eklenir.
            for key in sorted(mapping):
                if isinstance(mapping[key], str):
                    _add(terms, key, mapping[key])
        for field, exact in (("keep", False), ("keepExact", True)):
            names = root.get(field)
            if isinstance(names, list):
                for name in names:
                    if isinstance(name, str):
                        _add(terms, name, name, exact=exact)
        phrases: dict[str, str] = {}
        mapping = root.get("phrases")
        if isinstance(mapping, dict):
            for key, plain in mapping.items():
                # Bozuk düzenli ifade alınmaz.
                if not isinstance(plain, str) or not key or not plain:
                    continue
                try:
                    re.compile(key)
                except re.error:
                    continue
                phrases[key] = plain
        lines: dict[str, str] = {}
        mapping = root.get("lines")
        if isinstance(mapping, dict):
            for key, turkish in mapping.items():
                line = line_key(key)
                if not isinstance(turkish, str) or not line or not _collapse(turkish):
                    continue
                lines[line] = _collapse(turkish)
        return cls(terms, phrases, lines)

    @classmethod
    def merge(cls, glossaries: Iterable[Glossary]) -> Glossary:
        """Sözlükleri birleştirir; aynı terimde sonraki kazanır."""
        terms: dict[str, _Term] = {}
        phrases: dict[str, str] = {}
        lines: dict[str, str] = {}
        for glossary in glossaries:
            terms.update(glossary._terms)
            phrases.update(glossary._phrases)
            lines.update(glossary._lines)
        return cls(terms, phrases, lines)

    @classmethod
    def load(cls, directory: str | os.PathLike | None) -> Glossary:
        """Genel sözlük ve klasördeki `*.json` dosyaları; okunamayan ya da bozuk dosya atlanır."""
        all_glossaries = [cls.built_in()]
        for file in user_files(directory):
            try:
                all_glossaries.append(cls.parse(file.read_bytes()))
            except (OSError, ValueError):
                continue
        return cls.merge(all_glossaries)

    # ------------------------------------------------------------------ sorgular
    @property
    def count(self) -> int:
        return len(self._terms)

    @property
    def is_empty(self) -> bool:
        return not self._terms

    def turkish(self, english: str) -> str | None:
        """Terimin Türkçesi; yoksa None."""
        term = self._terms.get(_collapse(english).lower())
        return term.turkish if term else None

    def find(self, text: str) -> list[TermMatch]:
        """Metindeki terimler: büyük/küçük harfe bakmadan (`keepExact` adları bakarak), tam sözcük, uzun terim önce;
        çakışan kısa terim alınmaz. Sonuç metindeki sıraya göredir."""
        if not self._ordered or not text:
            return []
        found: list[TermMatch] = []
        for term in self._ordered:
            start = 0
            while start < len(text):
                if term.exact:
                    location = text.find(term.english, start)
                    if location < 0:
                        break
                    length = len(term.english)
                else:
                    match = self._search[term.english].search(text, start)
                    if match is None:
                        break
                    location, length = match.start(), match.end() - match.start()
                end = location + length
                if _is_boundary(text, location - 1) and _is_boundary(text, end) \
                        and not any(location < f.start + f.length and f.start < end for f in found):
                    found.append(TermMatch(location, length, term.english, term.turkish))
                start = location + 1
        return sorted(found, key=lambda m: m.start)

    def matches(self, text: str) -> bool:
        return bool(self.find(text))

    def line(self, sentence: str) -> str | None:
        """Satırın hazır Türkçesi (`lines`); Türkçede son noktalama yoksa kaynağınki (".", "!", "?", "…") eklenir."""
        if not self._lines:
            return None
        turkish = self._lines.get(line_key(sentence))
        if turkish is None:
            return None
        if turkish[-1] in _ENDINGS:
            return turkish
        trimmed = bosluk_satir_kirp(sentence)
        tail = len(trimmed)
        while tail > 0 and trimmed[tail - 1] in _ENDINGS:
            tail -= 1
        return turkish + trimmed[tail:]

    def plain(self, text: str) -> str:
        """Oyun argosu düz İngilizceye çevrilir (`phrases`); eşleşmenin baş harfi büyükse karşılığınınki de büyük olur."""
        for pattern, plain in self._phrase_patterns:
            def replacement(match: re.Match, plain: str = plain) -> str:
                return plain[:1].upper() + plain[1:] if match.group(0)[:1].isupper() else plain
            text = pattern.sub(replacement, text)
        return text

    def rewrites(self, text: str) -> bool:
        """Metin bir `lines` ya da `phrases` kuralına giriyor mu (önbellek anahtarına sözlüğün izi girsin diye)."""
        if self._lines and line_key(text) in self._lines:
            return True
        return any(pattern.search(text) for pattern, _ in self._phrase_patterns)


def _add(terms: dict[str, _Term], english: str, turkish: str, exact: bool = False) -> None:
    english = _collapse(english)
    turkish = _collapse(turkish)
    # Harfsiz terim her yerde eşleşirdi; yer tutucu sayısı sınırlı olduğundan çok uzun terim de alınmaz.
    if not harf_var(english) or not turkish or utf16_uzunluk(english) > 80:
        return
    terms[english.lower()] = _Term(english, turkish, exact)


def line_key(text: str) -> str:
    """`lines` anahtarı: küçük harf, düz kesme, tek boşluk; baştaki ve sondaki harf/rakam dışı karakterler atılır."""
    key = _collapse(text.lower().replace("’", "'").replace("‘", "'"))
    start, end = 0, len(key)
    while start < end and not (key[start].isalpha() or key[start].isnumeric()):
        start += 1
    while end > start and not (key[end - 1].isalpha() or key[end - 1].isnumeric()):
        end -= 1
    return key[start:end]


def _is_boundary(text: str, index: int) -> bool:
    if index < 0 or index >= len(text):
        return True
    return not harf_rakam_mi(text[index])


def _make_fingerprint(terms: list[_Term], phrases: dict[str, str], lines: dict[str, str]) -> str:
    """FNV-1a (32 bit), terimler İngilizcesine göre sıralı; Windows ve Swift'te de aynı hesap."""
    value = 2_166_136_261

    def mix(text: str) -> None:
        nonlocal value
        for byte in text.encode("utf-8"):
            value = ((value ^ byte) * 16_777_619) & 0xFFFFFFFF

    for term in sorted(terms, key=lambda t: _utf8(t.english.lower())):
        # `exact` işareti yalnız varsa eklenir; eski sözlüklerin izi değişmez.
        mix(term.english.lower() + "\x01" + term.turkish + ("\x03" if term.exact else "") + "\x02")
    # `phrases` ve `lines` de yalnız varsa girer.
    for key in sorted(phrases, key=_utf8):
        mix(key + "\x04" + phrases[key] + "\x05")
    for key in sorted(lines, key=_utf8):
        mix(key + "\x06" + lines[key] + "\x07")
    return f"g{value:08x}"


def user_files(directory: str | os.PathLike | None) -> list[Path]:
    """Klasördeki `*.json` dosyaları, ad sırasıyla; klasör yoksa boş."""
    if directory is None:
        return []
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return [Path(directory) / name for name in sorted(names) if name.endswith(".json")]


class GlossaryStore:
    """Kullanıcı sözlük klasörünü izler: dosyalar değişince (ad, boyut, değişiklik zamanı) sözlük yeniden okunur.
    Klasöre en çok birkaç saniyede bir bakılır; her altyazıda diske gidilmez."""

    CHECK_EVERY = 5.0

    def __init__(self, directory: str | os.PathLike | None, clock: Callable[[], float] = time.time):
        """`directory`: kullanıcı sözlüklerinin klasörü; None ise yalnız genel sözlük. `clock`: saniye."""
        self._directory = directory
        self._clock = clock
        self._lock = threading.Lock()
        self._current: Glossary | None = None
        self._stamp = ""
        self._checked_at = float("-inf")

    @classmethod
    def built_in_only(cls) -> GlossaryStore:
        """Yalnız uygulamayla gelen sözlük (testler)."""
        return cls(None)

    @property
    def glossary(self) -> Glossary:
        with self._lock:
            now = self._clock()
            if self._current is not None and now - self._checked_at < self.CHECK_EVERY:
                return self._current
            self._checked_at = now
            stamp = self._make_stamp()
            if self._current is None or stamp != self._stamp:
                self._current = Glossary.load(self._directory)
                self._stamp = stamp
            return self._current

    def _make_stamp(self) -> str:
        parts = []
        for file in user_files(self._directory):
            try:
                info = file.stat()
                size, modified = info.st_size, info.st_mtime
            except OSError:
                size, modified = -1, 0.0
            parts.append(f"{file}|{size}|{modified}")
        return "\n".join(parts)


@lru_cache(maxsize=1)
def _empty() -> Glossary:
    return Glossary()


@lru_cache(maxsize=1)
def _built_in() -> Glossary:
    try:
        return Glossary.parse(BUILT_IN_JSON)
    except ValueError:
        return _empty()


# Nino Game Translator: core/Sources/CouchSubsCore/Resources/glossary-en-tr.json (Windows da aynı dosyayı gömer).
BUILT_IN_JSON = r"""{
  "game": "Genel",
  "terms": {
    "health potion": "can iksiri",
    "skill tree": "yetenek ağacı",
    "fast travel": "hızlı seyahat",
    "side quest": "yan görev",
    "main quest": "ana görev",
    "quest log": "görev günlüğü",
    "experience points": "deneyim puanı",
    "checkpoint": "kontrol noktası",
    "save point": "kayıt noktası",
    "cooldown": "bekleme süresi",
    "smoke grenade": "sis bombası",
    "smoke grenades": "sis bombaları",
    "smoke bomb": "sis bombası",
    "smoke bombs": "sis bombaları",
    "flashbang": "flaş bombası",
    "flashbangs": "flaş bombaları",
    "flash grenade": "flaş bombası",
    "frag grenade": "el bombası",
    "frag grenades": "el bombaları",
    "medkit": "ilk yardım çantası",
    "medkits": "ilk yardım çantaları",
    "health pack": "sağlık paketi",
    "headshot": "kafa atışı",
    "sniper rifle": "keskin nişancı tüfeği",
    "assault rifle": "taarruz tüfeği",
    "ammo crate": "cephane sandığı"
  },
  "keep": [],
  "keepExact": ["Soul"],
  "phrases": {
    "(?:toss|throw|pop|drop|chuck) (?:a |some |the |your )?smokes?(?! grenade| bomb)": "throw a smoke grenade",
    "(?:toss|throw|chuck) (?:a |the |your )?flash(?:bang)?(?! grenade)": "throw a flashbang",
    "(?:toss|throw|chuck|cook) (?:a |the |your )?frag(?! grenade)": "throw a frag grenade",
    "nades": "grenades",
    "nade": "grenade",
    "hostiles": "enemies",
    "tangos": "enemies",
    "take point": "lead the way",
    "on my mark": "when I give the signal",
    "stay frosty": "stay alert"
  },
  "lines": {
    "reload": "Şarjör değiştir",
    "reloading": "Şarjör değiştiriyorum",
    "i'm reloading": "Şarjör değiştiriyorum",
    "i need to reload": "Şarjör değiştirmem lazım",
    "cover me, i'm reloading": "Şarjör değiştiriyorum, koru beni",
    "cover me while i reload": "Şarjör değiştirirken koru beni",
    "changing mags": "Şarjör değiştiriyorum",
    "frag out": "Bomba atıyorum",
    "grenade out": "Bomba atıyorum",
    "grenade": "El bombası",
    "flash out": "Flaş atıyorum",
    "flashbang out": "Flaş atıyorum",
    "smoke out": "Sis atıyorum",
    "popping smoke": "Sis atıyorum",
    "toss a smoke": "Sis bombası at",
    "throw a smoke": "Sis bombası at",
    "fire in the hole": "Patlama geliyor",
    "cover me": "Koru beni",
    "covering fire": "Ateş desteği",
    "man down": "Yaralı var",
    "i'm hit": "Vuruldum",
    "i'm down": "Yerdeyim",
    "revive me": "Kaldır beni",
    "enemy down": "Düşman etkisiz",
    "target down": "Hedef etkisiz",
    "tango down": "Hedef etkisiz",
    "enemy spotted": "Düşman görüldü",
    "enemies spotted": "Düşman görüldü",
    "contact": "Düşman var",
    "contact front": "Önde düşman",
    "contact left": "Solda düşman",
    "contact right": "Sağda düşman",
    "sniper": "Keskin nişancı",
    "get down": "Yere yat",
    "take cover": "Siper al",
    "get to cover": "Sipere geç",
    "find cover": "Siper bul",
    "fall back": "Geri çekilin",
    "move up": "İlerleyin",
    "push up": "İlerleyin",
    "push forward": "İleri",
    "move, move, move": "Hadi, hadi, hadi",
    "go, go, go": "Hadi, hadi, hadi",
    "on me": "Yanıma gelin",
    "regroup": "Toplanın",
    "flank them": "Yandan sarın",
    "flank left": "Soldan sarın",
    "flank right": "Sağdan sarın",
    "hold the line": "Hattı tutun",
    "hold position": "Yerinizi koruyun",
    "watch your fire": "Ateşine dikkat et",
    "cease fire": "Ateşi kesin",
    "hold fire": "Ateş etmeyin",
    "open fire": "Ateş açın",
    "we're pinned down": "Kıstırıldık",
    "i'm out of ammo": "Mermim bitti",
    "out of ammo": "Mermi bitti",
    "need ammo": "Mermi lazım",
    "i need ammo": "Mermi lazım",
    "low ammo": "Mermi az",
    "area clear": "Bölge temiz",
    "room clear": "Oda temiz",
    "all clear": "Her yer temiz",
    "copy that": "Anlaşıldı",
    "roger that": "Anlaşıldı",
    "headshot": "Kafadan",
    "incoming": "Geliyor"
  }
}
"""
