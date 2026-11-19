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


if __name__ == "__main__":
    main()
