"""Bütün kurulum ve kullanım süreçlerinin tek kaynağı.

Aynı metin ve görseller üç yerde kullanılır: kurulum sihirbazı, uygulamadaki Rehber sayfası ve GitHub README'si
(tools/readme_rehber.py üretir). Bir adımı değiştirmek için yalnız bu dosyayı düzenle.

Metin biçimi: her adımın 'items' listesi sırayla yapılacakları tutar; **kalın** yazılabilir. 'note' adımın altına
soluk renkle yazılır. 'img' altyazi/ui/rehber/ içindeki görselin adıdır (uzantısız). 'id', sihirbazın adıma düğme
ya da durum satırı eklemesi içindir. 'link' = (düğme yazısı, adres).
"""

from __future__ import annotations

import re

CHIAKI_DOWNLOAD = "https://github.com/streetpea/chiaki-ng/releases"
PSN_SIGNUP = "https://www.playstation.com/tr-tr/playstation-network/"
CLAUDE_KEYS = "https://console.anthropic.com/settings/keys"
GEMINI_KEYS = "https://aistudio.google.com/apikey"
DEEPL_SIGNUP = "https://www.deepl.com/pro-api"
OLLAMA_DOWNLOAD = "https://ollama.com/download"
NUMS = "①②③④⑤⑥⑦⑧⑨"


def step(title: str, items: list[str], img: str | None = None, note: str = "", sid: str = "",
         link: tuple[str, str] | None = None) -> dict:
    return {"title": title, "items": items, "img": img, "note": note, "id": sid, "link": link}


# ---------------------------------------------------------------------------------------------- PS5 + chiaki-ng
def chiaki_steps(where: str = "monitor") -> list[dict]:
    """chiaki-ng kurulumu. where: monitor (kasada oynar) | tv (TV'de oynar, kasa izler) | ikisi."""
    account = {"monitor": "**Kendi PlayStation hesabınla** giriş yap (oyunların ve kayıtların o hesapta).",
               "tv": "**İkinci PSN hesabınla** giriş yap. Kendi hesabınla girersen TV'de oynarken kolun kopar.",
               "ikisi": "Bugün nerede oynayacaksan o hesapla gir: **monitörde kendi hesabın**, **TV'de ikinci "
                        "hesap**. Diğerini sonra aynı adımlarla eklersin."}[where]
    steps: list[dict] = []
    if where in ("tv", "ikisi"):
        steps.append(step(
            "İkinci PSN hesabı aç (ücretsiz)",
            ["Ücretsiz yeni bir PlayStation hesabı aç.",
             "PS5'i aç ve bu yeni hesapla **bir kez** oturum aç."],
            note="TV'de oynarken bilgisayar PS5'i ikinci bir hesapla izler; kendi hesabınla bağlanırsa TV'deki kolun "
                 "kopar." + (" Sadece monitörde oynayacaksan bu adımı geçebilirsin." if where == "ikisi" else ""),
            sid="psn", link=("PSN hesabı aç", PSN_SIGNUP)))
    steps += [
        step("chiaki-ng'yi indir ve kur",
             ["**İndirme sayfasını aç**'a bas.",
              "En üstteki sürümün **Assets** listesinde adında **windows** geçen dosyayı indir.",
              "İndirdiğin dosyayı çalıştırıp kur."],
             img="chiaki-indir", note="chiaki-ng, PS5'in görüntüsünü ağ üzerinden bilgisayara getiren ücretsiz programdır.",
             sid="indir", link=("İndirme sayfasını aç", CHIAKI_DOWNLOAD)),
        step("chiaki-ng'de PSN girişi",
             ["chiaki-ng'yi aç. PS5 eklemek için hesabını ister: **PSN Login** ekranı açılır.",
              "**Click to Re-Copy URL**'ye bas. Sony'nin giriş adresi kopyalanır."],
             img="chiaki-kopyala"),
        step("Tarayıcıda giriş yap",
             ["Chrome ya da Edge'i aç, adres çubuğuna tıkla, **Ctrl+V** yap ve **Enter**'a bas.",
              f"Açılan PlayStation sayfasında {account}"],
             img="tarayici-giris"),
        step("Açılan sayfanın adresini kopyala",
             ["Giriş bitince boş ya da hatalı görünen bir sayfa açılır. **Bu normal.**",
              "Adres çubuğuna tıkla (adres *remoteplay.dl.playstation.net/…redirect?code=* ile başlar).",
              "**Ctrl+A**, sonra **Ctrl+C** yap."],
             img="tarayici-adres", note="Bu kod birkaç dakika geçerli, hızlı ol."),
        step("chiaki-ng'ye yapıştır",
             ["chiaki-ng'ye dön, **Click to Paste URL**'ye bas.",
              "Hesap bilgisi alınır; sol üstteki **‹** ile ana ekrana dön."],
             img="chiaki-yapistir", note="Hata verirse kodun süresi dolmuştur: PSN girişi adımından tekrarla."),
        step("PS5'te bağlantı kodunu al",
             ["PS5'te chiaki'ye girdiğin hesapla oturum açıkken **Ayarlar › Sistem › Uzaktan Oynatma**: "
              "**Uzaktan Oynatmayı Etkinleştir** açık olsun.",
              "**Cihazı Bağla**'ya bas; 8 haneli bir kod çıkar (ekranda bırak).",
              "**Ayarlar › Sistem › Güç Tasarrufu › Dinlenme Modunda Kullanılabilir Özellikler**: **İnternete Bağlı "
              "Kal** ve **Ağ Üzerinden PS5'i Açmayı Etkinleştir**'i aç."],
             img="ps5-kod",
             note="TV'de oynayacaksan Uzaktan Oynatma ayarlarındaki bağlantı durumu açılır penceresini gizle; yoksa "
                  "chiaki bağlanınca TV ekranında \"bağlandı\" yazısı çıkar."),
        step("PS5'i chiaki-ng'ye kaydet",
             ["chiaki-ng ana ekranında PS5'in kutusuna tıkla.",
              "**PIN** kutusuna PS5'teki 8 haneli kodu yaz.",
              "**Register**'a bas."],
             img="chiaki-kayit",
             note="PS5 görünmüyorsa PS5 ve bilgisayar aynı modeme bağlı mı bak; sağ üstteki + ile IP'siyle de eklenir."),
        step("Görüntü ayarları (bir kere)",
             ["chiaki-ng ayarlarında (dişli simgesi) **Video** bölümüne gir.",
              "**Resolution: 1080p**, **FPS: 60** seç.",
              "**Bitrate**'i en yükseğe al."],
             img="chiaki-ayar", note="Yazıların net okunması için bu önemli."),
    ]
    if where in ("monitor", "ikisi"):
        steps.append(step("Kolu bilgisayara bağla",
                          ["DualSense'i **USB kablosuyla** bilgisayara tak (titreşim de çalışır). Bluetooth da olur."],
                          img="kol-usb",
                          note="TV günlerinde kolu yine PS5'e bağlarsın." if where == "ikisi" else ""))
    last = {"monitor": ["chiaki-ng'de PS5'in kutusuna tıkla; PS5'in ekranı açılır, kolla oynarsın.",
                        "İstersen **F11** ile tam ekran yap."],
            "tv": ["chiaki-ng'de PS5'in kutusuna tıkla. Sen TV'den oynamaya devam et; chiaki açık kalsın.",
                   "chiaki penceresini **simge durumuna küçültme**, program görüntüyü oradan okuyor."],
            "ikisi": ["chiaki-ng'de PS5'in kutusuna tıkla.",
                      "Monitörde oynuyorsan **F11** ile tam ekran yap; TV'de oynuyorsan chiaki açık kalsın, küçültme."]}
    steps.append(step("Bağlan", last[where], img="chiaki-baglan", sid="baglan"))
    return steps


START_STEP = step("Türkçeyi aç",
                  ["**GTA6 Altyazı**'yı aç.",
                   "Ana ekrandaki büyük düğmeye (**Başlat**) bas.",
                   "Oyunda İngilizce altyazıyı aç; yazılar Türkçe görünür."],
                  img="baslat",
                  note="Kısayollar: Ctrl+Shift+9 ekranın tamamını çevirir, Ctrl+Shift+0 duraklatır.")

# ---------------------------------------------------------------------------------------------- TV'ler
GOOGLE_TV = [
    step("TV'de geliştirici seçeneklerini aç",
         ["TV kumandasıyla **Ayarlar › Sistem › Hakkında**'ya gir.",
          "**Android TV OS derlemesi** satırına gel ve **OK**'a arka arkaya **7 kez** bas. \"Artık geliştiricisiniz\" "
          "yazar."],
         img="tv-gelistirici",
         note="TCL'de menü adları biraz farklı olabilir: Ayarlar › Sistem › Hakkında › Derleme / Yapı numarası."),
    step("USB hata ayıklamayı aç",
         ["**Ayarlar › Sistem › Geliştirici seçenekleri**'ne gir.",
          "**USB hata ayıklama**'yı aç (düz olanı; Kablosuz hata ayıklama gerekmez).",
          "Eşleştirme kodu da gerekmez: program TV'ye ağdan doğrudan bağlanır."],
         img="tv-hata-ayiklama",
         note="Yalnız TV'de USB hata ayıklama hiç yoksa: Kablosuz hata ayıklama › 'Eşleştirme koduyla cihaz eşleştir'; "
              "açılan küçük penceredeki adres:port ve kodu programdaki Gelişmiş › Eşleştir kısmına yaz."),
    step("Bağlan ve izin ver",
         ["Programda **Ağda ara**'ya bas ve listeden TV'yi seç. Bulamazsa TV'nin IP'sini elle yaz: TV'de "
          "**Ayarlar › Ağ ve İnternet**'te bağlı olduğun Wi-Fi'ye gir, IP adresi orada yazar.",
          "**Bağlan, kur ve başlat**'a bas (kurulum sihirbazında: **Bağlan ve kur**).",
          "TV'de çıkan soruda **Bu bilgisayardan her zaman izin ver**'i işaretle, **İzin ver**'e bas."],
         img="tv-izin", sid="baglan",
         note="TV ile bilgisayar aynı modeme bağlı olmalı. TV uygulaması PS5'in HDMI'ını kendisi bulur; TV HDMI'yı "
              "öne alırsa ya da görüntü siyah kalırsa kendiliğinden katman moduna geçer."),
    step("Tek resimde özet",
         ["Bütün adımlar bir arada: yazdırıp TV'nin yanında tutabilirsin.",
          "Bunu bir kez yaparsın; sonra program TV uygulamasını kendisi kurar ve günceller."], img="kurulum-android"),
]

LG_TV = [
    step("LG geliştirici hesabı aç (ücretsiz)",
         ["Bilgisayarda LG'nin geliştirici sitesini aç ve **Sign Up** ile ücretsiz hesap aç.",
          "E-postana gelen onayı tamamla. Bu kullanıcı adı ve şifreyi TV'de kullanacaksın."],
         img="lg-devmode", link=("LG geliştirici sitesi", "https://webostv.developer.lge.com/"),
         note="Normal LG hesabın değil, geliştirici sitesinden açılan hesap gerekir."),
    step("TV'ye Developer Mode uygulamasını kur",
         ["TV'de **LG Content Store**'u (Uygulamalar) aç.",
          "Aramaya **Developer Mode** yaz, ücretsiz uygulamayı **Yükle**."],
         img="lg-store"),
    step("Developer Mode'u aç",
         ["**Developer Mode** uygulamasını aç, geliştirici hesabınla gir.",
          "**Dev Mode Status**'u aç; TV yeniden başlar.",
          "Uygulamayı tekrar aç ve **Key Server**'ı da aç. Ekranda **IP** ve **Passphrase** görünür."],
         img="lg-devmode", note="Geliştirici modu en çok 1000 saat açık kalır; program her bağlanışta süreyi "
                                "kendisi baştan başlatır."),
    step("Programdan kur",
         ["Developer Mode ekranındaki **IP**'yi ve **Passphrase**'i programa yaz.",
          "**Bağlan, kur ve başlat**'a bas (kurulum sihirbazında: **Bağlan ve kur**); uygulama kurulur ve açılır.",
          "LG başka uygulamanın üstüne yazı çizmeye izin vermez: PS5 görüntüsü bizim uygulamanın içinde açılır. "
          "Kumandada **◀ ▶** ile PS5'in takılı olduğu HDMI girişini seç."],
         img="lg-devmode", sid="baglan"),
    step("Tek resimde özet",
         ["Bütün adımlar bir arada: yazdırıp TV'nin yanında tutabilirsin.",
          "Bunu bir kez yaparsın; sonra program TV uygulamasını kendisi kurar ve günceller."], img="kurulum-lg"),
]

SAMSUNG_TV = [
    step("Uygulamalar sayfasını aç",
         ["Kumandada **ev** tuşuna (evcik simgesi) bas.",
          "Alttaki şeritte **Uygulamalar**'a gel ve **OK**'a bas.",
          "Uygulamaların büyük kareler halinde dizildiği **tam sayfa** açılmalı."],
         img="samsung-uygulamalar",
         note="Şeritte Uygulamalar'ın üstünde dururken yazarsan çalışmaz; sayfanın içine girmiş olmalısın."),
    step("1 2 3 4 5 yaz",
         ["Kumandanda rakam tuşları varsa sırayla **1 2 3 4 5**'e bas.",
          "İnce akıllı kumandada rakam yok: üstünde **123** ya da **4 renkli nokta** olan tuşa bas, ekranda rakamlar "
          "çıkar. Önce bir menü gelirse rakam tuş takımını seç.",
          "Yön tuşlarıyla **1**'e gel, **OK**'a bas. Sonra **2** → OK, **3** → OK, **4** → OK, **5** → OK. Arada "
          "başka tuşa basma.",
          "Doğru yazınca **Developer mode** penceresi açılır."],
         img="samsung-123",
         note="Olmazsa Uygulamalar sayfasından çıkıp yeniden gir ve baştan yaz."),
    step("Kumandayla olmazsa: telefondan yaz",
         ["Telefona Samsung'un ücretsiz **SmartThings** uygulamasını kur.",
          "Telefon ve TV aynı Wi-Fi'de olsun. Uygulamada **+** ile TV'yi ekle, TV'de çıkan onaya **İzin ver** de.",
          "SmartThings'te TV'ye dokun; kumanda ekranında **123**'e bas, gerçek rakam tuşları çıkar.",
          "TV'de Uygulamalar sayfası açıkken telefondan **1 2 3 4 5**'e bas."],
         img="samsung-telefon",
         note="USB klavye de olur: TV'nin USB girişine tak, Uygulamalar sayfası açıkken üst sıradaki rakamlarla "
              "12345 yaz."),
    step("Developer mode'u aç",
         ["Açılan pencerede **Developer mode**'u **On** yap.",
          "**Host PC IP**'ye bu bilgisayarın IP'sini yaz (program sihirbazda ve Televizyon sayfasında gösterir), "
          "**OK**'a bas.",
          "TV'yi kapatıp açmak yetmez: kumandadaki **güç** tuşunu yaklaşık **2 saniye basılı** tut. TV kapanıp "
          "kendiliğinden yeniden açılır.",
          "Açılınca Uygulamalar sayfasının üstünde genelde **Developer mode** yazar."],
         img="samsung-devmode", sid="pcip"),
    step("HDMI'ya kendiliğinden geçişi kapat",
         ["TV'de **Ayarlar › Genel › Harici Aygıt Yöneticisi**'ne gir.",
          "**Anynet+ (HDMI-CEC)**'yi **Kapalı** yap.",
          "Aynı yerde **Otomatik Kaynak Değiştirme** varsa onu da kapat."],
         img="samsung-anynet",
         note="Kapatmazsan PS5 açılınca TV bizim uygulamadan çıkıp doğrudan HDMI'ya geçer ve altyazı görünmez."),
    step("Programdan kur",
         ["Programda **Ağda ara**'ya bas ve listeden TV'yi seç. Bulamazsa TV'nin IP'sini elle yaz: TV'de "
          "**Ayarlar › Genel › Ağ › Ağ Durumu › IP Ayarları**'nda yazar.",
          "**Bağlan, kur ve başlat**'a bas (kurulum sihirbazında: **Bağlan ve kur**).",
          "İlk seferde tarayıcıda Samsung hesabı sayfası açılır: gir (hesabın yoksa aynı sayfadan ücretsiz aç). "
          "Program uygulamayı bu TV'ye özel imzalatır, kurar ve açar. Sonraki seferlerde giriş gerekmez."],
         img="samsung-devmode", sid="baglan", note="Tizen Studio gerekmez."),
    step("HDMI girişini seç",
         ["Samsung başka uygulamanın üstüne yazı çizmeye izin vermez: PS5 görüntüsü bizim uygulamanın içinde açılır.",
          "Kumandada **◀ ▶** ile PS5'in takılı olduğu HDMI girişini seç.",
          "Altyazı yeri kaymışsa **Yeşil** tuşla ayar panelini aç (ince kumandada **123** / renkli nokta tuşundan "
          "renkli tuşlara geç)."],
         img="samsung-hdmi"),
    step("Tek resimde özet",
         ["Bütün adımlar bir arada: yazdırıp TV'nin yanında tutabilirsin.",
          "Bunu bir kez yaparsın; sonra program TV uygulamasını kendisi kurar ve günceller."], img="kurulum-samsung"),
]

MAC = [
    step("GTA6 Altyazı'yı kur",
         ["Releases sayfasından **GTA6Altyazi-mac.dmg**'yi indir ve aç (yalnız Apple Silicon: M1 ve sonrası).",
          "Açılan pencerede **GTA6 Altyazı**'yı **Applications** (Uygulamalar) klasörüne sürükle.",
          "Uygulamalar'dan **GTA6 Altyazı**'yı aç.",
          "\"Apple doğrulayamadı\" uyarısı çıkarsa **Bitti**'ye bas; **Sistem Ayarları › Gizlilik ve Güvenlik**'in en "
          "altında **GTA6 Altyazı engellendi** yazısının yanındaki **Yine de Aç**'a bas, Mac şifreni gir. Bunu yalnız ilk "
          "açılışta bir kez yaparsın."],
         link=("Releases sayfası", "https://github.com/CH4P4R/gta6-altyazi/releases"),
         note="Mac'te NVIDIA yok: çeviri ve OCR işlemcide çalışır; M serisi Mac'lerde bu yeterince hızlı. Güncellemeyi "
              "program kendisi kurar ve yeniden açar."),
    step("chiaki-ng'yi kur",
         ["chiaki-ng'nin indirme sayfasından **macOS** sürümünü (.dmg) indir, Uygulamalar'a sürükle.",
          "PS5 eşleme adımları Windows'takiyle aynı (Rehber › Bilgisayar monitöründe oyna)."],
         link=("chiaki-ng indirme sayfası", CHIAKI_DOWNLOAD)),
    step("İzinleri ver",
         ["**Ekran Kaydı:** Çeviri başlayınca macOS sorar. **Sistem Ayarları › Gizlilik ve Güvenlik › Ekran ve Sistem Ses "
          "Kaydı**'nda **GTA6 Altyazı**'yı aç, programı kapatıp yeniden aç. chiaki penceresini okumak için gerekir.",
          "**Erişilebilirlik:** Kısayol tuşları (Control+Shift+9 ekranı çevir) için **Gizlilik ve Güvenlik › "
          "Erişilebilirlik**'te **GTA6 Altyazı**'yı aç.",
          "**Yerel Ağ:** TV'ye bağlanırken macOS sorarsa **İzin Ver** de."],
         note="İzin verdikten sonra programı kapatıp yeniden açman gerekir; macOS izni ancak yeniden açılışta tanır. "
              "Güncellemeden sonra çeviri başlamazsa Ekran Kaydı listesinde GTA6 Altyazı'yı kapatıp yeniden aç."),
    step("Oyna",
         ["chiaki-ng'de PS5'e bağlan, istersen tam ekran yap.",
          "GTA6 Altyazı'da **Başlat**'a bas; Türkçe chiaki'nin üstünde, tam ekranda da görünür.",
          "TV kurulumları (Google TV, LG, Samsung) Mac'te de aynı adımlarla yapılır."],
         img="baslat"),
]

TV_STEPS = {"android": GOOGLE_TV, "lg": LG_TV, "samsung": SAMSUNG_TV}
TV_BRANDS = [("android", "Google TV / Android TV (TCL, Sony, Philips, Xiaomi, Hisense...)"),
             ("lg", "LG (webOS)"), ("samsung", "Samsung (Tizen)")]


def brief_html(steps: list[dict]) -> str:
    """Adımların resimsiz, kısa özeti (Televizyon sayfası için): ① Başlık: ilk madde..."""
    out = []
    for i, st in enumerate(steps):
        n = NUMS[i] if i < len(NUMS) else f"{i + 1}."
        out.append(f"{n} <b>{st['title']}</b>: " + " ".join(_bold_html(x) for x in st["items"]))
    return "<br>".join(out)


# ---------------------------------------------------------------------------------------------- yayın ve ayar
DISCORD = [
    step("Bilgisayardan yayın aç",
         ["Bilgisayarda ikinci bir Discord hesabıyla sesli kanala gir; mikrofonunu ve sesini kapat.",
          "**Ekran Paylaş**'a bas, **Ekranlar** sekmesinden chiaki'nin olduğu monitörü seç, **Yayına Başla**'ya bas."],
         img="discord-paylas",
         note="Tüm ekranı paylaşmak şart: Türkçe yazı ayrı bir katman olduğu için sadece chiaki penceresini "
              "paylaşırsan görünmez."),
    step("Başka cihazdan konuş",
         ["Telefondan ya da başka bir bilgisayardan kendi hesabınla aynı kanala gir ve konuş.",
          "Kulaklık kullan; yoksa mikrofon TV'nin sesini de alır."],
         img="discord-paylas", note="Bilgisayarın ekranı kilitlenirse okuma durur: ekranı hiç kapanmayacak şekilde ayarla."),
]

OBS = [
    step("OBS'ye tarayıcı kaynağı ekle",
         ["OBS'de **Kaynaklar** kutusunda **+**'ya bas, **Tarayıcı**'yı seç.",
          "URL: **http://localhost:8787/obs**, genişlik **1920**, yükseklik **1080** yaz.",
          "Bu kaynağı oyun görüntüsünün **üstüne** koy."],
         img="obs-kaynak",
         note="Capture kart kullanıyorsan OBS'de Sanal Kamerayı Başlat'a bas ve programda kaynak olarak OBS Virtual "
              "Camera'yı seç."),
]

GTA6_ALAN = [
    step("Oyundan bir kare al",
         ["Oyunda bir altyazı ekrandayken programda **Okuma alanları** sayfasına gir.",
          "**Görüntü al**'a bas."],
         img="alan-ayar"),
    step("Kutuları yazıların üstüne çek",
         ["**altyazi** kutusunu alttaki diyalog ve görev yazısının üstüne, **yardim**'ı sol üstteki yardım kutusuna, "
          "**bildirim**'i sağ üstteki bildirimlere, **telefon**'u sağda açılan telefon/mesaj ekranına oturt.",
          "**Algılanan yazıyı kırmızı göster** açıkken kırmızı noktalar yazının üstünde toplanıyorsa ayar doğrudur.",
          "**Kaydet**'e bas."],
         img="alan-ayar"),
]

PAKETLER = [
    step("Hazır paket indir",
         ["**Çeviri** sayfasında **Önbellek ve çeviri paketleri** kartına in.",
          "Listeden oyunu seç (**GTA 6**, GTA V, RDR2...) ve **Hazır paketi indir**'e bas."],
         note="GTA 6 dahil paketler kurulumla birlikte gelir; pakette olan satırlar anında ve ücretsiz çıkar. Paketler "
              "bu projenin GitHub sayfasında her 6 saatte bir güncellenir (GTA 6 paketi oyuncular oynadıkça büyür); "
              "ara sıra Listeyi yenile'ye basıp yeniden indirebilirsin."),
    step("Kendi paketini paylaş",
         ["**Önbelleği paket olarak kaydet** ile oynadıkça biriken çevirileri dosya yap.",
          "Arkadaşların bu dosyayı **Paket ekle** ile yükler."]),
]

UCRETSIZ = [
    step("Yerel model zaten ücretsiz",
         ["Hiçbir şey yapmasan da ekran kartındaki yerel model çevirir: internetsiz, ücretsiz ve anında.",
          "Daha doğal Türkçe için üstüne aşağıdaki ücretsiz yapay zekâlardan birini ekleyebilirsin."],
         note="Herkes kendi anahtarını kullanır; kimse başkasının çevirisini ödemez. Claude şart değil."),
    step("Google Gemini (ücretsiz anahtar)",
         ["**Anahtar al**'a bas, Google hesabınla gir ve **Create API key**'e bas.",
          "Programda **Çeviri** sayfasında kalite katmanını **Google Gemini** seç, anahtarı yapıştır, **Kaydet**'e bas."],
         note="Ücretsiz kotası oyun oynamak için genelde yeter.", link=("Anahtar al", GEMINI_KEYS)),
    step("DeepL (ücretsiz plan)",
         ["DeepL'in sayfasında **DeepL API Free** planına üye ol (kart bilgisi ister, ücret almaz).",
          "Hesap sayfasındaki anahtarı kopyala (sonu **:fx** ile biter).",
          "Programda kalite katmanını **DeepL** seç, anahtarı yapıştır, **Kaydet**'e bas."],
         note="Ayda 500 bin karaktere kadar ücretsiz.", link=("DeepL API sayfası", DEEPL_SIGNUP)),
    step("Yerel yapay zekâ (Ollama, tamamen ücretsiz)",
         ["**Ollama**'yı indirip kur.",
          "Komut satırında (PowerShell) **ollama pull qwen2.5:7b** yaz, modelin inmesini bekle.",
          "Programda kalite katmanını **Yerel yapay zekâ** seç; adres **http://localhost:11434/v1**, model "
          "**qwen2.5:7b** olarak gelir. **Kaydet**'e bas."],
         note="Anahtar, kota ve ücret yok; altyazı bilgisayardan çıkmaz. Ekran kartı varsa bir satır 1-2 saniyede gelir.",
         link=("Ollama'yı indir", OLLAMA_DOWNLOAD)),
    step("Arkadaşlarınla çevirileri paylaş",
         ["Biri Claude ya da Gemini ile oynadıkça çeviriler önbelleğe birikir.",
          "**Çeviri** sayfasında **Önbelleği paket olarak kaydet** ile dosya yapıp arkadaşlarına at.",
          "Onlar **Paket ekle** ile yükler; o satırlar onlarda da aynı kalitede, anında ve ücretsiz çıkar."]),
]

GUNCELLEME = [
    step("Paketler kendiliğinden güncellenir",
         ["Program her açılışta GitHub'daki hazır paketlere bakar.",
          "Bilgisayarındaki bir paketin (ör. GTA 6) yenisi varsa sessizce indirir; köşede \"Hazır paket güncellendi\" "
          "yazar."],
         note="Kurulumu yeniden yapmana gerek yok. Ayarlar › Güncellemeler'den kapatabilirsin."),
    step("Uygulama tek tıkla güncellenir",
         ["Yeni sürüm çıkınca ana ekranın en üstünde **Yeni sürüm hazır** kartı çıkar.",
          "**Güncelle**'ye bas: kurulum dosyası iner, kendiliğinden kurulur ve program yeni sürümle yeniden açılır.",
          "Ayarların, anahtarların ve paketlerin korunur."],
         note="Neyin değiştiğini GitHub'daki sürüm notlarında (CHANGELOG) görebilirsin."),
]

SORUNLAR = [
    step("TV bilgisayara bağlanamıyor",
         ["**Televizyon** sayfasında **Bağlantı izni › İzin ver**'e bas (Windows bir kez \"Evet\" ister).",
          "Bilgisayarın ağı **Ortak** görünüyorsa Windows Ayarları › Ağ ve İnternet'te **Özel** yap.",
          "TV ve bilgisayar aynı modeme mi bağlı, bak; menzil arttırıcı bazen cihazları ayırır."]),
    step("Altyazı hiç çıkmıyor",
         ["Oyunun kendi ayarlarında **altyazılar açık** mı, bak.",
          "chiaki penceresi **simge durumunda** olmasın.",
          "**Okuma alanları › Görüntü al** ile kutuların yazının üstünde olduğunu kontrol et."]),
    step("Türkçe kayık ya da yanlış yerde",
         ["chiaki'yi tam ekran (**F11**) yap ya da pencereyi büyüt.",
          "**Okuma alanları**'nda kutuları yeniden oturt.",
          "TV'de kumandanın **Yeşil** tuşu bilgi panelini açar; bağlantı ve HDMI orada görünür."]),
    step("chiaki PS5'e bağlanmıyor",
         ["PS5'te **Uzaktan Oynatma** açık mı, bak.",
          "Kayıt sırasında PIN hatası verdiyse kodun süresi dolmuştur; PS5'te **Cihazı Bağla**'ya yeniden bas.",
          "chiaki'ye girdiğin hesapla PS5'te oturum açtığından emin ol."]),
    step("Çeviri yavaş ya da Claude çalışmıyor",
         ["**Çeviri** sayfasındaki **Dene** kutusuna bir cümle yazıp **Çevir**'e bas; süreyi ve motoru gösterir.",
          "Claude anahtarını ve Anthropic hesabındaki krediyi kontrol et.",
          "Anahtar yoksa da program yerel modelle çalışmaya devam eder."]),
]

# ---------------------------------------------------------------------------------------------- liste
TV_ARKA_PLAN = [
    step("İkinci PSN hesabı (bir kez)",
         ["playstation.com'da **farklı bir e-postayla** ücretsiz yeni hesap aç (PS Plus gerekmez).",
          "PS5'te **Kullanıcı Ekle** de, yeni hesapla bir kez oturum aç.",
          "Hâlâ yeni kullanıcıyken: **Ayarlar › Sistem › Uzaktan Oynatma › Uzaktan Oynatmayı Etkinleştir**'i aç.",
          "Aynı yerde **Uzaktan Oynatma Bağlantı Durumu Açılır Penceresini Gizle**'yi aç (iki hesapta da), ekranda "
          "\"bağlandı\" yazısı çıkmasın."],
         note="Neden ikinci hesap? Bilgisayar oyunu Remote Play'den izler. Kendi hesabınla bağlansaydı PS5 kolunu "
              "kapatırdı; ikinci hesapla sen oynamaya devam edersin."),
    step("Programda ikinci hesapla giriş",
         ["Ana ekranda PS5 kartındaki **TV'de oynuyorum (chiaki'siz)**'e bas (ya da Ayarlar › Görüntü kaynağı › "
          "**PS5'i bağla**).",
          "**Sony giriş sayfasını aç**'a bas, **ikinci hesapla** giriş yap.",
          "Giriş bitince tarayıcı yalnız *redirect* yazan bir sayfada kalır (bu normal). Adres çubuğundaki adresin "
          "**tamamını** kopyala; program kendisi alır."]),
    step("PS5'i eşle (bir kez)",
         ["PS5'te **ikinci kullanıcıya geç**.",
          "**Ayarlar › Sistem › Uzaktan Oynatma › Cihazı Eşleştir**'i aç; ekranda 8 haneli kod çıkar.",
          "Programda PS5'ini seç, kodu yaz, **Eşle**'ye bas (30 saniyeye kadar sürer).",
          "Bitince PS5'te **kendi kullanıcına geri dön**."]),
    step("Oyna",
         ["PS5'i aç, kolu açınca **kendi (ana) hesabını** seç ve oyna.",
          "Program PS5'in açıldığını görür, arka planda bağlanır ve çeviriyi kendisi başlatır; Türkçe TV'de çıkar.",
          "TV uygulaması kurulu değilse önce Rehber › TV uygulaması adımlarını yap."],
         note="PS5'i kapatınca (dinlenme modu) bağlantı bekler; PS5 açılınca kendiliğinden yeniden bağlanır. "
              "Kablosuz ağda görüntü sık koparsa program kendiliğinden 720p'ye geçer; kalıcı çözüm PS5'i modeme "
              "kabloyla bağlamak."),
]

CAPTURE = [
    step("Kabloları bağla",
         ["PS5'in HDMI kablosunu capture kartın **HDMI IN** girişine tak.",
          "Kartın **HDMI OUT** (passthrough) çıkışını TV'ye bağla: görüntü TV'ye gecikmesiz geçer.",
          "Kartın USB kablosunu bilgisayara tak (Elgato HD60 / 4K, AVerMedia Live Gamer, USB HDMI kartlar)."],
         note="PS5'te Ayarlar › Sistem › HDMI › **HDCP'yi Etkinleştir**'i kapat; açıkken capture kart görüntüyü siyah "
              "verir."),
    step("Programda kartı seç",
         ["**Bağlantı › Görüntü kaynağı**'nda **Yakalama kartı**'nı seç.",
          "**Aygıtları ara**'ya bas: kartlar adıyla listelenir, capture kart olan kendiliğinden seçilir.",
          "**Önizle** ile oyunun görüntüsünün geldiğini gör. Görüntü: 1080p · 60 kare (eski kartta 720p)."]),
    step("Oyunu nerede oynayacaksın",
         ["**TV'de oynuyorum:** görüntü TV'ye kartın HDMI çıkışından gider; Türkçe TV uygulamasında oyunun üstünde "
          "çıkar (Rehber › TV uygulaması).",
          "**Bilgisayar ekranında:** görüntü ve Türkçe bu programın penceresinde birlikte açılır. **Capture kartın "
          "sesini hoparlöre aktar** açıkken oyunun sesi bilgisayardan gelir; ses gelmezse **Ses girişlerini ara**'dan "
          "kartın girişini seç."]),
    step("Kaydet ve başlat",
         ["**Kaydet**'e bas, sonra ana ekranda fişi prize tak (ya da Çeviriyi Başlat).",
          "İlk açılışta macOS kamera ve mikrofon izni ister: capture kartın görüntüsü ve sesi için **İzin Ver**."]),
]

FIS = [
    step("\"Fişi takın\" ne demek?",
         ["Ana ekrandaki TV, PS5 ve küçük fiş çizimi programın **Başlat düğmesidir**.",
          "**Fişe tıkla** ya da prize sürükle: çeviri başlar, TV'nin arkası mavi yanar, ekranda ● CANLI çıkar.",
          "Durdurmak için fişi çek (ya da yeniden tıkla). İstersen Altyazı görünümü › Ana ekran'dan **Cam düğme**'ye "
          "geç: pembe-turuncu düğmeyi sağa kaydırınca açılır."],
         img="fis-nedir",
         note="PS5'in ya da TV'nin gerçek elektrik fişine dokunma; konsol her zamanki gibi açık kalsın."),
]

GUIDES: list[dict] = [
    {"key": "tv-arka-plan", "icon": "tv", "title": "TV'de oyna (chiaki'siz, önerilen)",
     "summary": "PS5 HDMI ile TV'de; bilgisayar PS5'e arka planda ikinci hesapla bağlanır, Türkçe TV'de çıkar.",
     "steps": TV_ARKA_PLAN},
    {"key": "monitor", "icon": "ps", "title": "Bilgisayar monitöründe oyna",
     "summary": "chiaki-ng ile PS5'i bilgisayarda oyna; Türkçe chiaki'nin üstünde çıksın.",
     "steps": chiaki_steps("monitor") + [START_STEP]},
    {"key": "tv-izle", "icon": "tv", "title": "TV'de oyna, bilgisayar izlesin",
     "summary": "Sen TV'den HDMI ile oyna; bilgisayar ikinci hesapla izleyip Türkçeyi TV'ye göndersin.",
     "steps": chiaki_steps("tv") + [START_STEP]},
    {"key": "capture", "icon": "monitor", "title": "Capture kart ile oyna",
     "summary": "Elgato, AVerMedia ya da USB HDMI kartla: görüntü TV'ye geçer, Türkçe TV'de ya da bilgisayarda.",
     "steps": CAPTURE},
    {"key": "fis", "icon": "play", "title": "\"Fişi takın\" ne demek?",
     "summary": "Ana ekrandaki fiş, programın Başlat düğmesidir.", "steps": FIS},
    {"key": "mac", "icon": "ps", "title": "Mac'te kullanım (Apple Silicon)",
     "summary": "M1 ve sonrası Mac'lerde kurulum, chiaki-ng ve macOS izinleri.", "steps": MAC},
    {"key": "google-tv", "icon": "tv", "title": "TV uygulaması: Google TV / Android TV",
     "summary": "TCL, Sony, Philips, Xiaomi, Hisense ve diğer Android TV'ler.", "steps": GOOGLE_TV},
    {"key": "lg", "icon": "tv", "title": "TV uygulaması: LG (webOS)",
     "summary": "LG Developer Mode ile kurulum.", "steps": LG_TV},
    {"key": "samsung", "icon": "tv", "title": "TV uygulaması: Samsung (Tizen)",
     "summary": "Tizen Studio olmadan, Samsung hesabıyla kurulum.", "steps": SAMSUNG_TV},
    {"key": "discord", "icon": "phone", "title": "Discord'da arkadaşlarına yayın",
     "summary": "Arkadaşların Türkçe altyazılı izlesin.", "steps": DISCORD},
    {"key": "obs", "icon": "play", "title": "OBS ile yayın",
     "summary": "Türkçe altyazıyı OBS'de oyunun üstüne koy.", "steps": OBS},
    {"key": "gta6", "icon": "regions", "title": "GTA 6 için okuma alanlarını ayarla",
     "summary": "Kutuları gerçek altyazının üstüne oturt (5 dakika).", "steps": GTA6_ALAN},
    {"key": "ucretsiz", "icon": "translate", "title": "Ücretsiz çeviri (Gemini, DeepL, Ollama)",
     "summary": "Claude şart değil: ücretsiz yapay zekâ seçenekleri ve arkadaşlarla paylaşım.", "steps": UCRETSIZ},
    {"key": "paketler", "icon": "translate", "title": "Hazır çeviri paketleri",
     "summary": "GTA 6, GTA V, RDR2 ve diğer oyunların paketleri; kendi paketini paylaş.", "steps": PAKETLER},
    {"key": "guncelleme", "icon": "history", "title": "Güncellemeler",
     "summary": "Paketler sessizce, uygulama tek tıkla güncellenir; yeniden kurmak gerekmez.", "steps": GUNCELLEME},
    {"key": "sorunlar", "icon": "settings", "title": "Sorun giderme",
     "summary": "TV bağlanmıyor, altyazı çıkmıyor, yazı kayık...", "steps": SORUNLAR},
]


# ---------------------------------------------------------------------------------------------- biçimlendirme
def _bold_html(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)


def to_html(st: dict, faint: str = "#8a8399") -> str:
    lines = [f"{NUMS[i] if i < len(NUMS) else i + 1} {_bold_html(x)}" for i, x in enumerate(st["items"])]
    if len(st["items"]) == 1:
        lines = [_bold_html(st["items"][0])]
    html = "<br>".join(lines)
    if st.get("note"):
        html += f"<br><span style='color:{faint}'>{_bold_html(st['note'])}</span>"
    return html


def to_markdown(st: dict, img_prefix: str = "altyazi/ui/rehber/") -> str:
    out = []
    if st.get("img"):
        out.append(f'<img src="{img_prefix}{st["img"]}.png" alt="{st["title"]}" width="640">\n')
    for i, x in enumerate(st["items"], 1):
        out.append(f"{i}. {x}")
    if st.get("link"):
        out.append(f"\n🔗 [{st['link'][0]}]({st['link'][1]})")
    if st.get("note"):
        out.append(f"\n> {st['note']}")
    return "\n".join(out)
