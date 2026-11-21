# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın GameSenseTests.swift, LinePoolTests.swift (RunningGame) ve GamePacksTests.swift
(GameChoice) denemelerinden taşındı; paket eşlemesi ve GameChoice zamanlayıcısı için ek denemeler."""

import json
from pathlib import Path
from types import SimpleNamespace

from altyazi.oyun.oyun_algi import (GameChoice, GameSense, RunningGame, Source, distinctive_pack, game_key,
                                    pack_for_game, pack_games, pool_pack_id, running_game_from_console, suggestions,
                                    title_id_from_pack)
from altyazi.packs import Pack, key

GTA = ("gta-v", "Grand Theft Auto V")
RDR = ("rdr-2", "Red Dead Redemption 2")


# ------------------------------------------------------------------------------------------------- GameSense
def test_one_stray_line_does_not_change_the_game():
    """Tek bir yabancı satır oyunu değiştirmez; son 20 satırın 5'i başka paketten gelince oyun o olur."""
    sense = GameSense()
    for _ in range(5):
        sense.note_line(*GTA)
    assert sense.current.name == GTA[1]
    assert not sense.note_line(*RDR)
    assert sense.current.name == GTA[1]
    for _ in range(3):
        assert not sense.note_line(*RDR)
    assert sense.current.name == GTA[1]
    assert sense.note_line(*RDR)
    assert sense.current.name == RDR[1]
    assert sense.pack_id == "rdr-2"


def test_without_a_stable_game_the_chosen_name_or_nothing_is_sent():
    sense = GameSense()
    for _ in range(4):
        sense.note_line(*RDR)
    assert sense.current is None
    sense.choose(GTA[1])
    assert sense.current.name == GTA[1]
    sense.set_console(RunningGame.named("Mafia: The Old Country"))
    assert sense.current.name == "Mafia: The Old Country"


def test_chosen_game_beats_the_pack_but_not_the_console():
    sense = GameSense()
    sense.choose("Marvel's Wolverine")
    for _ in range(5):
        sense.note_line(*RDR)
    assert sense.current.name == "Marvel's Wolverine"
    assert sense.source is Source.USER
    assert sense.pack_limit == "Marvel's Wolverine"
    sense.set_console(RunningGame.named("Mafia: The Old Country"))
    assert sense.current.name == "Mafia: The Old Country"
    assert sense.source is Source.CONSOLE
    assert sense.pack_limit is None
    # PS5 başka oyun bildirdiyse elle seçim eskidi: PS5 bildirmeyi bırakınca paketten tanınan gelir.
    sense.set_console(None)
    assert sense.current.name == RDR[1]
    assert sense.pack_limit is None


def test_same_game_from_the_console_keeps_the_choice():
    sense = GameSense()
    sense.choose("GTA 5")
    sense.set_console(RunningGame.named("Grand Theft Auto V"))
    sense.set_console(None)
    assert sense.current.name == "GTA 5"
    assert sense.pack_limit == "GTA 5"


def test_general_pool_pack_is_not_a_game_and_pool_pack_carries_title_id():
    sense = GameSense()
    for _ in range(10):
        assert not sense.note_line("pool-genel", "Genel")
    assert sense.current is None
    for _ in range(5):
        sense.note_line("pool-ppsa01234", "Grand Theft Auto VI")
    assert sense.current == RunningGame("PPSA01234", "Grand Theft Auto VI")
    assert sense.source is Source.PACK and not sense.is_sure


def test_should_ask_after_two_minutes_only_when_nothing_is_known():
    sense = GameSense()
    assert not sense.should_ask(119, True)
    assert sense.should_ask(120, True)
    assert not sense.should_ask(500, False)
    sense.set_seen("Grand Theft Auto VI")
    assert not sense.should_ask(500, True)
    assert sense.source is Source.SCREEN and sense.is_sure
    sense.set_seen(None)
    sense.mark_asked()
    assert not sense.should_ask(500, True)
    sense.start_session()
    assert sense.should_ask(500, True)


# ------------------------------------------------------------------------------------------------- RunningGame
def test_running_game_validates_the_title_id():
    assert RunningGame.from_console("CUSA00419_00", None).title_id == "CUSA00419_00"
    assert RunningGame.from_console("ppsa12345", "  Grand Theft Auto VI\n") == RunningGame("PPSA12345",
                                                                                           "Grand Theft Auto VI")
    assert RunningGame.from_console("PPSA1234", "x") is None
    assert RunningGame.from_console("PPSA01234_0", "x") is None
    assert RunningGame.from_console("", "x") is None
    assert RunningGame.from_console(None, "x") is None
    assert RunningGame.from_console("PPSA01234", " \x00 ").name is None
    assert len(RunningGame.from_console("PPSA01234", "x" * 300).name) == 120
    assert RunningGame.named("  ") is None
    assert RunningGame.named("GTA 6", "bad").title_id is None


def test_running_game_from_console_info():
    info = SimpleNamespace(host="1.2.3.4", name="PS5", awake=True, title_id="PPSA03420", app_name="Grand Theft Auto V")
    assert running_game_from_console(info) == RunningGame("PPSA03420", "Grand Theft Auto V")
    assert running_game_from_console(SimpleNamespace(title_id=None, app_name=None)) is None


# ------------------------------------------------------------------------------------------------- GameName
def test_game_key():
    assert game_key("Grand Theft Auto VI") == "gta 6"
    assert game_key("GTA 6") == "gta 6"
    assert game_key("gta6") == "gta 6"
    assert game_key("Grand Theft Auto V") == game_key("gta-v") == "gta 5"
    assert game_key("Red Dead Redemption 2") == game_key("red-dead-redemption-2") == "rdr 2"
    assert game_key("The Witcher 3: Wild Hunt") == "witcher 3 wild hunt"
    assert game_key("EA SPORTS FC™ 26") == "fc 26"
    assert game_key("Marvel’s Spider-Man 2") == game_key("marvels-spider-man-2")
    assert game_key("God of War Ragnarök") == "god of war ragnarok"
    assert game_key("Ratchet & Clank") == "ratchet and clank"


# ------------------------------------------------------------------------------------------------- paket eşlemesi
PACKS = [("gta-v", "Grand Theft Auto V"), ("red-dead-redemption-2", "Red Dead Redemption 2"),
         ("elden-ring", "Elden Ring + Shadow of the Erdtree"), ("pool-genel", "Genel"),
         ("pool-ppsa01234", "Grand Theft Auto VI")]


def test_title_id_and_pool_pack_round_trip():
    assert title_id_from_pack("pool-ppsa01234") == "PPSA01234"
    assert title_id_from_pack("pool-cusa00419-00") == "CUSA00419_00"
    assert title_id_from_pack("gta-v") is None
    assert pool_pack_id("CUSA00419_00") == "pool-cusa00419-00"


def test_pack_for_game_by_title_id_then_name():
    assert pack_for_game(RunningGame("PPSA01234", "whatever"), PACKS) == "pool-ppsa01234"
    assert pack_for_game(RunningGame("PPSA99999", "Grand Theft Auto V"), PACKS) == "gta-v"
    assert pack_for_game("GTA 5", PACKS) == "gta-v"
    assert pack_for_game("RED DEAD REDEMPTION 2", PACKS) == "red-dead-redemption-2"
    assert pack_for_game("ELDEN RING", PACKS) == "elden-ring"          # kimliğin anahtarı
    assert pack_for_game("Elden Ring Nightreign", PACKS) is None       # başka oyun
    assert pack_for_game("Marvel's Wolverine", PACKS) is None
    assert pack_for_game("Genel", PACKS) is None
    assert pack_for_game(None, PACKS) is None


def test_later_pack_with_the_same_game_wins():
    packs = PACKS + [("gta-5-topluluk", "GTA 5")]
    assert pack_for_game("Grand Theft Auto V", packs) == "gta-5-topluluk"


def test_distinctive_pack_counts_only_lines_in_a_single_pack():
    gta = Pack("gta-v", "Grand Theft Auto V", Path("a"), {key("Let's go."): "Hadi.", key("Franklin!"): "Franklin!"})
    rdr = Pack("rdr-2", "Red Dead Redemption 2", Path("b"), {key("Let's go."): "Gidelim.", key("Arthur!"): "Arthur!"})
    library = SimpleNamespace(packs=[gta, rdr])
    assert distinctive_pack(library, "Let's go.") is None
    assert distinctive_pack(library, "Franklin!") == "gta-v"
    assert distinctive_pack(library, "LAMAR: Franklin!") == "gta-v"
    assert distinctive_pack(library, "Hey. Arthur!") == "rdr-2"
    assert distinctive_pack(library, "Unknown line.") is None
    assert distinctive_pack(SimpleNamespace(packs=[]), "Franklin!") is None


def test_suggestions_and_pack_games():
    assert pack_games(PACKS)[:2] == ["Grand Theft Auto V", "Red Dead Redemption 2"]
    assert "Genel" not in pack_games(PACKS)
    s = suggestions("", ["Grand Theft Auto V"], last="Mafia: The Old Country")
    assert s[0] == "Mafia: The Old Country" and s[1] == "Grand Theft Auto V" and len(s) == 8
    assert s.count("Grand Theft Auto V") == 1
    assert suggestions("gta", [], None)[:2] == ["Grand Theft Auto VI", "Grand Theft Auto V"]
    assert suggestions("ring", [], None) == ["Elden Ring", "Elden Ring Nightreign"]


# ------------------------------------------------------------------------------------------------- GameChoice
class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def test_game_choice_limits_packs_to_the_chosen_game(tmp_path):
    """Elle seçim paket aramasını sınırlar; PS5 oyun bildirince sınır kalkar (Nino: testGameChoiceLimitsPacks...)."""
    limits, changes = [], []
    choice = GameChoice(tmp_path / "oyun.json", clock=Clock())
    choice.on_limit = limits.append
    choice.on_change = changes.append
    choice.start(None, lambda: False)
    choice.choose("Marvel's Wolverine")
    assert limits[-1] == "Marvel's Wolverine"
    for _ in range(6):
        choice.note_line(*RDR)
    assert choice.game.name == "Marvel's Wolverine"
    choice.console_reported(RunningGame.from_console("PPSA01234", "Red Dead Redemption 2"))
    assert limits[-1] is None
    assert choice.game.name == "Red Dead Redemption 2" and choice.source is Source.CONSOLE
    assert [g.name for g in changes] == ["Marvel's Wolverine", "Red Dead Redemption 2"]
    choice.stop()


def test_card_opens_once_after_two_minutes():
    clock, asked = Clock(), []
    choice = GameChoice(None, clock=clock)
    choice.on_ask = lambda: asked.append(True)
    assert not choice.tick()                   # başlamadan sorulmaz
    choice.start("Oturma odası PS5", lambda: True)
    clock.t = 119
    assert not choice.tick()
    clock.t = 120
    assert choice.tick() and choice.asking and asked == [True]
    clock.t = 999
    assert not choice.tick()                   # bir kez
    choice.dismiss()
    assert not choice.asking


def test_card_is_not_needed_when_the_game_is_recognized():
    clock = Clock()
    choice = GameChoice(None, clock=clock)
    choice.start(None, lambda: True)
    for _ in range(5):
        choice.note_line(*GTA)
    clock.t = 500
    assert not choice.tick()
    assert choice.game.name == GTA[1] and choice.source is Source.PACK


def test_choice_is_remembered_per_console(tmp_path):
    store = tmp_path / "oyun.json"
    choice = GameChoice(store, clock=Clock())
    choice.start("Salon PS5", lambda: True)
    choice.choose("  Grand Theft Auto VI ")
    assert json.loads(store.read_text())["lastGames"] == {"Salon PS5": "Grand Theft Auto VI"}
    again = GameChoice(store, clock=Clock())
    again.start("Salon PS5", lambda: True)
    assert again.last_played == "Grand Theft Auto VI"
    assert again.suggestions("")[0] == "Grand Theft Auto VI"
    other = GameChoice(store, clock=Clock())
    other.start("Yatak odası PS5", lambda: True)
    assert other.last_played is None


def test_seen_game_closes_the_card_and_empty_choice_is_ignored():
    choice = GameChoice(None, clock=Clock())
    choice.start(None, lambda: True)
    choice.ask()
    assert choice.asking
    choice.choose("   ")
    assert choice.asking and choice.game is None
    choice.seen("Grand Theft Auto VI")
    assert not choice.asking and choice.game.name == "Grand Theft Auto VI" and choice.source is Source.SCREEN
