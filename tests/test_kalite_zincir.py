"""Yerel çeviri kalite zinciri (Nino FreeTranslation) ve çevirmene bağlanışı."""

import types

from altyazi.kalite.yerel_cevirmen import QualityLocal, after_separator


class Echo:
    """Sahte OPUS-MT: aldığı metni kaydeder, basit bir 'çeviri' döndürür."""

    def __init__(self):
        self.seen = []

    def __call__(self, text):
        self.seen.append(text)
        if " *** " in text:
            a, b = text.split(" *** ", 1)
            return f"TR({a}) *** TR({b})"
        return f"TR({text})"


def test_speaker_label_is_not_sent_and_kept():
    eng = Echo()
    q = QualityLocal.build(eng, {}, ["Lucia", "Jason"])
    out = q.translate("LUCIA: We have to go now.")
    assert out.startswith("LUCIA:") and all("LUCIA" not in s for s in eng.seen)


def test_short_line_uses_previous_sentence_as_context():
    eng = Echo()
    q = QualityLocal.build(eng, {}, [])
    q.translate("Where is the money?")
    q.translate("Right here.")
    assert "Where is the money? *** Right here." in eng.seen


def test_protected_term_survives_with_suffix():
    seen = []

    def eng(text):
        seen.append(text)
        return text.replace("Get in", "Bin").replace("the car", "arabaya")   # yer tutucu adı aynen kalır
    q = QualityLocal.build(eng, {"Vice City": "Vice City"}, ["Vice City"])
    out = q.translate("Get in the car in Vice City.")
    assert out == "Bin arabaya in Vice City." and "Vice City" not in seen[0]      # motor uydurma adı gördü


def test_after_separator_rules():
    assert after_separator("Önce *** Sonra geldi", "Then came") == "Sonra geldi"
    assert after_separator("Önce *** Sonra *** fazla", "x") is None
    assert after_separator("*** yalnız", "x") is None


def test_engine_uses_chain_and_drops_ai_echo():
    from altyazi.translate import TranslationEngine
    eng = TranslationEngine.__new__(TranslationEngine)
    eng.local_chain = types.SimpleNamespace(translate=lambda t: "zincir")
    assert eng._local_quality("Hello") == "zincir"

    class Refine:
        name = "claude"

        def translate(self, text, kind, ctx):
            return {"We need to leave right now.": "We need to leave right now!",
                    "Get in the car.": "Arabaya bin."}[text]
    eng.refine = Refine()
    assert eng._refine_text("We need to leave right now.", "altyazi", []) is None      # yankı
    assert eng._refine_text("JASON: Get in the car.", "altyazi", []) == "JASON: Arabaya bin."
