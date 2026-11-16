package com.gta6altyazi.tv;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** Bilgisayarın /olaylar akışını (Server-Sent Events) dinler; koparsa 1 sn sonra yeniden bağlanır. */
class EventStream {
    interface Listener {
        void onEvent(String json);
        void onDisconnected();
    }

    final String host;
    private final Listener listener;
    private volatile boolean running = true;
    private volatile HttpURLConnection conn;
    private Thread thread;

    EventStream(String host, Listener listener) {
        this.host = host;
        this.listener = listener;
    }

    void start() {
        thread = new Thread(this::loop, "altyazi-akis");
        thread.start();
    }

    void stop() {
        running = false;
        HttpURLConnection c = conn;
        if (c != null) c.disconnect();
        if (thread != null) thread.interrupt();
    }

    private void loop() {
        while (running) {
            try {
                HttpURLConnection c = (HttpURLConnection) new URL("http://" + host + "/olaylar").openConnection();
                conn = c;
                c.setConnectTimeout(3000);
                c.setReadTimeout(40000);   // sunucu 15 sn'de bir ping atar
                c.setRequestProperty("Accept", "text/event-stream");
                try (BufferedReader r = new BufferedReader(
                        new InputStreamReader(c.getInputStream(), StandardCharsets.UTF_8), 1024)) {
                    String line;
                    while (running && (line = r.readLine()) != null) {
                        if (line.startsWith("data: ")) listener.onEvent(line.substring(6));
                    }
                }
            } catch (Exception ignored) {
                // bağlantı yok ya da koptu
            }
            listener.onDisconnected();
            if (!running) break;
            try { Thread.sleep(1000); } catch (InterruptedException e) { break; }
        }
    }
}
