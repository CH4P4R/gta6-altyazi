"""Zaten Türkçe satır çevrilmez (CouchSubs TurkishText kuralları)."""

from altyazi.turkce_metin import is_close, is_sure


def test_turkish_lines():
    assert is_sure("Yardımcı olabilir miyim, efendim?")
    assert is_sure("Sistem Yazılımı Güncellemesi")
    assert is_sure("Ekran görüntüsü kaydedildi")
    assert is_sure("Lütfen bekleyin")


def test_english_lines_still_translated():
    assert not is_sure("Atatürk said that peace at home is peace in the world.")
    assert not is_sure("Get in the car, we got company!")
    assert not is_sure("Müller is waiting at the docks.")


def test_is_close():
    assert is_close("guncellemesi", "guncellemesl")
    assert not is_close("evet", "even")          # kısa sözcükte harf farkına izin yok
