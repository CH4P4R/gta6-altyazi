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
 * Bilgisayar şöyle başlatır: am start -n com.gta6altyazi.tv/.MainActivity --es host 192.168.1.10:8787
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
        host = prefs.getString("host", null);

        if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Üstüne çizme izni yok. Bilgisayardaki programdan TV kurulumunu tekrar çalıştır.",
                    Toast.LENGTH_LONG).show();
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
