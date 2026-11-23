#!/usr/bin/env bash
# GTA6 Altyazı ortak çeviri havuzunu bir Linux VPS'e (Ubuntu 22.04+/Debian 12+) kurar ya da günceller.
#
#   sudo bash kur.sh havuz.alanadin.com     # alan adıyla (önerilen): Caddy ile HTTPS, sertifika kendiliğinden
#   sudo bash kur.sh                         # alan adı yoksa: http://SUNUCU_IP:8787 (şifresiz bağlantı)
#
# Alan adının DNS kaydı (A kaydı) önce bu sunucunun IP'sine yönlendirilmiş olmalı.
set -euo pipefail
DOMAIN="${1:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "sudo ile çalıştır: sudo bash kur.sh $DOMAIN"; exit 1; }

command -v python3 >/dev/null || { apt-get update -q && apt-get install -y -q python3; }
id havuz >/dev/null 2>&1 || useradd --system --home /var/lib/gta6-havuz --shell /usr/sbin/nologin havuz
install -d -o havuz -g havuz -m 750 /var/lib/gta6-havuz
install -d -m 755 /opt/gta6-havuz
install -m 644 "$HERE/havuz_sunucu.py" /opt/gta6-havuz/havuz_sunucu.py

if [ -n "$DOMAIN" ]; then
  HOST=127.0.0.1; VEKIL=1
else
  HOST=0.0.0.0; VEKIL=0
fi
mkdir -p /etc/gta6-havuz
[ -f /etc/gta6-havuz/ayar.env ] || cat > /etc/gta6-havuz/ayar.env <<ENV
# Değiştirince: sudo systemctl restart gta6-havuz
HAVUZ_HOST=$HOST
HAVUZ_PORT=8787
HAVUZ_VEKIL=$VEKIL
# Bir satırın herkese dağıtılması için aynı Türkçeyi gönderen farklı kurulum sayısı
HAVUZ_MIN_OY=2
HAVUZ_OYUNLAR=gta-6
HAVUZ_VERI=/var/lib/gta6-havuz/havuz.sqlite
ENV
install -m 644 "$HERE/gta6-havuz.service" /etc/systemd/system/gta6-havuz.service
systemctl daemon-reload
systemctl enable --now gta6-havuz
systemctl restart gta6-havuz

if [ -n "$DOMAIN" ]; then
  if ! command -v caddy >/dev/null; then
    apt-get update -q && apt-get install -y -q caddy || {
      echo "Caddy kurulamadı. https://caddyserver.com/docs/install adresindeki adımlarla kurup betiği yeniden çalıştır."; exit 1; }
  fi
  if ! grep -q "# gta6-havuz" /etc/caddy/Caddyfile 2>/dev/null; then
    sed "s/ALAN_ADI/$DOMAIN/" "$HERE/Caddyfile" >> /etc/caddy/Caddyfile
  fi
  systemctl enable --now caddy
  systemctl reload caddy || systemctl restart caddy
  command -v ufw >/dev/null && ufw status | grep -q active && { ufw allow 80/tcp; ufw allow 443/tcp; } || true
  URL="https://$DOMAIN"
else
  command -v ufw >/dev/null && ufw status | grep -q active && ufw allow 8787/tcp || true
  URL="http://$(hostname -I | awk '{print $1}'):8787"
fi
sleep 2
echo
echo "Havuz çalışıyor. Deneme:  curl $URL/v1/saglik"
echo "Uygulamadaki havuz adresi: $URL"
echo "İstatistik: sudo -u havuz HAVUZ_VERI=/var/lib/gta6-havuz/havuz.sqlite python3 /opt/gta6-havuz/havuz_sunucu.py istatistik"
