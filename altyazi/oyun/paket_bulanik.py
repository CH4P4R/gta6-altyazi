# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın PackFuzzy.swift dosyasından taşındı.

Paketteki satırın bulanık imzası: OCR'ın bozduğu satırı (harf hatası, birleşmiş sözcük, köşe yazısı eklenmiş ya da
yarım okunmuş satır) paketin "fuzzy" bölümünde bulmak için. canon metnin boşlukları atılır, OCR'ın karıştırdığı
harfler birleştirilir (l/1/ı/j → i, 0 → o, 5 → s), kalan dizinin her farklı üçlüsü FNV-1a 64 ile özetlenip m bitten
birine düşer (Bloom kümesi; m uzunlukla büyür: 64/128/256). İngilizce metin geri çıkarılamaz.

İmza Nino'nun, CouchSubs'ın Windows sürümünün ve paket betiğinin (augment.py) yazdığıyla bit bit aynıdır; paketlerdeki
"fuzzy" nesnesi doğrudan okunur. Tarama numpy ile vektörleştirildi (Swift'teki döngüyle aynı sonuç).
"""

from __future__ import annotations

import base64
import gzip
import json
import re
import unicodedata
from bisect import bisect_left
from pathlib import Path
from typing import Callable

import numpy as np

from ..packs import canon, key as pack_key

MIN_LENGTH = 16                     # bundan kısa satırda bulanık arama yok
MAX_BITS = 256                      # Bloom kümesinin en büyük boyu (32 bayt)
BITS_PER_GRAM = 3                   # üçlü başına bit
CLEAN_MINIMUM = [(24, 90.0), (256, 80.0)]                 # OCR izi olmayan satır: (uzunluk sınırı, en düşük benzerlik)
DAMAGED_MINIMUM = [(24, 70.0), (40, 60.0), (256, 55.0)]   # OCR izi olan satır
MARGIN = 5.0                        # Türkçesi farklı ikinci aday en az bu kadar geride olmalı
# Tek yönlü kapsama (yarım ya da fazlalıklı okuma); bkz. PackFuzzy.containment
CONTAIN_MIN_LENGTH, CONTAIN_INNER, CONTAIN_PARTIAL, CONTAIN_EXTRA, CONTAIN_PENALTY = 22, 90.0, 25.0, 55.0, 10.0
# Fazlalıklı okumada yan cümle denetimi: en az bu kadar harfli her yan cümlenin üçlülerinin en az şu kadarı adayda
SENTENCE_LETTERS, SENTENCE_COVERED = 6, 30.0
VARIANT_MIN, VARIANT_MAX = 6, 48    # tek düzeltmeyle denenecek canon satır boyu

_FOLD = {"l": "i", "1": "i", "ı": "i", "j": "i", "0": "o", "5": "s", "æ": "a", "ø": "o", "œ": "o", "ß": "s"}
# Yazı tanımanın sık karıştırdığı harf dizileri (canon metinde): okunan → asıl olabilecek
CONFUSIONS = [
    ("rn", "m"), ("m", "rn"), ("cl", "d"), ("d", "cl"), ("vv", "w"), ("ri", "n"), ("n", "ri"), ("li", "h"),
    ("l", "i"), ("i", "l"), ("1", "l"), ("1", "i"), ("0", "o"), ("5", "s"), ("j", "i"), ("c", "e"), ("e", "c"),
    ("a", "o"), ("o", "a"), ("h", "b"), ("b", "h"), ("f", "t"), ("t", "f"), ("u", "v"), ("v", "u"), ("y", "v"),
    ("v", "y"), ("q", "g"), ("g", "q"),
]
_FNV_OFFSET, _FNV_PRIME, _MASK64 = 0xcbf29ce484222325, 0x100000001b3, (1 << 64) - 1


# ------------------------------------------------------------------------------------------------- yardımcılar
def _is_letter(ch: str) -> bool:
    return unicodedata.category(ch)[0] == "L"


def _is_digit(ch: str) -> bool:
    return unicodedata.digit(ch, None) is not None


def folded(text: str) -> str:
    """canon metin, boşluksuz ve OCR'ın karıştırdığı harfler birleşmiş."""
    return "".join(_FOLD.get(ch, ch) for ch in canon(text) if ch != " ")


def bits_for_length(length: int) -> int:
    """Uzunluğa göre Bloom boyu (bit)."""
    bits = 64
    while bits < MAX_BITS and length * BITS_PER_GRAM > bits:
        bits *= 2
    return bits


def trigram_hashes(scalars: str) -> list[int]:
    """Her farklı üçlünün FNV-1a 64 özeti (UTF-8 baytları üzerinden)."""
    if len(scalars) < 3:
        return []
    out = set()
    for i in range(len(scalars) - 2):
        h = _FNV_OFFSET
        for b in scalars[i:i + 3].encode("utf-8"):
            h = ((h ^ b) * _FNV_PRIME) & _MASK64
        out.add(h)
    return list(out)


def bloom(hashes: list[int], bits: int) -> list[int]:
    words = [0] * (bits // 64)
    for h in hashes:
        bit = h & (bits - 1)
        words[bit >> 6] |= 1 << (bit & 63)
    return words


def coverage(both: int, in_query: int, in_entry: int, bits: int) -> tuple[float, float]:
    """Rastlantıdan arındırılmış tek yönlü kapsamalar (0-100): sorgunun adayda olanı, adayın sorguda olanı."""
    if in_query <= 0 or in_entry <= 0:
        return 0.0, 0.0
    fill_q, fill_e = in_query / bits, in_entry / bits
    if fill_q >= 1 or fill_e >= 1:
        return 0.0, 0.0
    q = (both / in_query - fill_e) / (1 - fill_e)
    e = (both / in_entry - fill_q) / (1 - fill_q)
    return 100.0 * q, 100.0 * e


def score(both: int, in_query: int, in_entry: int, bits: int) -> float:
    q, e = coverage(both, in_query, in_entry, bits)
    return min(q, e)


def similarity(query: list[int], entry: list[int], offset: int, bits: int) -> float:
    """İki yönlü kapsama (0-100): min(sorgunun adayda olanı, adayınkinin sorguda olanı)."""
    both = in_q = in_e = 0
    for i in range(bits // 64):
        q, e = query[i], entry[offset + i]
        both += (q & e).bit_count()
        in_q += q.bit_count()
        in_e += e.bit_count()
    return score(both, in_q, in_e, bits)


def signature(text: str) -> tuple[int, bytes] | None:
    """(uzunluk, Bloom baytları) — paket betiğinin yazdığıyla aynı; satır çok kısaysa None."""
    s = folded(text)
    if len(s) < MIN_LENGTH:
        return None
    length = min(len(s), 255)
    words = bloom(trigram_hashes(s), bits_for_length(length))
    return length, b"".join(w.to_bytes(8, "little") for w in words)


def required(length: int, damaged_: bool) -> float:
    """Kabul için en düşük benzerlik (0-100), OCR izine ve uzunluğa göre."""
    table = DAMAGED_MINIMUM if damaged_ else CLEAN_MINIMUM
    for limit, value in table:
        if length < limit:
            return value
    return table[-1][1]


_EDGE = set(".,!?;:'\"()[]-…“”’‘")
_TYPOGRAPHIC = set("’‘“”—–…")


def damaged(text: str) -> bool:
    """OCR izi: ASCII dışı harf/işaret, sözcük içinde harf olmayan işaret ya da harf-rakam karışımı, tek harfli garip
    sözcük, çok uzun (birleşmiş) sözcük."""
    if any(ord(ch) > 127 and ch not in _TYPOGRAPHIC for ch in text):
        return True
    for word in text.split():
        core = word
        while core and core[0] in _EDGE:
            core = core[1:]
        while core and core[-1] in _EDGE:
            core = core[:-1]
        if not core:
            continue
        if len(core) >= 3:
            for i in range(1, len(core) - 1):
                if _is_letter(core[i - 1]) and _is_letter(core[i + 1]) and not _is_letter(core[i]) \
                        and core[i] not in "'’-":
                    return True
        for i in range(1, len(core)):
            p, c = core[i - 1], core[i]
            if (_is_letter(p) and _is_digit(c)) or (_is_digit(p) and _is_letter(c)):
                return True
        if len(core) == 1 and _is_letter(core) and core not in "aAIoO":
            return True
        if len(core) > 14:
            return True
    return False


def variants(text: str) -> list[str]:
    """Satırın tek bir OCR düzeltmesiyle olabileceği canon hâller: karıştırılan dizi değişir, bir harf düşer, sözcük
    ikiye bölünür ("cant" → "can t") ya da iki sözcük birleşir. Pakette tam anahtarla aranır."""
    c = canon(text)
    if not VARIANT_MIN <= len(c) <= VARIANT_MAX:
        return []
    out: set[str] = set()

    def add(value: str) -> None:
        if value and not value.startswith(" ") and not value.endswith(" ") and "  " not in value:
            out.add(value)

    for i in range(len(c)):
        for read, real in CONFUSIONS:
            if c.startswith(read, i):
                add(c[:i] + real + c[i + len(read):])
        add(c[:i] + c[i + 1:])
        if c[i] != " " and i > 0 and c[i - 1] != " ":
            add(c[:i] + " " + c[i:])
    out.discard(c)
    return sorted(out)


# ------------------------------------------------------------------------------------------------- yan cümleler
_CLAUSE_ENDERS = set(".!?…,;:")
_CLAUSE_MARKS = set(",;:")
_CLAUSE_CLOSERS = set("\"'”’)]")


def clauses(text: str) -> list[str]:
    """Satırın cümle ve yan cümleleri. Tek noktadan sonra küçük harfle süren yer bölünmez (OCR çöpüdür)."""
    out: list[str] = []
    begin = i = 0
    n = len(text)

    def cut(end: int) -> None:
        part = text[begin:end].strip()
        if part:
            out.append(part)

    while i < n:
        if text[i] not in _CLAUSE_ENDERS:
            i += 1
            continue
        end = i
        while end < n and text[end] in _CLAUSE_ENDERS:
            end += 1
        while end < n and text[end] in _CLAUSE_CLOSERS:
            end += 1
        nxt = end
        while nxt < n and text[nxt].isspace():
            nxt += 1
        run = text[i:end]
        soft = any(ch in _CLAUSE_MARKS or ch == "…" for ch in run) or run.count(".") > 1
        if end < nxt < n and (soft or text[nxt].isupper()):
            cut(end)
            begin = nxt
        i = max(nxt, i + 1)
    cut(n)
    # Kısa yan cümle ("Bye," "Dad.") sonrakine (sonuncuysa öncekine) eklenir.
    merged: list[str] = []
    pending = ""
    for part in out:
        joined = part if not pending else pending + " " + part
        if len(folded(joined)) < SENTENCE_LETTERS:
            pending = joined
        else:
            merged.append(joined)
            pending = ""
    if pending:
        if merged:
            merged[-1] = merged[-1] + " " + pending
        else:
            merged.append(pending)
    return merged


def capitalized(word: str) -> bool:
    """Büyük harfle başlayan, yalnız harf ve rakamlı sözcük (köşe yazısı sözcüğü: "Vinewood", "LOSNN")."""
    return bool(word) and word[0].isupper() and all(_is_letter(ch) or _is_digit(ch) for ch in word)


def overlay_like(text: str) -> bool:
    """Köşe yazısına benzeyen parça: "•" içerir ya da en çok dört büyük harfli sözcük, noktalama yok."""
    if "•" in text:
        return True
    words = text.split()
    return bool(words) and len(words) <= 4 and all(map(capitalized, words))


def clause_hashes(text: str) -> list[list[list[int]]]:
    """Fazlalıklı okumanın denetlenecek yan cümleleri: her biri için üçlü kümesi seçenekleri. Tek yan cümleyse boş."""
    parts = clauses(text)
    if len(parts) <= 1:
        return []
    out = []
    for position, part in enumerate(parts):
        if overlay_like(part):
            continue
        words = part.split()
        options = [part]
        for count in range(1, 4):
            if count >= len(words):
                continue
            if position == 0 and all(map(capitalized, words[:count])):
                options.append(" ".join(words[count:]))
            if position == len(parts) - 1 and all(map(capitalized, words[-count:])):
                options.append(" ".join(words[:-count]))
        folds = [folded(o) for o in options]
        if not all(len(f) >= SENTENCE_LETTERS for f in folds):
            continue
        out.append([trigram_hashes(f) for f in folds])
    return out


def covers_clauses(clause_sets: list[list[list[int]]], entry: list[int], bits: int, in_entry: int) -> bool:
    """Her yan cümlenin seçeneklerinden birinin üçlülerinin en az `SENTENCE_COVERED`'ı adayın Bloom'unda mı."""
    fill = in_entry / bits
    if fill >= 1:
        return False

    def covered(hashes: list[int]) -> bool:
        words = bloom(hashes, bits)
        both = sum((w & e).bit_count() for w, e in zip(words, entry))
        in_clause = sum(w.bit_count() for w in words)
        if in_clause == 0:
            return True
        return 100.0 * (both / in_clause - fill) / (1 - fill) >= SENTENCE_COVERED

    return all(any(covered(h) for h in options) for options in clause_sets)


# ------------------------------------------------------------------------------------------------- dizin
_HEX16 = re.compile(r"[0-9a-fA-F]{16}")


def key_number(k: str) -> int | None:
    """16 haneli hex anahtarın sayı hâli; geçersizse None."""
    return int(k, 16) if isinstance(k, str) and _HEX16.fullmatch(k) else None


def _popcount(a: np.ndarray) -> np.ndarray:
    return np.bitwise_count(a).astype(np.int64)


def _scores(both: np.ndarray, in_query: int, in_entry: np.ndarray, bits: int) -> np.ndarray:
    """`score`un vektör hâli (aynı işlem sırası, aynı sonuç); geçersiz adayda 0."""
    fill_q = in_query / bits
    fill_e = in_entry / bits
    if in_query <= 0 or fill_q >= 1:
        return np.zeros(len(both))
    valid = (in_entry > 0) & (fill_e < 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        q = (both / in_query - fill_e) / (1 - fill_e)
        e = (both / in_entry - fill_q) / (1 - fill_q)
        out = np.minimum(100.0 * q, 100.0 * e)
    return np.where(valid, out, 0.0)


class FuzzyIndex:
    """Bir paketin bulanık dizini (PackFuzzyIndex). Satırlar uzunluğa göre sıralı (aynı uzunlukta anahtar sırasıyla);
    her Bloom boyu (64/128/256) ayrı numpy dizisinde."""

    def __init__(self, data: dict, order: list[int]):
        """`data`: paketteki "fuzzy" nesnesi; `order`: paketteki bütün anahtarlar (entries + segments) sayı sırasıyla.
        Biçim tutmazsa ValueError (paket yine tam eşleşmeyle çalışır)."""
        if data.get("version") != 1 or data.get("count") != len(order):
            raise ValueError("fuzzy: sürüm ya da sayı tutmuyor")
        mask = base64.b64decode(data["mask"])
        lengths = base64.b64decode(data["lengths"])
        blooms = base64.b64decode(data["blooms"])
        if len(mask) != (len(order) + 7) // 8:
            raise ValueError("fuzzy: maske boyu tutmuyor")
        total = len(lengths)
        mask_bits = np.unpackbits(np.frombuffer(mask, np.uint8), bitorder="little")[:len(order)].astype(bool)
        file_keys = np.asarray(order, dtype=np.uint64)[mask_bits]
        if len(file_keys) != total:
            raise ValueError("fuzzy: imzalı satır sayısı tutmuyor")
        lens = np.frombuffer(lengths, np.uint8).astype(np.int64)
        sizes = np.where(lens * BITS_PER_GRAM <= 64, 8, np.where(lens * BITS_PER_GRAM <= 128, 16, 32))
        offsets = np.concatenate(([0], np.cumsum(sizes)[:-1])) if total else np.zeros(0, np.int64)
        if int(sizes.sum()) != len(blooms):
            raise ValueError("fuzzy: Bloom baytları tutmuyor")
        raw = np.frombuffer(blooms, np.uint8)
        # Uzunluğa göre kararlı sıralama (aynı uzunlukta dosya sırası = anahtar sırası korunur).
        order_idx = np.argsort(lens, kind="stable")
        self.count = total
        self._groups: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        for nbytes in (8, 16, 32):
            idx = order_idx[sizes[order_idx] == nbytes]
            words = np.zeros((len(idx), nbytes // 8), dtype=np.uint64)
            if len(idx):
                gather = offsets[idx][:, None] + np.arange(nbytes)[None, :]
                words = raw[gather].copy().view("<u8").astype(np.uint64).reshape(len(idx), nbytes // 8)
            self._groups[nbytes * 8] = (lens[idx], file_keys[idx], words, _popcount(words).sum(axis=1))

    def _select(self, low: int, high: int):  # noqa: ANN202
        """Uzunluğu [low, high] aralığındaki adaylar, Bloom boylarına göre."""
        for bits, (lens, keys, words, ones) in self._groups.items():
            a, b = np.searchsorted(lens, low, "left"), np.searchsorted(lens, high, "right")
            if b > a:
                yield bits, lens[a:b], keys[a:b], words[a:b], ones[a:b]

    def nearest(self, text: str, translation: Callable[[int], str | None]) -> int | None:
        """Eşik, uzunluk ve ikinci aday şartlarını sağlayan en benzer satırın anahtarı; yoksa None.
        Önce boyu yakın adaylar (iki yönlü kapsama); hiçbiri eşiği geçmezse boyu çok farklı adaylarda tek yönlü
        kapsama (yarım okunan ya da köşe yazısı/çöp eklenmiş satır)."""
        s = folded(text)
        if len(s) < MIN_LENGTH or not self.count:
            return None
        length = min(len(s), 255)
        need = required(length, damaged(text))
        floor = need - MARGIN
        hashes = trigram_hashes(s)
        query = {b: np.asarray(bloom(hashes, b), dtype=np.uint64) for b in (64, 128, 256)}
        q_ones = {b: int(_popcount(q).sum()) for b, q in query.items()}
        near = (length - length // 4, min(255, length + length // 4))
        wide = ((max(CONTAIN_MIN_LENGTH, length * 11 // 20), min(255, length * 5 // 2))
                if length >= CONTAIN_MIN_LENGTH else near)

        close: list[tuple[float, int]] = []
        for bits, _lens, keys, words, ones in self._select(*near):
            both = _popcount(words & query[bits]).sum(axis=1)
            sc = _scores(both, q_ones[bits], ones, bits)
            hit = np.flatnonzero(sc >= floor)
            close += zip(sc[hit].tolist(), keys[hit].tolist())

        def pick(found: list[tuple[float, int]]) -> tuple[int | None, bool]:
            if not found:
                return None, False
            best = max(found)
            if best[0] < need:
                return None, False
            turkish = translation(best[1])
            for sc, k in found:
                if k != best[1] and sc > best[0] - MARGIN and translation(k) != turkish:
                    return None, True
            return best[1], False

        first, ambiguous = pick(close)
        if first is not None or ambiguous or length < CONTAIN_MIN_LENGTH:
            return first
        contained: list[tuple[float, int]] = []
        clause_sets = None
        for bits, lens, keys, words, ones in self._select(*wide):
            in_q = q_ones[bits]
            both = _popcount(words & query[bits]).sum(axis=1)
            shorter = np.where(lens > length, in_q, ones)
            # Kısa tarafın bitlerinin en az %90'ı ortak olmalı (hızlı eleme).
            ok = (lens >= CONTAIN_MIN_LENGTH) & (lens != length) & (both * 10 >= 9 * shorter)
            for i in np.flatnonzero(ok).tolist():
                el, b, e = int(lens[i]), int(both[i]), int(ones[i])
                cq, ce = coverage(b, in_q, e, bits)
                inner, outer, least = (cq, ce, CONTAIN_PARTIAL) if el > length else (ce, cq, CONTAIN_EXTRA)
                if inner < CONTAIN_INNER or outer < least or inner - CONTAIN_PENALTY < floor:
                    continue
                # Fazlalıklı okumada her yan cümle adayda olmalı: ikinci bir altyazının cümlesi fazlalık sayılmaz.
                if el < length:
                    if clause_sets is None:
                        clause_sets = clause_hashes(text)
                    if clause_sets and not covers_clauses(clause_sets, [int(w) for w in words[i]], bits, e):
                        continue
                contained.append((inner - CONTAIN_PENALTY, int(keys[i])))
        if not contained:
            return None
        return pick(close + contained)[0]


def build_fuzzy(texts: dict[int, str], order: list[int]) -> dict:
    """Paket betiğinin yazdığı "fuzzy" nesnesi (İngilizce metinlerden). `texts`: anahtar sayısı → İngilizce;
    `order`: paketteki bütün anahtarlar sayı sırasıyla. Kendi paketimizi bulanık aramaya açmak ve denemeler için."""
    mask = bytearray((len(order) + 7) // 8)
    lengths, blooms = bytearray(), bytearray()
    for i, k in enumerate(order):
        sig = signature(texts[k]) if k in texts else None
        if sig is None:
            continue
        mask[i >> 3] |= 1 << (i & 7)
        lengths.append(sig[0])
        blooms += sig[1]
    enc = (lambda b: base64.b64encode(bytes(b)).decode("ascii"))
    return {"version": 1, "count": len(order), "mask": enc(mask), "lengths": enc(lengths), "blooms": enc(blooms)}


# ------------------------------------------------------------------------------------------------- paket
class FuzzyPack:
    """Tek bir oyun paketi, bulanık aramayla (Nino'da oynanan oyunun paketi: `GamePackLibrary` kapsamı).
    Tam anahtar PackLibrary'de bulunmazsa bu paket tek OCR düzeltmesiyle (`variants`) ve bulanık dizinle aranır."""

    def __init__(self, pack_id: str, title: str, entries: dict[int, str], segments: dict[int, str],
                 keys: list[int], fuzzy: FuzzyIndex | None):
        self.id, self.title = pack_id, title
        self.entries, self.segments = entries, segments
        self.keys = keys
        self.fuzzy = fuzzy

    @classmethod
    def from_data(cls, d: dict, name: str = "") -> FuzzyPack:
        """Paket nesnesi: {"format", "id", "title", "entries", "segments", "fuzzy"} ya da yalnız {anahtar: Türkçe}."""
        wrapped = isinstance(d.get("entries"), dict)
        raw, segs = (d["entries"], d.get("segments") or {}) if wrapped else (d, {})
        pid = (str(d.get("id") or "") or name) if wrapped else name
        title = (str(d.get("title") or "") or pid) if wrapped else name
        order: list[int] = []

        def read(section: dict) -> dict[int, str]:
            out = {}
            for k, v in section.items():
                n = key_number(k)
                if n is None or not isinstance(v, str):
                    continue
                order.append(n)              # Türkçesi boş kalan anahtar da imza sırasına girer
                if v.strip():
                    out[n] = v.strip()
            return out

        entries, segments = read(raw), read(segs)
        keys = sorted(set(order))
        fuzzy = None
        if wrapped and isinstance(d.get("fuzzy"), dict):
            try:
                fuzzy = FuzzyIndex(d["fuzzy"], keys)
            except (ValueError, KeyError, TypeError):
                fuzzy = None
        return cls(pid, title, entries, segments, keys, fuzzy)

    @classmethod
    def load(cls, path: Path) -> FuzzyPack:
        raw = Path(path).read_bytes()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        name = Path(path).name.split(".")[0]
        return cls.from_data(json.loads(raw.decode("utf-8")), name)

    def own(self, number: int) -> str | None:
        return self.entries.get(number) or self.segments.get(number)

    def exact(self, line: str) -> str | None:
        k = pack_key(line)
        return self.own(int(k, 16)) if k else None

    def contains(self, number: int) -> bool:
        i = bisect_left(self.keys, number)
        return i < len(self.keys) and self.keys[i] == number

    def corrected(self, line: str) -> str | None:
        """Tek OCR düzeltmesiyle pakette tam bulunan satırın Türkçesi; düzeltmeler farklı Türkçeye çıkıyorsa None."""
        found = None
        for v in variants(line):
            k = pack_key(v)
            if not k:
                continue
            n = int(k, 16)
            tr = self.own(n) if self.contains(n) else None
            if tr is None:
                continue
            if found is not None and found != tr:
                return None
            found = tr
        return found

    def nearest(self, line: str) -> str | None:
        """Tek düzeltme ya da bulanık dizinde en yakın satırın Türkçesi."""
        found = self.corrected(line)
        if found is None and self.fuzzy is not None:
            k = self.fuzzy.nearest(line, self.own)
            found = self.own(k) if k is not None else None
        return found

    def match(self, text: str) -> str | None:
        """Satırın Türkçesi (Nino: PackLookup.match). Önce yalnız tam anahtarla (tüm satır, satır satır, cümle cümle),
        bulunamazsa her parça tam ya da bulanık aranır. Konuşan etiketi ve diyalog tiresi olduğu gibi kalır."""
        text = text.strip()
        if not text:
            return None
        found = _phase(text, self.exact)
        if found is not None:
            return found
        cache: dict[str, str | None] = {}

        def find(line: str) -> str | None:
            if line not in cache:            # aynı parça birkaç yoldan sorulabilir; bulanık sonuç bir kez hesaplanır
                cache[line] = self.exact(line) or self.nearest(line)
            return cache[line]

        return _phase(text, find)


_SENT = re.compile(r"(?<=[.!?…])\s+")


_DASH = re.compile(r"^[-–—]+\s*")
# Büyük harfle başlayıp iki noktayla biten ama ad olmayan başlıklar; bunlar çevrilir (SubtitleSegmenter.notNames).
NOT_NAMES = {
    "note", "warning", "tip", "hint", "objective", "objectives", "quest", "goal", "new", "reward", "rewards",
    "location", "chapter", "mission", "task", "tutorial", "update", "info", "status", "level", "controls",
    "press", "hold", "tap", "remember", "example", "question", "answer", "result", "results", "time",
    "listen", "look", "wait", "okay", "ok", "well", "so", "yes", "no", "now", "then", "and", "but",
}


def _caps_word(word: str, first: bool) -> bool:
    rest = word[1:]
    return word[:1].isupper() and (len(rest) >= 1 or not first) and \
        all(ch.isupper() or unicodedata.category(ch) == "Nd" or ch in "'’.-" for ch in rest)


def _title_word(word: str, first: bool) -> bool:
    if not word[:1].isupper():
        return False
    rest = word[1:]
    if first:
        if not rest[:1].islower():
            return False
        rest = rest[1:]
    return all(_is_letter(ch) or ch in "'’.-" for ch in rest)


def speaker_label(line: str) -> str | None:
    """Satır başındaki konuşmacı etiketi, boşluğuyla ("ATREUS: ", "Mimir Head: "): en çok üç sözcüklü ad ve iki nokta;
    ya tümü büyük harf ya da her sözcüğü büyük harfle başlayan (SubtitleSegmenter.speakerLabel). Unicode harfler de
    olur ("MİNER: "); tek sözcüklü başlıklar ("Note:", "Objective:") ad değildir."""
    idx = line.find(":")
    if idx <= 0:
        return None
    end = idx + 1
    while end < len(line) and line[end].isspace():
        end += 1
    if end == idx + 1:
        return None
    words = line[:idx].split(" ")
    if not 1 <= len(words) <= 3 or any(not w for w in words):
        return None
    caps = all(_caps_word(w, i == 0) for i, w in enumerate(words))
    title = all(_title_word(w, i == 0) for i, w in enumerate(words))
    if not (caps or title):
        return None
    if len(words) == 1 and words[0].lower() in NOT_NAMES:
        return None
    return line[:end]


def speaker_lead(line: str) -> tuple[str, str] | None:
    """(ekranda kalacak diyalog tiresi ve etiket, aranacak gövde) ya da None."""
    block = " ".join(line.split())
    lead = ""
    m = _DASH.match(block)
    if m:
        lead, block = m.group(0).strip() + " ", block[m.end():]
    label = speaker_label(block)
    if label:
        lead, block = lead + label.strip()[:-1] + ": ", block[len(label):]
    return (lead, block) if lead and block else None


def _single(line: str, find: Callable[[str], str | None]) -> str | None:
    """Tek satır: önce etiketsiz/tiresiz gövde (etiket çeviriye eklenir), sonra tamamı, sonra bozuk etiketsiz hâli."""
    split = speaker_lead(line) if "\n" not in line else None
    if split:
        hit = find(split[1])
        if hit:
            return split[0] + hit
    hit = find(line)
    if hit:
        return hit
    loose = loose_label(line)
    if loose:
        hit = find(loose[1])
        if hit:
            return loose[0] + hit
    return None


def _phase(text: str, find: Callable[[str], str | None]) -> str | None:
    hit = _single(text, find)
    if hit:
        return hit
    # Her satır ayrı bir altyazı olabilir (iki konuşmacı alt alta); köşe yazısı satırları atlanır.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        out = []
        for ln in lines:
            h = _single(ln, find)
            if h is None:
                if is_overlay_line(ln):
                    continue
                out = []
                break
            out.append(h)
        if out:
            return "\n".join(out)
    # Cümle cümle (etiket ve tire olduğu gibi kalır).
    lead, body = speaker_lead(text) or ("", text)
    parts = [p for p in _SENT.split(body.strip()) if p.strip()]
    if len(parts) <= 1:
        return None
    hits = [find(p) for p in parts]
    return lead + " ".join(hits) if all(hits) else None


def is_overlay_line(line: str) -> bool:
    """Altyazı olmayan köşe yazısı satırı (PackLookup.isOverlay): en çok dört sözcük; "•" içerir ya da her sözcük büyük
    harfle başlayıp yalnız harf/rakamdır ("San Andreas", "LOSNN")."""
    words = line.split()
    if not words or len(words) > 4:
        return False
    return "•" in line or all(map(capitalized, words))


def loose_label(line: str) -> tuple[str, str] | None:
    """OCR'ın bozduğu konuşmacı etiketi: "-GAETANO:", "M]:", "li LUCA:", "MİNE GUARD•" (ilk 32 karakterde iki nokta ya
    da • ve önündeki sözcükte küçük harf yok) ya da iki noktasız "SEBASTIAN Where…". (ekranda kalacak etiket, aranacak
    gövde) ya da None. Yalnız paket aramasında yeniden deneme içindir."""
    n = len(line)

    def name_like(token: str, minimum: int) -> bool:
        letters = [ch for ch in token if _is_letter(ch)]
        return len(letters) >= minimum and not any(ch.islower() for ch in letters)

    for index in range(1, min(n, 33)):
        if line[index] not in ":•":
            continue
        before = line[:index].split()
        if not before or not name_like(before[-1], 1):
            continue
        start = index + 1
        while start < n and not _is_letter(line[start]) and unicodedata.numeric(line[start], None) is None:
            start += 1
        body = line[start:].strip()
        if not any(map(_is_letter, body)):
            return None
        return line[:index + 1].strip() + " ", body
    start = 0
    while start < n and not _is_letter(line[start]):
        start += 1
    for _ in range(3):
        end = start
        while end < n and not line[end].isspace():
            end += 1
        if not (end < n and line[start].isupper() and name_like(line[start:end], 2)):
            break
        while end < n and line[end].isspace():
            end += 1
        start = end
        if start + 1 < n and line[start].isupper() and line[start + 1].islower():
            return line[:start].strip() + " ", line[start:].strip()
    return None
