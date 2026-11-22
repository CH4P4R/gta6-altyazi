/* Tanıtım görsellerini HTML'den PNG'ye çizer (ekransız Chromium, Playwright).
 *
 * Yeniden üretmek için depo kökünde:
 *     NODE_PATH=$(npm root -g) node tools/tanitim_gorsel/ciz.js            # hepsi
 *     NODE_PATH=$(npm root -g) node tools/tanitim_gorsel/ciz.js kutu arac  # yalnız seçilenler
 *
 * Çıktılar: docs/tanitim/*.png  (+ fis-nedir.png → altyazi/ui/rehber/fis-nedir.png kopyası)
 * Ağ/CDN kullanılmaz; yazı tipi tools/marka/fonts/ içindeki Inter, görseller altyazi/ui/marka/.
 * Sahneler (gün batımı şehri, palmiyeler, telefon arayüzleri) tamamen çizimdir; oyun görüntüsü,
 * oyun logosu, karakter ya da konsol logosu kullanılmaz.
 * kutu.png önce çizilir, çünkü tanitim-duyuru.html onu kullanır.
 */
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const KOK = path.resolve(__dirname, "../..");
const CIKTI = path.join(KOK, "docs", "tanitim");

const SAYFALAR = [
  { ad: "kutu", w: 1260, h: 1260, saydam: true },
  { ad: "tanitim-telefon", w: 800, h: 1000 },
  { ad: "tanitim-arac", w: 800, h: 1000 },
  { ad: "tanitim-banka", w: 800, h: 1000 },
  { ad: "tanitim-antrenman", w: 800, h: 1000 },
  { ad: "tanitim-haber", w: 800, h: 1000 },
  { ad: "tanitim-harita", w: 800, h: 1000 },
  { ad: "tanitim-altyazi", w: 800, h: 1000 },
  { ad: "tanitim-kalite", w: 800, h: 1000 },
  { ad: "tanitim-platformlar", w: 800, h: 1000 },
  { ad: "tanitim-duyuru", w: 800, h: 1000 },
  { ad: "fis-nedir", w: 1600, h: 900, kopya: path.join(KOK, "altyazi", "ui", "rehber", "fis-nedir.png") },
];

(async () => {
  const secim = process.argv.slice(2);
  fs.mkdirSync(CIKTI, { recursive: true });
  const tarayici = await chromium.launch();
  for (const s of SAYFALAR) {
    if (secim.length && !secim.includes(s.ad)) continue;
    const sayfa = await tarayici.newPage({ viewport: { width: s.w, height: s.h }, deviceScaleFactor: 1 });
    sayfa.on("console", (m) => { if (m.type() === "error") console.error(`[${s.ad}] ${m.text()}`); });
    sayfa.on("pageerror", (e) => console.error(`[${s.ad}] ${e.message}`));
    await sayfa.goto("file://" + path.join(__dirname, s.ad + ".html"));
    await sayfa.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map((i) => i.complete ? 0 : new Promise((r) => { i.onload = i.onerror = r; })));
      if (window.hazir) await window.hazir();
    });
    await sayfa.waitForTimeout(150);
    const dosya = path.join(CIKTI, s.ad + ".png");
    await sayfa.screenshot({ path: dosya, omitBackground: !!s.saydam, clip: { x: 0, y: 0, width: s.w, height: s.h } });
    if (s.kopya) fs.copyFileSync(dosya, s.kopya);
    console.log("yazıldı:", path.relative(KOK, dosya));
    await sayfa.close();
  }
  await tarayici.close();
})();
