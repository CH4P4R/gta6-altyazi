# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.konusan — Nino Game Translator'ın SpeakerPrefixTests.swift'inden taşındı (Android SpeakerPrefixTest
ve Windows SpeakerPrefixTests ile aynı örnekler). Reading.joiningRows testi taşınmadı (o kod bu pakette yok)."""

import pytest

from altyazi.kalite import konusan
from altyazi.kalite.konusan import SpokenLine, Split


def test_name_is_split_from_the_sentence():
    assert konusan.split("ARTHUR: We need to go.") == Split("ARTHUR", "We need to go.")
    assert konusan.split("Dutch: I have a plan.") == Split("Dutch", "I have a plan.")
    assert konusan.split("Mrs. Adler：Leave me.") == Split("Mrs. Adler", "Leave me.")
    assert konusan.split("OLD MAN : Hm.").name == "OLD MAN"
    assert konusan.split("ARTHUR:We go.").body == "We go."
    assert konusan.split("Arthur:\nWe need to go.").body == "We need to go."


@pytest.mark.parametrize("text", [
    "10:30 at the station.", "Meet me at 10:30.", "HTTPS://example.com", "Ratio 16:9", "Note: the gate is shut.",
    "I told you: get out!", "Very Long Name Of Four: words", "Bartholomew Montgomeryson: Hi.", "ARTHUR:",
])
def test_false_matches_are_left_alone(text):
    assert konusan.split(text) is None


def test_present_adds_or_hides_the_name():
    source = "ARTHUR: We need to go."
    assert konusan.present("Gitmeliyiz.", source=source, show=True) == "ARTHUR: Gitmeliyiz."
    assert konusan.present("Gitmeliyiz.", source=source, show=False) == "Gitmeliyiz."
    # Paket adlı satırı bulduysa ad iki kez yazılmaz.
    assert konusan.present("ARTHUR: Gitmeliyiz.", source=source, show=True) == "ARTHUR: Gitmeliyiz."
    assert konusan.present("ARTHUR: Evet.\nDUTCH: Hayır.", source="ARTHUR: Yes.\nDUTCH: No.", show=False) == "Evet.\nHayır."
    # İngilizcede ad olmayan Türkçe başlık atılmaz.
    assert konusan.present("Hedef: Kampa dön.", source="Objective: Return to camp.", show=False) == "Hedef: Kampa dön."


def test_voiced_lines_get_the_speaker():
    lines = konusan.voiced([SpokenLine(english="We go.", turkish="Gidiyoruz.")], prefix=Split("ARTHUR", "We go."))
    assert [line.speaker for line in lines] == ["ARTHUR"]


def test_voiced_stops_at_a_named_line_or_a_new_turn():
    lines = [SpokenLine("We go.", "Gidiyoruz."), SpokenLine("Wait.", "Bekle.", new_turn=True),
             SpokenLine("Now.", "Şimdi.")]
    assert [line.speaker for line in konusan.voiced(lines, Split("ARTHUR", "x"))] == ["ARTHUR", None, None]
    named = [SpokenLine("We go.", "Gidiyoruz.", speaker="DUTCH"), SpokenLine("Now.", "Şimdi.")]
    assert [line.speaker for line in konusan.voiced(named, Split("ARTHUR", "x"))] == ["DUTCH", None]
    assert konusan.voiced(lines, None) == lines
