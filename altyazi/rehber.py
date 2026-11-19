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
          "**Android TV OS derlemesi** satırına arka arkaya **7 kez** bas. \"Artık geliştiricisiniz\" yazar."],
         img="tv-gelistirici"),
    step("USB hata ayıklamayı aç",
         ["**Ayarlar › Sistem › Geliştirici seçenekleri**'ne gir.",
          "**USB hata ayıklama**'yı aç."],
         img="tv-hata-ayiklama",
         note="Yoksa ya da TV bulunamazsa Kablosuz hata ayıklama'yı aç; ekrandaki eşleştirme adresi ve kodunu "
              "programdaki Eşleştir kısmına yazarsın."),
    step("Bağlan ve izin ver",
         ["Programda **Televizyon** sayfasında **Ağda ara**'ya bas (ya da TV'nin IP'sini yaz), sonra **Bağlan, kur ve "
          "başlat**'a bas.",
          "TV'de çıkan soruda **Bu bilgisayardan her zaman izin ver**'i işaretle, **İzin ver**'e bas."],
         img="tv-izin", sid="baglan",
         note="TV uygulaması PS5'in HDMI'ını kendisi bulur. TV HDMI'yı öne alırsa ya da görüntü siyah kalırsa "
              "kendiliğinden katman moduna geçer."),
]

LG_TV = [
    step("TV'de Developer Mode'u aç",
         ["TV'de **LG Content Store**'dan ücretsiz **Developer Mode** uygulamasını kur ve LG hesabınla gir.",
          "**Dev Mode Status**'u aç; TV yeniden başlar.",
          "Uygulamayı tekrar aç ve **Key Server**'ı aç."],
         img="lg-devmode"),
    step("Programdan kur",
         ["Programda **Televizyon** sayfasında markayı **LG** seç.",
          "Developer Mode ekranındaki **IP** adresini ve **Passphrase**'i yaz.",
          "**Bağlan, kur ve başlat**'a bas."],
         img="lg-devmode", note="Geliştirici modu en çok 1000 saat açık kalır; program her bağlanışta süreyi kendisi "
                                "baştan başlatır."),
]

SAMSUNG_TV = [
    step("TV'de Developer mode'u aç",
         ["TV'de **Uygulamalar** ekranını aç.",
          "Kumandayla **1 2 3 4 5** yaz; Developer mode penceresi açılır.",
          "**Developer mode**'u **On** yap, **Host PC IP**'ye bu bilgisayarın IP'sini yaz (program Televizyon "
          "sayfasında gösterir), **OK**'a bas.",
          "TV'yi güç tuşuna yaklaşık 2 saniye basılı tutarak yeniden başlat."],
         img="samsung-devmode", note="Tizen Studio gerekmez."),
    step("Programdan kur",
         ["Programda **Televizyon** sayfasında markayı **Samsung** seç ve **Bağlan, kur ve başlat**'a bas.",
          "İlk seferde tarayıcıda bir kez **Samsung hesabınla** giriş yap; program uygulamayı TV'ne özel imzalatır, "
          "kurar ve açar."],
         img="samsung-devmode",
         note="TV kendiliğinden HDMI'ya geçiyorsa Anynet+ (HDMI-CEC) ve Otomatik Kaynak Değiştirme'yi kapat."),
]

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
          "**bildirim**'i sağ üstteki bildirimlere oturt.",
          "**Algılanan yazıyı kırmızı göster** açıkken kırmızı noktalar yazının üstünde toplanıyorsa ayar doğrudur.",
          "**Kaydet**'e bas."],
         img="alan-ayar"),
]

PAKETLER = [
    step("Hazır paket indir",
         ["**Çeviri** sayfasında **Önbellek ve çeviri paketleri** kartına in.",
          "Listeden oyunu seç (**GTA 6**, GTA V, RDR2...) ve **Hazır paketi indir**'e bas."],
         note="Pakette olan satırlar anında ve ücretsiz gelir, yapay zekâya sorulmaz. GTA 6 paketi CouchSubs'ın paket "
              "sunucusundan gelir ve oyuncular oynadıkça büyür; ara sıra Listeyi yenile'ye basıp yeniden indir."),
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
GUIDES: list[dict] = [
    {"key": "monitor", "icon": "ps", "title": "Bilgisayar monitöründe oyna",
     "summary": "chiaki-ng ile PS5'i bilgisayarda oyna; Türkçe chiaki'nin üstünde çıksın.",
     "steps": chiaki_steps("monitor") + [START_STEP]},
    {"key": "tv-izle", "icon": "tv", "title": "TV'de oyna, bilgisayar izlesin",
     "summary": "Sen TV'den HDMI ile oyna; bilgisayar ikinci hesapla izleyip Türkçeyi TV'ye göndersin.",
     "steps": chiaki_steps("tv") + [START_STEP]},
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
