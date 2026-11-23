# GTA6 Altyazı ortak çeviri havuzu (sunucu)

Oyuncuların yapay zekâyla çevirdiği satırlar bu sunucuda toplanır. Aynı satırın aynı Türkçesini en az iki farklı
kurulum gönderince satır "havuz paketine" girer ve herkese ücretsiz dağıtılır. Böylece oynayan herkesin yapay zekâ
harcaması düşer, altyazı hızlanır.

- Yalnız Python 3 gerekir (ek kurulum yok), veri tek bir SQLite dosyasında.
- Kişisel bilgi tutulmaz: IP yalnız bellekte, her gün değişen tuzla özetlenip hız sınırı için kullanılır.
- Saçma satırlar (çevrilmemiş, bağlantı içeren, İngilizce kalmış) kabul edilmez; en çok oyu alan Türkçe kazanır.

## Kurulum (VPS, Ubuntu 22.04+ / Debian 12+)

Alan adın varsa önce DNS'te bir A kaydı aç (ör. `havuz.alanadin.com` → sunucunun IP'si). Sonra sunucuda:

```bash
git clone https://github.com/CH4P4R/gta6-altyazi.git
```

```bash
sudo bash gta6-altyazi/sunucu/havuz/kur.sh havuz.alanadin.com
```

Alan adın yoksa adresi boş bırak (`sudo bash gta6-altyazi/sunucu/havuz/kur.sh`); havuz `http://SUNUCU_IP:8787`
adresinde açılır. Betiğin en sonda yazdığı adresi uygulamada **Ayarlar → Çeviri → Ortak çeviri havuzu** alanına yaz
(ya da bana söyle, uygulamaya varsayılan olarak koyayım).

Güncellemek için depoyu çekip betiği yeniden çalıştırman yeter (`git -C gta6-altyazi pull`). Ayarlar
`/etc/gta6-havuz/ayar.env` dosyasında.

## Yönetim

```bash
sudo -u havuz HAVUZ_VERI=/var/lib/gta6-havuz/havuz.sqlite python3 /opt/gta6-havuz/havuz_sunucu.py istatistik
```

```bash
sudo -u havuz HAVUZ_VERI=/var/lib/gta6-havuz/havuz.sqlite python3 /opt/gta6-havuz/havuz_sunucu.py sil "English line"
```

Günlük: `journalctl -u gta6-havuz -f`. Yedek: `/var/lib/gta6-havuz/havuz.sqlite` dosyasını kopyalamak yeterli.
