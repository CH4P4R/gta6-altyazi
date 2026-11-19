"""Kurulum sihirbazındaki adım adım rehberin görselleri.

    python tools/rehber_gorsel.py

Çıktı: altyazi/ui/rehber/*.png (kuruluma gömülür). Hepsi bu projenin kendi çizimidir; gerçek ekranların
düzenini anlatmak için sadeleştirilmiş benzerleridir (marka logosu ya da başka bir uygulamanın ekran görüntüsü yok).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "altyazi" / "ui" / "rehber"
W, H = 960, 540
BG = (20, 15, 29)
ACC = (255, 92, 138)
ACC2 = (255, 159, 107)
TXT = (235, 232, 242)
MUTED = (150, 145, 165)
FONTS = ["/usr/share/fonts/opentype/inter/", "C:/Windows/Fonts/"]


def font(size: int, weight: str = "Medium"):
    names = {"Bold": ["Inter-Bold.otf", "segoeuib.ttf"], "Medium": ["Inter-Medium.otf", "segoeui.ttf"],
             "Mono": ["JetBrainsMono-Regular.ttf", "consola.ttf"], "Black": ["Inter-ExtraBold.otf", "seguibl.ttf"]}
    for d in FONTS + ["/usr/share/fonts/truetype/jetbrains-mono/"]:
        for n in names[weight]:
            try:
                return ImageFont.truetype(d + n, size)
            except OSError:
                continue
    import glob
    for p in glob.glob("/usr/share/fonts/**/JetBrainsMono-Regular.ttf", recursive=True):
        return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def window(d, box, title, bar=(32, 28, 40), body=(26, 26, 30)):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, 14, fill=body, outline=(60, 54, 74), width=2)
    d.rounded_rectangle([x0, y0, x1, y0 + 34], 14, fill=bar)
    d.rectangle([x0, y0 + 20, x1, y0 + 34], fill=bar)
    for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
        d.ellipse([x1 - 26 - i * 22, y0 + 11, x1 - 14 - i * 22, y0 + 23], fill=c)
    d.text((x0 + 16, y0 + 8), title, font=font(15), fill=MUTED)


def badge(d, xy, n):
    x, y = xy
    d.ellipse([x - 20, y - 20, x + 20, y + 20], fill=ACC, outline=(255, 255, 255), width=3)
    f = font(22, "Black")
    tw = d.textlength(str(n), font=f)
    d.text((x - tw / 2, y - 14), str(n), font=f, fill=(255, 255, 255))


def highlight(d, box, n=None, pad=8):
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], 12, outline=ACC, width=4)
    if n is not None:
        badge(d, (x0 - pad, y0 - pad), n)


def button_(d, box, text, fill=(70, 70, 76), color=(240, 240, 240), size=19):
    d.rounded_rectangle(box, (box[3] - box[1]) // 2, fill=fill)
    f = font(size)
    tw = d.textlength(text, font=f)
    d.text(((box[0] + box[2] - tw) / 2, (box[1] + box[3]) / 2 - size * 0.62), text, font=f, fill=color)


def caption(d, text, y=H - 46):
    f = font(22, "Bold")
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([(W - tw) / 2 - 18, y - 8, (W + tw) / 2 + 18, y + 34], 20, fill=(48, 34, 64))
    d.text(((W - tw) / 2, y - 1), text, font=f, fill=(255, 225, 235))


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, optimize=True)
    print("hazır:", name)


# ---------------------------------------------------------------------------------------------- chiaki
def chiaki_indir():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "github.com/streetpea/chiaki-ng/releases")
    d.text((80, 90), "chiaki-ng  v1.x  (Latest)", font=font(30, "Bold"), fill=TXT)
    d.text((80, 136), "Assets", font=font(22, "Bold"), fill=TXT)
    rows = ["chiaki-ng-macos.dmg", "chiaki-ng-linux.AppImage", "chiaki-ng-windows-installer.exe",
            "chiaki-ng-windows-portable.zip", "Source code (zip)"]
    for i, r in enumerate(rows):
        y = 180 + i * 50
        d.line([(80, y - 8), (880, y - 8)], fill=(50, 46, 60))
        d.text((110, y + 4), "📦" if False else "▢", font=font(20), fill=MUTED)
        d.text((140, y + 2), r, font=font(21), fill=(110, 170, 255) if "windows" in r else MUTED)
    highlight(d, (130, 280, 520, 312), 1)
    caption(d, "Adında “windows” geçen dosyayı indir, çalıştır, kur")
    save(img, "chiaki-indir.png")


def chiaki_ekran(active: str):
    img, d = canvas()
    window(d, (40, 30, 920, 470), "chiaki-ng", bar=(30, 30, 30), body=(30, 30, 33))
    d.rectangle([42, 64, 918, 124], fill=(160, 166, 220))
    d.text((440, 80), "PSN Login", font=font(24, "Bold"), fill=(255, 255, 255))
    d.text((70, 78), "‹", font=font(30, "Bold"), fill=(255, 255, 255))
    d.text((180, 196), "Open Web Browser with copied URL", font=font(20), fill=TXT)
    button_(d, (560, 184, 760, 228), "Click to Re-Copy URL")
    d.text((180, 268), "Redirect URL from Web Browser", font=font(20), fill=TXT)
    d.rounded_rectangle([540, 254, 740, 300], 6, fill=(22, 22, 24), outline=(80, 80, 86), width=2)
    button_(d, (752, 256, 900, 298), "Click to Paste URL", size=16)
    if active == "kopyala":
        highlight(d, (560, 184, 760, 228), 1)
        caption(d, "1. “Click to Re-Copy URL”e bas: giriş adresi kopyalanır")
    else:
        d.text((548, 268), "https://remoteplay.dl.pl…", font=font(15), fill=MUTED)
        highlight(d, (752, 256, 900, 298), 4)
        caption(d, "4. “Click to Paste URL”e bas, sonra sol üstteki ‹ ile geri dön")
    save(img, f"chiaki-{active}.png")


def tarayici_giris():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "Yeni sekme", bar=(40, 40, 46), body=(245, 245, 248))
    d.rounded_rectangle([70, 52, 890, 88], 18, fill=(255, 255, 255), outline=(200, 200, 210), width=2)
    d.text((92, 60), "Ctrl+V  →  Enter", font=font(18, "Bold"), fill=(80, 80, 90))
    highlight(d, (70, 52, 890, 88), 2, pad=6)
    d.rounded_rectangle([300, 130, 660, 420], 16, fill=(255, 255, 255), outline=(220, 220, 228), width=2)
    d.text((372, 150), "Hesabınla oturum aç", font=font(22, "Bold"), fill=(30, 30, 40))
    for i, t in enumerate(("E-posta / Oturum açma kimliği", "Parola")):
        y = 200 + i * 70
        d.text((330, y), t, font=font(15), fill=(110, 110, 120))
        d.rounded_rectangle([330, y + 22, 630, y + 56], 8, fill=(248, 248, 250), outline=(200, 200, 210), width=2)
    button_(d, (330, 350, 630, 394), "Oturum Aç", fill=(0, 112, 209), color=(255, 255, 255))
    caption(d, "2. Tarayıcıya yapıştır ve PlayStation hesabınla giriş yap")
    save(img, "tarayici-giris.png")


def tarayici_adres():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "remoteplay.dl.playstation.net", bar=(40, 40, 46), body=(245, 245, 248))
    d.rounded_rectangle([70, 52, 890, 88], 18, fill=(255, 255, 255), outline=(200, 200, 210), width=2)
    d.text((92, 61), "https://remoteplay.dl.playstation.net/remoteplay/redirect?code=v3.AbC12…",
           font=font(16), fill=(30, 30, 40))
    d.rectangle([90, 58, 760, 84], outline=None)
    highlight(d, (70, 52, 890, 88), 3, pad=6)
    d.text((300, 200), "Bu sayfa boş ya da hatalı görünebilir.", font=font(22, "Bold"), fill=(60, 60, 70))
    d.text((330, 240), "Normal! Lazım olan yukarıdaki adres.", font=font(20), fill=(100, 100, 110))
    for i, k in enumerate(("Ctrl", "A")):
        button_(d, (360 + i * 90, 300, 440 + i * 90, 350), k, fill=(230, 230, 236), color=(30, 30, 40), size=22)
    d.text((545, 310), "sonra", font=font(20), fill=(100, 100, 110))
    for i, k in enumerate(("Ctrl", "C")):
        button_(d, (620 + i * 90, 300, 700 + i * 90, 350), k, fill=(230, 230, 236), color=(30, 30, 40), size=22)
    caption(d, "3. Adres çubuğuna tıkla, adresin tamamını kopyala")
    save(img, "tarayici-adres.png")


def ps5_kod():
    img, d = canvas()
    d.rounded_rectangle([40, 30, 920, 470], 18, fill=(12, 16, 32), outline=(60, 70, 110), width=3)
    path = ["Ayarlar", "Sistem", "Uzaktan Oynatma"]
    x = 80
    for i, p in enumerate(path):
        f = font(22, "Bold" if i == len(path) - 1 else "Medium")
        d.text((x, 62), p, font=f, fill=TXT if i == len(path) - 1 else MUTED)
        x += d.textlength(p, font=f) + 14
        if i < len(path) - 1:
            d.text((x, 62), "›", font=font(22), fill=MUTED)
            x += 26
    items = [("Uzaktan Oynatmayı Etkinleştir", "AÇIK"), ("Cihazı Bağla", "")]
    for i, (t, v) in enumerate(items):
        y = 120 + i * 62
        d.rounded_rectangle([80, y, 880, y + 50], 10, fill=(28, 36, 64) if i == 1 else (20, 26, 48))
        d.text((104, y + 12), t, font=font(22), fill=TXT)
        if v:
            d.text((800, y + 12), v, font=font(20, "Bold"), fill=(120, 220, 140))
    highlight(d, (80, 182, 880, 232), 1, pad=6)
    d.rounded_rectangle([250, 272, 710, 396], 16, fill=(20, 26, 48), outline=(90, 100, 150), width=2)
    d.text((330, 284), "Cihazı bağlamak için bu kodu girin", font=font(18), fill=MUTED)
    d.text((318, 318), "1234 5678", font=font(56, "Black"), fill=(255, 255, 255))
    highlight(d, (300, 312, 660, 384), 2, pad=4)
    caption(d, "PS5'te: Ayarlar › Sistem › Uzaktan Oynatma › Cihazı Bağla")
    save(img, "ps5-kod.png")


def chiaki_kayit():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "chiaki-ng", bar=(30, 30, 30), body=(30, 30, 33))
    d.rounded_rectangle([90, 90, 330, 300], 14, fill=(48, 48, 56), outline=(100, 100, 120), width=2)
    d.rounded_rectangle([150, 130, 270, 210], 10, fill=(230, 230, 236))
    d.text((176, 156), "PS5", font=font(28, "Black"), fill=(30, 30, 40))
    d.text((120, 232), "PS5-123", font=font(20, "Bold"), fill=TXT)
    d.text((120, 262), "kayıtlı değil", font=font(16), fill=MUTED)
    highlight(d, (90, 90, 330, 300), 1)
    d.rounded_rectangle([420, 100, 880, 420], 14, fill=(40, 40, 46), outline=(90, 90, 100), width=2)
    d.text((450, 120), "Register Console", font=font(22, "Bold"), fill=TXT)
    for i, (k, v) in enumerate((("Host", "192.168.1.25"), ("PSN Account ID", "(otomatik)"), ("PIN", "12345678"))):
        y = 170 + i * 66
        d.text((450, y), k, font=font(16), fill=MUTED)
        d.rounded_rectangle([450, y + 22, 850, y + 56], 6, fill=(26, 26, 30), outline=(80, 80, 86), width=2)
        d.text((462, y + 28), v, font=font(18), fill=TXT)
    highlight(d, (450, 324, 850, 358), 2, pad=5)
    button_(d, (700, 372, 850, 410), "Register", fill=(160, 166, 220), color=(20, 20, 30))
    highlight(d, (700, 372, 850, 410), 3, pad=5)
    caption(d, "PS5'e tıkla → PS5'teki 8 haneli kodu PIN'e yaz → Register")
    save(img, "chiaki-kayit.png")


def chiaki_ayar():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "chiaki-ng · Settings", bar=(30, 30, 30), body=(30, 30, 33))
    d.text((90, 80), "Video", font=font(24, "Bold"), fill=TXT)
    rows = [("Resolution", "1080p"), ("FPS", "60"), ("Bitrate", "en yüksek"), ("Codec", "H265 (HEVC)")]
    for i, (k, v) in enumerate(rows):
        y = 130 + i * 66
        d.text((110, y + 10), k, font=font(21), fill=TXT)
        d.rounded_rectangle([520, y, 840, y + 46], 8, fill=(44, 44, 50), outline=(90, 90, 100), width=2)
        d.text((540, y + 10), v, font=font(20, "Bold"), fill=(255, 255, 255))
        if i < 3:
            highlight(d, (520, y, 840, y + 46), None, pad=4)
    caption(d, "Ayarlar: 1080p · 60 fps · bitrate en yüksek")
    save(img, "chiaki-ayar.png")


def kol_usb():
    img, d = canvas()
    # bilgisayar kasası
    d.rounded_rectangle([600, 110, 760, 420], 16, fill=(36, 32, 46), outline=(90, 80, 110), width=3)
    for i in range(3):
        d.ellipse([660, 150 + i * 30, 676, 166 + i * 30], fill=(80, 220, 140) if i == 0 else (70, 64, 86))
    d.rounded_rectangle([640, 300, 720, 316], 4, fill=(20, 18, 26))
    d.text((612, 430), "Bilgisayar", font=font(20, "Bold"), fill=TXT)
    # kol
    d.rounded_rectangle([140, 220, 420, 360], 70, fill=(240, 240, 246))
    d.ellipse([110, 260, 230, 420], fill=(240, 240, 246))
    d.ellipse([330, 260, 450, 420], fill=(240, 240, 246))
    d.ellipse([185, 270, 225, 310], fill=(40, 40, 50))
    d.ellipse([335, 270, 375, 310], fill=(40, 40, 50))
    d.rounded_rectangle([250, 236, 310, 250], 6, fill=(120, 160, 255))
    d.text((180, 430), "Kol (DualSense)", font=font(20, "Bold"), fill=TXT)
    # kablo
    d.line([(280, 222), (280, 170), (520, 170), (520, 308), (640, 308)], fill=ACC2, width=8, joint="curve")
    d.text((380, 130), "USB kablosu", font=font(20, "Bold"), fill=ACC2)
    caption(d, "Kolu USB kablosuyla bilgisayara tak (Bluetooth da olur)")
    save(img, "kol-usb.png")


def chiaki_baglan():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "chiaki-ng", bar=(30, 30, 30), body=(30, 30, 33))
    d.rounded_rectangle([90, 90, 330, 300], 14, fill=(48, 48, 56), outline=(100, 100, 120), width=2)
    d.rounded_rectangle([150, 130, 270, 210], 10, fill=(230, 230, 236))
    d.text((176, 156), "PS5", font=font(28, "Black"), fill=(30, 30, 40))
    d.text((120, 232), "PS5-123", font=font(20, "Bold"), fill=TXT)
    d.text((120, 262), "hazır · kayıtlı", font=font(16), fill=(120, 220, 140))
    highlight(d, (90, 90, 330, 300), 1)
    d.text((420, 150), "PS5'e tıkla:", font=font(26, "Bold"), fill=TXT)
    d.text((420, 196), "PS5'in ekranı bu pencerede açılır.", font=font(21), fill=MUTED)
    d.text((420, 236), "Tam ekran için:", font=font(21), fill=MUTED)
    button_(d, (600, 228, 680, 268), "F11", fill=(230, 230, 236), color=(30, 30, 40), size=20)
    d.text((420, 296), "PS5 kapalıysa chiaki onu uzaktan açar.", font=font(19), fill=MUTED)
    caption(d, "Bağlan: PS5'e tıkla")
    save(img, "chiaki-baglan.png")


# ---------------------------------------------------------------------------------------------- TV
def tv_screen(d):
    d.rounded_rectangle([40, 30, 920, 470], 18, fill=(14, 14, 18), outline=(70, 70, 80), width=3)


def tv_gelistirici():
    img, d = canvas()
    tv_screen(d)
    d.text((80, 62), "Ayarlar  ›  Sistem  ›  Hakkında", font=font(22, "Bold"), fill=TXT)
    rows = ["Cihaz adı", "Ürün modeli", "Android TV OS sürümü", "Android TV OS derlemesi"]
    for i, r in enumerate(rows):
        y = 120 + i * 60
        d.rounded_rectangle([80, y, 880, y + 50], 10, fill=(30, 30, 38) if i == 3 else (22, 22, 28))
        d.text((104, y + 12), r, font=font(21), fill=TXT)
    highlight(d, (80, 300, 880, 350), 1, pad=6)
    d.text((560, 380), "7 kez arka arkaya bas", font=font(26, "Black"), fill=ACC2)
    d.text((560, 418), "“Artık geliştiricisiniz!” yazar", font=font(18), fill=MUTED)
    caption(d, "TV'de: Ayarlar › Sistem › Hakkında")
    save(img, "tv-gelistirici.png")


def tv_hata_ayiklama():
    img, d = canvas()
    tv_screen(d)
    d.text((80, 62), "Ayarlar  ›  Sistem  ›  Geliştirici seçenekleri", font=font(22, "Bold"), fill=TXT)
    rows = [("USB hata ayıklama", True), ("Kablosuz hata ayıklama", False), ("Pencere animasyon ölçeği", None)]
    for i, (r, on) in enumerate(rows):
        y = 130 + i * 70
        d.rounded_rectangle([80, y, 880, y + 54], 10, fill=(22, 22, 28))
        d.text((104, y + 14), r, font=font(22), fill=TXT)
        if on is not None:
            fill = (80, 200, 120) if on else (70, 70, 80)
            d.rounded_rectangle([790, y + 14, 850, y + 40], 13, fill=fill)
            cx = 836 if on else 804
            d.ellipse([cx - 11, y + 16, cx + 11, y + 38], fill=(255, 255, 255))
    highlight(d, (80, 130, 880, 184), 1, pad=6)
    d.text((110, 360), "USB hata ayıklama yoksa ya da TV bulunamazsa:", font=font(19), fill=MUTED)
    d.text((110, 390), "Kablosuz hata ayıklama'yı aç ve eşleştirme kodunu programa yaz.", font=font(19), fill=MUTED)
    caption(d, "USB hata ayıklama'yı aç")
    save(img, "tv-hata-ayiklama.png")


def tv_izin():
    img, d = canvas()
    tv_screen(d)
    d.rounded_rectangle([200, 110, 760, 400], 18, fill=(36, 36, 44), outline=(90, 90, 100), width=2)
    d.text((240, 140), "USB hata ayıklamaya izin verilsin mi?", font=font(23, "Bold"), fill=TXT)
    d.text((240, 186), "Bilgisayarın RSA anahtarı parmak izi:", font=font(17), fill=MUTED)
    d.text((240, 212), "AB:CD:12:34:…", font=font(17), fill=MUTED)
    d.rounded_rectangle([240, 256, 266, 282], 5, fill=ACC)
    d.text((248, 254), "✓", font=font(20, "Bold"), fill=(255, 255, 255))
    d.text((280, 256), "Bu bilgisayardan her zaman izin ver", font=font(19), fill=TXT)
    highlight(d, (240, 256, 640, 282), 1, pad=6)
    button_(d, (420, 320, 560, 364), "İptal", fill=(56, 56, 66))
    button_(d, (580, 320, 720, 364), "İzin ver", fill=ACC, color=(255, 255, 255))
    highlight(d, (580, 320, 720, 364), 2, pad=5)
    caption(d, "Programda Bağlan'a bas → TV'de çıkan soruya İzin ver de")
    save(img, "tv-izin.png")


# ---------------------------------------------------------------------------------------------- diğer rehberler
def lg_devmode():
    img, d = canvas()
    tv_screen(d)
    d.text((80, 62), "Developer Mode", font=font(28, "Bold"), fill=TXT)
    rows = [("Dev Mode Status", True), ("Key Server", True)]
    for i, (r, on) in enumerate(rows):
        y = 120 + i * 70
        d.rounded_rectangle([80, y, 520, y + 54], 10, fill=(22, 22, 28))
        d.text((104, y + 14), r, font=font(22), fill=TXT)
        d.rounded_rectangle([440, y + 14, 500, y + 40], 13, fill=(80, 200, 120))
        d.ellipse([475, y + 16, 497, y + 38], fill=(255, 255, 255))
    highlight(d, (80, 120, 520, 174), 1, pad=6)
    highlight(d, (80, 190, 520, 244), 2, pad=6)
    d.rounded_rectangle([560, 120, 880, 330], 12, fill=(22, 22, 28))
    for i, (k, v) in enumerate((("IP", "192.168.1.40"), ("Passphrase", "A1B2C3"), ("Remain Session", "999:59:59"))):
        d.text((584, 136 + i * 64), k, font=font(16), fill=MUTED)
        d.text((584, 158 + i * 64), v, font=font(24, "Bold"), fill=TXT)
    highlight(d, (576, 132, 864, 254), 3, pad=4)
    caption(d, "Dev Mode Status ve Key Server açık; IP ile Passphrase'i programa yaz")
    save(img, "lg-devmode.png")


def samsung_devmode():
    img, d = canvas()
    tv_screen(d)
    d.text((80, 62), "Uygulamalar", font=font(26, "Bold"), fill=TXT)
    for i, k in enumerate("12345"):
        button_(d, (90 + i * 74, 120, 150 + i * 74, 176), k, fill=(48, 48, 58), size=26)
    highlight(d, (90, 120, 446, 176), 1, pad=6)
    d.rounded_rectangle([480, 110, 880, 410], 14, fill=(36, 36, 44), outline=(90, 90, 100), width=2)
    d.text((510, 128), "Developer mode", font=font(22, "Bold"), fill=TXT)
    d.text((510, 178), "Developer mode", font=font(18), fill=MUTED)
    d.rounded_rectangle([700, 174, 760, 200], 13, fill=(80, 200, 120))
    d.ellipse([735, 176, 757, 198], fill=(255, 255, 255))
    d.text((775, 176), "On", font=font(18, "Bold"), fill=TXT)
    d.text((510, 230), "Host PC IP", font=font(18), fill=MUTED)
    d.rounded_rectangle([510, 256, 850, 296], 8, fill=(26, 26, 30), outline=(80, 80, 86), width=2)
    d.text((524, 264), "192.168.1.25", font=font(20), fill=TXT)
    highlight(d, (510, 256, 850, 296), 2, pad=5)
    button_(d, (720, 336, 850, 380), "OK", fill=(0, 112, 209), color=(255, 255, 255))
    caption(d, "Uygulamalar'da 1-2-3-4-5 → Developer mode On → Host PC IP → OK")
    save(img, "samsung-devmode.png")


def _ribbon(d, active=None):
    """TV ana ekranının alt şeridi."""
    d.rounded_rectangle([60, 380, 900, 450], 12, fill=(30, 30, 38))
    tiles = ["Kaynak", "Uygulamalar", "TV Plus", "Netflix", "YouTube", "Ayarlar"]
    for i, t in enumerate(tiles):
        x = 76 + i * 136
        d.rounded_rectangle([x, 392, x + 124, 438], 8, fill=(52, 52, 64) if t == active else (40, 40, 50))
        tw = d.textlength(t, font=font(16))
        d.text((x + 62 - tw / 2, 404), t, font=font(16), fill=TXT)
    return 76 + tiles.index(active) * 136 if active in tiles else None


def samsung_uygulamalar():
    img, d = canvas()
    tv_screen(d)
    # sol: ana ekran şeridi, Uygulamalar seçili
    x = _ribbon(d, "Uygulamalar")
    highlight(d, (x, 392, x + 124, 438), 1, pad=5)
    d.text((104, 60), "Uygulamalar", font=font(26, "Bold"), fill=TXT)
    d.text((104, 98), "Tam sayfa: uygulamalar büyük kareler halinde", font=font(17), fill=MUTED)
    for r in range(2):
        for c in range(6):
            x0, y0 = 80 + c * 134, 140 + r * 104
            d.rounded_rectangle([x0, y0, x0 + 118, y0 + 88], 12, fill=(40 + c * 6, 36, 58 - c * 3))
    highlight(d, (80, 60, 330, 92), 2, pad=6)
    caption(d, "Ev tuşu → Uygulamalar → OK: bu tam sayfa açılmalı")
    save(img, "samsung-uygulamalar.png")


def _remote(d, x, y, hl_123=True):
    """Rakam tuşu olmayan ince akıllı kumanda (sadeleştirilmiş)."""
    d.rounded_rectangle([x, y, x + 110, y + 400], 50, fill=(44, 44, 50), outline=(80, 80, 90), width=2)
    d.ellipse([x + 45, y + 22, x + 65, y + 42], fill=(200, 60, 60))                 # güç
    d.ellipse([x + 20, y + 70, x + 90, y + 140], fill=(60, 60, 68))                 # yön halkası
    d.ellipse([x + 40, y + 90, x + 70, y + 120], fill=(80, 80, 90))                 # OK
    d.text((x + 46, y + 96), "OK", font=font(13, "Bold"), fill=TXT)
    for i in range(3):
        d.ellipse([x + 8 + i * 34, y + 160, x + 36 + i * 34, y + 188], fill=(60, 60, 68))
    hx, hy = x + 56, y + 174                                                        # ev tuşu simgesi
    d.polygon([(hx - 8, hy - 1), (hx, hy - 8), (hx + 8, hy - 1)], fill=TXT)
    d.rectangle([hx - 6, hy - 1, hx + 6, hy + 7], fill=TXT)
    d.line([(x + 16, y + 174), (x + 28, y + 174)], fill=TXT, width=3)                # geri
    d.polygon([(x + 16, y + 168), (x + 10, y + 174), (x + 16, y + 180)], fill=TXT)
    d.polygon([(x + 84, y + 167), (x + 84, y + 181), (x + 94, y + 174)], fill=TXT)   # oynat
    d.rounded_rectangle([x + 18, y + 210, x + 46, y + 300], 14, fill=(60, 60, 68))   # ses
    d.rounded_rectangle([x + 64, y + 210, x + 92, y + 300], 14, fill=(60, 60, 68))   # kanal
    d.ellipse([x + 35, y + 314, x + 75, y + 354], fill=(70, 70, 82))                # 123 / renk
    for k, c in enumerate(((230, 70, 70), (70, 190, 90), (240, 200, 60), (70, 130, 230))):
        cx, cy = x + 47 + (k % 2) * 16, y + 326 + (k // 2) * 16
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=c)
    if hl_123:
        highlight(d, (x + 35, y + 314, x + 75, y + 354), 1, pad=6)
        d.text((x + 120, y + 318), "123 / renkli", font=font(17, "Bold"), fill=ACC2)
        d.text((x + 120, y + 340), "nokta tuşu", font=font(17, "Bold"), fill=ACC2)


def samsung_123():
    img, d = canvas()
    _remote(d, 40, 60)
    d.rounded_rectangle([300, 40, 930, 470], 18, fill=(14, 14, 18), outline=(70, 70, 80), width=3)
    d.text((330, 64), "Uygulamalar", font=font(24, "Bold"), fill=TXT)
    for r in range(2):
        for c in range(5):
            x0, y0 = 330 + c * 116, 110 + r * 84
            d.rounded_rectangle([x0, y0, x0 + 100, y0 + 70], 10, fill=(40, 36, 54))
    # ekrandaki sanal tuş takımı
    d.rounded_rectangle([330, 300, 900, 450], 14, fill=(36, 36, 44), outline=(90, 90, 100), width=2)
    keys = "1234567890"
    for i, k in enumerate(keys):
        x0 = 346 + i * 55
        d.rounded_rectangle([x0, 320, x0 + 46, 370], 8, fill=(70, 70, 82) if k in "12345" else (52, 52, 62))
        d.text((x0 + 15, 328), k, font=font(26, "Bold"), fill=TXT)
    highlight(d, (346, 320, 392, 370), 2, pad=4)
    d.text((346, 392), "Yön tuşlarıyla rakama gel → OK", font=font(19, "Bold"), fill=ACC2)
    d.text((346, 420), "1 OK · 2 OK · 3 OK · 4 OK · 5 OK", font=font(18), fill=MUTED)
    caption(d, "Rakam tuşu yoksa: 123 tuşu → ekrandaki rakamlar")
    save(img, "samsung-123.png")


def samsung_telefon():
    img, d = canvas()
    # telefon
    d.rounded_rectangle([90, 30, 340, 500], 34, fill=(24, 24, 30), outline=(90, 90, 100), width=3)
    d.text((118, 60), "SmartThings › TV", font=font(17, "Bold"), fill=TXT)
    d.text((118, 86), "Kumanda", font=font(15), fill=MUTED)
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", ""]
    for i, k in enumerate(keys):
        if not k:
            continue
        r, c = divmod(i, 3)
        x0, y0 = 122 + c * 66, 130 + r * 72
        d.ellipse([x0, y0, x0 + 54, y0 + 54], fill=(60, 60, 72) if k in "12345" else (44, 44, 54))
        d.text((x0 + 19, y0 + 11), k, font=font(26, "Bold"), fill=TXT)
    highlight(d, (122, 130, 308, 256), 2, pad=6)
    button_(d, (140, 440, 290, 476), "123", fill=ACC, color=(255, 255, 255), size=18)
    highlight(d, (140, 440, 290, 476), 1, pad=5)
    # TV
    d.rounded_rectangle([420, 90, 920, 400], 16, fill=(14, 14, 18), outline=(70, 70, 80), width=3)
    d.text((450, 112), "Uygulamalar", font=font(22, "Bold"), fill=TXT)
    for c in range(4):
        d.rounded_rectangle([450 + c * 114, 160, 550 + c * 114, 230], 10, fill=(40, 36, 54))
    d.rounded_rectangle([560, 260, 900, 380], 12, fill=(36, 36, 44), outline=(90, 90, 100), width=2)
    d.text((580, 278), "Developer mode", font=font(20, "Bold"), fill=TXT)
    d.text((580, 312), "açılır →", font=font(18), fill=ACC2)
    d.line([(350, 200), (440, 200)], fill=ACC2, width=4)
    d.polygon([(440, 192), (456, 200), (440, 208)], fill=ACC2)
    caption(d, "Telefondan: SmartThings › TV › 123 → 1 2 3 4 5")
    save(img, "samsung-telefon.png")


def samsung_anynet():
    img, d = canvas()
    tv_screen(d)
    d.text((80, 62), "Ayarlar  ›  Genel  ›  Harici Aygıt Yöneticisi", font=font(22, "Bold"), fill=TXT)
    rows = [("Anynet+ (HDMI-CEC)", False), ("Otomatik Kaynak Değiştirme", False), ("Giriş Sinyali Artı", None)]
    for i, (r, on) in enumerate(rows):
        y = 130 + i * 70
        d.rounded_rectangle([80, y, 880, y + 54], 10, fill=(22, 22, 28))
        d.text((104, y + 14), r, font=font(22), fill=TXT)
        if on is not None:
            d.rounded_rectangle([790, y + 14, 850, y + 40], 13, fill=(70, 70, 80))
            d.ellipse([793, y + 16, 815, y + 38], fill=(255, 255, 255))
            d.text((720, y + 15), "Kapalı", font=font(18, "Bold"), fill=MUTED)
    highlight(d, (80, 130, 880, 184), 1, pad=6)
    highlight(d, (80, 200, 880, 254), 2, pad=6)
    d.text((110, 360), "Açık kalırsa PS5 açılınca TV bizim uygulamadan çıkıp HDMI'ya geçer.", font=font(19),
           fill=MUTED)
    caption(d, "Anynet+ ve Otomatik Kaynak Değiştirme: Kapalı")
    save(img, "samsung-anynet.png")


def samsung_hdmi():
    img, d = canvas()
    tv_screen(d)
    d.rounded_rectangle([60, 50, 900, 450], 12, fill=(40, 70, 60))
    d.text((90, 80), "PS5 görüntüsü (uygulamanın içinde)", font=font(20, "Bold"), fill=(220, 240, 230))
    d.rounded_rectangle([250, 360, 710, 420], 10, fill=(10, 10, 12))
    d.text((290, 374), "Arabaya bin, misafirlerimiz var!", font=font(22, "Bold"), fill=TXT)
    d.rounded_rectangle([320, 160, 640, 230], 14, fill=(30, 30, 38), outline=(90, 90, 100), width=2)
    d.text((344, 182), "◀", font=font(26, "Bold"), fill=ACC2)
    d.text((410, 182), "HDMI 2 · PS5", font=font(24, "Bold"), fill=TXT)
    d.text((598, 182), "▶", font=font(26, "Bold"), fill=ACC2)
    highlight(d, (320, 160, 640, 230), 1, pad=6)
    caption(d, "Kumandada ◀ ▶ ile PS5'in HDMI girişini seç")
    save(img, "samsung-hdmi.png")


def lg_store():
    img, d = canvas()
    tv_screen(d)
    d.text((80, 62), "LG Content Store", font=font(26, "Bold"), fill=TXT)
    d.rounded_rectangle([80, 110, 600, 156], 10, fill=(26, 26, 30), outline=(80, 80, 86), width=2)
    d.ellipse([98, 122, 116, 140], outline=TXT, width=3)
    d.line([(113, 137), (122, 146)], fill=TXT, width=3)
    d.text((134, 120), "Developer Mode", font=font(20), fill=TXT)
    highlight(d, (80, 110, 600, 156), 1, pad=5)
    d.rounded_rectangle([80, 190, 300, 380], 14, fill=(40, 36, 54))
    d.text((100, 300), "Developer Mode", font=font(18, "Bold"), fill=TXT)
    d.text((100, 326), "Ücretsiz", font=font(16), fill=MUTED)
    button_(d, (340, 300, 500, 344), "Yükle", fill=ACC, color=(255, 255, 255))
    highlight(d, (340, 300, 500, 344), 2, pad=5)
    caption(d, "Content Store'da Developer Mode'u ara ve yükle")
    save(img, "lg-store.png")


def discord_paylas():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "Discord", bar=(30, 31, 34), body=(49, 51, 56))
    d.rounded_rectangle([200, 90, 760, 420], 14, fill=(43, 45, 49), outline=(70, 72, 78), width=2)
    d.text((230, 108), "Ekran Paylaş", font=font(22, "Bold"), fill=(242, 243, 245))
    for i, (t, act) in enumerate((("Uygulamalar", False), ("Ekranlar", True))):
        x = 230 + i * 170
        d.text((x, 150), t, font=font(18, "Bold"), fill=(242, 243, 245) if act else (148, 155, 164))
        if act:
            d.rectangle([x, 176, x + 90, 180], fill=(88, 101, 242))
    highlight(d, (400, 146, 500, 182), 1, pad=4)
    for i in range(2):
        x = 230 + i * 260
        d.rounded_rectangle([x, 200, x + 240, 335], 8, fill=(30, 31, 34), outline=(88, 101, 242) if i == 0 else None,
                            width=3)
        d.text((x + 12, 344), "Ekran 1 (chiaki)" if i == 0 else "Ekran 2", font=font(16), fill=(242, 243, 245))
    highlight(d, (230, 200, 470, 335), 2, pad=6)
    button_(d, (590, 366, 740, 406), "Yayına Başla", fill=(88, 101, 242), color=(255, 255, 255), size=17)
    highlight(d, (590, 366, 740, 406), 3, pad=5)
    caption(d, "Ekran Paylaş → Ekranlar → chiaki'nin olduğu ekran → Yayına Başla")
    save(img, "discord-paylas.png")


def obs_kaynak():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "OBS Studio", bar=(30, 30, 36), body=(39, 42, 51))
    d.rounded_rectangle([70, 80, 600, 380], 6, fill=(16, 18, 24))
    d.text((90, 96), "Oyun görüntüsü", font=font(18), fill=MUTED)
    d.rounded_rectangle([170, 320, 500, 356], 6, fill=(0, 0, 0))
    d.text((210, 326), "Türkçe altyazı burada", font=font(18, "Bold"), fill=(255, 255, 255))
    d.text((630, 84), "Kaynaklar", font=font(18, "Bold"), fill=TXT)
    for i, (t, hi) in enumerate((("GTA6 Altyazı (Tarayıcı)", True), ("Oyun (Pencere Yakalama)", False))):
        y = 116 + i * 40
        d.rounded_rectangle([630, y, 890, y + 32], 6, fill=(60, 66, 82) if hi else (48, 52, 64))
        d.text((642, y + 6), t, font=font(15), fill=TXT)
    highlight(d, (630, 116, 890, 148), 1, pad=4)
    d.rounded_rectangle([630, 210, 890, 380], 8, fill=(48, 52, 64))
    for i, (k, v) in enumerate((("URL", "http://localhost:8787/obs"), ("Genişlik", "1920"), ("Yükseklik", "1080"))):
        d.text((644, 222 + i * 52), k, font=font(14), fill=MUTED)
        d.text((644, 240 + i * 52), v, font=font(16, "Bold"), fill=TXT)
    highlight(d, (640, 218, 880, 372), 2, pad=4)
    caption(d, "Kaynaklar → + → Tarayıcı → localhost:8787/obs, 1920×1080, en üste")
    save(img, "obs-kaynak.png")


def alan_ayar():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "GTA6 Altyazı · Okuma alanları", bar=(28, 22, 38), body=(20, 15, 29))
    d.rounded_rectangle([70, 76, 890, 430], 8, fill=(48, 26, 70))
    for i in range(10):
        x = 90 + i * 80
        h = 60 + (i * 37) % 130
        d.rectangle([x, 330 - h, x + 60, 330], fill=(30, 16, 46))
    d.rectangle([70, 330, 890, 430], fill=(22, 14, 30))
    d.text((300, 352), "Hurry up, they are right behind us!", font=font(20, "Bold"), fill=(255, 255, 255))
    d.text((390, 388), "Go to the car.", font=font(20, "Bold"), fill=(255, 255, 255))
    d.rounded_rectangle([96, 92, 360, 130], 4, fill=(10, 8, 14))
    d.text((106, 100), "Press E to enter the vehicle.", font=font(15, "Bold"), fill=(240, 240, 240))
    for box, name, col in (((150, 340, 810, 420), "altyazi", ACC), ((84, 84, 380, 170), "yardim", ACC2),
                           ((620, 84, 880, 170), "bildirim", (100, 180, 255))):
        d.rounded_rectangle(box, 6, outline=col, width=3)
        d.rounded_rectangle([box[0], box[1] - 24, box[0] + 90, box[1]], 6, fill=col)
        d.text((box[0] + 8, box[1] - 22), name, font=font(15, "Bold"), fill=(20, 15, 29))
    for (x, y) in ((150, 340), (810, 340), (150, 420), (810, 420)):
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=ACC, outline=(255, 255, 255), width=2)
    caption(d, "Görüntü al → kutuları yazıların üstüne çek → Kaydet")
    save(img, "alan-ayar.png")


def baslat():
    img, d = canvas()
    window(d, (40, 30, 920, 470), "GTA6 Altyazı", bar=(28, 22, 38), body=(20, 15, 29))
    d.rounded_rectangle([90, 100, 870, 300], 18, fill=(30, 24, 42), outline=(60, 50, 80), width=2)
    d.ellipse([130, 130, 270, 270], outline=ACC, width=8)
    d.rounded_rectangle([182, 182, 218, 218], 6, fill=ACC)
    highlight(d, (130, 130, 270, 270), 1, pad=8)
    d.text((310, 150), "Çeviri açık", font=font(34, "Black"), fill=TXT)
    d.text((310, 200), "Oyundaki yazılar okunuyor ve çevriliyor.", font=font(19), fill=MUTED)
    d.text((310, 236), "Ctrl+Shift+9 ekranı çevir · Ctrl+Shift+0 duraklat", font=font(16), fill=MUTED)
    d.rounded_rectangle([90, 320, 870, 420], 14, fill=(30, 24, 42))
    d.text((116, 336), "ALTYAZI", font=font(14, "Bold"), fill=ACC2)
    d.text((116, 360), "Arabaya bin, misafirlerimiz var!", font=font(22, "Bold"), fill=TXT)
    d.text((116, 392), "Get in the car, we got company!", font=font(15), fill=MUTED)
    caption(d, "Ana ekrandaki büyük düğmeye bas: çeviri başlar")
    save(img, "baslat.png")


def main() -> None:
    chiaki_indir()
    chiaki_ekran("kopyala")
    tarayici_giris()
    tarayici_adres()
    chiaki_ekran("yapistir")
    ps5_kod()
    chiaki_kayit()
    chiaki_ayar()
    kol_usb()
    chiaki_baglan()
    tv_gelistirici()
    tv_hata_ayiklama()
    tv_izin()
    lg_devmode()
    samsung_devmode()
    samsung_uygulamalar()
    samsung_123()
    samsung_telefon()
    samsung_anynet()
    samsung_hdmi()
    lg_store()
    discord_paylas()
    obs_kaynak()
    alan_ayar()
    baslat()


if __name__ == "__main__":
    main()
