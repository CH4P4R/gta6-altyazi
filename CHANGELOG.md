# Sürüm notları

Her sürümün kurulum dosyası [Releases](https://github.com/CH4P4R/gta6-altyazi/releases) sayfasındadır. Eski bir
sürümün üstüne kurabilirsin; ayarların ve Claude anahtarın korunur.

## Sıradaki sürüm
- **Telefonun yanındaki mesaj paneli telefon ekranının Türkçe kopyası gibi:** gündüz sohbette panel süt beyazı ve
  buzlu (arkası bulanık), telefon boyunda; kişinin adı üstte, her mesaj telefondaki hizasında, gelenler solda beyaz,
  giden mesaj sağda açık mavi balonda. Yazılar biraz büyüdü, panelin sağ altında küçük GTA6 Altyazı rozeti var.
  Telefonun koyu çerçevesi ya da başparmak yüzünden panel koyu çıkıyordu, düzeldi.
- **GTA 6 paketi GameTranslator + CouchSubs:** GameTranslator'ın kendi GTA 6 paketi artık alınıyor (önceden aynı adlı
  CouchSubs paketi yüzünden atlanıyordu). İkisi tek pakette birleşir: GameTranslator'ın Türkçesi önce gelir, onda
  olmayan satırlar CouchSubs'tan tamamlanır. GTA V ve RDR2 için de aynısı.
- **Hazır paketler:** GameTranslator'ın Final Fantasy VII Rebirth paketi dosya başındaki görünmez bir işaret (BOM)
  yüzünden ve eski düz biçimde olduğu için alınamıyordu; artık 32 bin satırıyla alınıyor.

## 0.9.5 · GameTranslator'ın yeni paket sunucusu, zaten Türkçe satırlar çevrilmez
- **Hazır paketler:** GameTranslator paketlerini 23 Kasım'da kendi sunucusuna taşıdı; paket aynamız artık oradan da
  alıyor (eski yer yedek). Yeni GameTranslator paketleri kendiliğinden gelir.
- **Zaten Türkçe satır çevrilmez** (CouchSubs #298, GameTranslator'da da var): PS5'in Türkçe menüleri ve oyunun Türkçe
  altyazısı çevirmene gitmez, olduğu gibi kalır; içinde Türkçe ad geçen İngilizce satır yine çevrilir.
- **Capture kart listesinde OBS Sanal Kamera** da tanınır: görüntüyü OBS'ten almak isteyen onu seçebilir.

## 0.9.4 · GTA 6 oyun metniyle okuma düzeltme, CouchSubs'tan bağlantı düzeltmeleri
- **GTA 6 oyun metni** (Çeviri ve paketler › İndir): oyunun İngilizce satırlarının tamamı (~460 bin, kaynak
  github.com/psviethoa/gta6-text-en) bilgisayarda küçük bir dizine kurulur. Okunan satırda bir iki harf hatası varsa
  gerçek satırla düzeltilir ("Stop your vehic1e!" → "Stop your vehicle!"): hazır paketin Türkçesi bulunur, yapay zekâya
  hatasız İngilizce gider. Emin olunmayan satıra dokunulmaz; başka oyunda kapalıdır. Program bu metni dağıtmaz.
- **PS5 bağlantısı (CouchSubs #353):** PS5 akışı kendisi kapattığında (PS5'te ikinci hesap seçildi) sınırsız yeniden
  bağlanma yok: bir kez denenir, sonra nedeni söylenir. Ağ kopmasında art arda en çok beş deneme.
- **Remote Play:** akla yatmayan boyuttaki görüntü kareleri çözücüye verilmez (CouchSubs #855).
- **TV:** başka bilgisayara geçince eski altyazı ekranda kalmaz.

## 0.9.3 · Yeni simge ve logo, gerçekçi ana ekran, kaydırmalı düğme, yeni telefon kumandası
- **Yeni marka:** uygulama simgesi (ay yıldızlı oyun kolu, EN → TR balonları), büyük simge, logo, rozet, yardımcının robot
  yüzü; Windows / macOS simgesi, kurulum görselleri, Android TV simgesi ve ana ekran banner'ı, LG / Samsung simgeleri,
  README tanıtım görseli.
- **Ana ekran (Nino):** lacivert duvarda gerçekçi TV, metal sehpa, PS5 ve priz. Fişi prize takınca TV'nin arkası mavi
  ışıkla parlar, ekranda ● CANLI ve Türkçe altyazı çıkar; çekince durur. TV kapalıyken ekranda logo ve "Oyunlarınız artık
  Türkçe".
- **Kaydırmalı düğme görünümü:** TV önizlemesi (Türkçe altyazı, altında İngilizcesi) ve pembe-turuncu "Türkçe · Altyazı açık"
  düğmesi; ay yıldızlı topu kaydırarak aç / kapat. Ana ekranın sağ üstünden ya da Altyazı görünümü › Ana ekran'daki
  resimli kartlardan **Salon / Cam düğme** seçilir.
- **Fişe tıklamak yeter:** sürüklemeden tıklayınca da çeviri başlar / durur; fişin çevresinde kırmızı halka ve "Bu fişe
  tıklayın" / "Prizde: çeviri açık ✓" notu.
- **Dört yazı tipi:** Aksiyon (GTA tarzı, Barlow Condensed), Modern (Barlow), Yuvarlak (Nunito), Sade (TV'nin kendi
  yazı tipi); düğmeler kendi yazı tipleriyle görünür, önizleme seçilen tiple çizilir.
- **Capture kart:** aygıtlar adıyla listelenir (capture kart olan kendiliğinden seçilir), çözünürlük / kare hızı seçimi,
  tek kare önizleme, sesi hoparlöre aktarma ve ses girişi seçimi. Oyun bilgisayardaysa görüntü + Türkçe programın
  penceresinde açılır; TV'deyse (kartın HDMI çıkışı TV'ye) Türkçe TV uygulamasında çıkar.
- **Rehber:** "Capture kart ile oyna" ve "Fişi takın ne demek?" eklendi; Android TV, LG ve Samsung kurulumu tek resimde
  özet görselle. README'de ekran yazılarının tanıtım kartları.
- **Kendi renklerimiz:** simge, logo, robot, banner'lar, ana ekran sahnesi (pembe arka ışık, gün batımı duvar kağıdı),
  kaydırmalı düğme, TV bekleme ekranı, telefon kumandası, kurulum ve tanıtım görselleri mor zemin ve pembe → turuncu
  vurguyla.
- **Köşede logo** (isteğe bağlı): TV'de sol alt köşede küçük GTA6 Altyazı logosu, yayın ve ekran görüntüsü için.
- **Telefon kumandası sayfası yenilendi** (tarayıcıda açılan /kumanda; ayrı telefon uygulaması yok).
- **Kurulum:** hoş geldin sayfasında büyük simge, ad ve örnek çeviri kartı. **Sor:** robot yüzlü yardımcı.
- **TV bekleme ekranı:** ışıklı halkada logo, "GTA6 Altyazı · Oyunlarınız artık Türkçe" (TV uygulaması 0.6.0).

## 0.9.2 · Fişi prize tak, OBS katmanı, TV uygulaması sürümü
- **Fişi prize sürükle (Nino):** ana ekranda TV, sehpa, PS5 ve priz; fişi prize sürükleyince çeviri başlar, çekince
  durur. Çeviri açıkken TV'de son Türkçe altyazı görünür.
- **OBS katmanı** sayfası: tarayıcı kaynağı adresleri (localhost ve ağ adresi, Kopyala) ve **yayın penceresi** (yeşil /
  siyah / mor zemin; Chroma key ile silinir).
- **Sistem sağlığı:** TV uygulamasının kurulu sürümü ve güncel olup olmadığı (TV uygulaması bağlanırken sürümünü bildirir;
  TV uygulaması 0.5.0).

## 0.9.1 · Görsellerdeki kalan her şey
- **Açık / koyu görünüm** (Hakkında › Görünüm; programı yeniden açınca geçer).
- **Okuma alanı:** "Otomatik (önerilen)" (öğrenilen yeri unutup yeniden öğrenir), seçili bölge için Üst / Alt / Sol / Sağ
  kaydırıcıları ve "Ortada tut", "Son okunan ve çevrilen" (oyunda İngilizce / TV'de Türkçe), ek alanlarda kutu zemini.
- **Çeviri ve paketler:** oyun paketlerini aç / kapat, "Oynadığın oyun" seçimi (Otomatik ya da paketteki oyunlar), Gemini
  modeli (hızlı / en iyi), yazı tanıma seçimi (Otomatik / Apple / PP-OCR), yazıyı okurken ekran kartı, ücretsiz çeviri
  aygıtı (ekran kartı / işlemci) ve çekirdek sayısı, "Değişmeyen altyazı alanını daha sık oku", bozuk ve yarım okunan
  satır için bekleme (varsayılan kapalı: beklemeden gösterip yerinde düzeltir).
- **Altyazı görünümü:** "Boyutu oyunun altyazısına uydur" (kapalıysa sabit boyut).
- **Ana ekran:** TV kartında "TV'de test et" ve "TV uygulamasını yeniden kur"; "Görüntü" ve "Çeviri" kısayolları.
- **PS5 bağlama (Nino):** numaralı adım satırları, üç adım kartı, "Giriş yapıldı · PSN hesap kimliği (gizli) · Çıkış yap",
  "PS5 bulundu".
- **Kurulum:** alt çubukta "Deneme modu (konsol olmadan dene)"; hoş geldin sayfasında "Monitörde Remote Play ile
  oynuyorum" ve "Capture Card'ım var".

## 0.9.0 · Deneme modu, GTA 6 tek tık, iki kısayol, Nino kurulum ekranları
- **Deneme modu (konsol olmadan dene):** ana ekranda ve Bağlantı'da. Örnek görüntüde İngilizce altyazılar sırayla çıkar;
  program gerçek oyundaki gibi okur, çevirir, kendi penceresinde ve TV bağlıysa TV'de gösterir.
- **Altyazıyı göster: TV / Bilgisayar ekranı / İkisi de** ana ekranda tek tıkla.
- **Okuma alanı:** "Tek tıkla GTA 6 için en iyi okuma" düğmesi; ek alanlar (altyazı ve görev yazısı, ipucu kutusu, bildirim,
  telefon) tek tek açılıp kapanır, her birinin yazı boyutu ayarlanır.
- **Altyazı seçenekleri:** konuşan adını göster / gizle, konuşana göre renk (TV'de her karakter kendi renginde), oynanan
  oyunu sor (paketle tanınmazsa "Hangi oyunu oynuyorsun?"), telefon mesajları yanında ya da balonların üstünde.
- **TV yazı tipi:** Yuvarlak (okunaklı) ya da Aksiyon (GTA tarzı).
- **Kısayollar:** her işin iki kısayolu (ör. Ctrl+Shift+9 ve Num 9); yeni: çeviriyi başlat / durdur, seslendirmeyi aç /
  kapat, TV'ye deneme gönder. Mac'te sayı tuş takımı da çalışır.
- **Kurulum (Nino):** "İhtiyacınız olanlar" kartları, TV seçimi büyük kartlarla (Android TV / LG-Samsung / TV'm yok),
  Gemini için 1-2-3 adımlar ve "Gemini hazır" ekranı. **Yardım sohbetinde** hazır soru düğmeleri.
- Düzeltme: pencere kaynağında chiaki penceresi yokken açılan çeviri hemen kapanıyordu (deneme modunda da).

## 0.8.0 · Yeni arayüz
GameTranslator, CouchSubs ve Nino'dan esinlenen düzen; renkler ve kimlik bizim.
- **Ana ekran:** ortada büyük durum ("Çeviri kapalı.") ve tek Başlat düğmesi; PS5 / Bilgisayar / TV kartları renkli
  durum etiketleriyle; son çeviri büyük Türkçe + İngilizcesi + okuma / çeviri / gecikme süreleri; "Oyun", "Okunan yer",
  "TV'deki görünüm" kısayolları. TV'de oynayana artık chiaki-ng'den hiç söz edilmez.
- **Altyazı görünümü (yeni):** canlı önizleme, TV ve bilgisayar ekranı ayrı; yazı rengi (beyaz, sarı, camgöbeği, yeşil,
  turuncu), boyut, arka plan koyuluğu ve alanı, yer (örterek / üstünde / altında / sabit), kalın yazı, önceki satırlar;
  6 hazır stil (Klasik, Sinema, Minimal, Gün batımı cam, Yüksek kontrast, Kenarlıklı). Değişiklik anında TV'ye gider.
- **Bağlantı:** PS5 ve TV tek sayfada, görüntü kaynağı seçim kartlarıyla, ikinci ekran QR kodu, güvenlik duvarı izni.
- **Çeviri ve paketler:** oyun paketleri kart kart; çeviri motoru seçim kartlarıyla; "✓ Anahtar kayıtlı · Dene · Anahtarı
  sil"; diğer motorlar ve gelişmiş ayarlar katlanır.
- **Sistem sağlığı (yeni):** bilgisayarın ağı (Wi-Fi / kablo), PS5 bağlantısı ve görüntüsü (kare hızı, donma), çeviri hızı,
  TV; her biri "İyi / İyileştirilebilir" ve ne yapılacağı. Cihaz bilgilerini kopyala, Sorun bildir.
- **Kurulum:** PS5 kodu 8 ayrı kutuya (yapıştırınca dağılır), ikonlu başlıklar, adım noktaları, "Deneyelim: TV'de
  görüyor musun?" adımı, sağ altta yardım düğmesi.
- Açma/kapama anahtarları, yumuşak ışıltılı zemin, Altyazı geçmişi TXT / JSON olarak kaydedilir, Ayarları sıfırla.

## 0.7.0 · Telefon, harita ve mesajlar Türkçe; seslendirme; daha akıllı çeviri
Nino Game Translator'ın (CouchSubs türevi, AGPL-3.0) en iyi özellikleri eklendi, Xbox hariç:
- **Oyundaki telefon Türkçe:** telefon ekranı görüntüden bulunur (eğik tutulsa da); sohbetin Türkçesi telefonun yanında,
  her mesaj kendi balonunda ve oyundaki sırayla; mesajlar önceki mesajlarla birlikte çevrilir. Banka/haber
  uygulamalarında her yazının altında Türkçesi. Telefon açıkken içindeki yazılar altyazı sanılmaz.
- **Harita görev kartı Türkçe:** seçili görevin kartının Türkçesi kartın altında, kart gibi. Dükkân adları çevrilmez.
- **Gelen mesaj ve arama kartı:** Türkçesi kartın üstünde, gönderenin adıyla; "Paradise Taxi aranıyor…".
- **TV'de yeni altyazı stili** (büyük, yuvarlak köşeli yarı saydam kutu) ve telefon balonları, yan panel, kart, eğik yazı
  (LG, Samsung, Android TV). Bilgisayar ekranındaki katmanda da.
- **Türkçe seslendirme (dublaj):** doğal Türkçe sesler (Ahmet/Emel), konuşan adına göre kadın/erkek; yeni satırda
  kesilir. Ayarlar › Ekran › Türkçe seslendir.
- **Sor (yardım sohbeti):** rehberi ve programın durumunu bilen yapay zekâ; fotoğraf eklenebilir (kendi anahtarınla).
- **Daha akıllı çeviri:** bulanık paket araması (okuma bir iki harf hatalı olsa da oyunun paketinden anında Türkçe),
  konuşan adı çeviriye karışmaz, özel adlar korunup Türkçe ekiyle geri konur, kısa satır önceki cümleyle çevrilir,
  sen/siz uyumu, oyun deyimleri ("got your six"), OCR çöpü temizliği, yapay zekâ çevirmeden geri verirse yok sayılır.
- **Oyunu kendiliğinden tanır** (PS5'in bildirdiği oyun ve paketten gelen satırlar) ve **altyazının yerini öğrenir**
  (yalnız o şerit okunur: daha hızlı, HUD karışmaz). Yarım okunan satır ikinci kez çevrilmez.
- **Mac'te Apple'ın yazı tanıması (Neural Engine):** altyazı, telefon ve harita yazıları Mac'in kendi Vision motoruyla
  okunur (GameTranslator'daki gibi); açılışta kendini sınar, okuyamazsa eski motora geçer.
- **Hız:** yerel çeviri en hızlı ayarı ölçerek seçer (Mac'te float32/int8, yavaş işlemcide ışın 1).

## 0.6.1 · Yeni kurulum sihirbazı
- **Kurulum sihirbazı baştan tasarlandı:** daha büyük yazılar ve düğmeler, büyük ikonlu seçim kartları, "TV'de
  oynuyorum" en üstte ve önerilen.
- TV'de oynayan için PS5 adımı artık doğrudan PS5 bağlantısı (ikinci hesapla giriş ve eşleme sihirbazın içinde);
  chiaki-ng adımları yalnız monitörde oynayana gösteriliyor. "Bazen ikisi" seçilince iki sekme var.
- Son sayfa seçime göre: TV'de "PS5 açılınca kendiliğinden başlar", monitörde chiaki adımları.
- Rehberde görseli olmayan adımlarda metnin üstünde kalan boşluk giderildi.
- Sistem katman penceresini kapatınca (Windows kapanışı) program da tamamen kapanıyor.

## 0.6.0 · PS5'i TV'de oyna, chiaki gerekmez
- **Yerleşik Remote Play:** Oyunu TV'de, HDMI'dan oynarsın; bilgisayar PS5'e arka planda **ikinci PSN hesabıyla**
  bağlanıp yalnız altyazıyı okur, Türkçesini TV'ye gönderir. chiaki-ng penceresi açmak gerekmez (CouchSubs'ın
  yöntemi; libchiaki ile). Ana ekranda PS5 kartındaki **TV'de oynuyorum (chiaki'siz)** ya da Ayarlar › Görüntü
  kaynağı › **PS5'i bağla**: ikinci hesapla Sony girişi ve PS5'teki 8 haneli kodla bir kez eşleme.
  - PS5 açılınca çeviri kendiliğinden başlar; PS5 dinlenmedeyse çeviri başlarken uyandırılır, kapatınca bağlantı
    bekler ve PS5 açılınca yeniden bağlanır. PS5'in adresi değişirse adıyla yeniden bulunur.
  - Bağlantı kablosuz ağda sık koparsa görüntü 720p'ye düşürülür; görüntü takılırsa oturum yeniden kurulur.
  - Hatalar Türkçe ve sebebiyle: Uzaktan Oynatma kapalı, başka cihazda açık, eşleme geçersiz, giriş şifresi...
  - "TV'de oynuyorum" seçiliyken bilgisayar ekranına katman açılmaz; Türkçe yalnız TV'de görünür.
- **Pencere kapatılınca program kapanmıyordu:** Çeviri sürerken ana pencere kapatılınca program penceresiz açık kalıp
  port 8787'yi tutuyordu (yeniden açınca "port başka bir programda"). Artık kesin kapanıyor (Windows denemesi yakaladı).
- Rehber'e "TV'de oyna (chiaki'siz)" konusu eklendi.

## 0.5.2
- **"Port 8787 başka bir programda" hatası düzeltildi.** Sebepleri:
  - Program zaten açıkken (ör. Windows açılışında simge durumunda açılmışken) yeniden açılınca ikinci bir kopya
    açılıyordu. Artık ikinci kopya açılmıyor; açık olan pencere öne geliyor.
  - Pencere kapatılınca arka planda süren bir iş (çeviri isteği, model yükleme) programı penceresiz açık tutup portu
    bırakmayabiliyordu. Artık pencere kapanınca program tamamen kapanıyor.
  - TV bağlıyken program kapatılıp hemen açılınca port birkaç dakika açılamayabiliyordu. Düzeltildi.
- Port yine doluysa program onu kimin tuttuğunu buluyor: penceresiz kalmış eski bir GTA6 Altyazı kopyasıysa kendisi
  kapatıyor; başka bir programsa (ör. CouchSubs) adını söylüyor ve o kapanınca birkaç saniye içinde kendiliğinden
  bağlanıyor. Programı yeniden açmana gerek yok.
- Mac rehberi ve sürüm notlarına Mac kurulumu (ilk açılışta "Yine de Aç") eklendi.

## 0.5.1
- Program açılışta bazı ağlarda (özellikle Mac'te) bilgisayarın adını sorarken bir dakikaya kadar bekleyebiliyordu
  (Mac denemesinde 70 sn görüldü); artık hemen açılıyor. Mac denemesi açılışın 30 saniyeden kısa sürdüğünü de denetliyor.

## 0.5.0 · macOS
- **Mac sürümü (Apple Silicon, M1 ve sonrası):** GTA6Altyazi-mac.dmg. chiaki-ng penceresi ScreenCaptureKit ile
  okunur, Türkçe tam ekranda da chiaki'nin üstünde görünür; kısayol tuşları, TV kurulumları (Google TV, LG, Samsung),
  capture kart, hazır paketler, Claude/Gemini/yerel model Windows'takiyle aynı. Uygulama içi güncelleme Mac'te de var.
- Mac için Rehber'de yeni konu: kurulum, chiaki-ng ve macOS izinleri (Ekran Kaydı, Erişilebilirlik, Yerel Ağ).
- Mac sürümü de yayınlanmadan önce gerçek bir Mac'te deneniyor (açılış, çeviri, TV akışı, güncelleme).

## 0.4.21
- **Tuş simgeli yazılar artık çevriliyor:** "Press △ to enter" gibi ipuçlarında tuş bir resim olduğu için OCR okuyamıyordu
  ve bu satırlar çevrilmiyordu. Artık o satırın küçük resmi yapay zekâya (Claude ya da Gemini) gösteriliyor; simgeyi
  görüp çeviride yerinde bırakıyor: "Binmek için △ tuşuna bas". Aynı yazı önbelleğe girdiği için yapay zekâya bir kez
  sorulur. Claude ya da Gemini seçili değilse bu satırlar eskisi gibi oyunun kendi yazısıyla kalır.
- "Ekranı çevir" artık Gemini ile de ekranın resmine bakarak okuyor (ücretsiz).

## 0.4.20
- **Uygulama içi güncelleme düzeltildi:** program kapanmadan kurulum başlıyordu; dosyalar kullanımdayken sessiz kurulum
  hiçbir şey demeden iptal oluyor, eski sürüm kalıyor ve program yeniden açılmıyordu. Artık kurulum program tamamen
  kapandıktan sonra çalışıyor, bitince yeni sürüm kendiliğinden açılıyor. Kurulamazsa eski program yeniden açılıp
  nedenini söylüyor.
- **Bu düzeltme bir kereliğine elle kurulum ister:** eski sürümdeki güncelleme düğmesi hâlâ eski yöntemi kullanır.
  Releases sayfasından GTA6Altyazi-Setup.exe'yi indirip kur (ayarlar ve anahtarlar korunur); sonraki güncellemeler
  düğmeyle sorunsuz gelir.
- Her kurulum dosyası artık yayınlanmadan önce gerçek bir Windows makinesinde baştan sona deneniyor: eski sürümü
  kurup uygulama içi güncellemeyle yenisine geçiyor, altyazılı oyun karesinden çeviriyi TV akışında görüyor,
  güvenlik duvarı iznini yazıp doğruluyor. Bunlardan biri bozuksa kurulum dosyası yayınlanmıyor.
- **API anahtarları artık kaybolmuyor:** boş bir kayıt dolu anahtarın üstüne yazamıyor (yalnız anahtar alanını kendin
  boşaltırsan silinir); anahtarlar ayrıca ayrı bir yedek dosyada tutuluyor ve ayar dosyasında yoksa oradan geri
  geliyor. Çeviri sayfası her açılışta anahtar alanlarını güncel ayardan dolduruyor (sihirbazda girilen anahtar orada
  boş görünüp "Kaydet"le silinmiyor).

## 0.4.18
- **Güvenlik duvarı "İzin ver" baştan yazıldı:** eskisi Windows'a komutu gönderip sonucunu hiç beklemiyordu; çalışıp
  çalışmadığı belli olmuyordu. Ağ "Ortak" ise (kablolu bağlantılarda Windows çoğu zaman böyle işaretler) verilen izin
  hiç işe yaramıyordu. Artık düğme ev ağını "Özel" yapıyor, izni ekliyor, sonucu doğruluyor ve ne olduğunu yazıyor
  (izin verildi / Windows'un sorusuna Hayır denildi / başka bir güvenlik programı engelliyor).
- Durum denetimi Windows'un "gelen bütün bağlantıları engelle" ayarını ve bu programa konmuş engel kurallarını da görüyor.

## 0.4.17 · Ayrıntılı TV denetimi
Programın TV kısmı baştan sona CouchSubs'ın gerçek TV'lerde denenmiş koduyla satır satır karşılaştırıldı; bulunan
hatalar düzeltildi.

**Bütün TV'ler**
- "TV hazır" artık TV uygulaması bu bilgisayara gerçekten bağlanınca yazıyor. Bağlanamazsa sebebi söyleniyor: Windows
  ağı "Ortak" sayıyor, güvenlik duvarı engelliyor ya da modemde misafir ağı / AP izolasyonu açık.
- Türkçe Windows'ta güvenlik duvarı durumu hiç görünmüyordu (karakter kodlaması hatası); düzeldi.
- Altyazı, İngilizcesi ekrandayken TV'de 15 saniye sonra kayboluyordu; artık yazı gidince kalkıyor.
- Wi-Fi kısa kopunca TV'de eski yazılar takılı kalıyordu; yeniden bağlanınca temizleniyor.
- Çeviri durdurulduktan sonra gelen geç çeviri TV'de takılı kalıyordu; artık basılmıyor.
- Aynı cümlenin düzelen okuması TV'de iki kez (üst üste) görünüyordu; artık yerini alıyor.
- Yardım, bildirim ve telefon kutularında çok satırlı İngilizce yazının alt satırları görünüyordu; Türkçe kutu artık
  tamamını örtüyor.
- Program iki kez açılırsa (ya da CouchSubs açıksa) sunucu portu sessizce paylaşılıyordu; artık açıkça uyarıyor.
- "Ağda ara" bilgisayarın bütün ev ağlarında arıyor; internet yokken takılı kalmıyor.
- chiaki penceresi program adına göre bulunuyor; tarayıcıda açık "chiaki-ng" sayfası yanlışlıkla yakalanmıyor.

**Google TV / Android TV**
- TV uygulaması CouchSubs'ın güncel koduyla eşitlendi: bazı TV'lerde katman moduna geçerken uygulamanın kapanması ve
  kumandadan açınca kapanması düzeldi.
- TV'de kaldırılmış ama kaydı kalmış eski kopya temizlenip yeniden kuruluyor; açılmayan uygulama bir kez yeniden
  kuruluyor.
- Hatalar Türkçe ve ne yapılacağıyla (Play Protect, yer yok, bağlantı koptu...).
- Kablosuz hata ayıklama ekranındaki IP:PORT yazılırsa onunla bağlanıyor; aynı anda iki bağlantı başlamıyor.

**Samsung**
- TV uygulamasına bu bilgisayarın adresi kurulumda yazılıyor (ağda aramadan bulur).
- TV'deki Host PC IP yanlışsa ne yazılması gerektiği söyleniyor.
- Ekran koruyucuyu kapatan Samsung kütüphanesi yükleniyor; TV uygulaması sürümü programla birlikte güncelleniyor.

**LG**
- Kurulum her seferinde 15 saniye sonra boş bir hatayla düşüyordu; kurulum komutu CouchSubs'tan birebir alındı.
- Eski webOS'lara bağlanılamıyordu (SSH algoritmaları); düzeldi. SFTP'si olmayan TV'lere de yükleniyor.
- TV anahtarı reddederse yenisi alınıyor; hatalar Türkçe. Ekran koruyucu oyunun üstüne çıkmıyor.

## 0.4.16
- **Google TV / Android TV'ye adb'siz, eşleştirmesiz bağlantı:** program artık TV'ye kendi ADB istemcisiyle bağlanıyor
  (CouchSubs'ın yöntemi). TV'de yalnız **USB hata ayıklama** açık olsun; eşleştirme kodu, Kablosuz hata ayıklama ve
  adb.exe gerekmiyor. Bilgisayardaki başka programların (emülatör, telefon aracı) adb'siyle çakışma da bitti. İlk
  bağlantıda TV "hata ayıklamaya izin verilsin mi?" diye bir kez sorar.
- Eşleştir'e basıldığında TV zaten doğrudan bağlantıyı kabul ediyorsa kod sorulmadan bağlanılır. Kablosuz eşleştirme
  yalnız USB hata ayıklaması olmayan TV'ler için "Gelişmiş" seçenek olarak kaldı.

## 0.4.15
- **Google TV kablosuz eşleştirme düzeltmesi:** "protocol fault (couldn't read status message)" hatası. Kablosuz hata
  ayıklama ana ekranındaki port yazıldığında eşleştirme olmuyordu; program artık TV'deki eşleştirme penceresinin
  doğru portunu ağdan kendisi bulur. Olmazsa ne yapılacağını Türkçe söyler (yanlış port / pencere kapandı / kod yanlış).
  Kodda boşluk olsa da kabul edilir. Başka bir programın (emülatör, telefon aracı) eski adb'si araya girdiğinde de
  aynı hata çıkıyordu: program adb'yi baştan başlatıp yeniden dener.

## 0.4.14
- **Kurulum sihirbazında TV markası seçimi:** Televizyon adımında Google TV / LG / Samsung seçilir, o markanın
  resimli adımları gelir (önceden sihirbaz yalnız Google TV'yi anlatıyordu). LG parolası ve bilgisayarın IP'si
  ilgili adımda gösterilir.
- **Samsung rehberi baştan, ayrıntılı ve resimli:** Uygulamalar sayfasına doğru giriş; rakam tuşu olmayan ince
  kumandada **123** tuşuyla ekrandaki rakamları tek tek seçme; olmazsa telefondan **SmartThings** kumandası ya da USB
  klavye; Developer mode, güç tuşuyla yeniden başlatma; Anynet+ ve Otomatik Kaynak Değiştirme'yi kapatma; TV'nin
  IP'sini bulma; HDMI girişini seçme.
- LG rehberi de ayrıntılandı (geliştirici hesabı, Content Store, Dev Mode, Key Server); Google TV'de TV'nin IP'sini
  bulma eklendi. Televizyon sayfasındaki anlatım artık rehberle aynı kaynaktan geliyor ve **Resimli anlat** düğmesi
  doğrudan o markanın rehberini açıyor.

## 0.4.13
- **Claude harcama sayacı:** ana ekranda gecikmenin altında "Claude: bu oturum 0,37 $ · saatte ~0,90 $" ve
  "Bu ay … · toplam …". Claude'un her yanıtta bildirdiği token sayısıyla Anthropic liste fiyatından hesaplanır
  (hızlı mod, önbellek ve "Ekranı çevir" dahil); hazır paketten ve önbellekten gelen çeviriler ücretsiz sayılır.
  Toplam bu bilgisayarda saklanır; kesin fatura console.anthropic.com'dadır.

## 0.4.12
- **Yardım kutusu alanı aşağı uzatıldı:** GTA 6'da sol üstteki yardım kutusu köşede değil biraz aşağıda çıkıyor; eski
  alan uzun kutuların son satırını kesiyordu. Alan artık ekranın ortasına kadar iniyor. Okuma alanlarını elle
  değiştirmediysen kendiliğinden düzelir.
- "Long guns" artık "uzun kollu silahlar" değil, "uzun namlulu silahlar" / "tüfekler" diye çevriliyor; önbellekteki
  eski yanlış çeviri bir kez silinir.

## 0.4.11
- Araç plakaları ("46EEK572", "5ABC 123") ve plakadaki eyalet yazısı ("LEONIDA") çevrilmiyor; yalnız özel addan oluşan
  yazılar (ör. tek başına "Vice City") da çevrilmeden bırakılıyor. "Ekranı çevir"de de geçerli.

## 0.4.10
- **Telefon mesajları için 4. okuma alanı:** sağ ortada açılan telefon/mesaj ekranı ayrıca okunup konuşma dilinde
  çevriliyor. Artık aynı anda dört yer çevriliyor: alttaki diyalog ve görev yazısı, sol üstteki yardım kutusu, sağ
  üstteki bildirimler ve sağdaki telefon mesajları. Okuma alanlarında "Sağ orta (telefon mesajları)" hazır konumu da var.
- Bu sürüm, uygulama içi güncellemenin ilk denemesi: 0.4.9'dan ana ekrandaki Güncelle düğmesiyle gelir.

## 0.4.9 · Paketler bizde, güncellemeler otomatik
- **Uygulama kendini güncelliyor:** yeni sürüm çıkınca ana ekranda "Yeni sürüm hazır" kartı; Güncelle'ye basınca iner,
  kendiliğinden kurulur ve program yeniden açılır. Ayarlar, anahtarlar ve paketler korunur. Bundan sonraki
  sürümler için kurulum dosyasını elle indirmeye gerek yok.
- **Paketler kendiliğinden güncelleniyor:** açılışta GTA 6 paketinin (ve bilgisayardaki diğer paketlerin) yenisi
  varsa sessizce iniyor. Ayarlar › Güncellemeler'den kapatılabilir.
- **GTA 6 dahil hazır paketler kurulumla birlikte geliyor:** kurar kurmaz GTA 6 satırları anında ve ücretsiz çıkar,
  indirmeye gerek yok.
- Paketler artık bu projenin kendi GitHub sayfasından iniyor ("paketler" sürümü). GitHub her 6 saatte bir CouchSubs
  ve GameTranslator'daki son hallerini alıp doğrulayarak buraya koyuyor; GTA 6 paketi büyüdükçe **Listeyi yenile** ile
  yenisi alınır. GitHub yanıt vermezse program doğrudan kaynağa döner.

## 0.4.8 · GTA 6 paketi
- **Hazır paketlere CouchSubs'ın paket sunucusu eklendi: GTA 6 paketi tek tıkla.** Çeviri sayfasındaki listede en üstte
  çıkar; oyuncular oynadıkça büyüdüğü için ara sıra **Listeyi yenile** ile yeniden indirilebilir. İndirilen dosya
  sunucunun verdiği SHA-256 ile doğrulanır.

## 0.4.7 · Ücretsiz çeviri
- **Claude şart değil:** kurulum sihirbazında ve Çeviri sayfasında yapay zekâ seçimi; ücretsiz seçenekler öne çıktı:
  Google Gemini (ücretsiz anahtar), DeepL Free, bilgisayarda çalışan Ollama / LM Studio (anahtar ve kota yok).
  Her seçeneğin yanında anahtar sayfasını açan düğme. Herkes kendi anahtarını kullanır.
- Yeni: **Yerel yapay zekâ** motoru (Ollama, LM Studio ya da OpenAI uyumlu başka bir sunucu).
- Düzeltme: Gemini seçeneği kurulum dosyasında çalışmıyordu (eksik paket); artık ek paket gerektirmeden çalışıyor,
  eskimiş model adında yenisine kendiliğinden geçiyor.
- Rehber'e "Ücretsiz çeviri (Gemini, DeepL, Ollama)" konusu.

## 0.4.6
- **Uygulamada Rehber sayfası:** kurulumdan yayına bütün süreçler resimli, adım adım. Konular: bilgisayar monitöründe
  oynamak (chiaki-ng), TV'de oynayıp bilgisayarın izlemesi, Google TV / LG / Samsung TV uygulaması, Discord yayını,
  OBS, GTA 6 için okuma alanları, hazır paketler, sorun giderme.
- Aynı rehber GitHub sayfasında da var; ikisi tek kaynaktan üretiliyor, hep aynı kalıyor.
- Yeni rehber görselleri: LG Developer Mode, Samsung Developer mode, Discord ekran paylaşımı, OBS tarayıcı kaynağı,
  okuma alanları, Başlat.
- Sürüm notları artık bu dosyadan Releases sayfasına yazılıyor.
- Düzeltme: tuş adı okunabilen ipuçları ("Press E to enter", "Hold [RB] to aim") yine çevriliyor; yalnız tuş simgesi
  okunamayanlar oyunun kendi yazısıyla bırakılıyor.

## 0.4.5 · GTA 6 günü
- GTA 6'da görev yazısı konuşmanın hemen altında dakikalarca duruyor: 6 saniyeden uzun ekranda kalan satır ayrı yazı
  sayılıyor, konuşmayla birleştirilip çevrilmiyor (boşluğa bakan kuralımız da duruyor).
- Simgesi okunamayan tuş ipuçları ("Press [RB] to take cover") çevrilmiyor; oyunun yazısı tuş simgesiyle görünür kalıyor.
- "TAKE AMMO PACK", "SIT" gibi kısa büyük harfli etkileşim yazıları altyazı sayılmıyor.
- Claude'a GTA için yerleşik Türkçe karşılık rehberi (hitaplar, küfürler, suç argosu, arayüz); sözlüğe GTA yer ve marka adları.
- Sihirbazda PS5'in "bağlandı" açılır penceresini gizleme ayarı.

## 0.4.4
- **Resimli kurulum sihirbazı:** "Nerede oynayacaksın?" seçimi (monitör / TV / ikisi), chiaki-ng ve PS5 eşleme için
  resimli alt adımlar, TV adımlarına görseller.

## 0.4.3
- Önbellek benzer ama farklı cümleleri karıştırmıyor ("Go to the bar" ≠ "Go to the car", "$5000" ≠ "$500").
- İki satıra bölünmüş tek cümle ikiye ayrılmıyor.
- Altyazıdan ayrılan paragraf TV'de de altyazı boyunda ve İngilizceyi örterek çiziliyor.
- chiaki pencere modunda başlık çubuğu ve siyah bantlar kırpılıyor (TV'de yazı kaymıyor).
- Aynı bölgedeki ayrı yazılar (görev yazısı + diyalog) ayrı çevrilip kendi yerine basılıyor.

## 0.4.1
- Yeni Android TV uygulaması (CouchSubs tabanlı), kendi imza anahtarımızla.

## 0.4.0
- TV uygulamaları CouchSubs'tan: LG, Samsung ve Android TV, gerçek TV'lerde denenmiş (TCL C6K dahil).
- Samsung'a Tizen Studio'suz kurulum; LG'de geliştirici modu süresinin her bağlanışta yenilenmesi.
- Hazır çeviri paketleri (GTA V, RDR2...) tek tıkla; önbelleği paket olarak paylaşma.
- Daha kötü okunan satırı atlama, oyun deyimleri, isimleri koruyup doğru Türkçe ek takma.
- Uyku engeli, tek tıkla güvenlik duvarı izni. Lisans AGPL-3.0.

## 0.3.x
- Argo düzeltme ve kalite öncelikli mod; İngilizce OCR modeli ve GTA 6 sözlüğü; LG ve Samsung desteğinin ilk hali.

## 0.2.0
- İlk Windows kurulum dosyası: arayüz, sihirbaz, okuma alanları, TV, OBS, telefon kumandası.
