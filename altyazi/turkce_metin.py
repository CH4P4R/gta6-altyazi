# SPDX-License-Identifier: AGPL-3.0-only
"""Ekranda zaten Türkçe olan satır (PS5'in Türkçe arayüzü, oyunun Türkçe altyazısı): çevirmene gönderilmez.

CouchSubs'ın TurkishText / PoolFilter kurallarından (#289, #298, #337; GameTranslator 5764fea'da da alındı). Ölçüt
temkinlidir: Türkçe harf ve bilinen bir Türkçe sözcük birlikte bulunmalı; içinde Türkçe ad geçen İngilizce satır
("Atatürk said...") çevrilir. Yazı tanıma Türkçe harfleri bozabildiği için ("Sistem Yazillml Güncellem€") sözcükler
katlanmış halleriyle ve bir harf farkına izin verilerek karşılaştırılır.
"""

from __future__ import annotations

import unicodedata

LETTERS = set("ğĞşŞıİüÜöÖçÇ")


def fold(text: str) -> list[str]:
    plain = unicodedata.normalize("NFD", text.lower().replace("ı", "i"))
    out = []
    for ch in plain:
        if unicodedata.category(ch) == "Mn":
            continue
        out.append({"q": "c", "l": "i", "1": "i"}.get(ch, ch))
    words, cur = [], []
    for ch in "".join(out):
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            words.append("".join(cur))
            cur = []
    if cur:
        words.append("".join(cur))
    return words


def _fw(word: str) -> str:
    return "".join(fold(word))


_POOL = ["icin", "lutfen", "bekleyin", "oyunu", "oyun", "oyunlar", "kapat", "ekran", "ekranda", "ekrani", "sistemini",
         "yeniden", "baslat", "ayarlar", "ayarlari", "kupalar", "kupa", "oturum", "acti", "kapatti", "secenekleri",
         "sifirlama", "tut", "kesfet", "ilgili", "takip", "edin", "ilerlemenizi", "cikanlar", "goruntusu", "kaydedildi",
         "bildirimler", "arkadaslar", "medya", "galerisi", "indiriliyor", "guncelleme", "kitaplik", "denetleyici"]
_COMMON = ["daha", "sonra", "simdi", "degil", "haydi", "tamam", "evet", "hayir", "devam", "iptal", "giris", "guncelle",
           "guncellemesi", "yazilimi", "kurulum", "sirasinda", "sisteminizi", "sistemindeki", "kapatmayin", "baglanti",
           "baglantinizi", "uzaktan", "oynama", "dosyasi", "gostergesi", "kablosunu", "bir", "efendim", "yardimci",
           "olabilir", "miyim", "misin", "musun", "nasil", "neden", "burada", "tesekkurler", "merhaba", "gibi", "kadar",
           "belki", "hemen", "benim", "senin"]
KNOWN = [_fw(w) for w in _POOL + _COMMON]


def is_close(a: str, b: str) -> bool:
    """Aynı ya da (6+ harfte) bir harf farklı."""
    if a == b:
        return True
    if len(a) < 6 or len(b) < 6 or abs(len(a) - len(b)) > 1:
        return False
    i = j = edits = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(a) > len(b):
            i += 1
        elif len(b) > len(a):
            j += 1
        else:
            i += 1
            j += 1
    return edits + (len(a) - i) + (len(b) - j) <= 1


def is_sure(text: str) -> bool:
    """Satır yüksek güvenle Türkçe mi: en az bir Türkçe harf ve en az bir bilinen Türkçe sözcük."""
    if not any(c in LETTERS for c in text):
        return False
    return any(is_close(w, k) for w in fold(text) for k in KNOWN)
