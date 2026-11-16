# GTA 6 Türkçe Altyazı

GTA 6'daki İngilizce yazıları gerçek zamanlı okuyup Türkçesini **aynı yere, İngilizcenin üstüne** yazan Windows uygulaması. Alt ortadaki diyalog altyazılarını, sol üstteki yardım kutusunu ve sağ üstteki bildirimleri çevirir.

Tek bilgisayar iki yere birden altyazı verir:

```
PS5 ──HDMI──► TV (sen buradan oynarsın, gecikmesiz)
 │              ▲  TV uygulaması Türkçeyi oyunun üstüne çizer
 │              │  (ev ağı)
 └─ chiaki-ng ─► Kasa: okur → çevirir ──┤
   (2. PSN hesabı)                      └─► Discord Go Live: arkadaşlar Türkçe altyazılı izler
```

> **İkinci PSN hesabı şart.** chiaki-ng'ye kendi hesabınla bağlanırsan TV'deki kolun kopar. Ücretsiz ikinci bir PSN hesabı aç, PS5'te bu hesapla bir kez oturum açıp Uzaktan Oynatma'yı etkinleştir ve chiaki-ng'yi bu hesapla kaydet.

## Nasıl çalışıyor, neden hızlı?

```
PS5 ──► chiaki-ng penceresi / capture kart
          │  (1 kare, ~8-16 ms)
          ▼
   Bölge tespiti  ── her karede ~1-2 ms; sadece yazı DEĞİŞTİĞİNDE devam eder
          │
          ▼
   OCR (GPU)      ── satırlar zaten ayrılmış, sadece tanıma modeli çalışır
          │
          ├──► Önbellek ──────────────► (daha önce görüldüyse 0 ms)
          ├──► Yerel model (GPU) ─────► ekrana hemen basılır (~15-40 ms)
          └──► Claude Opus 5.5 ───────► birkaç yüz ms sonra daha doğal çeviriyle
                                        günceller ve önbelleğe yazar
```

- **Ağır iş sadece yazı değişince yapılır.** Her karede bölgedeki "konturlu beyaz/renkli yazı" pikselleri çıkarılıp bir önceki kareyle karşılaştırılır. Yeni altyazı çıktığı ilk karede OCR başlar.
- **Hiçbir şey birbirini beklemez.** Yakalama sadece en son kareyi tutar. Çeviriler ayrı iş parçacıklarında çalıştığı için yavaş bir çeviri yeni altyazının okunmasını geciktirmez.
- **İki katmanlı çeviri.** Yerel model hemen bir çeviri gösterir, Claude daha iyisini gönderince yazı yerinde güncellenir. Claude'a önceki 6 diyalog satırı bağlam olarak gider, böylece hitaplar ve anlam tutarlı kalır.
- **Önbellek.** Her çeviri `cache.sqlite`'a yazılır. OCR bir harfi yanlış okusa bile benzerlikle bulunur. Tekrar eden yardım mesajları ve bildirimler ikinci kez görüldüğünde anında ve en kaliteli haliyle gelir.
- **Gecikme göstergesi.** Sağ üstte her çevirinin yakalamadan ekrana kaç ms sürdüğü yazar.

Tahmini gecikme (RTX 3060-4060): ilk Türkçe yazı **~40-80 ms**, Claude'un iyileştirmesi **+0.4-1.5 sn**, önbellekteki metin **~0 ms**. GPU ölçümleri senin bilgisayarında doğrulanacak. Geliştirme ortamında CPU ile ölçülen değerler: tespit 1.6 ms/bölge, OCR 13-55 ms.

## Donanım: hangi yolu seçmeli?

| | chiaki-ng (önerilen başlangıç) | Capture kart |
|---|---|---|
| Ek masraf | Yok | Kart (ör. Elgato HD60 X, AVerMedia GC553/GC575) |
| PS5 nerede durur | Herhangi bir yerde, ağ üzerinden bağlanır | Bilgisayarın yanında (USB + HDMI) |
| Senin ekranındaki gecikme | Akış gecikmesi ~40-100 ms | Passthrough ile TV/monitörde 0 ms |
| Görüntü kalitesi | Sıkıştırmalı (OCR yine de çalışıyor) | Kayıpsıza yakın |
| `config.yaml` | `kaynak.tur: pencere`, `gosterim.mod: overlay` | `kaynak.tur: capture`, `gosterim.mod: pencere` |

**chiaki-ng neden resmi Remote Play'den iyi:** daha yüksek bitrate, 1080p60, daha düşük gecikme ve donanımsal kod çözme sunuyor. Kurulum: [chiaki-ng](https://github.com/streetpea/chiaki-ng) → PS5'i kaydet (PSN hesap kimliği + PS5'te Ayarlar > Sistem > Uzaktan Oynatma > Cihazı Eşleştir kodu) → ayarlardan 1080p, 60 fps, en yüksek bitrate ve PS5'i kabloyla bağla.

**Bazı günler TV'den, bazı günler monitörden:** İkisi aynı anda çalışır. Kasa chiaki-ng ile okur ve çevirir. Türkçe yazı hem TV'deki uygulamaya hem de kasanın ekranındaki katmana (ve Discord yayınına) gider. Monitörden oynadığın günlerde chiaki penceresinden, TV'den oynadığın günlerde TV'den oynarsın. Hiçbir ayarı değiştirmen gerekmez.

## Kurulum (Windows 10/11, NVIDIA)

1. [Python 3.12](https://www.python.org/downloads/)'yi kur, "Add python.exe to PATH" seçeneğini işaretle.
2. Bu klasörde `kur.bat`'a çift tıkla. Kütüphaneleri, CUDA dosyalarını ve yerel çeviri modelini (Helsinki-NLP OPUS-MT, ~300 MB) kurar.
3. Claude API anahtarını [console.anthropic.com](https://console.anthropic.com)'dan al ve bir kere çalıştır:
   ```bat
   setx ANTHROPIC_API_KEY "sk-ant-..."
   ```
4. chiaki-ng'yi aç ve PS5'e bağlan. Sonra `baslat.bat`'ı çalıştır.

## TV kurulumu (Google/Android TV, ör. TCL)

TV'de bir kez yapılır:
1. **Ayarlar › Sistem › Hakkında › Android TV OS derlemesi** satırına art arda 7 kez bas ("Artık geliştiricisiniz" yazar).
2. **Ayarlar › Sistem › Geliştirici seçenekleri › USB hata ayıklama**'yı aç.
3. Bilgisayarda:
   ```bat
   baslat.bat tv bul
   baslat.bat tv kur 192.168.1.xx
   ```
4. TV'de "Hata ayıklamaya izin verilsin mi?" sorusu çıkınca **Bu bilgisayardan her zaman izin ver**'i işaretle ve **İzin ver**'e bas.
5. Çıkan IP'yi `config.local.yaml`'a yaz, sonraki açılışlarda TV uygulaması kendiliğinden başlar:
   ```yaml
   tv:
     ip: "192.168.1.xx"
   ```

Windows güvenlik duvarı ilk açılışta sorarsa **Özel ağlar**'a izin ver, yoksa TV bilgisayara bağlanamaz. TV görüntüyü kenarlardan kırpıyorsa (overscan) `tv.kalibrasyon` ile kaydırabilirsin.

TV'de İngilizce yazı anında görünür, Türkçesi ~0.1-0.2 sn sonra üstüne gelir. Bunun sebebi kasanın görüntüyü chiaki üzerinden biraz geç alması. Discord'daki arkadaşların ise Türkçeyi İngilizceyle aynı karede görür.

TV uygulamasının kaynağı `tv-android/` klasöründe. APK, GitHub Actions ile `tv-android/release/` klasörüne otomatik derlenir.

**Discord'da konuşmak:** Bir Discord hesabı aynı anda tek sesli kanalda olabiliyor. Kasa yayını ikinci bir Discord hesabıyla açarsa sen ana hesabınla PS5'in Discord sesli sohbetinden, Mac'ten ya da telefondan konuşabilirsin.

## Komutlar

```bat
baslat.bat                 :: çalıştır
baslat.bat pencereler      :: açık pencereler (chiaki başlığı farklıysa config'e yaz)
baslat.bat kameralar       :: capture kartlar ve ses girişleri
baslat.bat kalibre         :: o anki kareyi bölgeler + algılanan yazıyla kalibrasyon.png'ye kaydet
baslat.bat test ekran.png  :: bir ekran görüntüsünde OCR + çeviriyi dene
baslat.bat tv bul          :: ev ağındaki Android/Google TV'yi bul
baslat.bat tv kur [ip]     :: TV uygulamasını kur/güncelle ve başlat
```

**Discord'da yayın:** overlay modunda ekranın tamamını paylaş (Türkçe yazı ayrı bir katman olduğu için sadece chiaki penceresini paylaşırsan görünmez). Capture kart modunda sadece "GTA6 Altyazi" penceresini paylaşman yeterli. `F11` ile tam ekran olur.

## GTA 6 çıkınca yapılacak ayar

Bölgelerin yeri ve yazı renkleri GTA V'e göre tahmin edildi. Oyun çıkınca `baslat.bat kalibre` ile birkaç kare (altyazı, yardım kutusu, bildirim, telefon) kaydedip `kalibrasyon_ham.png` dosyalarını paylaş, `config.yaml` → `bolgeler` kısmını gerçek arayüze göre ayarlarız. Kırmızı boyanan pikseller uygulamanın "yazı" saydığı yerlerdir.

## Ayarlar (özet)

- `ceviri.kalite`: `claude` (varsayılan, en iyi kalite) | `gemini` | `deepl` | `yok`
- `ceviri.claude_model`: `claude-opus-5-5`. Daha ucuz ve hızlısı için `claude-haiku-5-5` yazabilirsin.
- `ceviri.claude_hizli_mod`: Opus 5.5 hızlı modu (çıktı ~2.5 kat hızlı, fiyat 2 kat). Hızlı modun ayrı limiti dolarsa uygulama kendiliğinden normal hıza geçer.
- `ceviri.sozluk`: zorunlu terimler. Yapay zekaya verilir.
- `bolgeler[].sabit_kare`: 0 = en hızlı. Yazılar yavaşça beliriyorsa 1 yap.
- `bolgeler[].kutu_opaklik`: İngilizceyi kapatan kutu (255 = tam kapalı).

Kişisel ayarlar ve anahtarlar için `config.local.yaml` oluştur (git'e girmez). Bu dosya `config.yaml`'ın üstüne yazılır.

## Geliştirme

```bash
pip install -r requirements.txt pytest pillow
python -m pytest tests
```

`tests/synth.py` gürültülü arka plan, JPEG bozulması, konturlu altyazı ve yarı saydam yardım kutusu içeren GTA tarzı sahte kareler üretir.

## Yol haritası

- [ ] GTA 6 gerçek ekran görüntüleriyle bölge/renk kalibrasyonu
- [ ] Telefon, harita ve menüler için tam ekran OCR modu (kısayol tuşuyla)
- [x] Google/Android TV katman uygulaması ve ağdan otomatik kurulum
- [ ] TV'de katman izni olmayan modeller için HDMI'yı uygulama içinde gösterme (TvView)
- [ ] Capture kart modunda izleyiciler için görüntüyü geciktirip altyazıyla tam aynı karede gösterme
- [ ] İngilizce'ye özel PP-OCRv4 tanıma modeli (`ocr.model`)
