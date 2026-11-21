# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.metin_eslesme — Nino Game Translator'ın TextMatchTests.swift ve NumericGlyphTests.swift dosyalarından
taşındı (TextBox.centeredOnScreen testleri bu pakette olmayan kod için olduğundan taşınmadı)."""

import pytest

from altyazi.kalite import metin_eslesme as tm
from altyazi.kalite import ocr_gurultu


@pytest.mark.parametrize("reread,sent", [
    ("I can't do that for you right now.", "I can do that for you right now."),
    ("I said that I would never help you with this.", "I said that I would help you with this."),
    ("He is not coming back tonight.", "He is coming back tonight."),
    ("Meet me at the docks at 6.", "Meet me at the docks at 5."),
])
def test_meaning_changing_reread_is_not_same_subtitle(reread, sent):
    assert not tm.is_same_subtitle(tm.normalize(reread), tm.normalize_rows(sent))


@pytest.mark.parametrize("reread,sent", [
    ("I can’t do that for you right now.", "I can't do that for you right now."),
    ("I dont know what to do.", "I don't know what to do."),
    ("He is n0t coming back tonight.", "He is not coming back tonight."),
])
def test_spelling_noise_keeps_negated_line_same(reread, sent):
    assert tm.is_same_subtitle(tm.normalize(reread), tm.normalize_rows(sent))


@pytest.mark.parametrize("reread,sent,expected", [
    ("I can't do that.", "I can do that.", True),
    ("I can do that.", "I can't do that.", False),
    ("Meet me at 6.", "Meet me at 5.", True),
    ("Meet me at", "Meet me at 5.", False),
    ("He is n0t here.", "He is here.", True),
    ("I dont know.", "I don't know.", False),
    ("Buy a t shirt.", "Buy a shirt.", False),
    ("Buy a cotton t shirt.", "Buy a cotton shirt.", False),
    ("I won t go.", "I will go.", True),
    ("We haven t left.", "We have left.", True),
    ("Bring 5 and 5.", "Bring 5.", True),
    ("Bring 5.", "Bring 5 and 5.", False),
    ("It costs $500 now.", "It costs $500.", False),
    ("1 can do that.", "I can do that.", False),
])
def test_adds_meaning_counts_only_added_marks(reread, sent, expected):
    assert tm.adds_meaning(reread, sent) is expected


def test_normalize_strips_punctuation_and_case():
    assert tm.normalize("Kratos: We do NOT have time, boy.") == "kratos we do not have time boy"


def test_similar_tolerates_ocr_noise():
    assert tm.is_similar("the gate will not hold", "the gale will not hold")


def test_different_lines_are_not_similar():
    assert not tm.is_similar("we do not have time", "the gate will not hold")


def test_same_subtitle_ignores_garbled_words():
    a = tm.normalize("Across the deep waters, Pbo ou$3e went, hoping a boat would carry him home.")
    b = tm.normalize("Across the deep waters2aljd O went, Hoping a boat would carry him home.")
    assert tm.is_same_subtitle(b, a)
    word_swap = tm.normalize("Across the deep waters, 2aljd Pbo went, Hoping 3e boat would carry him home now.")
    assert not tm.is_similar(word_swap, a)
    assert tm.is_same_subtitle(word_swap, a)


def test_reread_missing_a_line_is_same_subtitle():
    # İki satırlık altyazı solarken alt satır kaçırıldı: yeni satır değil.
    two_rows = "Across the deep waters, Pbo went,\nhoping a boat would carry him home."
    sent = tm.normalize_rows(two_rows)
    assert tm.is_same_subtitle(tm.normalize(ocr_gurultu.clean("Across the deep waters2aljd O went,")), sent)
    assert tm.is_same_subtitle(tm.normalize("Across the deep waters, Pbo went,"), sent)
    assert tm.is_same_subtitle(tm.normalize("hoping a boat would carry him home."), sent)
    # Daktilo efektinde uzayan metin ise yenidir.
    assert not tm.is_same_subtitle(tm.normalize(two_rows), tm.normalize("Across the deep waters, Pbo went,"))


@pytest.mark.parametrize("reread,sent", [
    ("Where are you going?", "Where are you going, boy?"),
    ("Where are you going, boy?", "Where are you going?"),
    ("We need to leave this place before the sun goes down, boy.", "We need to leave this place before the sun goes down."),
    ("Boy, we need to leave this place before the sun goes down.", "We need to leave this place before the sun goes down."),
])
def test_line_sharing_most_words_is_a_new_subtitle(reread, sent):
    # İki konuşmacı aynı sözlerle konuşuyor: sözcüklerin çoğu ortak olsa da ikisi de ayrı çevrilmeli.
    assert not tm.is_same_subtitle(tm.normalize(reread), tm.normalize_rows(sent))


def test_shortened_single_row_is_not_a_missing_row():
    assert not tm.is_same_subtitle("we have to cross the river",
                                   tm.normalize_rows("We have to cross the river before the sun goes down"))
    assert tm.is_same_subtitle("we have to cross the river",
                               tm.normalize_rows("We have to cross the river\nbefore the sun goes down"))


@pytest.mark.parametrize("a,b", [
    ("we do not have time", "the gate will not hold"),
    # Daktilo efektiyle uzayan satır yeni sayılır.
    ("we do not have time for this boy and you know it", "we do not have time"),
    ("where is the boy", "where is the ship"),
    ("you should not be here", "i told you to stay with your mother"),
    ("we have to cross the river before the sun goes down", "the river is too deep for us to cross today"),
])
def test_same_subtitle_keeps_distinct_lines_apart(a, b):
    assert not tm.is_same_subtitle(a, b)


def test_empty_is_never_similar_to_text():
    assert not tm.is_similar("", "abc")
    assert not tm.is_similar("", "")


@pytest.mark.parametrize("new,old", [
    ("We do not have time for this.", "We do not have"),
    ("We do not have", "We do not have time for this."),
    ("have time for this, boy.", "We do not have time for this, boy."),
    ("The gate will not hold!", "The gale will not hold"),
    ("Across the deep waters he went, hoping a boat would carry him home.",
     "Across the deep waters O went, Hoping a boal would carry him home"),
])
def test_revisions_of_the_same_sentence(new, old):
    # Uzayan, yarım ya da bir iki sözcüğü başka okunan aynı cümle: TV'de öncekinin yerine geçer.
    assert tm.is_revision(new, old)


@pytest.mark.parametrize("new,old", [
    ("Run to the boat!", "We do not have time for this."),
    ("Where is the ship?", "Where is the boy?"),
    ("No.", "Yes."),
    ("I told you to stay with your mother.", "You should not be here."),
])
def test_different_sentences_are_not_revisions(new, old):
    assert not tm.is_revision(new, old)


def test_growth_only_counts_added_words():
    assert tm.is_growth("We do not have time.", "We do not")
    assert not tm.is_growth("We do not", "We do not have time.")
    assert not tm.is_growth("We do not have time.", "We do not have time.")
    assert tm.is_growth("Then we go home.", "Then")
    # Başı okunmamış satır: sondaki tek sözcük yetmez, iki sözcük yeter.
    assert not tm.is_growth("Then we go home.", "home")
    assert tm.is_growth("Then we go home.", "go home")


def test_worse_reread_of_the_same_sentence():
    full = "Shit, I just came by to see if there's somethin' I can help you with."
    worse = "Shit, I came by to see if there somethinl I can help ya."
    assert tm.is_worse_reread(worse, full)
    assert not tm.is_worse_reread(full, worse)


# --------------------------------------------------------------------------- NumericGlyphTests
@pytest.mark.parametrize("reread,sent", [
    ("I have 1 bullet left.", "I have 5 bullets left."),
    ("I have 1 bullet left.", "I have 5 bullet left."),
    ("1 have 1 bullet left.", "I have 5 bullets left."),
    ("I need 1 more key.", "I need more keys."),
    ("I have 1 and 1 left.", "I have 1 left."),
    ("I have 1 and 1 left.", "I have 1 and 5 left."),
    ("O, we have 0 keys left.", "O, we have 5 keys left."),
    ("I have 10 keys left.", "I have 5 keys left."),
    ("I have 1 key left.", "I have\n5 keys left."),
])
def test_number_changes_are_not_hidden_by_letters_elsewhere(reread, sent):
    assert tm.adds_meaning(reread, sent)
    assert not tm.is_same_subtitle(tm.normalize(reread), tm.normalize_rows(sent))
    assert not tm.is_worse_reread(reread, sent)


@pytest.mark.parametrize("reread,sent", [
    ("1 can do that.", "I can do that."),
    ("0, we should leave now.", "O, we should leave now."),
    ("Now 1 can do that.", "Now I can do that."),
    ("Ycs 1 can do thal.", "Yes I can do that."),
    ("Yes 1 can do that.", "Well I can do that."),
    ("1 can do that now.", "I can do that."),
    ("Now 1 can do that.", "I can do that."),
    ("1 have 1 key left.", "I have 1 key left."),
    ("1 said 1 can do that.", "I said I can do that."),
    ("1 have 5 keys left.", "I have 5 keys left."),
])
def test_aligned_letter_digit_noise_does_not_add_a_number(reread, sent):
    assert not tm.adds_meaning(reread, sent)


def test_python_levenshtein_matches_the_fast_one():
    # rapidfuzz varsa onunla, yoksa saf Python ile hesaplanır; ikisi aynı sonucu vermeli.
    pairs = [("the gate will not hold", "the gale will not hold"), ("kitten", "sitting"), ("", "abc"),
             (["we", "do", "not"], ["we", "not"])]
    for x, y in pairs:
        assert tm._levenshtein_python(x, y) == tm._levenshtein(x, y)
