package com.gta6altyazi.tv;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.View;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Bilgisayardaki overlay.py ile aynı yerleşim: İngilizce yazının yerini (kare oranı olarak) siyah kutuyla kapatır,
 * Türkçeyi aynı satır yüksekliğinde ortasına yazar; sığmazsa çapa yönüne doğru büyür.
 */
class SubtitleView extends View {
    static class Item {
        float[] rect = new float[4];
        float[] zone = new float[4];
        float lineH;
        String text, align, anchor;
        int opacity;
        float scale;
    }

    private final Map<String, Item> items = new LinkedHashMap<>();
    private final Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint box = new Paint(Paint.ANTI_ALIAS_FLAG);
    // TV ekranı ile oyun görüntüsü arasındaki fark (overscan) için düzeltme; bilgisayardan gelir
    private float offX = 0, offY = 0, scaleX = 1, scaleY = 1;

    SubtitleView(Context ctx) {
        super(ctx);
        Typeface tf = Typeface.create("sans-serif-medium", Typeface.NORMAL);
        fill.setTypeface(tf);
        fill.setColor(Color.WHITE);
        stroke.setTypeface(tf);
        stroke.setColor(Color.BLACK);
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeJoin(Paint.Join.ROUND);
        setWillNotDraw(false);
    }

    void handle(String json) {
        try {
            JSONObject o = new JSONObject(json);
            String type = o.optString("type");
            if ("clear".equals(type)) {
                items.remove(o.getString("zone"));
            } else if ("clear_all".equals(type)) {
                items.clear();
            } else if ("show".equals(type)) {
                Item it = new Item();
                read(o.getJSONArray("rect"), it.rect);
                JSONArray z = o.optJSONArray("zone_rect");
                if (z != null) read(z, it.zone); else it.zone = it.rect.clone();
                it.lineH = (float) o.optDouble("line_h", 0.035);
                it.text = o.optString("text");
                it.align = o.optString("align", "orta");
                it.anchor = o.optString("anchor", "alt");
                it.opacity = o.optInt("box_opacity", 255);
                it.scale = (float) o.optDouble("font_scale", 1.0);
                JSONObject cal = o.optJSONObject("tv");
                if (cal != null) {
                    offX = (float) cal.optDouble("x", 0); offY = (float) cal.optDouble("y", 0);
                    scaleX = (float) cal.optDouble("w", 1); scaleY = (float) cal.optDouble("h", 1);
                }
                items.put(o.getString("zone"), it);
            }
            invalidate();
        } catch (Exception ignored) {
            // bozuk mesajı atla
        }
    }

    void clearAll() {
        if (!items.isEmpty()) {
            items.clear();
            invalidate();
        }
    }

    private static void read(JSONArray a, float[] out) throws Exception {
        for (int i = 0; i < 4; i++) out[i] = (float) a.getDouble(i);
    }

    @Override
    protected void onDraw(Canvas c) {
        float W = getWidth() * scaleX, H = getHeight() * scaleY;
        float X = getWidth() * offX, Y = getHeight() * offY;
        for (Item it : items.values()) draw(c, it, X, Y, W, H);
    }

    private void draw(Canvas c, Item it, float X, float Y, float W, float H) {
        RectF R = new RectF(X + it.rect[0] * W, Y + it.rect[1] * H, X + it.rect[2] * W, Y + it.rect[3] * H);
        float zoneW = (it.zone[2] - it.zone[0]) * W;
        float linePx = Math.max(14f, it.lineH * H);
        float size = linePx * 0.92f * it.scale;
        fill.setTextSize(size);
        stroke.setTextSize(size);
        stroke.setStrokeWidth(Math.max(2f, linePx * 0.10f));
        float pad = linePx * 0.28f;

        float maxW = "orta".equals(it.align) ? Math.max(R.width(), zoneW * 0.96f)
                : Math.min(zoneW, Math.max(R.width() * 1.15f, linePx * 12));
        List<String> lines = wrap(it.text, maxW - 2 * pad);
        Paint.FontMetrics fm = fill.getFontMetrics();
        float fh = fm.descent - fm.ascent;
        float spacing = fh * 1.05f;
        float tw = 0;
        for (String s : lines) tw = Math.max(tw, fill.measureText(s));
        tw += 2 * pad;
        float th = spacing * lines.size() + 2 * pad - (spacing - fh);

        float bx;
        if ("sol".equals(it.align)) bx = R.left - pad;
        else if ("sag".equals(it.align)) bx = R.right + pad - tw;
        else bx = R.centerX() - tw / 2;
        float by;
        if (th <= R.height() + 2 * pad) by = R.centerY() - th / 2;
        else by = "alt".equals(it.anchor) ? R.bottom + pad - th : R.top - pad;
        RectF text = new RectF(bx, by, bx + tw, by + th);
        RectF cover = new RectF(R.left - pad, R.top - pad, R.right + pad, R.bottom + pad);
        cover.union(text);

        box.setColor(Color.argb(it.opacity, 0, 0, 0));
        c.drawRoundRect(cover, pad * 0.8f, pad * 0.8f, box);

        float y = text.top + pad - fm.ascent;
        for (String s : lines) {
            float w = fill.measureText(s);
            float x;
            if ("sol".equals(it.align)) x = text.left + pad;
            else if ("sag".equals(it.align)) x = text.right - pad - w;
            else x = text.centerX() - w / 2;
            c.drawText(s, x, y, stroke);
            c.drawText(s, x, y, fill);
            y += spacing;
        }
    }

    private List<String> wrap(String text, float maxW) {
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        for (String word : text.trim().split("\\s+")) {
            String trial = cur.length() == 0 ? word : cur + " " + word;
            if (cur.length() > 0 && fill.measureText(trial) > maxW) {
                out.add(cur.toString());
                cur = new StringBuilder(word);
            } else {
                cur = new StringBuilder(trial);
            }
        }
        if (cur.length() > 0) out.add(cur.toString());
        if (out.isEmpty()) out.add("");
        return out;
    }
}
