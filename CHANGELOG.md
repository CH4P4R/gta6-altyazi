# Sürüm notları

Her sürümün kurulum dosyası [Releases](https://github.com/CH4P4R/gta6-altyazi/releases) sayfasındadır. Eski bir
sürümün üstüne kurabilirsin; ayarların ve Claude anahtarın korunur.

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
