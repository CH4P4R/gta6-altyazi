# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.kalite.sozluk — Nino Game Translator'ın FreeTranslationTests.swift'indeki GlossaryTests, GameTermsTests ve
FreeTranslationTests'ten taşındı.

FreeTranslation.swift taşınmadı (entegrasyonu çağıran yapacak); zincirin sınanabilmesi için aşağıdaki `_ceviri`
yardımcısı FreeTranslation.translate'in adımlarını aynı sırayla izler (README_entegrasyon'daki yerel motor sırası).
"""

from __future__ import annotations

import re

import pytest

from altyazi.kalite import bolucu, oyun_ingilizce, son_duzelti
from altyazi.kalite.sozluk import Glossary, GlossaryStore, ParseError, line_key, user_files
from altyazi.kalite.terim import TermProtector

GOD_OF_WAR = """
    { "game": "God of War",
      "terms": { "Leviathan Axe": "Leviathan Baltası", "Axe": "Balta", "Midgard": "Midgard", "World Serpent": "Dünya Yılanı" },
      "keep": ["Kratos", "Atreus"] }
"""


@pytest.fixture
def gow() -> Glossary:
    return Glossary.parse(GOD_OF_WAR)


# --------------------------------------------------------------------------- GlossaryTests
def test_parses_terms_and_keep_names(gow):
    assert gow.count == 6
    assert gow.turkish("leviathan  axe") == "Leviathan Baltası"
    assert gow.turkish("KRATOS") == "Kratos"
    assert gow.turkish("Freya") is None


def test_finds_whole_words_case_insensitive_longest_first(gow):
    found = gow.find("THROW THE LEVIATHAN AXE, then the axe. Kratos's axes. Midgardian.")
    assert [m.english for m in found] == ["Leviathan Axe", "Axe", "Kratos"]
    assert found[0].start == 10
    assert found[0].length == len("Leviathan Axe")


def test_capitalized_terms_and_keep_names_are_capital_words(gow):
    assert sorted(gow.capital_words) == ["atreus", "axe", "kratos", "leviathan", "midgard", "serpent", "world"]
    assert "health" not in Glossary.built_in().capital_words


def test_built_in_glossary_has_general_game_terms():
    assert Glossary.built_in().count >= 10
    assert Glossary.built_in().turkish("Health Potion") == "can iksiri"
    assert Glossary.built_in().turkish("skill tree") == "yetenek ağacı"


def test_keep_exact_names_match_only_as_written():
    # Phantom Blade Zero: kahramanın adı "Soul" çevrilmez, sıradan "soul" çevrilir.
    found = Glossary.built_in().find("Soul, you sold your soul. SOUL!")
    assert [m.english for m in found] == ["Soul"]
    assert found[0].start == 0
    assert "soul" not in Glossary.built_in().capital_words
    exact = Glossary.parse('{ "keepExact": ["Soul"] }')
    loose = Glossary.parse('{ "keep": ["Soul"] }')
    assert exact.fingerprint != loose.fingerprint


def test_later_glossary_wins_and_fingerprint_follows_content():
    user = Glossary.parse('{ "terms": { "skill tree": "beceri ağacı" } }')
    merged = Glossary.merge([Glossary.built_in(), user])
    assert merged.turkish("skill tree") == "beceri ağacı"
    assert merged.fingerprint != Glossary.built_in().fingerprint
    assert merged.fingerprint == Glossary.merge([Glossary.built_in(), user]).fingerprint


def test_ignores_entries_without_letters():
    assert Glossary.parse('{ "terms": { "...": "x", "Odin": "Odin", "": "y" }, "keep": [3] }').count == 1


def test_overlong_terms_and_non_objects_are_rejected():
    assert Glossary.parse('{ "keep": ["' + "a" * 81 + '", "' + "b" * 80 + '"] }').count == 1
    with pytest.raises(ParseError):
        Glossary.parse("[1, 2]")
    with pytest.raises(ValueError):
        Glossary.parse("{ not json")


def test_loads_user_folder_and_skips_broken_files(tmp_path):
    (tmp_path / "gow.json").write_text(GOD_OF_WAR, encoding="utf-8")
    (tmp_path / "broken.json").write_text("{ not json", encoding="utf-8")
    (tmp_path / "notes.txt").write_text('{ "keep": ["Ignored"] }', encoding="utf-8")
    glossary = Glossary.load(tmp_path)
    assert glossary.turkish("Leviathan Axe") == "Leviathan Baltası"
    assert glossary.turkish("health potion") == "can iksiri"
    assert glossary.turkish("Ignored") is None
    assert Glossary.load(tmp_path / "missing").count == Glossary.built_in().count
    assert [p.name for p in user_files(tmp_path)] == ["broken.json", "gow.json"]
    assert user_files(None) == []


def test_store_reloads_when_a_file_changes(tmp_path):
    now = [0.0]
    store = GlossaryStore(tmp_path, clock=lambda: now[0])
    assert store.glossary.turkish("Kratos") is None
    (tmp_path / "gow.json").write_text(GOD_OF_WAR, encoding="utf-8")
    # Klasöre birkaç saniyede bir bakılır.
    assert store.glossary.turkish("Kratos") is None
    now[0] += 6
    assert store.glossary.turkish("Kratos") == "Kratos"
    assert GlossaryStore.built_in_only().glossary.turkish("Kratos") is None


def test_fingerprint_matches_the_other_platforms():
    # Windows, Android ve Mac'le aynı iz: önbellek anahtarları aynı kalır.
    assert Glossary.built_in().fingerprint == "g978a414e"


def test_empty_glossary_finds_nothing():
    assert Glossary.empty().is_empty
    assert Glossary.empty().find("Kratos") == []
    assert Glossary.empty().line("Reloading!") is None
    assert Glossary.empty().plain("toss a smoke") == "toss a smoke"


# --------------------------------------------------------------------------- FreeTranslation zinciri (testte)
SEPARATOR = " *** "


def _is_short(sentence: str) -> bool:
    words = sum(1 for w in sentence.split() if any(c.isalpha() for c in w))
    return 0 < words < 4


def _after_separator(output: str, source: str) -> str | None:
    first = output.find("***")
    if first < 0 or output.find("***", first + 3) >= 0:
        return None
    before, after = output[:first], output[first + 3:].strip()
    if after.startswith("*") or before.endswith("*"):
        return None
    if not any(c.isalpha() for c in before) or not any(c.isalpha() for c in after):
        return None
    if len(after.encode("utf-16-le")) // 2 > 3 * (len(source.encode("utf-16-le")) // 2) + 20:
        return None
    return after


def _ceviri(sentence, context, glossary, engine, normalize=lambda t: t):
    """FreeTranslation.translate ile aynı adımlar."""
    fixed = glossary.line(sentence)
    if fixed is not None:
        return son_duzelti.apply(sentence, fixed)
    apostrophe = son_duzelti.apostrophe(sentence)

    def prepare(text):
        return oyun_ingilizce.plain(glossary.plain(normalize(text)))

    if context is not None:
        protector = TermProtector(glossary, [sentence, context])
        context_text = protector.protect(prepare(context))[0]
        sentence_text, slots = protector.protect(prepare(sentence))
        output = engine(context_text + SEPARATOR + sentence_text)
        after = _after_separator(output, sentence)
        if after is not None:
            restored = TermProtector.restore(after, slots, protector.all_slots, apostrophe)
            if restored is not None:
                return son_duzelti.apply(sentence, restored)
    single = TermProtector(glossary, [sentence])
    text, used = single.protect(prepare(sentence))
    translated = engine(text)
    if not used:
        return son_duzelti.apply(sentence, translated)
    done = TermProtector.restore(translated, used, single.all_slots, apostrophe)
    if done is not None:
        return son_duzelti.apply(sentence, done)
    # Model bir yer tutucuyu düşürdü: terimsiz ama eksiksiz çeviri, eksik terimli çeviriden iyidir.
    return son_duzelti.apply(sentence, engine(prepare(sentence)))


class Engine:
    """Çağrıları kaydeden sahte motor."""

    def __init__(self, mapping):
        self.calls: list[str] = []
        self.mapping = mapping

    def __call__(self, text: str) -> str:
        self.calls.append(text)
        return self.mapping(text)


FREE_GOW = Glossary.parse('{ "terms": { "Leviathan Axe": "Leviathan Baltası" }, "keep": ["Kratos", "Atreus"] }')


@pytest.mark.parametrize("sentence,expected", [
    ("Boy!", True), ("Do it.", True), ("Not you, boy.", True), ("We go to the mountain.", False), ("...", False),
])
def test_short_lines_have_fewer_than_four_words(sentence, expected):
    assert _is_short(sentence) is expected


@pytest.mark.parametrize("output,expected", [
    ("Annen nerede? *** Sen değil.", "Sen değil."), ("Annen nerede?***Sen değil.", "Sen değil."),
    ("ANNEN NEREDE? *** SEN DEĞİL.", "SEN DEĞİL."), ("Annen nerede? Sen değil.", None),
    ("Annen *** nerede? *** Sen değil.", None), ("Annen nerede? **** Sen değil.", None), ("*** Sen değil.", None),
    ("Annen nerede? ***", None),
    ("Annen nerede? *** Sen değil, sen değil, sen değil, sen değil, sen değil, sen değil, sen değil.", None),
])
def test_part_after_the_separator_only_when_unambiguous(output, expected):
    assert _after_separator(output, "Not you.") == expected


def test_terms_are_protected_and_restored():
    engine = Engine(lambda _: "Zarmon, Velkor'u fırlat.")
    result = _ceviri("Kratos, throw the Leviathan Axe!", None, FREE_GOW, engine)
    assert engine.calls == ["Zarmon, throw the Velkor!"]
    assert result == "Kratos, Leviathan Baltası'nı fırlat!"


def test_lost_placeholder_falls_back_to_plain_translation():
    engine = Engine(lambda t: "Baltayı fırlat!" if "Zarmon" in t else "Leviathan Baltasını fırlat!")
    result = _ceviri("Throw the Leviathan Axe!", None, FREE_GOW, engine)
    assert engine.calls == ["Throw the Zarmon!", "Throw the Leviathan Axe!"]
    assert result == "Leviathan Baltasını fırlat!"


def test_short_line_is_translated_with_its_context():
    engine = Engine(lambda _: "Annen nerede? *** Sen değil.")
    result = _ceviri("Not you.", "Where is your mother?", FREE_GOW, engine)
    assert engine.calls == ["Where is your mother? *** Not you."]
    assert result == "Sen değil."


def test_ambiguous_context_falls_back_to_the_line_alone():
    engine = Engine(lambda t: "Annen nerede, sen değil." if "***" in t else "Sen değil.")
    result = _ceviri("Not you.", "Where is your mother?", FREE_GOW, engine)
    assert engine.calls == ["Where is your mother? *** Not you.", "Not you."]
    assert result == "Sen değil."


def test_context_terms_do_not_leak_into_the_line():
    # Bağlamdaki terimin yer tutucusu satıra kaydıysa ayrım güvenilmez; satır tek başına çevrilir.
    engine = Engine(lambda t: "Burada. *** Git, Zarmon Velkor!" if "***" in t else "Git, Zarmon!")
    assert _ceviri("Go, Atreus!", "Kratos is here.", FREE_GOW, engine) == "Git, Atreus!"


def test_contextual_line_keeps_terms_of_its_own():
    engine = Engine(lambda _: "Zarmon burada. *** Git, Velkor!")
    result = _ceviri("Go, Atreus!", "Kratos is here.", FREE_GOW, engine)
    assert engine.calls == ["Zarmon is here. *** Go, Velkor!"]
    assert result == "Git, Atreus!"


def test_normalize_and_game_english_run_before_protection():
    engine = Engine(lambda _: "Dikkat et, Zarmon!")
    _ceviri("HEADS UP, KRATOS!", None, FREE_GOW, engine,
            normalize=lambda t: "Heads up, kratos!" if t == "HEADS UP, KRATOS!" else t)
    assert engine.calls == ["Watch out, Zarmon!"]


def test_all_caps_line_uses_learned_names_and_capital_words():
    # FreeLineTranslatorTests.testGlossaryTermsGetTheirTurkishAndSuffix: büyük harfli satır önce cümle düzenine gelir.
    glossary = Glossary.parse('{ "game": "God of War", "terms": { "Leviathan Axe": "Leviathan Baltası" }, "keep": ["Kratos"] }')
    engine = Engine(lambda t: "Zarmon, Velkor'u fırlat." if t == "Zarmon, throw the Velkor!" else "?")
    known = glossary.capital_words
    result = _ceviri("KRATOS, THROW THE LEVIATHAN AXE!", None, glossary, engine,
                     normalize=lambda t: bolucu.normalize_case(t, names=known))
    assert result == "Kratos, Leviathan Baltası'nı fırlat!"
    assert engine.calls == ["Zarmon, throw the Velkor!"]


def test_informal_line_gets_informal_imperatives():
    # FreeLineTranslatorTests.testInformalLineGetsInformalImperatives: hitap satırın bütününe bakar.
    def mapping(text):
        return {
            "I told you to wait for me.": "Sana beni beklemeni söyledim.",
            "I told you to wait for me. *** Stay here!": "Sana beni beklemeni söyledim. *** Burada bekleyin!",
        }.get(text, "?")
    engine = Engine(mapping)
    pieces = bolucu.split("I told you to wait for me. Stay here!")
    translations, previous = [], None
    for piece in pieces:
        if not piece.translate:
            translations.append(None)
            continue
        context = previous if _is_short(piece.text) else None
        translations.append(_ceviri(piece.text, context, Glossary.empty(), engine))
        previous = piece.text
    final = son_duzelti.register(translations)
    result = "".join(final[i] if final[i] is not None else p.text for i, p in enumerate(pieces))
    assert result == "Sana beni beklemeni söyledim. Burada bekle!"


# --------------------------------------------------------------------------- GameTermsTests
def _game(sentence, engine):
    return _ceviri(sentence, None, Glossary.built_in(), engine,
                   normalize=lambda t: bolucu.normalize_case(t, names=Glossary.built_in().capital_words))


@pytest.mark.parametrize("english,turkish", [
    ("Toss a smoke!", "Sis bombası at!"),
    ("Reloading!", "Şarjör değiştiriyorum!"),
    ("RELOADING!", "Şarjör değiştiriyorum!"),
    ("Frag out!", "Bomba atıyorum!"),
    ("Cover me, I’m reloading!", "Şarjör değiştiriyorum, koru beni!"),
    ("Man down!", "Yaralı var!"),
    ("Get down!", "Yere yat!"),
    ("Move up.", "İlerleyin."),
    ("- Contact!", "Düşman var!"),
])
def test_callouts_use_their_turkish_line(english, turkish):
    # Ünlem satırları motora gitmeden hazır Türkçesini alır; büyük harf, noktalama ve kıvrık kesme fark etmez.
    engine = Engine(lambda _: "?")
    assert _game(english, engine) == turkish
    assert engine.calls == []


@pytest.mark.parametrize("english,sent,engine_says,turkish", [
    ("Toss a smoke and move up.", "Throw a Zarmon and move up.", "Bir Zarmon at ve ilerle.", "Bir sis bombası at ve ilerle."),
    ("THROW A FLASHBANG IN THERE!", "Throw a Zarmon in there!", "Oraya bir Zarmon at!", "Oraya bir flaş bombası at!"),
    ("Pop smoke, we're leaving.", "Throw a Zarmon, we're leaving.", "Bir Zarmon at, gidiyoruz.", "Bir sis bombası at, gidiyoruz."),
    ("Hostiles on the bridge.", "Enemies on the bridge.", "Köprüde düşmanlar.", "Köprüde düşmanlar."),
    ("Grab the medkit before you go.", "Grab the Zarmon before you go.", "Gitmeden Zarmon'u al.", "Gitmeden ilk yardım çantasını al."),
])
def test_slang_and_weapon_terms_in_longer_lines(english, sent, engine_says, turkish):
    # Uzun cümlede argo düz İngilizceye, silah adı yer tutucuya döner; Türkçe terim ekiyle geri konur.
    engine = Engine(lambda _: engine_says)
    result = _game(english, engine)
    assert engine.calls[0] == sent
    assert result == turkish


@pytest.mark.parametrize("english", ["I smell smoke.", "Turn on your flashlight.", "Where is the grenade launcher?",
                                     "I'm covering you."])
def test_ordinary_sentences_are_unchanged(english):
    # "smoke" tek başına sis bombası değildir, "flashlight" flaş değildir.
    engine = Engine(lambda t: t)
    _game(english, engine)
    assert engine.calls == [english]


def test_user_glossary_can_add_lines_and_phrases():
    user = Glossary.parse('{ "phrases": { "nerf": "weaken" }, "lines": { "GG!": "İyi oyundu" } }')
    merged = Glossary.merge([Glossary.built_in(), user])
    assert merged.line("gg") == "İyi oyundu"
    assert merged.plain("Nerf the boss") == "Weaken the boss"
    assert merged.fingerprint != Glossary.built_in().fingerprint
    assert merged.rewrites("They nerf it.")
    assert not merged.rewrites("Nerfed.")
    # Bozuk düzenli ifade alınmaz.
    assert Glossary.parse('{ "phrases": { "(": "x" } }').plain("( a") == "( a"


def test_rewrites_and_matches_drive_the_cache_key():
    # FreeTranslation.cacheKey sözlüğün izini yalnız bu ikisinden biri doğruysa anahtara koyar.
    glossary = Glossary.built_in()
    assert glossary.rewrites("Reloading!")
    assert glossary.rewrites("Toss a smoke and go.")
    assert not glossary.rewrites("I smell it.") and not glossary.matches("I smell it.")
    assert FREE_GOW.matches("Kratos, go.")
    assert not FREE_GOW.matches("We go.")


def test_line_adds_the_source_ending_when_turkish_has_none():
    glossary = Glossary.parse('{ "lines": { "Go!": "Git", "Stop": "Dur!" } }')
    assert glossary.line("go?!") == "Git?!"
    assert glossary.line("  GO…  ") == "Git…"
    assert glossary.line("stop.") == "Dur!"
    assert line_key("  “Cover me, I’m reloading!” ") == "cover me, i'm reloading"


def test_phrase_keeps_the_capital_of_the_match():
    assert Glossary.built_in().plain("Stay frosty, team. stay frosty.") == "Stay alert, team. stay alert."
    assert re.search("when I give the signal", Glossary.built_in().plain("on my mark"))

