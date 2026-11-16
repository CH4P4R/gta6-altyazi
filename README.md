# GTA6 Altyazı

GTA 6'daki İngilizce yazıları gerçek zamanlı okuyup Türkçesini **İngilizcenin tam yerine, daha büyük yazıyla** basan Windows uygulaması. Diyalog altyazılarını, sol üstteki yardım kutusunu ve sağ üstteki bildirimleri sürekli çevirir. Telefon, menü ve harita gibi diğer yazılar için tek tuşla tüm ekranı çevirir.

Tek bilgisayar dört yere birden altyazı verir:

```
PS5 ──HDMI──► TV (sen buradan oynarsın, gecikmesiz)
 │              ▲  TV uygulaması Türkçeyi oyunun üstüne çizer
 │              │  (ev ağı)
 └─ chiaki-ng ─► Kasa: okur → çevirir ──┼─► Kasanın ekranı (chiaki'nin üstünde katman)
   (2. PSN hesabı)                      ├─► Discord Go Live: arkadaşlar Türkçe altyazılı izler
                                        ├─► OBS tarayıcı kaynağı (/obs)
                                        └─► Telefon kumandası (/kumanda)
```

## İndir ve kur

1. GitHub'da bu deponun **Releases** sayfasından `GTA6Altyazi-Setup.exe`'yi indir.
2. Çalıştır. Yönetici izni istemez. "Windows kişisel bilgisayarınızı korudu" uyarısı çıkarsa **Ek bilgi › Yine de çalıştır**'a bas.
3. İlk açılışta 5 adımlı sihirbaz seni karşılar: PS5 bağlantısı, TV, çeviri ve hazır.

Kurulumun içinde her şey var: çeviri modeli (internetsiz çalışır), OCR, TV uygulaması ve TV'ye kurmak için gereken `adb`. Ayrıca bir şey indirmen gerekmez.

## Neden hızlı?

```
Kare (1 kare, ~8-16 ms)
  → Bölge tespiti: her karede ~1-2 ms, ağır iş sadece yazı DEĞİŞİNCE
  → OCR (GPU, satırlar önceden ayrılmış): birkaç ms
  → Önbellek ............ daha önce görüldüyse 0 ms
  → Yerel model (GPU) ... ekrana hemen basılır (~15-40 ms)
  → Claude Opus 5.5 ..... birkaç yüz ms sonra daha doğal haliyle günceller, önbelleğe yazar
```

- **Hiçbir şey birbirini beklemez.** Yakalama sadece en son kareyi tutar. Çeviriler ayrı iş parçacıklarında çalıştığı için yavaş bir çeviri yeni altyazının okunmasını geciktirmez.
- **İki katmanlı çeviri.** Yerel model hemen gösterir, Claude daha iyisini gönderince yazı yerinde güncellenir. Claude'a önceki 6 diyalog satırı bağlam olarak gider. Argo, küfür ve espriler yumuşatılmaz, isimler (Jason, Lucia, Vice City...) çevrilmez.
- **Önbellek.** OCR bir harfi yanlış okusa bile benzerlikle bulunur. Tekrar eden yardım mesajları anında ve en kaliteli haliyle gelir.
- **Gecikme göstergesi.** Ana ekranda ve oyunun sağ üstünde her çevirinin kaç ms sürdüğü görünür.

## Evdeki kurulum (kasa + TCL Google TV + MacBook)

### 1. Ağ
- **Kasa:** kabloyla modeme.
- **PS5:** mümkünse kabloyla. chiaki'nin görüntüsü PS5'ten kasaya bu yoldan gider.
- **TV:** kabloya alabiliyorsan al. Wi-Fi'da da çalışır.
- Hepsi aynı ağda olmalı. TV bulunamıyorsa menzil arttırıcı cihazları ayırıyor demektir, TV'yi kabloya almak çözer.

### 2. İkinci PSN hesabı (chiaki için)
chiaki-ng'ye kendi hesabınla bağlanırsan TV'deki kolun kopar.
1. [PlayStation sitesinden](https://www.playstation.com) ücretsiz yeni bir hesap aç ve PS5'te bu hesapla bir kez giriş yap.
2. Bu kullanıcıdayken **Ayarlar › Sistem › Uzaktan Oynatma**: aç ve **Cihazı Bağla**'ya bas (8 haneli kod çıkar).
3. [chiaki-ng](https://github.com/streetpea/chiaki-ng/releases)'yi kur. PS5'i kaydederken ikinci hesapla giriş yap ve kodu gir. Ayarlardan 1080p, 60 fps ve en yüksek bitrate seç.
4. **Ayarlar › Sistem › Güç Tasarrufu › Dinlenme Modunda Kullanılabilir Özellikler**: **İnternete Bağlı Kal** ve **Ağ Üzerinden PS5'i Açmayı Etkinleştir** açık olsun.

### 3. TCL 65C6K (Google TV)
1. **Ayarlar › Sistem › Hakkında › Android TV OS derlemesi** satırına 7 kez bas.
2. **Ayarlar › Sistem › Geliştirici seçenekleri**: **USB hata ayıklama**'yı aç. Yoksa ya da TV bulunamazsa **Kablosuz hata ayıklama**'yı aç.
3. Uygulamada **Televizyon** sayfası: **Ağda ara › Bağlan, kur ve başlat**. TV'de çıkan "Hata ayıklamaya izin verilsin mi?" sorusunda **Her zaman izin ver**'i işaretleyip **İzin ver**'e bas.
   - Kablosuz hata ayıklamada önce TV'deki **Eşleştirme koduyla cihaz eşleştir** ekranındaki adres:port ve kodu **Eşleştir** kısmına yaz.
4. **Deneme altyazısı gönder** ile TV'de yerini kontrol et. Kayıyorsa konum kaydırıcılarıyla düzelt.

TV oyunun üstüne çizmeye izin vermezse uygulama kendiliğinden **yedek moda** geçer. Bu modda PS5'in HDMI görüntüsü TV uygulamasının içinde açılır ve altyazı üstüne çizilir. Kumandada sol/sağ ile HDMI girişi değiştirilir.

TV'de İngilizce yazı anında görünür, Türkçesi ~0.1-0.2 sn sonra üstüne gelir. Bunun sebebi kasanın görüntüyü chiaki üzerinden biraz geç alması. Discord'daki arkadaşların ise Türkçeyi İngilizceyle aynı karede görür.

### 4. Discord (yayın kasadan, konuşma Mac'ten)
- **Kasa:** ikinci bir Discord hesabıyla sesli kanala gir. Mikrofonu ve sesi kapat, sonra **Ekran paylaş › Ekranlar › chiaki'nin olduğu monitör › Go Live**. Tüm ekranı paylaşmak şart: Türkçe yazı ayrı bir katman olduğu için sadece chiaki penceresini paylaşırsan görünmez.
- **MacBook:** kendi hesabınla aynı kanala gir ve konuş. Kulaklık kullan, yoksa mikrofon TV'nin sesini de alır.
- Kasanın ekranı kilitlenir ya da uykuya geçerse okuma durur. **Ayarlar › Sistem › Güç ve pil**: ekran ve uyku için **Hiçbir zaman** seç. chiaki penceresini simge durumuna küçültme.

## Uygulamanın sayfaları

| Sayfa | Ne yapar |
|---|---|
| **Ana ekran** | Büyük başlat/durdur düğmesi, ortalama gecikme grafiği, PS5/TV/çeviri motoru durumları, telefon kumandası QR kodu, canlı çeviri akışı (kopyalama düğmeli) |
| **Okuma alanları** | Oyun görüntüsü üstünde bölgeleri fareyle taşı ve boyutlandır. Hazır konumlar sunar, yazı sayılan pikselleri kırmızıyla gösterir, Türkçe yazı boyutu ve kapatma kutusu buradan ayarlanır |
| **Televizyon** | TV'yi ağda bulma, eşleştirme, kurma, mod seçimi (katman/yedek), konum ayarı, deneme altyazısı |
| **Çeviri** | Yerel model / Google, Claude / Gemini / DeepL, API anahtarı, deneme çevirisi, sözlük |
| **Geçmiş** | Oturumdaki tüm çeviriler. Arama yapılabilir, metin olarak kaydedilebilir |
| **Ayarlar** | Görüntü kaynağı (chiaki / capture kart), gösterim, kısayollar, OBS adresi, sihirbazı tekrar açma |

**Kısayollar:**
- **Ctrl+Shift+9:** Ekrandaki her şeyi çevirir. Tekrar basınca ya da 20 saniye sonra kapanır.
- **Ctrl+Shift+0:** Duraklatır / devam ettirir.

TV'den oynarken aynı düğmeler telefon kumandasında da var. QR kodunu okutman yeterli.

## GTA 6 çıkınca yapılacak ayar

Bölgelerin yeri ve yazı renkleri GTA V'e göre tahmin edildi. Oyun çıkınca **Okuma alanları › Görüntü al** ile bir kare al ve kutuları gerçek altyazının, yardım kutusunun ve bildirimin üstüne çek. Kırmızı noktalar yazının üstünde toplanıyorsa ayar doğrudur.

## OBS ile yayın (capture kart kullananlar için)

OBS'de **Kaynak ekle › Tarayıcı**: URL `http://localhost:8787/obs`, genişlik 1920, yükseklik 1080. Bu kaynağı oyun görüntüsünün üstüne koy. Capture kartı OBS kullanıyorsa OBS'de **Sanal Kamerayı Başlat**'a bas ve uygulamada kaynak olarak capture kart + OBS Virtual Camera'yı seç.

## Geliştirme

```bash
pip install -r requirements.txt pytest pillow
python -m altyazi              # arayüz
python -m altyazi calistir     # arayüzsüz
python -m pytest tests
```

| Klasör | İçerik |
|---|---|
| `altyazi/` | Çekirdek: yakalama, tespit, OCR, çeviri, hat, sunucu, TV kurulumu |
| `altyazi/ui/` | Arayüz (PySide6) |
| `tv-android/` | Android TV uygulaması (katman servisi + HDMI yedek modu) |
| `packaging/` | PyInstaller tarifi, Inno Setup kurulum betiği, görseller |
| `tests/` | Testler. `synth.py` GTA tarzı sahte kareler üretir |

- **Derleme:** TV APK'sı `tv-android/` değişince GitHub Actions ile otomatik derlenir. Windows kurulum dosyası, commit mesajında `[exe]` geçince (ya da Actions'tan elle) derlenir ve Releases'e konur.
- **Yerel çeviri modeli:** `python tools/model_indir.py` ile hazırlanır.
