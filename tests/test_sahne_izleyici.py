"""Ekran yazıları izleyicisi uçtan uca: yapay telefon karesi + sahte okuyucu/çevirmen → TV'ye giden Türkçeler."""

import numpy as np

from altyazi.sahne import izleyici, telefon
from tests.test_sahne_harita import map_reading
from tests.test_sahne_telefon import synthetic_phone

THREAD = [("Donnie", 0.665, 0.225, 0.705, 0.245),
          ("BUT dropoff is to me NOT Brian", 0.600, 0.372, 0.752, 0.394),
          ("TO MY TRAILER! Comprendo?", 0.600, 0.430, 0.740, 0.452),
          ("Dropped that stuff off for you", 0.640, 0.520, 0.775, 0.542)]


class Fake:
    """read_lines: verilen görüntünün boyutuna göre satırları piksel koordinatında döndürür."""

    def __init__(self):
        self.mode = "phone"
        self.panel = None
        self.asked = []
        self.sent = []

    def read_lines(self, img):
        h, w = img.shape[:2]
        if self.mode == "phone":
            b = self.panel.box
            out = []
            for text, l, t, r, bt in THREAD:
                x0, y0 = (l - b.left) / (b.right - b.left), (t - b.top) / (b.bottom - b.top)
                x1, y1 = (r - b.left) / (b.right - b.left), (bt - b.top) / (b.bottom - b.top)
                out.append((text, (x0 * w, y0 * h, x1 * w, y1 * h)))
            return out
        lines = map_reading().lines if self.mode == "map" else []
        return [(ln.text, (ln.box.left * w, ln.box.top * h, ln.box.right * w, ln.box.bottom * h)) for ln in lines]

    def translate(self, text, kind, context):
        self.asked.append((text, kind, list(context)))
        return {"BUT dropoff is to me NOT Brian": "Ama teslimat bana, Brian'a DEĞİL",
                "TO MY TRAILER! Comprendo?": "KARAVANIMA! Anladın mı?",
                "Dropped that stuff off for you": "O şeyleri senin için bıraktım"}.get(text, "TR " + text)


def make(fake):
    return izleyici.SceneWatcher(fake.read_lines, fake.translate, lambda items: fake.sent.append(list(items)))


def test_phone_thread_becomes_side_bubbles_with_context():
    frame = synthetic_phone()
    fake = Fake()
    fake.panel = telefon.find(frame)
    assert fake.panel is not None
    w = make(fake)
    assert w.phone_mode == "yan"       # varsayılan: telefonun yanında mesaj paneli (Nino)
    w._watch_phone(frame)              # ilk okuma: bekletilir (kaydırma bitsin)
    assert not w.phone_items
    w._watch_phone(frame)              # aynı okuma ikinci kez: çevrilir
    texts = [it.translation for it in w.phone_items if not it.backdrop]
    assert "KARAVANIMA! Anladın mı?" in texts and len(texts) == 3
    assert any(it.backdrop for it in w.phone_items)          # telefonun yanındaki panel
    kinds = {k for _, k, _ in fake.asked}
    assert kinds == {"mesaj"}
    ctx = dict((t, c) for t, _, c in fake.asked)
    assert ctx["TO MY TRAILER! Comprendo?"] == [("BUT dropoff is to me NOT Brian", "")]   # önceki mesaj bağlam
    js = fake.sent[-1][0].to_json()
    assert "box" in js and "text" in js
    # telefondaki yazı altyazı sayılmaz
    assert w.is_phone_text("TO MY TRAILER! Comprendo?") and w.phone_box() is not None
    n = len(fake.asked)
    w._watch_phone(frame)              # aynı ekran: yeniden çevrilmez
    assert len(fake.asked) == n


def test_map_card_is_translated_below_card():
    fake = Fake()
    fake.mode = "map"
    w = make(fake)
    frame = np.full((1080, 1920, 3), 60, np.uint8)
    w._watch_screen(frame)
    assert len(w.map_items) == 1
    card = w.map_items[0]
    assert card.card and card.translation.splitlines()[0] == "TR BUY FLOWERS".upper().replace("I", "İ") \
        or card.translation.splitlines()[0].startswith("TR ")
    assert card.box.top >= 0.55 or card.box.bottom <= 0.43           # kartın altında ya da üstünde, üstüne binmez
    assert w.now() < w.map_seen_until
    fake.mode = "empty"                                               # harita kapandı: iki okumada kalkar
    w._watch_screen(frame)
    w._watch_screen(frame)
    assert not w.map_items


def test_message_card_needs_two_readings_and_goes_above():
    from altyazi.sahne.metin import Reading, TextBox, TextLine
    fake = Fake()
    w = make(fake)
    card = Reading([TextLine("Donnie", TextBox(0.70, 0.78, 0.75, 0.80)),
                    TextLine("Bring me the package tonight", TextBox(0.70, 0.81, 0.90, 0.835))])
    w._message(card)
    assert not w.message_items
    w._message(card)
    assert w.message_items and w.message_items[0].plain
    it = w.message_items[0]
    assert it.translation.splitlines()[0] == "Donnie" and it.box.bottom <= 0.78


def test_phone_translation_on_the_bubbles_when_chosen():
    """Ayar 'üstünde': Türkçe her mesaj balonunun tam üstünde, balonun renginde, panel yok."""
    frame = synthetic_phone()
    fake = Fake()
    fake.panel = telefon.find(frame)
    w = make(fake)
    w.phone_mode = "ust"
    w._watch_phone(frame)
    w._watch_phone(frame)
    items = w.phone_items
    assert items and not any(it.backdrop for it in items)
    b = fake.panel.box
    by_src = {it.source: it for it in items}
    it = by_src["TO MY TRAILER! Comprendo?"]
    assert it.translation == "KARAVANIMA! Anladın mı?" and it.fill
    # balonun yerinde: mesaj kutusunun ortası Türkçe kutunun içinde
    text, l, t, r, bt = THREAD[2]
    cx, cy = (l + r) / 2, (t + bt) / 2
    assert it.box.left <= cx <= it.box.right and it.box.top <= cy <= it.box.bottom
    assert b.left <= it.box.left and it.box.right <= b.right + 0.02
