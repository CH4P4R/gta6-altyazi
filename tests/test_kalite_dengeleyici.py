# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.dengeleyici — Nino Game Translator'ın SubtitleStabilizerTests.swift ve NumericGlyphTests.swift
(testStabilizerSendsNumericCorrectionButNotLetterNoise) dosyalarından taşındı."""

import pytest

from altyazi.kalite.dengeleyici import (
    SIGNATURE_HEIGHT,
    SIGNATURE_WIDTH,
    StabilizerAction,
    StabilizerNote,
    SubtitleStabilizer,
    TextBox,
    changed,
)

NONE, CLEAR = StabilizerAction.NONE, StabilizerAction.CLEAR
translate, restore = StabilizerAction.translate, StabilizerAction.restore


class Clock:
    """Testlerde elle ilerletilen saat (milisaniye)."""

    def __init__(self):
        self.now = 1_000_000

    def __call__(self):
        return self.now


def test_unfinished_line_is_sent_after_two_stable_frames():
    # Noktalamayla bitmeyen satır yazılmakta olabilir; iki kare aynı okununca gönderilir.
    s = SubtitleStabilizer()
    assert s.feed("We do not have time") == NONE
    assert s.feed("We do not have time") == translate("We do not have time")
    assert s.feed("We do not have time") == NONE


@pytest.mark.parametrize("line", ["We do not have time.", "Wait!", "Who are you?", "I know…", "\"Run.\""])
def test_finished_sentence_is_sent_on_first_frame(line):
    # Cümle bitmişse beklemeye gerek yok; hızlı konuşmada her kare önemli.
    s = SubtitleStabilizer()
    assert s.feed(line) == translate(line)
    assert s.feed(line) == NONE


def test_garbled_sentence_is_not_sent_on_first_frame():
    s = SubtitleStabilizer()
    assert s.feed("Gtt solkolfege.") == NONE
    assert s.feed("Go to college.") == translate("Go to college.")


def test_garbled_line_is_sent_only_after_staying_longer_than_a_crossfade():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    garbled = "- Nat) but, you knpw. shit, I m"
    for _ in range(5):
        assert s.feed(garbled) == NONE
        clock.now += 100
    clock.now += SubtitleStabilizer.GARBLED_STABLE_MS
    assert s.feed(garbled) == translate(garbled)


def test_ocr_noise_does_not_reemit():
    s = SubtitleStabilizer()
    s.feed("The gate will not hold")
    s.feed("The gate will not hold")
    assert s.feed("The gale will not hold") == NONE
    assert s.feed("The gale will not hold") == NONE


def test_garbled_reread_of_sent_line_does_not_reemit():
    # Süslü yazıda aynı cümle her karede başka çöple okunur; TV'de iki çeviri olarak görünmemeli.
    s = SubtitleStabilizer()
    first = "Across the deep waters, Pbo ou$3e went, hoping a boat would carry him home."
    assert s.feed(first) == translate(first)
    assert s.feed("Across the deep waters2aljd O went, Hoping a boat would carry him home.") == NONE
    assert s.feed("Across the deep waters2aljd O went, Hoping a boat would carry him home.") == NONE
    assert s.feed("Across the deep waters, he went.") == translate("Across the deep waters, he went.")


FULL = "Shit, I just came by to see if there's somethin' I can help you with."
WORSE = "Shit, I came by to see if there somethinl I can help ya."


def test_worse_reread_of_sent_line_is_not_translated_again():
    s = SubtitleStabilizer()
    assert s.feed(FULL) == translate(FULL)
    assert s.feed(WORSE) == NONE
    assert s.feed(FULL) == NONE
    assert s.feed(WORSE) == NONE


def test_better_reread_of_sent_line_is_translated():
    # Önce eksik okunan cümlenin daha çok sözcüklü okuması gelirse yeniden çevrilir (TV eskisinin yerine koyar).
    s = SubtitleStabilizer()
    assert s.feed(WORSE) == translate(WORSE)
    assert s.feed(FULL) == translate(FULL)
    assert s.feed(WORSE) == NONE


def test_flickering_hud_does_not_spam():
    s = SubtitleStabilizer()
    sent = sum(1 for i in range(20) if s.feed("24 / 120" if i % 2 == 0 else "").kind == "translate")
    assert sent == 0


def test_typewriter_sends_completed_line():
    s = SubtitleStabilizer()
    s.feed("We do")
    s.feed("We do not have")
    assert s.feed("We do not have time for this, boy.") == translate("We do not have time for this, boy.")
    assert s.feed("We do not have time for this, boy.") == NONE


def test_empty_region_clears_after_clear_time():
    # Altyazının kalktığına okuma sayısıyla değil süreyle karar verilir: bölge 800 ms boş kalınca silinir.
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hello there")
    s.feed("Hello there")
    assert s.feed("") == NONE
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS - 1
    assert s.feed("") == NONE
    clock.now += 1
    assert s.feed("") == CLEAR
    assert s.feed("") == NONE


def test_short_flicker_neither_clears_nor_resends():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate")
    assert s.feed("Hold the gate") == translate("Hold the gate")
    for _ in range(3):
        for _ in range(10):
            clock.now += 50
            assert s.feed("") == NONE
        for _ in range(4):
            clock.now += 50
            assert s.feed("Hold the gate") == NONE


def test_line_returning_soon_after_clear_is_restored():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    assert s.feed("Hold the gate.") == translate("Hold the gate.")
    s.feed("")
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS
    assert s.feed("") == CLEAR
    clock.now += SubtitleStabilizer.RESTORE_WITHIN_MS
    assert s.feed("Hold the gate") == NONE
    assert s.feed("Hold the gate") == restore("Hold the gate.")
    assert s.feed("Hold the gate.") == NONE
    # Geri gelen satır da kalkınca silinir.
    s.feed("")
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS
    assert s.feed("") == CLEAR


def test_line_returning_later_is_translated_again():
    # Daha geç gelen aynı satır gerçek bir tekrardır (oyunda aynı söz yeniden söylendi); yeniden çevrilir.
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate.")
    s.feed("")
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS
    assert s.feed("") == CLEAR
    clock.now += SubtitleStabilizer.RESTORE_WITHIN_MS + 1
    assert s.feed("Hold the gate.") == translate("Hold the gate.")


def test_replaced_line_coming_back_is_restored():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    assert s.feed("Hold the gate.") == translate("Hold the gate.")
    clock.now += 100
    assert s.feed("Run!") == translate("Run!")
    clock.now += 100
    assert s.feed("Hold the gate.") == restore("Hold the gate.")
    clock.now += 100
    assert s.feed("Run!") == restore("Run!")


@pytest.mark.parametrize("first,second", [
    ("Where are you going?", "Where are you going, boy?"),
    ("Where are you going, boy?", "Where are you going?"),
    ("We need to leave this place before the sun goes down.", "We need to leave this place before the sun goes down, boy."),
])
def test_two_speakers_with_overlapping_words_are_both_translated(first, second):
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    assert s.feed(first) == translate(first)
    clock.now += 50
    assert s.feed(second) == translate(second)


def test_already_translated_is_skipped():
    s = SubtitleStabilizer()
    assert not s.should_send("Kullanıcı Ekle Oturum Açtı", "Kullanıcı Ekle Oturum Açtı")
    assert s.should_send("Add user", "Kullanıcı ekle")


def test_reset_clears_only_after_something_was_sent():
    s = SubtitleStabilizer()
    assert s.reset() == NONE
    s.feed("Hello there")
    s.feed("Hello there")
    assert s.reset() == CLEAR
    assert s.reset() == NONE


def test_prefixed_reread_does_not_flip_shown_line():
    # Başına önceki satırdan çöp eklenmiş okuma ekrandaki satırı değiştirmez (TV'de 1/2 satır gidip gelmesin).
    assert SubtitleStabilizer.is_prefixed_reread("CESADE. TAl CESARE: Told me you wanted to make yourself useful.",
                                                 "CESARE: Told me you wanted to make yourself useful.")
    assert not SubtitleStabilizer.is_prefixed_reread("CESARE: Told me you wanted to make yourself useful.",
                                                     "CESARE: Told me you wanted to make yourself useful.")
    assert not SubtitleStabilizer.is_prefixed_reread("Hey. Busy.", "Busy."), "kısa satırda değil"


def test_ends_sentence_ignores_closing_quotes():
    assert SubtitleStabilizer.ends_sentence(' "Run." ')
    assert SubtitleStabilizer.ends_sentence("Wait…)")
    assert not SubtitleStabilizer.ends_sentence("We go")
    assert not SubtitleStabilizer.ends_sentence('"')


# --------------------------------------------------------------------------- SubtitleStabilizerRetryTests
def test_forgotten_line_is_translated_again_after_backoff():
    # Çevirisi başarısız olan satır ekranda kaldıkça yeniden denenebilmeli; ama saniyede en çok bir kez.
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate")
    assert s.feed("Hold the gate") == translate("Hold the gate")
    s.forget_sent()
    for _ in range(19):
        clock.now += 50
        assert s.feed("Hold the gate") == NONE
    clock.now += 50
    assert s.feed("Hold the gate") == translate("Hold the gate")


def test_backoff_does_not_delay_a_new_line():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate")
    s.feed("Hold the gate")
    s.forget_sent()
    assert s.feed("Run!") == translate("Run!")


@pytest.mark.parametrize("misread,correct", [
    ("I can do that for you right now.", "I can't do that for you right now."),
    ("I said that I would help you with this.", "I said that I would never help you with this."),
    ("Meet me at the docks at 5.", "Meet me at the docks at 6."),
])
def test_corrected_read_that_changes_meaning_is_translated(misread, correct):
    # Noktayla biten satır ilk karede gider; o kare olumsuzluğu ya da sayıyı kaçırdıysa doğru okuma yeniden çevrilmeli.
    s = SubtitleStabilizer()
    assert s.feed(misread) == translate(misread)
    assert s.feed(correct) == translate(correct)


def test_notes_garbled_drop_and_worse_reread():
    # Günlük için: kararlı olmadan kalkan çöp okuma ve yok sayılan kötü yeniden okuma not edilir; kararlar değişmez.
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    garbled = "- Nat) but, you knpw. shit, I m"
    assert s.feed(garbled) == NONE
    assert s.note is None
    clock.now += 100
    assert s.feed("") == NONE
    assert s.note == StabilizerNote.garbled_dropped(garbled)
    assert s.feed("") == NONE
    assert s.note is None

    assert s.feed(FULL) == translate(FULL)
    assert s.note is None
    s.feed(WORSE)
    second = s.feed(WORSE)
    assert second == NONE
    assert s.note == StabilizerNote.worse_reread(WORSE)


def test_stabilizer_sends_numeric_correction_but_not_letter_noise():
    # NumericGlyphTests.testStabilizerSendsNumericCorrectionButNotLetterNoise
    s = SubtitleStabilizer()
    first = "I have 5 bullets left."
    corrected = "I have 1 bullet left."
    assert s.feed(first) == translate(first)
    assert s.feed("1 have 5 bullets left.") == NONE
    assert s.feed(corrected) == translate(corrected)
    assert s.feed("1 have 1 bullet left.") == NONE


# --------------------------------------------------------------------------- SubtitleStabilizerHoldTests
# Parlak zeminde beyaz altyazı: yazı tanıma ekranda duran altyazıyı saniyelerce okuyamıyor, TV'deki Türkçe siliniyordu.
# Boş okumada satırın yeri (bölge izi) son okunduğu kareyle karşılaştırılır.
PLACE = TextBox(left=0.3, top=0.6, right=0.7, bottom=0.85)


def scene(change=None):
    """Bölge izi (64 × 12 gri örnek)."""
    signature = [120] * (SIGNATURE_WIDTH * SIGNATURE_HEIGHT)
    if change:
        change(signature)
    return signature


def subtitle_spot(signature, delta):
    """Altyazının yerine düşen bir örnek (satır 8, sütun 30)."""
    signature[8 * SIGNATURE_WIDTH + 30] = 120 + delta


def test_line_is_kept_through_missed_reads_while_its_place_is_unchanged():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    assert s.feed("Hold the gate.", signature=scene(), box=PLACE) == translate("Hold the gate.")

    def moving_change(sig):
        sig[0] = 250
        sig[5] = 10
        subtitle_spot(sig, 10)
    moving = scene(moving_change)
    for _ in range(0, 3000, 50):
        clock.now += 50
        assert s.feed("", signature=moving) == NONE
    assert s.feed("Hold the gate.", signature=scene(), box=PLACE) == NONE
    # Okunduktan sonra yine kaçarsa süre baştan sayılır.
    for _ in range(0, 3000, 50):
        clock.now += 50
        assert s.feed("", signature=scene()) == NONE


def test_line_is_cleared_on_time_when_its_place_changes():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate.", signature=scene(), box=PLACE)
    gone = scene(lambda sig: subtitle_spot(sig, 60))
    assert s.feed("", signature=gone) == NONE
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS - 1
    assert s.feed("", signature=gone) == NONE
    clock.now += 1
    assert s.feed("", signature=gone) == CLEAR


def test_held_line_is_cleared_on_time_once_its_place_changes():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate.", signature=scene(), box=PLACE)
    clock.now += 2000
    assert s.feed("", signature=scene()) == NONE
    clock.now += 1000
    assert s.feed("", signature=scene(lambda sig: subtitle_spot(sig, -60))) == NONE
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS - 1
    assert s.feed("", signature=scene()) == NONE
    clock.now += 1
    assert s.feed("", signature=scene()) == CLEAR


def test_unchanged_place_holds_the_line_only_for_a_limited_time():
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate.", signature=scene(), box=PLACE)
    assert s.feed("", signature=scene()) == NONE
    clock.now += SubtitleStabilizer.HOLD_UNCHANGED_MS - 1
    assert s.feed("", signature=scene()) == NONE
    clock.now += 1
    assert s.feed("", signature=scene()) == CLEAR


@pytest.mark.parametrize("signature,box", [(scene(), None), (None, PLACE)])
def test_without_place_or_signature_empty_reads_clear_as_before(signature, box):
    # Satırın yeri bilinmiyorsa (okuyucu kutu vermedi) ya da kare izi yoksa eski kural: 800 ms boşlukta silinir.
    clock = Clock()
    s = SubtitleStabilizer(clock=clock)
    s.feed("Hold the gate.", signature=signature, box=box)
    s.feed("", signature=signature)
    clock.now += SubtitleStabilizer.CLEAR_AFTER_MS
    assert s.feed("", signature=signature) == CLEAR


def test_changed_looks_only_inside_the_box():
    a = scene()
    outside = scene(lambda sig: sig.__setitem__(0, 250))
    assert changed(a, outside, 16)
    assert not changed(a, outside, 16, within=PLACE)
    assert changed(a, scene(lambda sig: subtitle_spot(sig, 17)), 16, within=PLACE)
    assert changed(a, a[:-1], 16)
