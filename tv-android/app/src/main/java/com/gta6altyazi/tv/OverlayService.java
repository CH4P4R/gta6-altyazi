package com.gta6altyazi.tv;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.view.Gravity;
import android.view.WindowManager;

/** Tam ekran, dokunulmaz, saydam bir katman açar ve bilgisayardan gelen altyazıları çizer. */
public class OverlayService extends Service {
    private static final String CHANNEL = "altyazi";
    private WindowManager wm;
    private SubtitleView view;
    private EventStream stream;
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override
    public void onCreate() {
        super.onCreate();
        startAsForeground();
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        view = new SubtitleView(this);
        int type = Build.VERSION.SDK_INT >= 26
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                        | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        wm.addView(view, lp);
    }

    private void startAsForeground() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        Notification.Builder b;
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(new NotificationChannel(CHANNEL, "Altyazı", NotificationManager.IMPORTANCE_MIN));
            b = new Notification.Builder(this, CHANNEL);
        } else {
            b = new Notification.Builder(this);
        }
        Notification n = b.setContentTitle("GTA6 Altyazı")
                .setContentText("Türkçe altyazı katmanı açık")
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .build();
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        } else {
            startForeground(1, n);
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String host = intent != null ? intent.getStringExtra("host") : null;
        if (host == null) {
            host = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE).getString("host", null);
        }
        if (host != null && (stream == null || !host.equals(stream.host))) {
            if (stream != null) stream.stop();
            stream = new EventStream(host, new EventStream.Listener() {
                @Override public void onEvent(final String json) { main.post(() -> view.handle(json)); }
                @Override public void onDisconnected() { main.post(() -> view.clearAll()); }
            });
            stream.start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (stream != null) stream.stop();
        if (view != null) wm.removeView(view);
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
