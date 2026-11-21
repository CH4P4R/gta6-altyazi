# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.bolucu — Nino Game Translator'ın SubtitleTextTests.swift'indeki SubtitleSegmenterTests'ten ve
DubbingTests.swift'te parçalarla ilgili kısımdan taşındı."""

import pytest

from altyazi.kalite import bolucu
from altyazi.kalite.bolucu import Piece, SpeakerNames


def pieces(text):
    return [("+" if p.translate else "=") + p.text for p in bolucu.split(text)]


def test_wrapped_lines_become_one_sentence():
    assert pieces("We should keep\nmoving, boy.") == ["+We should keep moving, boy."]


def test_speaker_labels_are_not_translated():
    assert pieces("ATREUS: Father, look!") == ["=ATREUS: ", "+Father, look!"]
    assert pieces("Kratos: Stay close.\nMimir: Aye, brother.") \
        == ["=Kratos: ", "+Stay close.", "=\n", "=Mimir: ", "+Aye, brother."]
    assert pieces("Old Man: Who goes there?") == ["=Old Man: ", "+Who goes there?"]


@pytest.mark.parametrize("text,sent", [
    ("ATREUS: Father!", ["Father!"]),
    ("OLD MAN: Who goes there?", ["Who goes there?"]),
    ("Mimir Head: Brother, wait.", ["Brother, wait."]),
    ("Note: Press X.", ["Note: Press X."]),
])
def test_speaker_names_are_not_sent_to_the_translator(text, sent):
    assert [p.text for p in bolucu.split(text) if p.translate] == sent


def test_learned_names_keep_their_capitals():
    names = SpeakerNames()
    names.learn(bolucu.split("OLD MAN: Hello."))
    assert bolucu.normalize_case("RUN, OLD MAN!", names=names.all) == "Run, Old Man!"


def test_game_headings_are_translated():
    assert pieces("Objective: Find the gate.") == ["+Objective: Find the gate."]


def test_sentences_are_split_but_abbreviations_are_not():
    assert pieces("Boy! What is that? Ask Mr. Smith.") == ["+Boy!", "= ", "+What is that?", "= ", "+Ask Mr. Smith."]
    assert pieces("Wait... what was that?") == ["+Wait... what was that?"]


def test_dialogue_dashes_stay():
    assert pieces("- Run!\n- Where?") == ["=- ", "+Run!", "=\n", "=- ", "+Where?"]


def test_all_caps_sentence_is_normalized_keeping_names():
    assert bolucu.normalize_case("THE GATE WILL NOT HOLD, ATREUS. I KNOW.") == "The gate will not hold, atreus. I know."
    assert bolucu.normalize_case("THE GATE WILL NOT HOLD, ATREUS.", names={"ATREUS"}) == "The gate will not hold, Atreus."
    assert bolucu.normalize_case("BOY!") == "BOY!"
    assert bolucu.normalize_case("Already fine.") == "Already fine."


def test_names_are_learned_from_labels():
    names = SpeakerNames()
    names.learn(bolucu.split("OLD MAN: Hello.\nFreya: Hi."))
    assert names.all == {"OLD", "MAN", "Freya"}


def test_speaker_labels_belong_to_their_sentences():
    # DubbingTests.testSpeakerLabelsBelongToTheirSentences'in parça kısmı.
    assert bolucu.split("KRATOS: We go now. Stay close.\nATREUS: Okay.") == [
        Piece("KRATOS: ", False), Piece("We go now.", True), Piece(" ", False), Piece("Stay close.", True),
        Piece("\n", False), Piece("ATREUS: ", False), Piece("Okay.", True),
    ]


def test_initials_closers_and_symbol_only_pieces():
    assert pieces("J. R. R. Tolkien wrote it. \"Go!\" Now.") \
        == ["+J. R. R. Tolkien wrote it.", "= ", "+\"Go!\"", "= ", "+Now."]
    assert pieces("ATREUS: ...") == ["=ATREUS: ", "=..."]
    assert pieces("\r\n  \n") == []
    assert bolucu.speaker_label("Note: x") is None
    assert bolucu.speaker_label("OLD MAN: x") == "OLD MAN: "
    assert bolucu.name_from_label("OLD MAN: ") == "OLD MAN"
