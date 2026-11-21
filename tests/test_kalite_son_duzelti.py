# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.son_duzelti — Nino Game Translator'ın FreeTranslationTests.swift'indeki TurkishPostEditTests'ten
taşındı."""

import pytest

from altyazi.kalite import son_duzelti


@pytest.mark.parametrize("source,translation,expected", [
    ("Run!", "Koş.", "Koş!"), ("Run!", "Koş", "Koş!"), ("What?!", "Ne?", "Ne?!"), ("Wait…", "Bekle.", "Bekle…"),
    ("Wait...", "Bekle.", "Bekle..."), ("Where is he?", "O nerede.", "O nerede?"),
    ("He said \"Run!\"", "\"Koş.\" dedi.", "\"Koş.\" dedi."), ("He said \"Run!\"", "\"Koş\" dedi", "\"Koş\" dedi"),
    ("\"Run!\"", "\"Koş.\"", "\"Koş!\""), ("We go.", "Gidiyoruz!", "Gidiyoruz!"), ("We go.", "Gidiyoruz", "Gidiyoruz"),
    ("Boy!", "Evlat!", "Evlat!"),
])
def test_source_ending_is_kept(source, translation, expected):
    assert son_duzelti.apply(source, translation) == expected


@pytest.mark.parametrize("translation,expected", [
    ("Dur , bekle !", "Dur, bekle!"), ("Ne  oldu ?", "Ne oldu?"), ("Peki ... gidelim .", "Peki... gidelim."),
])
def test_space_before_punctuation_is_removed(translation, expected):
    assert son_duzelti.apply("Okay. Go.", translation) == expected


def test_quotes_follow_the_source():
    assert son_duzelti.apply("He said \"run\", Kratos's son.", "“Koş” dedi, Kratos’un oğlu.") \
        == "\"Koş\" dedi, Kratos'un oğlu."
    assert son_duzelti.apply("He said “run”, Kratos’s son.", "\"Koş\" dedi, Kratos'un oğlu.") \
        == "“Koş” dedi, Kratos’un oğlu."


def test_curly_translation_stays_curly_for_curly_source():
    # Belgedeki ve Windows'taki kural (bkz. son_duzelti.quotes notu): kıvrık kaynakta kıvrık çeviri bozulmaz.
    assert son_duzelti.apply("He said “run”.", "“Koş” dedi.") == "“Koş” dedi."


def test_apostrophe_follows_the_source():
    assert son_duzelti.apostrophe("Kratos’s axe") == "’"
    assert son_duzelti.apostrophe("Kratos's axe") == "'"


def test_text_without_letters_is_untouched():
    assert son_duzelti.apply("Run!", " ... ") == " ... "


def test_imperatives_follow_an_informal_line():
    assert son_duzelti.register(["Sana söyledim.", "Bekleyin!", "Dikkat edin, evlat."]) \
        == ["Sana söyledim.", "Bekle!", "Dikkat et, evlat."]
    assert son_duzelti.register(["Seni gördüm. Hemen gelin!"]) == ["Seni gördüm. Hemen gel!"]


@pytest.mark.parametrize("sentence", ["Bekleyin!", "Siz bekleyin, sana sonra bakarım!", "Sen gelin misin?"])
def test_other_lines_keep_their_register(sentence):
    # "Sen" yoksa hitap belirsiz; "siz" varsa bilerek seçilmiş; emir yerinde değilse başka anlam olabilir.
    assert son_duzelti.register([sentence]) == [sentence]


def test_nil_pieces_stay_nil():
    assert son_duzelti.register([None, "Sana söyledim.", None, "Durun!"]) == [None, "Sana söyledim.", None, "Dur!"]


def test_word_inside_another_word_is_not_an_imperative():
    # "durun" "durdurun"un içinde geçse de önünde harf var; yalnız kendi kuralıyla değişir.
    assert son_duzelti.register(["Sana dedim, durdurun!"]) == ["Sana dedim, durdur!"]
