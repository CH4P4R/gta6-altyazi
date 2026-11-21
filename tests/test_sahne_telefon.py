# SPDX-License-Identifier: AGPL-3.0-only
"""altyazi.sahne.telefon: Nino'nun PhonePanelTests.swift dosyasından aktarılan sınamalar.

Gerçek GTA 6 kareleriyle yapılan sınamalar Nino'nun `Tests/CouchSubsCoreTests/Fixtures` klasörünü ister; klasör bu
depoda yoktur, `NINO_FIXTURES` ortam değişkeniyle gösterilirse çalışır (yoksa atlanır). Apple Vision yazı tanıması
gereken sınamalar her zaman atlanır.
"""

import io
import math
import os
import time

import numpy as np
import pytest

from altyazi.sahne import telefon
from altyazi.sahne.ekran import ScreenItem
from altyazi.sahne.metin import Reading, TextBox, TextLine
from altyazi.sahne.telefon import Message, Panel

VISION = "Apple Vision yazı tanıması (VisionReader) gerekiyor; Python tarafında karşılığı yok"


def fixture(name):
    """Nino'nun gerçek karesi (BGR). JPEG'lerin gömülü renk profili (Apple "HDTV") sRGB'ye çevrilir: Swift'te
    CGImage çizilirken macOS aynı dönüşümü yapar ve eşikler buna göre ayarlıdır."""
    folder = os.environ.get("NINO_FIXTURES")
    if not folder:
        pytest.skip("NINO_FIXTURES ayarlı değil: Nino'nun gerçek kare örnekleri (Fixtures/*.jpg) bu depoda yok")
    path = os.path.join(folder, name)
    if not os.path.exists(path):
        pytest.skip(f"{name} yok")
    image_mod = pytest.importorskip("PIL.Image")
    cms = pytest.importorskip("PIL.ImageCms")
    im = image_mod.open(path)
    icc = im.info.get("icc_profile")
    im = im.convert("RGB")
    if icc:
        im = cms.profileToProfile(im, cms.ImageCmsProfile(io.BytesIO(icc)), cms.createProfile("sRGB"), outputMode="RGB")
    return np.ascontiguousarray(np.asarray(im)[:, :, ::-1])


def approx(value, target, accuracy):
    return abs(value - target) <= accuracy


# ---------------------------------------------------------------------------
# PhonePanelTests
# ---------------------------------------------------------------------------


def phone(x, y):
    """240×135 haritada telefonun ekranı: x 139–190, y 27–115 (gerçek karelerdeki yer)."""
    return 139 <= x <= 190 and 27 <= y <= 115


def find(is_white):
    """Beyaz olmayan her nokta koyu (karanlık sahne)."""
    found = telefon.find_map(240, 135, is_white, lambda x, y: not is_white(x, y))
    return found.box if found else None


def panel(left, top, right, bottom):
    return Panel(TextBox(left, top, right, bottom), left, 0, right - left)


def line(text, left, top, right, bottom):
    return TextLine(text, TextBox(left, top, right, bottom))


DEFAULT_PANEL = panel(0.58, 0.197, 0.793, 0.854)


def test_leaning_panel_is_found():
    """Yaya hâlde telefon eğik tutulur (sol kenar 81 satırda 13 nokta sola kayar); yine bulunur."""
    def white(x, y):
        if not 24 <= y <= 105:
            return False
        left = 99 - int(math.floor((y - 24) * 0.16 + 0.5))
        return left <= x <= left + 45

    found = telefon.find_map(240, 135, white, lambda x, y: True)
    assert found is not None
    assert approx(found.lean * 240 / 135, -0.16, 0.03)
    assert approx(found.box.top, 24.0 / 135, 0.01)
    assert approx(found.box.bottom, 106.0 / 135, 0.01)
    assert approx(found.center(found.box.top), (99 + 23) / 240.0, 0.012)
    assert approx(found.center(found.box.bottom), (86 + 23) / 240.0, 0.012)


def test_finds_white_portrait_panel():
    box = find(phone)
    assert box is not None
    assert approx(box.left, 139.0 / 240, 0.01)
    assert approx(box.right, 191.0 / 240, 0.01)
    assert approx(box.top, 27.0 / 135, 0.01)
    assert approx(box.bottom, 116.0 / 135, 0.01)


def test_panel_with_photo_and_bubbles_is_still_found():
    """Sohbetteki fotoğraf ve mavi balonlar bazı satırları böler; ekran yine bulunur."""
    def white(x, y):
        if not phone(x, y):
            return False
        if 40 <= y <= 75 and 144 <= x <= 185:
            return False
        if 95 <= y <= 108 and 160 <= x <= 186:
            return False
        return True

    assert find(white) is not None


def test_panel_without_dark_bezel_is_not_a_phone():
    """Çerçevesi koyu olmayan beyaz dikdörtgen (açık renk duvardaki kapı, pano) telefon değildir."""
    assert telefon.find_map(240, 135, phone, lambda x, y: False) is None


def test_lit_wall_at_the_edge_is_not_a_phone():
    assert find(lambda x, y: 12 <= x <= 65 and 7 <= y <= 88) is None
    assert find(lambda x, y: 100 <= x <= 150 and 0 <= y <= 68) is None


def test_dark_scene_has_no_panel():
    assert find(lambda x, y: False) is None


def test_sky_is_not_a_panel():
    assert find(lambda x, y: y < 70) is None


def test_wide_box_is_not_a_panel():
    """Yatay beyaz kutu (SMS kartı, tabela) telefon değildir."""
    assert find(lambda x, y: 150 <= x <= 220 and 110 <= y <= 134) is None


def test_ragged_blob_is_not_a_panel():
    """Kenarları satırdan satıra oynayan beyaz leke (bulut, duvar) telefon değildir."""
    assert find(lambda x, y: 20 <= y <= 120 and 100 + (y * 7) % 23 <= x <= 150 + (y * 11) % 29) is None


def test_thread_messages_are_grouped_and_labels_skipped():
    reading = Reading([
        line("Kenton", 0.66, 0.22, 0.70, 0.24),
        line("Nuestra Señora del Ocio", 0.63, 0.295, 0.755, 0.315),
        line("Dropped off scuba to yuh boat", 0.60, 0.372, 0.752, 0.394),
        line("man. Happy hunting!", 0.60, 0.398, 0.70, 0.42),
        line("New message", 0.648, 0.503, 0.718, 0.522),
        line("Still can't believe u found them", 0.60, 0.558, 0.753, 0.58),
        line("doubloons. U got that luck boy.", 0.60, 0.582, 0.754, 0.604),
        line("Need u out there on these", 0.60, 0.607, 0.731, 0.629),
        line("wrecks man.", 0.60, 0.632, 0.662, 0.652),
        line("Yeah, I'm on it man.", 0.667, 0.689, 0.766, 0.712),
    ])
    messages = telefon.messages(reading, DEFAULT_PANEL)
    assert [m.text for m in messages] == [
        "Dropped off scuba to yuh boat man. Happy hunting!",
        "Still can't believe u found them doubloons. U got that luck boy. Need u out there on these wrecks man.",
        "Yeah, I'm on it man.",
    ]


def test_thread_has_centered_name_on_top():
    thread = Reading([line("Kenton", 0.653, 0.233, 0.690, 0.248),
                      line("Hey Jason! Was good meeting u", 0.595, 0.351, 0.750, 0.377)])
    assert telefon.is_thread(thread, panel(0.575, 0.215, 0.783, 0.859))


def test_list_is_not_a_thread():
    """Mesaj listesi (en üstte sola yaslı "Suggested" ya da kişi adı) sohbet değildir."""
    lst = Reading([
        line("Suggested", 0.608, 0.230, 0.661, 0.249),
        line("Donnie", 0.635, 0.272, 0.669, 0.285), line("Go get em", 0.635, 0.297, 0.685, 0.313),
        line("Chuck's Gun Shop", 0.634, 0.347, 0.725, 0.367), line("Hey Jason. You good? I saw", 0.634, 0.371, 0.772, 0.391),
    ])
    assert not telefon.is_thread(lst, panel(0.583, 0.207, 0.792, 0.852))


def test_attachment_labels_are_not_messages():
    reading = Reading([
        line("Kenton", 0.653, 0.233, 0.690, 0.248),
        line("Messages encrypted", 0.620, 0.296, 0.734, 0.322),
        line("Map Pin Expired", 0.624, 0.478, 0.707, 0.496),
        line("Here r the spots man. These", 0.595, 0.557, 0.736, 0.576),
        line("wrecks should be a good place", 0.595, 0.581, 0.747, 0.602),
        line("Nuestra Señora de la", 0.626, 0.646, 0.734, 0.665),
        line("Ética Laxa", 0.625, 0.668, 0.681, 0.694),
    ])
    messages = telefon.messages(reading, panel(0.575, 0.215, 0.783, 0.859))
    assert [m.text for m in messages] == ["Here r the spots man. These wrecks should be a good place"]


def test_column_goes_to_the_roomier_side():
    """Telefon sağdaysa (araçta) Türkçeler soluna, ortada ya da soldaysa sağına konur."""
    left = telefon.column(DEFAULT_PANEL)
    assert left.right < DEFAULT_PANEL.box.left
    right = telefon.column(panel(0.39, 0.2, 0.61, 0.85))
    assert right.left > 0.61
    assert right.right <= 0.98


def test_boxes_do_not_overlap():
    messages = [Message("a", TextBox(0.6, 0.40, 0.7, 0.42), 0.022),
                Message("b", TextBox(0.6, 0.43, 0.7, 0.45), 0.022)]
    boxes = telefon.boxes(messages, [3, 1], [0.02, 0.02], (0.2, 0.5))
    assert boxes[1].top >= boxes[0].bottom


def test_probe_real_frames(capsys):
    """Elle: NINO_FRAME klasöründeki gerçek karelerde telefonu arar (yazı tanıma yok)."""
    path = os.environ.get("NINO_FRAME")
    if not path:
        pytest.skip("NINO_FRAME yok")
    cv2 = pytest.importorskip("cv2")
    for name in sorted(f for f in os.listdir(path) if f.endswith(".jpg")):
        image = cv2.imread(os.path.join(path, name))
        if image is None:
            continue
        found = telefon.find(image)
        if found is None:
            print("TELEFON", name, "yok")
            continue
        b = found.box
        print("TELEFON", name, "%.3f %.3f %.3f %.3f eğim %.3f" % (b.left, b.top, b.right, b.bottom, found.lean))


# ---------------------------------------------------------------------------
# Sentetik kareler (Swift'te CGImage ile yapılan bulmanın numpy karşılığı)
# ---------------------------------------------------------------------------


def synthetic_phone(dark_screen=False, size=(1920, 1080), bgra=False):
    """Koyu sahnede siyah çerçeveli dikey telefon (karede x 0.58–0.79, y 0.20–0.86)."""
    w, h = size
    img = np.full((h, w, 3), 25, np.uint8)
    x0, x1, y0, y1 = int(0.58 * w), int(0.79 * w), int(0.20 * h), int(0.86 * h)
    if dark_screen:
        # Koyu temalı uygulama: koyu ekran, açık gövde, beyaz yazı satırları.
        img[y0 - 30:y1 + 30, x0 - 30:x1 + 30] = (200, 200, 200)
        img[y0:y1, x0:x1] = (40, 30, 30)
        for y in range(y0 + 20, y1 - 20, 28):
            img[y:y + 8, x0 + 20:x0 + (x1 - x0) // 2] = (240, 240, 240)
    else:
        img[y0 - 12:y1 + 12, x0 - 12:x1 + 12] = (10, 10, 10)
        img[y0:y1, x0:x1] = (250, 250, 250)
        # Mesaj yazıları (ince koyu çizgiler) ve mavi giden balon.
        for y in range(y0 + 60, y1 - 60, 45):
            img[y:y + 4, x0 + 30:x0 + 200] = (40, 40, 40)
        img[int(0.6 * h):int(0.66 * h), x0 + 150:x1 - 20] = (250, 140, 40)
    if bgra:
        img = np.dstack([img, np.full((h, w), 255, np.uint8)])
    return img


def test_synthetic_white_phone_is_found_in_a_frame():
    found = telefon.find(synthetic_phone())
    assert found is not None
    assert approx(found.box.left, 0.58, 0.01)
    assert approx(found.box.right, 0.79, 0.01)
    assert approx(found.box.top, 0.20, 0.01)
    assert approx(found.box.bottom, 0.86, 0.01)
    assert found.lean == 0


def test_synthetic_bgra_and_small_frames_work():
    assert telefon.find(synthetic_phone(bgra=True)) is not None
    assert telefon.find(synthetic_phone(size=(640, 360))) is not None


def test_synthetic_dark_phone_is_found_but_plain_dark_box_is_not():
    found = telefon.find(synthetic_phone(dark_screen=True))
    assert found is not None
    assert approx((found.box.left + found.box.right) / 2, 0.685, 0.02)
    # Yazısız koyu dikdörtgen (koyu kıyafet) telefon değildir.
    plain = np.full((1080, 1920, 3), 200, np.uint8)
    plain[216:929, 1114:1517] = (40, 30, 30)
    assert telefon.find(plain) is None


def test_synthetic_dimmed_phone_is_found():
    """Kararmış ekran (beyaz ≈70) gece sahnesinde yine bulunur."""
    img = synthetic_phone()
    dim = (img.astype(np.float64) * 0.3).astype(np.uint8)
    assert telefon.find(dim) is not None


def test_empty_or_invalid_frames():
    assert telefon.find(None) is None
    assert telefon.find(np.zeros((0, 0, 3), np.uint8)) is None
    assert telefon.find(np.zeros((1080, 1920, 3), np.uint8)) is None
    assert telefon.sampler(None)(0.5, 0.5) is None


def test_sampler_reads_rgb_and_averages():
    img = np.zeros((540, 960, 3), np.uint8)
    img[:, :480] = (255, 0, 0)    # BGR mavi
    img[:, 480:] = (0, 0, 255)    # BGR kırmızı
    color = telefon.sampler(img)
    assert color(0.25, 0.5) == (0, 0, 255)
    assert color(0.75, 0.5) == (255, 0, 0)
    # Sınırda 3×3 ortalama: üç sütun kırmızı + altı sütun mavi (480'inci sütun ortada).
    assert color(0.5, 0.5) == (255 * 6 // 9, 0, 255 * 3 // 9)
    assert color(0.0, 0.5) is None and color(1.0, 0.5) is None


def test_lifted_sampler_brightens_a_dimmed_light_screen():
    img = (synthetic_phone().astype(np.float64) * 0.6).astype(np.uint8)
    found = telefon.find(img)
    assert found is not None
    plain = telefon.sampler(img)
    lifted = telefon.lifted_sampler(img, found)
    y = 0.30
    x = found.left(y) + found.width * 0.9
    assert plain(x, y)[0] < 160
    assert lifted(x, y)[0] >= 230


def test_find_is_fast_on_1080p(capsys):
    frame = synthetic_phone()
    telefon.find(frame)
    start = time.perf_counter()
    for _ in range(5):
        telefon.find(frame)
    elapsed = (time.perf_counter() - start) / 5 * 1000
    with capsys.disabled():
        print(f"\n    telefon.find 1920x1080: {elapsed:.1f} ms")
    assert elapsed < 500


# ---------------------------------------------------------------------------
# RealPhoneFrameTests (gerçek kareler)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["gta6-telefon-donnie.jpg", "gta6-telefon-kenton.jpg", "gta6-telefon-shirley.jpg",
                                  "gta6-telefon-liste.jpg"])
def test_silver_phone_is_found_in_every_frame(name):
    found = telefon.find(fixture(name))
    assert found is not None, name
    # Telefonun ekranı karede x ≈ 0.59–0.79, y ≈ 0.20–0.82.
    assert approx(found.box.left, 0.59, 0.02), name
    assert approx(found.box.right, 0.79, 0.02), name
    assert approx(found.box.top, 0.20, 0.03), name
    assert approx(found.box.bottom, 0.82, 0.03), name


def test_tilted_phone_cut_by_the_bottom_edge_is_found():
    found = telefon.find(fixture("gta6-telefon-egik-alt.jpg"))
    assert found is not None
    assert approx(found.box.top, 0.58, 0.03)
    assert found.box.bottom > 0.96
    assert approx((found.box.left + found.box.right) / 2, 0.52, 0.03)


# ---------------------------------------------------------------------------
# PhoneCoverTests
# ---------------------------------------------------------------------------

COVER_PANEL = Panel(TextBox(0.59, 0.2, 0.79, 0.81), 0.59, 0, 0.2)


def test_translation_covers_the_bubble_in_its_colour():
    messages = [Message("On my way", TextBox(0.61, 0.5, 0.7, 0.53), 0.02),
                Message("Casa De Donnie", TextBox(0.61, 0.6, 0.7, 0.63), 0.02)]
    # Balonun içi açık gri; yazının üstü koyu (en aydınlık nokta alınır).
    items = telefon.covers(messages, ["Geliyorum", "Casa De Donnie"],
                           color=lambda x, y: (233, 233, 236) if x < 0.6075 else (40, 40, 40))
    assert len(items) == 1, "çevirisi aslıyla aynı olan (ad) örtülmez"
    assert items[0].fill == "#e9e9ec"
    assert items[0].ink == "#2c2c2e"
    assert items[0].box.left < 0.61
    assert items[0].box.right > 0.7
    assert items[0].box.top < 0.5
    assert items[0].box.bottom > 0.53


def test_tilted_phone_tilts_the_covers():
    tilted = Panel(COVER_PANEL.box, 0.6, -0.1, 0.2)
    assert abs(tilted.angle - math.atan(0.1 * 16 / 9) * 180 / math.pi) < 1e-9
    assert tilted.angle > 9
    message = Message("On my way", TextBox(0.61, 0.5, 0.7, 0.53), 0.02)
    items = telefon.covers([message], ["Geliyorum"], angle=tilted.angle, color=lambda x, y: (233, 233, 236))
    assert abs((items[0].angle or 0) - tilted.angle) < 1e-9
    assert abs(COVER_PANEL.angle) < 1e-9


def test_side_bubbles_form_a_chat_panel_beside_the_phone():
    messages = [Message("On my way", TextBox(0.61, 0.5, 0.7, 0.53), 0.02),
                Message("Where at?", TextBox(0.72, 0.6, 0.77, 0.62), 0.02)]
    items = telefon.side_bubbles(messages, ["Geliyorum", "Nerede?"], COVER_PANEL,
                                 color=lambda x, y: (233, 233, 236) if x < 0.7 else (200, 220, 245),
                                 lines=lambda text, w, h: (1, len(text)))
    assert len(items) == 3
    backdrop = items[0]
    assert backdrop.backdrop
    assert abs(backdrop.box.top - COVER_PANEL.box.top) < 1e-9, "telefon boyunda"
    assert abs(backdrop.box.bottom - COVER_PANEL.box.bottom) < 1e-9
    assert backdrop.box.right <= COVER_PANEL.box.left, "telefonun solundaki boşlukta"
    incoming, outgoing = items[1], items[2]
    for item in (incoming, outgoing):
        assert item.side
        assert item.box.left >= backdrop.box.left
        assert item.box.right <= backdrop.box.right
        assert item.angle is None
    assert abs(incoming.box.top - 0.5) <= 0.001, "mesajın hizasında"
    assert incoming.box.left < outgoing.box.left, "gelen solda, giden sağda"
    assert incoming.fill == "#f8f8f9"
    assert outgoing.fill == "#acccfe", "giden mesajın mavi balonu"
    # Uzun giden mesaj telefonun genişliğini kaplar; sohbetin gri balonundan daha mavi olmasından anlaşılır.
    gray = Message("Honestly if they didn't let us", TextBox(0.61, 0.4, 0.77, 0.43), 0.02)
    long = Message("No go. Cal's tryin to avoid that chick", TextBox(0.61, 0.5, 0.77, 0.53), 0.02)
    tinted = telefon.side_bubbles([gray, long], ["Dürüst olmak gerekirse", "Yok, olmaz."], COVER_PANEL,
                                  color=lambda x, y: (137, 154, 183) if y < 0.45 else (120, 150, 215),
                                  lines=lambda text, w, h: (1, len(text)))
    assert abs(tinted[1].box.left - (tinted[0].box.left + 0.012)) < 1e-9, "mavimsi ışıktaki gelen balon solda"
    assert abs(tinted[2].box.right - (tinted[0].box.right - 0.012)) < 1e-9, "belirgin mavi balon sağa yaslı"


def test_covers_follow_the_phone():
    item = ScreenItem("a", "b", TextBox(0.6, 0.5, 0.7, 0.52), 0.02)
    item.fill = "#ffffff"
    moved = telefon.shifted([item], 0.01, -0.02)[0]
    assert abs(moved.box.left - 0.61) < 1e-9
    assert abs(moved.box.top - 0.48) < 1e-9
    assert moved.fill == "#ffffff"
    assert item.box.left == 0.6, "aslı değişmez"


@pytest.mark.skip(reason="RegionCropper.masking (bölgedeki telefonun siyaha boyanması) bu aktarımın kapsamında değil")
def test_phone_area_is_blackened_inside_the_region():
    pass


# ---------------------------------------------------------------------------
# PhoneThreadTitleTests, PhoneAppScreenTests, PhoneWorthShowingTests, PhoneGlossaryTests
# ---------------------------------------------------------------------------


def test_place_name_with_comma_is_a_thread_title():
    reading = Reading([
        TextLine("Fleeca, Laguna Lane", TextBox(0.64, 0.21, 0.74, 0.23)),
        TextLine("Hello Mr. Duval. Please see the", TextBox(0.61, 0.55, 0.76, 0.57)),
    ])
    assert telefon.is_thread(reading, COVER_PANEL)
    assert telefon.title_text(reading, COVER_PANEL) == "Fleeca, Laguna Lane"


def test_app_lines_skip_numbers_and_icons():
    reading = Reading([
        TextLine("$500", TextBox(0.70, 0.33, 0.77, 0.36)),
        TextLine("◆ Checking Account", TextBox(0.61, 0.38, 0.72, 0.40)),
        TextLine("$4,900 to next goal", TextBox(0.64, 0.65, 0.74, 0.67)),
    ])
    lines = telefon.app_lines(reading, COVER_PANEL)
    assert [m.text for m in lines] == ["Checking Account", "$4,900 to next goal"]
    items = telefon.side_bubbles(lines, ["Vadesiz Hesap", "Sonraki hedefe $4.900"], COVER_PANEL, chat=False,
                                 color=lambda x, y: (155, 80, 187) if y < 0.5 else (233, 233, 236),
                                 lines=lambda t, w, h: (1, len(t)))
    assert len(items) == 3
    assert items[1].box.left < items[2].box.left, "içeride başlayan satır panelde de içeride"
    assert items[1].ink == "#f5f5f7", "mor kartın üstünde beyaz yazı"


def test_brand_names_are_not_shown():
    assert not telefon.worth_showing("buckme", "BuckMe mi?")
    assert telefon.worth_showing("Checking Account", "Vadesiz Hesap")


def test_bank_terms_have_fixed_turkish():
    assert telefon.glossary("Checking Account") == "Vadesiz Hesap"
    assert telefon.glossary("Family Savings") == "Aile Birikimi"
    assert telefon.glossary("$4,900 to next goal") == "Sonraki hedefe $4.900"
    assert telefon.glossary("Are you high right now?") is None
    assert telefon.glossary("Book Ryde ($82)") == "Ryde Çağır ($82)"
    assert telefon.glossary("Trip Details") == "Yolculuk Bilgileri"
    assert telefon.glossary("Level 3/4") == "Seviye 3/4"
    assert telefon.glossary("Cardio Workout") == "Kardiyo Antrenmanı"
    assert telefon.glossary("Muscle - High") == "Kas - Yüksek"
    assert telefon.glossary("Body Fat - Low") == "Vücut Yağı - Düşük"
    assert telefon.glossary("Ripped") == "Kaslı"
    assert telefon.glossary("Muscle High") == "Kas - Yüksek"
    assert telefon.is_phone_ui("Body Fat Low")


def test_app_labels_are_not_sentences():
    assert not telefon.is_sentence("Book Ryde ($82)")
    assert not telefon.is_sentence("Righto Cash & Carry")
    assert not telefon.is_sentence("1.74 mi")
    assert telefon.is_sentence("Thx amigo! U find anything else")
    assert telefon.is_sentence("Are you high right now?")
    assert telefon.is_sentence("Dropped off scuba to yuh boat man")


def test_app_bubbles_use_the_app_colour_beside_the_phone():
    lines = [Message("Checking Account", TextBox(0.61, 0.38, 0.72, 0.40), 0.02),
             Message("buckme", TextBox(0.61, 0.28, 0.66, 0.30), 0.02)]
    items = telefon.app_bubbles(lines, ["Vadesiz Hesap", "BuckMe mi?"], COVER_PANEL,
                                lambda x, y: (155, 80, 187) if y < 0.45 else (233, 233, 236))
    assert [i.translation for i in items] == ["Vadesiz Hesap"]
    assert items[0].fill == "#9b50bb", "uygulamanın moru"
    assert items[0].ink == "#ffffff"
    assert items[0].box.right < COVER_PANEL.box.left, "telefonun solunda"
    assert approx((items[0].box.top + items[0].box.bottom) / 2, 0.39, 0.002), "satırın hizasında"


def test_app_bubbles_without_accent_use_background_and_ink():
    """Belirgin rengi olmayan (beyaz haber) uygulamada baloncuk ekranın baskın zemini ve yazı rengiyle çizilir."""
    lines = [Message("Patrons note improvement", TextBox(0.61, 0.38, 0.75, 0.40), 0.02)]

    def color(x, y):
        # Beyaz zemin, satırın ortasında koyu yazı.
        if 0.385 <= y <= 0.395 and 0.62 <= x <= 0.74:
            return (20, 20, 20)
        return (245, 245, 245)

    items = telefon.app_bubbles(lines, ["Müşteriler gelişme kaydetti"], COVER_PANEL, color)
    assert items[0].fill == "#f5f5f5"
    assert items[0].ink == "#0c0c0c"


# ---------------------------------------------------------------------------
# DarkPhoneTests, PhoneMessageListTests, PhoneTrackerTests, PhoneUIWordTests
# ---------------------------------------------------------------------------


def test_dark_themed_app_is_found_but_dark_clothes_are_not():
    found = telefon.find(fixture("gta6-telefon-koyu-rydeme.jpg"))
    assert found is not None
    assert approx((found.box.left + found.box.right) / 2, 0.69, 0.03)
    assert telefon.find(fixture("gta6-menu-kapusonlu.jpg")) is None, "Lucia'nın kapüşonlusu telefon değil"


def test_app_screen_with_title_case_rows_is_not_a_message_list():
    app = Reading([TextLine(t) for t in ["Righto Cash & Carry", "Standard Ryde", "Choose Ryde", "Change Destination"]])
    assert not telefon.is_message_list(app)
    lst = Reading([TextLine(t) for t in ["Donnie", "You got my plane?! You be...", "Brian", "Remember, you get your h..."]])
    assert telefon.is_message_list(lst)


def test_tracker_keeps_the_phone_while_its_body_is_there():
    first = fixture("gta6-telefon-koyu-rydeme.jpg")
    sheet = fixture("gta6-telefon-koyu-altpencere.jpg")
    menu = fixture("gta6-menu-kapusonlu.jpg")
    assert telefon.find(sheet) is None, "alt pencere açıkken baştan bulunamıyor"
    tracker = telefon.Tracker()
    found = tracker.locate(first)
    assert found is not None
    again = tracker.locate(sheet)
    assert again is not None and again.box == found.box, "gövdesinden takip edilir"
    assert tracker.locate(menu) is None, "telefon kalkınca takip biter"
    assert tracker.locate(sheet) is None, "takip bittikten sonra kendiliğinden geri gelmez"


def test_tracker_with_synthetic_frames():
    frame = synthetic_phone(dark_screen=True)
    tracker = telefon.Tracker()
    found = tracker.locate(frame)
    assert found is not None
    # Telefon bulunamayan karede (ekranın üstünde açık bir alt pencere) gövdesi yerinde: takip sürer.
    covered = frame.copy()
    covered[int(0.20 * 1080):int(0.5 * 1080), int(0.58 * 1920):int(0.79 * 1920)] = (40, 30, 30)
    covered[int(0.62 * 1080):int(0.86 * 1080), int(0.58 * 1920):int(0.79 * 1920)] = (40, 30, 30)
    assert telefon.find(covered) is None
    assert tracker.locate(covered) == found
    # Telefon kalkınca takip biter.
    assert tracker.locate(np.full((1080, 1920, 3), 200, np.uint8)) is None
    assert tracker.locate(covered) is None
    # Süre dolunca da biter.
    tracker.locate(frame)
    tracker.max_age = 0
    assert tracker.locate(covered) is None


def test_tracker_adopts_a_guess_from_app_words():
    frame = synthetic_phone(dark_screen=True)
    tracker = telefon.Tracker()
    tracker.adopt([TextBox(0.6, 0.3, 0.7, 0.33), TextBox(0.6, 0.7, 0.75, 0.73)], frame)
    covered = frame.copy()
    covered[int(0.20 * 1080):int(0.86 * 1080), int(0.58 * 1920):int(0.79 * 1920)] = (40, 30, 30)
    located = tracker.locate(covered)
    assert located is not None
    assert located == telefon.guess([TextBox(0.6, 0.3, 0.7, 0.33), TextBox(0.6, 0.7, 0.75, 0.73)])


def test_guess_around_boxes():
    guessed = telefon.guess([TextBox(0.62, 0.3, 0.7, 0.33)])
    assert abs(guessed.box.left - 0.605) < 1e-9
    assert abs(guessed.box.right - 0.815) < 1e-9
    assert guessed.box.top == 0.2 and guessed.box.bottom == 0.82
    assert guessed.lean == 0 and abs(guessed.width - 0.21) < 1e-9


def test_app_words_are_recognised():
    for text in ["Cardio Workout", "Calorie Balance", "You will maintain weight", "I Change Destination",
                 "I Change Destinatior", "Book Ryde ($82)", "Choose Ryde", "Trip Details", "buckme", "Checking Account"]:
        assert telefon.is_phone_ui(text), text
    for text in ["You got this!", "Get to the car", "Change of plans, meet me downtown", "Rydell's house is over there",
                 "I skipped my workout today"]:
        assert not telefon.is_phone_ui(text), text


# ---------------------------------------------------------------------------
# PhoneThreadGlareTests, DimPhoneTests, DarkOnLightTests, PhoneOutgoingTiltTests, DaylightPhoneTests
# ---------------------------------------------------------------------------


def test_chat_with_glare_phone_is_found():
    """Parlamalı karede telefon bulunur (Swift sınamasının görüntü kısmı)."""
    assert telefon.find(fixture("gta6-telefon-brian-parlama.jpg")) is not None


@pytest.mark.skip(reason=VISION)
def test_chat_with_glare_is_still_a_thread():
    pass


def test_dimmed_phone_is_found():
    found = telefon.find(fixture("gta6-telefon-karanlik.jpg"))
    assert found is not None
    assert approx(found.box.left, 0.36, 0.03)
    assert approx(found.box.right, 0.60, 0.03)


def test_dimmed_phone_colors_are_lifted():
    frame = fixture("gta6-telefon-karanlik.jpg")
    found = telefon.find(frame)
    assert found is not None
    color = telefon.lifted_sampler(frame, found)
    # "Dropped that stuff off for you" balonu (mavi).
    blue = color(0.44, 0.46)
    assert blue is not None
    assert blue[2] > blue[0] + 15, blue
    assert blue[2] > 150, blue


def test_rydeme_dark_theme_is_not_lifted():
    frame = fixture("gta6-telefon-koyu-rydeme.jpg")
    found = telefon.find(frame)
    assert found is not None
    lifted, plain = telefon.lifted_sampler(frame, found), telefon.sampler(frame)
    y = (found.box.top + found.box.bottom) / 2
    x = found.left(y) + found.width * 0.5
    assert lifted(x, y)[0] == plain(x, y)[0]


@pytest.mark.skip(reason=VISION)
def test_white_subtitle_is_not_dark_on_light():
    pass


@pytest.mark.skip(reason=VISION)
def test_phone_message_is_dark_on_light():
    pass


def test_dark_on_light_with_synthetic_colours():
    """Swift'teki görüntülü sınamaların yerine: koyu yazı / açık zemin ve beyaz yazı / koyu zemin."""
    box = TextBox(0.4, 0.5, 0.6, 0.53)

    def phone_text(x, y):
        return (30, 30, 30) if int(x * 400) % 4 == 0 else (235, 235, 238)

    def subtitle(x, y):
        return (250, 250, 250) if int(x * 400) % 4 == 0 else (35, 40, 45)

    assert telefon.is_dark_on_light(box, phone_text)
    assert not telefon.is_dark_on_light(box, subtitle)
    assert not telefon.is_dark_on_light(box, lambda x, y: None)


@pytest.mark.skip(reason=VISION)
def test_blue_messages_go_right_on_tilted_phone():
    pass


def test_daylight_phone_is_found():
    """Gündüz telefonun bir yanı güneşli korkuluk (koyu çerçeve görünmüyor); telefon yine bulunur."""
    found = telefon.find(fixture("gta6-telefon-lucia-foto.jpg"))
    assert found is not None
    assert approx((found.box.left + found.box.right) / 2, 0.47, 0.04)


@pytest.mark.skip(reason=VISION)
def test_daylight_phone_with_photo_is_a_thread():
    pass
