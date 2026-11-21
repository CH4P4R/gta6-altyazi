# SPDX-License-Identifier: AGPL-3.0-only
"""Nino Game Translator'ın PackFuzzyTests (GamePacksTests.swift) denemelerinden taşındı.

İmza vektörleri Nino'nun Tests/CouchSubsCoreTests/Fixtures/fuzzy-vectors.json dosyasından (Windows sürümü ve paket
betiğiyle ortak). Gerçek paketlerle denemeler için ALTYAZI_NINO_KAYNAK=<nino/core> verilir; yoksa atlanır.
"""

import gzip
import json
import os
from pathlib import Path

import pytest

from altyazi.oyun import paket_bulanik as pf
from altyazi.packs import key

VECTORS = json.loads(r"""
{
 "signatures": [
  {
   "input": "All this will be behind us soon. Until then don’t let any of these bastards get to you, alright?",
   "folded": "aiithiswiiibebehindussoonuntiithendontietanyofthesebastardsgettoyouairight",
   "damaged": false,
   "length": 74,
   "bits": 256,
   "bloom": "20040100b02884106103001004400a9384c02044120131404875a01f28508043"
  },
  {
   "input": "GAETANO: All this will bébehind u soon: Uötil'then don't let any of these båétards getpyou, alrightiz:t",
   "folded": "gaetanoaiithiswiiibebehindusoonuotiithendontietanyofthesebaetardsgetpyouairightizt",
   "damaged": true,
   "length": 82,
   "bits": 256,
   "bloom": "24048100b02884187113001006480a9204902004020131004871a11528508043"
  },
  {
   "input": "Trust me, Iknow this place.",
   "folded": "trustmeiknowthispiace",
   "damaged": false,
   "length": 21,
   "bits": 64,
   "bloom": "012790a2040d8020"
  },
  {
   "input": "Ah, good, Ignaziobhas 't packed up yet.",
   "folded": "ahgoodignaziobhastpackedupyet",
   "damaged": true,
   "length": 29,
   "bits": 128,
   "bloom": "04080008600802490c22420820103006"
  },
  {
   "input": "Who the hell was that?",
   "folded": "whotheheiiwasthat",
   "damaged": false,
   "length": 17,
   "bits": 64,
   "bloom": "8480100845200555"
  },
  {
   "input": "MİNER: Not even close. Shifts are•getting longer.",
   "folded": "minernotevencioseshiftsaregettingionger",
   "damaged": true,
   "length": 39,
   "bits": 128,
   "bloom": "0008224006242208203560006900d901"
  },
  {
   "input": "Caffè, per favore, signora mia.",
   "folded": "caffeperfavoresignoramia",
   "damaged": true,
   "length": 24,
   "bits": 128,
   "bloom": "00400801000001874990002115012800"
  },
  {
   "input": "Ｆｕｌｌ　ｗｉｄｔｈ ｌｉｎｅ ５０ ｃｈａｒｓ",
   "folded": "fuiiwidthiinesochars",
   "damaged": true,
   "length": 20,
   "bits": 64,
   "bloom": "0001c138030a8420"
  },
  {
   "input": "Look at the l1ght 0n the h1ll, my friend!",
   "folded": "iookattheiightonthehiiimyfriend",
   "damaged": true,
   "length": 31,
   "bits": 128,
   "bloom": "00443104c0224040889400850c010014"
  },
  {
   "input": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
   "folded": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
   "damaged": true,
   "length": 255,
   "bits": 256,
   "bloom": "0000000000000000000000000000000000800000000000000000000000000000"
  },
  {
   "input": "short line",
   "folded": "shortiine",
   "damaged": false,
   "length": null,
   "bits": null,
   "bloom": null
  },
  {
   "input": "I see it in his Hels crazy.",
   "folded": "iseeitinhisheiscrazy",
   "damaged": false,
   "length": 20,
   "bits": 64,
   "bloom": "07014d0086280908"
  },
  {
   "input": "Mount youtdi, now!",
   "folded": "mountyoutdinow",
   "damaged": false,
   "length": null,
   "bits": null,
   "bloom": null
  },
  {
   "input": "æsir øre straße œuvre jjjj",
   "folded": "asirorestraseouvreiiii",
   "damaged": true,
   "length": 22,
   "bits": 128,
   "bloom": "8000000a401010420100802420100901"
  }
 ],
 "similarities": [
  {
   "query": "All this will be behind us soon. Until then don’t let any of these bastards get to you, alright?",
   "entry": "GAETANO: All this will bébehind u soon: Uötil'then don't let any of these båétards getpyou, alrightiz:t",
   "bits": 256,
   "similarity": 80.63051702395964
  },
  {
   "query": "All this will be behind us soon. Until then don’t let any of these bastards get to you, alright?",
   "entry": "Who the hell was that?",
   "bits": 64,
   "similarity": 1.3151927437641713
  },
  {
   "query": "Trust me, Iknow this place.",
   "entry": "Trust me, I know this place.",
   "bits": 64,
   "similarity": 100.0
  },
  {
   "query": "MİNER: Not even close. Shifts are•getting longer.",
   "entry": "Not even close. Shifts are getting longer.",
   "bits": 128,
   "similarity": 91.03641456582633
  },
  {
   "query": "Who the hell was that?",
   "entry": "What the hell was that?",
   "bits": 64,
   "similarity": 82.58503401360544
  }
 ]
}
""")


def test_signature_vectors():
    """İmza Windows ve paket betiğiyle bit bit aynı."""
    assert len(VECTORS["signatures"]) > 10
    for v in VECTORS["signatures"]:
        assert pf.folded(v["input"]) == v["folded"], v["input"]
        assert pf.damaged(v["input"]) == v["damaged"], v["input"]
        sig = pf.signature(v["input"])
        assert (sig[0] if sig else None) == v.get("length"), v["input"]
        assert (pf.bits_for_length(sig[0]) if sig else None) == v.get("bits"), v["input"]
        assert (sig[1].hex() if sig else None) == v.get("bloom"), v["input"]
    for p in VECTORS["similarities"]:
        q = pf.bloom(pf.trigram_hashes(pf.folded(p["query"])), p["bits"])
        e = pf.bloom(pf.trigram_hashes(pf.folded(p["entry"])), p["bits"])
        assert pf.similarity(q, e, 0, p["bits"]) == pytest.approx(p["similarity"], abs=1e-9), p["query"]


def test_clauses():
    assert pf.clauses("Mirror Park Errr. Your broke. Call me back, okay? Bye, Dad.") == \
        ["Mirror Park Errr.", "Your broke.", "Call me back,", "okay? Bye, Dad."]
    assert pf.clauses("to escape... if we're able. You said seriously. nis seriously.") == \
        ["to escape...", "if we're able.", "You said seriously. nis seriously."]


def test_variants_cover_common_ocr_slips():
    assert "somebody help me" in pf.variants("Somebody help rne!")
    assert "you can t put a price on freedom" in pf.variants("You cant put a price on freedom.")
    assert pf.variants("short") == []


LOOSE_LABELS = [
    ("-GAETANO: Ah, good", "-GAETANO: ", "Ah, good"),
    ("M]: Any signs of where they went?", "M]: ", "Any signs of where they went?"),
    ("li LUCA: hey there", "li LUCA: ", "hey there"),
    ("\\ tilv„.. CESARE: In fact, I", "\\ tilv„.. CESARE: ", "In fact, I"),
    ("SEBASTIAN Where were you", "SEBASTIAN ", "Where were you"),
    ("O'NEAL Suit yourself.", "O'NEAL ", "Suit yourself."),
    ("I told you: no", None, None),
    ("MİNE GUARD• You skimming?", "MİNE GUARD• ", "You skimming?"),
    ("-, • RUSU: hi there", "-, • RUSU: ", "hi there"),
    ("Get down!", None, None),
    ("OK Thanks", "OK ", "Thanks"),
]


@pytest.mark.parametrize("line,label,body", LOOSE_LABELS)
def test_loose_label_vectors(line, label, body):  # noqa: ANN001
    """Nino: testLooseLabelVectors (fuzzy-vectors.json looseLabels)."""
    found = pf.loose_label(line)
    assert (found[0] if found else None) == label
    assert (found[1] if found else None) == body


def test_overlay_like():
    assert pf.overlay_like("San Andreas")
    assert pf.overlay_like("First Person • zoom")
    assert not pf.overlay_like("Get in the car.")


# ------------------------------------------------------------------------------------------- sentetik paket
LINES = {
    "All this will be behind us soon. Until then don’t let any of these bastards get to you, alright?":
        "Yakında hepsi geride kalacak. O zamana kadar bu herifler canını sıkmasın, tamam mı?",
    "Who the hell was that?": "O da kimdi be?",
    "Somebody help me!": "Biri bana yardım etsin!",
    "I told him to leave it, Trevor.": "Ona boş vermesini söyledim, Trevor.",
    "Not even close. Shifts are getting longer.": "Yaklaşamadın bile. Vardiyalar uzuyor.",
}


def _pack(lines=LINES, fuzzy=True) -> pf.FuzzyPack:  # noqa: ANN001
    entries = {key(en): tr for en, tr in lines.items()}
    texts = {int(key(en), 16): en for en in lines}
    order = sorted(texts)
    data = {"format": 2, "id": "deneme", "title": "Deneme", "entries": entries}
    if fuzzy:
        data["fuzzy"] = pf.build_fuzzy(texts, order)
    return pf.FuzzyPack.from_data(data)


def test_garbled_line_is_found_and_label_kept():
    pack = _pack()
    # "Somebody help me!" 16 harften kısa: imzası yok (tek düzeltmeyle bulunur)
    assert pack.fuzzy is not None and pack.fuzzy.count == len(LINES) - 1
    garbled = "GAETANO: All this will bébehind u soon: Uötil'then don't let any of these båétards getpyou, alrightiz:t"
    assert pack.match(garbled) == "GAETANO: " + LINES[next(iter(LINES))]


def test_single_ocr_correction_is_found_without_fuzzy_index():
    pack = _pack(fuzzy=False)
    assert pack.match("Somebody help rne!") == "Biri bana yardım etsin!"


def test_overlay_line_next_to_subtitle_is_skipped():
    pack = _pack()
    assert pack.match("LOSNN\nI told him to leave it, Trevor.") == "Ona boş vermesini söyledim, Trevor."


def test_unrelated_clean_line_is_not_matched():
    pack = _pack()
    assert pack.match("The quick brown fox jumps over the lazy dog near the river bank.") is None
    assert pack.match("Sauvage gentleman of the western plains") is None


def test_close_rival_with_other_turkish_makes_it_ambiguous():
    lines = {"Not even close. Shifts are getting longer.": "A", "Not even close. Shifts are getting longest.": "B"}
    pack = _pack(lines)
    assert pack.match("Not even clase. Shifts are getting langer!") is None


def test_broken_fuzzy_section_is_ignored():
    data = {"id": "x", "title": "X", "entries": {key("Who the hell was that?"): "O da kimdi be?"},
            "fuzzy": {"version": 1, "count": 99, "mask": "", "lengths": "", "blooms": ""}}
    pack = pf.FuzzyPack.from_data(data)
    assert pack.fuzzy is None
    assert pack.match("Who the hell was that?") == "O da kimdi be?"


def test_load_gzip_file(tmp_path: Path):
    entries = {key(en): tr for en, tr in LINES.items()}
    f = tmp_path / "deneme.json.gz"
    f.write_bytes(gzip.compress(json.dumps({"id": "deneme", "title": "Deneme", "entries": entries}).encode()))
    pack = pf.FuzzyPack.load(f)
    assert pack.id == "deneme" and pack.exact("Who the hell was that?") == "O da kimdi be?"


# ------------------------------------------------------------------------------------------- gerçek paketler
NINO = os.environ.get("ALTYAZI_NINO_KAYNAK")
needs_nino = pytest.mark.skipif(not NINO, reason="ALTYAZI_NINO_KAYNAK verilmedi")


def _real(name: str) -> pf.FuzzyPack:
    return pf.FuzzyPack.load(Path(NINO) / "Sources/CouchSubsCore/Resources/packs" / name)


@needs_nino
def test_gta_ocr_reads_are_found():
    """GTA V oyuncularının gerçek ıskalamaları (Nino: testGtaOcrReadsAreFound)."""
    pack = _real("gta-v.json.gz")
    for screen, line in [
        ("Somebody help rne!", "Somebody help me!"),
        ("Yeah, well, well see.", "Yeah, well, we'll see."),
        ("You cant put a price on freedom.", "You can't put a price on freedom."),
        ("LOSNN\nI told him to leave it, Trevor.", "I told him to leave it, Trevor."),
        ("I can't do crap with this deathship right",
         "I can't do crap with this deathship right on top of me! Bring it down, T!"),
        ("San Andreas LOSNN but it does mean he's got money to pay people who help him.",
         "but it does mean he's got money to pay people who help him."),
    ]:
        expected = pack.match(line)
        assert expected is not None, line
        assert pack.match(screen) == expected, screen
    assert pack.match("The quick brown fox jumps over the lazy dog near the river bank.") is None
    assert pack.match("Sauvage gentleman of the western plains") is None
    assert pack.match("Your vehicle? Sorry, we can't get that sorted at this time. San Andreas")
    assert pack.match("Vinewood Hills Just not my junk, okay? I'm already scarred down there.")


@needs_nino
def test_two_subtitles_read_as_one_line_are_not_half_translated():
    pack = _real("gta-v.json.gz")
    for first, second in [("Hey, look. Good shit on those contracts you been workin' on.",
                           "But listen, I got some other work."),
                          ("I'm calling it. Don't burn your eyes out.", "Bye, Dad.")]:
        alone = pack.match(first)
        assert alone
        assert pack.match(f"{first} {second}") != alone


@needs_nino
def test_real_mafia_misses_match_like_the_pack_script():
    """Nino'nun pack-matches.json ıskalamaları (Mafia: The Old Country)."""
    cases = json.loads((Path(NINO) / "Tests/CouchSubsCoreTests/Fixtures/pack-matches.json").read_text("utf-8"))
    pack = _real("mafia-the-old-country.json.gz")
    misses = [c["screen"] for c in cases["cases"] if pack.match(c["screen"]) != c.get("turkish")]
    assert len(cases["cases"]) >= 50
    assert misses == []


def test_speaker_label():
    assert pf.speaker_label("ATREUS: Father!") == "ATREUS: "
    assert pf.speaker_label("Mimir Head: Brother.") == "Mimir Head: "
    assert pf.speaker_label("MİNER: Federico") == "MİNER: "
    assert pf.speaker_label("Note: this is a tip") is None
    assert pf.speaker_label("I told you: no") is None
    assert pf.speaker_lead("- ENZO: Che buono.") == ("- ENZO: ", "Che buono.")


def test_exact_sentences_win_over_a_fuzzy_whole_line():
    """Önce yalnız tam anahtar (tüm satır, satır satır, cümle cümle); bulanık arama sonra."""
    lines = {"Signor Torrisi is a generous man.": "Signor Torrisi cömert bir adamdır.",
             "I'm glad he's opened his arms to you.": "Sana kucak açmasına sevindim."}
    pack = _pack(lines)
    assert pack.match("FATHER CICCONE: Signor Torrisi is a generous man. I'm glad he's opened his arms to you.") == \
        "FATHER CICCONE: Signor Torrisi cömert bir adamdır. Sana kucak açmasına sevindim."
