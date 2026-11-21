# SPDX-License-Identifier: AGPL-3.0-only
"""kalite paketinin ortak harf yardımcıları.

Nino Game Translator'ın Swift kodunun dayandığı Foundation/ICU davranışlarının Python karşılıkları: Türkçe büyük/küçük
harf (`Locale("tr_TR")`), `CharacterSet.alphanumerics`, `.whitespaces`, `.whitespacesAndNewlines`, UTF-16 uzunluğu ve
Python'un `re` modülünde olmayan `\\p{L}`, `\\p{Lu}`, `\\p{Ll}`, `\\p{N}` sınıfları.
"""

from __future__ import annotations

import unicodedata
from functools import lru_cache

# Harflerin ve rakamların tamamı 0-3. düzlemlerdedir; tarama burada biter (açılışta ~0,1 sn yerine anında).
_TARAMA_SONU = 0x40000


@lru_cache(maxsize=1)
def _kategoriler() -> tuple[str, ...]:
    return tuple(unicodedata.category(chr(cp)) for cp in range(_TARAMA_SONU))


@lru_cache(maxsize=None)
def sinif(*kategoriler: str) -> str:
    """Düzenli ifade karakter sınıfının içi (köşeli parantezsiz): ICU'daki `\\p{L}`, `\\p{Lu}`, `\\p{N}` karşılığı.

    `kategoriler`: Unicode genel kategorileri; tek harf ("L", "N") bütün alt kategorileri kapsar.
    """
    istenen = {k for k in kategoriler if len(k) == 2}
    ana = {k for k in kategoriler if len(k) == 1}
    istenen |= {k for k in set(_kategoriler()) if k[0] in ana}
    parcalar: list[str] = []
    bas = -1
    for cp, kat in enumerate(_kategoriler() + ("",)):
        uygun = kat in istenen
        if uygun and bas < 0:
            bas = cp
        elif not uygun and bas >= 0:
            son = cp - 1
            parcalar.append(_kacis(bas) if bas == son else f"{_kacis(bas)}-{_kacis(son)}")
            bas = -1
    return "".join(parcalar)


def _kacis(cp: int) -> str:
    return f"\\u{cp:04x}" if cp <= 0xFFFF else f"\\U{cp:08x}"


def tr_kucuk(metin: str) -> str:
    """Türkçe küçük harf: I → ı, İ → i (`lowercased(with: tr_TR)`)."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


def tr_buyuk(metin: str) -> str:
    """Türkçe büyük harf: i → İ, ı → I (`uppercased(with: tr_TR)`)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def harf_rakam_mi(karakter: str) -> bool:
    """`CharacterSet.alphanumerics`: harf, işaret (birleşen) ya da sayı kategorisi."""
    return unicodedata.category(karakter)[0] in "LMN"


def utf16_uzunluk(metin: str) -> int:
    """Swift'teki `utf16.count` / `NSString.length`."""
    return len(metin.encode("utf-16-le")) // 2


def _bosluk_mu(karakter: str) -> bool:
    """`CharacterSet.whitespaces`: Zs kategorisi ve sekme."""
    return karakter == "\t" or unicodedata.category(karakter) == "Zs"


def _bosluk_satir_mi(karakter: str) -> bool:
    """`CharacterSet.whitespacesAndNewlines`: Z* kategorileri, U+0009–U+000D ve U+0085."""
    return karakter in "\t\n\x0b\x0c\r\x85" or unicodedata.category(karakter)[0] == "Z"


def bosluk_kirp(metin: str) -> str:
    """`trimmingCharacters(in: .whitespaces)`."""
    bas, son = 0, len(metin)
    while bas < son and _bosluk_mu(metin[bas]):
        bas += 1
    while son > bas and _bosluk_mu(metin[son - 1]):
        son -= 1
    return metin[bas:son]


def bosluk_satir_kirp(metin: str) -> str:
    """`trimmingCharacters(in: .whitespacesAndNewlines)`."""
    bas, son = 0, len(metin)
    while bas < son and _bosluk_satir_mi(metin[bas]):
        bas += 1
    while son > bas and _bosluk_satir_mi(metin[son - 1]):
        son -= 1
    return metin[bas:son]


def harf_var(metin: str) -> bool:
    """`contains(where: \\.isLetter)`."""
    return any(c.isalpha() for c in metin)
