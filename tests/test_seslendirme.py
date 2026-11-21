"""Türkçe seslendirme: konuşan adı, ses seçimi, okunacak metin, yeni satırda kesme ve yedek ses."""

import threading
import time

from altyazi import seslendirme as s


def test_split_speaker_and_gender():
    assert s.split_speaker("LUCIA: Hadi gidelim!") == ("LUCIA", "Hadi gidelim!")
    assert s.split_speaker("Jason：Tamam.") == ("Jason", "Tamam.")
    assert s.split_speaker("Saat 12:30'da buluşalım.") == (None, "Saat 12:30'da buluşalım.")
    assert s.gender_of("LUCIA") == "kadin" and s.gender_of("Jason") == "erkek" and s.gender_of(None) == "erkek"


def test_speakable_drops_icons_and_emoji():
    assert s.speakable("Binmek için △ tuşuna bas 😀\nhadi…") == "Binmek için tuşuna bas hadi."


def test_new_line_interrupts_and_falls_back(monkeypatch):
    spoken, started = [], threading.Event()
    sp = s.Speaker(enabled=True)

    def edge(self, body, gender):  # noqa: ANN001
        raise OSError("internet yok")

    def system(self, body, gender):  # noqa: ANN001
        spoken.append((body, gender))
        started.set()

    monkeypatch.setattr(s.Speaker, "_speak_edge", edge)
    monkeypatch.setattr(s.Speaker, "_speak_system", system)
    sp.say("LUCIA: Bekle beni.")
    assert started.wait(3)
    assert spoken[0] == ("Bekle beni.", "kadin")
    assert sp._edge_ok is False                    # doğal ses kullanılamayınca bilgisayarın sesine geçildi
    sp.say("LUCIA: Bekle beni.")                   # aynı satır ikinci kez okunmaz
    time.sleep(0.2)
    assert len(spoken) == 1
    sp.close()
