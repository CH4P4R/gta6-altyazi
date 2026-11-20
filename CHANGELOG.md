# Sürüm notları

Her sürümün kurulum dosyası [Releases](https://github.com/CH4P4R/gta6-altyazi/releases) sayfasındadır. Eski bir
sürümün üstüne kurabilirsin; ayarların ve Claude anahtarın korunur.

## 0.4.19
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
