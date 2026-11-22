// GTA6 Altyazı TV kurulum görsellerini (Android TV / LG / Samsung) üretir.
//
// Yeniden üretmek için (depo kökünden):
//   NODE_PATH=$(npm root -g) node tools/kurulum_gorsel/ciz.js            # üçü birden
//   NODE_PATH=$(npm root -g) node tools/kurulum_gorsel/ciz.js samsung    # yalnız biri
// Gerekenler: Node + Playwright (Chromium). İnternet gerekmez; yazı tipleri tools/marka/fonts/ ve fonts/ içinden.
// İçerik veri.js'te, görünüm sablon.html'de. Çıktı: altyazi/ui/rehber/kurulum-<marka>.png ve docs/img/ kopyası.
"use strict";

const path = require("path");
const fs = require("fs");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..", "..");
const PAGE = pathToFileURL(path.join(__dirname, "sablon.html")).href;
const OUT = [path.join(ROOT, "altyazi", "ui", "rehber"), path.join(ROOT, "docs", "img")];
const BRANDS = ["android", "lg", "samsung"];

(async () => {
  const want = process.argv.slice(2);
  const brands = want.length ? BRANDS.filter((b) => want.includes(b)) : BRANDS;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => { console.error("Sayfa hatası:", e.message); process.exitCode = 1; });
  for (const b of brands) {
    await page.goto(`${PAGE}?marka=${b}`);
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map((im) => im.complete ? 0 : new Promise((r) => { im.onload = im.onerror = r; })));
    });
    const missing = await page.evaluate(() => [...document.fonts].filter((f) => f.status === "error").length);
    if (missing) console.warn(`Uyarı: ${missing} yazı tipi yüklenemedi`);
    const name = `kurulum-${b}.png`;
    const first = path.join(OUT[0], name);
    await page.screenshot({ path: first, fullPage: true });
    for (const dir of OUT.slice(1)) fs.copyFileSync(first, path.join(dir, name));
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    console.log(`${name}  1600×${h}`);
  }
  await browser.close();
})();
