package com.gta6altyazi.tv;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.media.tv.TvContract;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;
import android.media.tv.TvView;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * Yedek mod: TV başka uygulamaların üstüne çizmeye izin vermezse PS5'in HDMI görüntüsünü bu ekranın içinde
 * (TvView) oynatır ve altyazıyı üstüne çizer. Kumandada sol/sağ ile HDMI girişi değiştirilir, Geri ile çıkılır.
 */
public class HdmiActivity extends Activity {
    private TvView tv;
    private SubtitleView subs;
    private TextView hint;
    private EventStream stream;
    private final List<TvInputInfo> inputs = new ArrayList<>();
    private int current = 0;
    private final Handler main = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.BLACK);
        tv = new TvView(this);
        subs = new SubtitleView(this);
        hint = new TextView(this);
        hint.setTextColor(Color.WHITE);
        hint.setTextSize(18);
        hint.setBackgroundColor(Color.argb(170, 0, 0, 0));
        hint.setPadding(24, 12, 24, 12);
        FrameLayout.LayoutParams full = new FrameLayout.LayoutParams(-1, -1);
        root.addView(tv, full);
        root.addView(subs, new FrameLayout.LayoutParams(-1, -1));
        FrameLayout.LayoutParams hp = new FrameLayout.LayoutParams(-2, -2);
        hp.leftMargin = 40;
        hp.topMargin = 40;
        root.addView(hint, hp);
        setContentView(root);
        root.setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);

        SharedPreferences prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE);
        TvInputManager tim = (TvInputManager) getSystemService(Context.TV_INPUT_SERVICE);
        if (tim != null) {
            for (TvInputInfo info : tim.getTvInputList()) {
                if (info.getType() == TvInputInfo.TYPE_HDMI && info.getParentId() == null) inputs.add(info);
            }
            if (inputs.isEmpty()) {
                for (TvInputInfo info : tim.getTvInputList()) {
                    if (info.isPassthroughInput()) inputs.add(info);
                }
            }
        }
        String saved = prefs.getString("hdmi", null);
        for (int i = 0; i < inputs.size(); i++) {
            if (inputs.get(i).getId().equals(saved)) current = i;
        }
        tuneCurrent();

        String host = prefs.getString("host", null);
        if (host != null) {
            stream = new EventStream(host, new EventStream.Listener() {
                @Override public void onEvent(final String json) { main.post(() -> subs.handle(json)); }
                @Override public void onDisconnected() { main.post(() -> subs.clearAll()); }
            });
            stream.start();
        }
    }

    private void tuneCurrent() {
        if (inputs.isEmpty()) {
            showHint("HDMI girişi bulunamadı. Bu TV yedek modu desteklemiyor olabilir.", 0);
            return;
        }
        TvInputInfo info = inputs.get(current);
        tv.tune(info.getId(), TvContract.buildChannelUriForPassthroughInput(info.getId()));
        getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE).edit().putString("hdmi", info.getId()).apply();
        CharSequence label = info.loadLabel(this);
        showHint("Giriş: " + label + "   (◀ ▶ değiştir, Geri: çıkış)", 4000);
    }

    private void showHint(String text, long hideAfterMs) {
        hint.setText(text);
        hint.setVisibility(View.VISIBLE);
        main.removeCallbacksAndMessages("hint");
        if (hideAfterMs > 0) {
            main.postAtTime(() -> hint.setVisibility(View.GONE), "hint",
                    android.os.SystemClock.uptimeMillis() + hideAfterMs);
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (!inputs.isEmpty() && (keyCode == KeyEvent.KEYCODE_DPAD_LEFT || keyCode == KeyEvent.KEYCODE_DPAD_RIGHT)) {
            int n = inputs.size();
            current = (current + (keyCode == KeyEvent.KEYCODE_DPAD_RIGHT ? 1 : n - 1)) % n;
            tuneCurrent();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onDestroy() {
        if (stream != null) stream.stop();
        tv.reset();
        super.onDestroy();
    }
}
