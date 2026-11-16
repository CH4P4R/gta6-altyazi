package com.gta6altyazi.tv;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Toast;

/**
 * Görünmez başlatıcı: bilgisayarın adresini kaydeder, katman servisini başlatır ve hemen kapanır,
 * böylece TV önceki ekrana (PS5'in HDMI girişine) geri döner.
 * Bilgisayar şöyle başlatır: am start -n com.gta6altyazi.tv/.MainActivity --es host 192.168.1.10:8787 [--es mod hdmi]
 * mod=katman (varsayılan): TV'nin kendi HDMI ekranının üstüne çizer. mod=hdmi: yedek mod (HdmiActivity).
 */
public class MainActivity extends Activity {
    static final String PREFS = "ayarlar";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String host = getIntent().getStringExtra("host");
        if (host != null && !host.isEmpty()) {
            prefs.edit().putString("host", host).apply();
        }
        String mode = getIntent().getStringExtra("mod");
        if (mode != null) prefs.edit().putString("mod", mode).apply();
        mode = prefs.getString("mod", "katman");
        host = prefs.getString("host", null);
        boolean canOverlay = Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this);

        if (host != null && ("hdmi".equals(mode) || !canOverlay)) {
            // Yedek mod: HDMI görüntüsünü uygulamanın içinde göster, altyazıyı üstüne çiz
            stopService(new Intent(this, OverlayService.class));
            startActivity(new Intent(this, HdmiActivity.class));
        } else if (host == null) {
            Toast.makeText(this, "Bilgisayarın adresi bilinmiyor. Bilgisayardaki programı başlat.",
                    Toast.LENGTH_LONG).show();
        } else {
            Intent svc = new Intent(this, OverlayService.class).putExtra("host", host);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(svc); else startService(svc);
            Toast.makeText(this, "GTA6 Altyazı açık (" + host + ")", Toast.LENGTH_SHORT).show();
        }
        finish();
    }
}
