# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.satir — Nino Game Translator'ın SubtitleWrapTests.swift'inden taşındı (SubtitleStack.Line'ı kullanan
paragraf denetimi bu pakette olmadığından yalnız `fit` kısmı)."""

from altyazi.kalite import satir
from altyazi.kalite.satir import Result


def test_short_text_is_untouched():
    assert satir.fit("Gitmeliyiz, hemen.") == Result("Gitmeliyiz, hemen.", 1)


def test_long_text_splits_into_two_balanced_lines():
    text = "Bu işin sonunda hepimiz için bir çıkış yolu bulmamız gerekiyor artık"
    result = satir.fit(text)
    lines = result.text.split("\n")
    assert len(lines) == 2
    assert result.scale == 1
    assert abs(len(lines[0]) - len(lines[1])) <= 12
    assert " ".join(lines) == text


def test_very_long_text_uses_at_most_three_lines_and_shrinks():
    text = " ".join(["kelime"] * 30)
    result = satir.fit(text)
    assert len(result.text.split("\n")) == 3
    assert result.scale < 1
    assert result.scale >= satir.MIN_SCALE


def test_speaker_name_stays_on_first_line_with_text():
    result = satir.fit("ARTHUR: We need to leave before they find us here in the middle of the night, understand?")
    first = result.text.split("\n")[0]
    assert first.startswith("ARTHUR: "), first
    assert len(first) > len("ARTHUR:")


def test_existing_breaks_are_kept():
    text = "Birinci satır uzun uzun uzun uzun\nİkinci satır da oldukça uzun bir satır"
    assert satir.fit(text).text == text


def test_single_long_word_is_untouched():
    word = "a" * 60
    assert satir.fit(word) == Result(word, 1)


def test_balance_prefers_the_shortest_longest_line():
    assert satir.balance(["aa", "bb", "cc", "dd"], 2) == "aa bb\ncc dd"
    assert satir.balance(["aaaa", "b", "c", "d"], 3) == "aaaa\nb c\nd"
    assert satir.tokens("ARTHUR: We go now.") == ["ARTHUR: We", "go", "now."]
