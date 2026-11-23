// SPDX-License-Identifier: AGPL-3.0-only
// "Ekranı çevir" (screen) olayının yeni alanları ve yeni altyazı stili, gerçek Chromium'da (Playwright).
//   node --test tv-web/test/
// Playwright ya da tarayıcısı yoksa testler atlanır. Alanların TV'deki çizimi Nino Game Translator'dan alındı.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { openTv } = require('./harness');

let chromium = null;
try { chromium = require('playwright').chromium; } catch (e) { /* aşağıda atlanır */ }
const available = !!chromium && (() => { try { return fs.existsSync(chromium.executablePath()); } catch (e) { return false; } })();

const W = 1920;
const H = 1080;
const item = (text, left, top, right, bottom, extra = {}) => Object.assign({ text, box: { left, top, right, bottom }, line: 0.025 }, extra);

// Ekrandaki öğelerin ölçümü (sınıf, yazı, kutu, hesaplanan stil).
function measure(page) {
  return page.evaluate(() => Array.from(document.getElementById('screen').children).map(el => {
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const title = el.querySelector('.panel-title');
    return {
      cls: el.className, text: el.textContent, left: el.offsetLeft, top: el.offsetTop, width: el.offsetWidth,
      height: el.offsetHeight, rectLeft: b.left, bg: cs.backgroundColor, color: cs.color, font: parseFloat(cs.fontSize),
      fontStyle: cs.fontStyle, align: cs.textAlign, transform: el.style.transform, delay: el.style.animationDelay,
      scrollHeight: el.scrollHeight, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, clientWidth: el.clientWidth,
      borderTop: cs.borderTopWidth, borderImage: cs.borderImageSource, title: title ? title.textContent : null,
      images: el.querySelectorAll('img').length, dataText: el.getAttribute('data-text'),
    };
  }));
}

const state = page => page.evaluate(() => ({
  screen: document.getElementById('screen').className,
  subtitle: document.getElementById('subtitle').className,
  body: document.body.className,
}));

let browser = null;
test.before(async () => { if (available) browser = await chromium.launch(); });
test.after(async () => { if (browser) await browser.close(); });
const skip = () => !available && 'Playwright Chromium bulunamadı';

test('alanı olmayan öğe eskisi gibi çizilir', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('screen', { duration: 10000, items: [item('Araca bin', 0.1, 0.2, 0.3, 0.23)] });
    const [el] = await measure(tv.page);
    assert.equal(el.cls, 'item');
    assert.equal(el.text, 'Araca bin');
    assert.equal(el.bg, 'rgba(0, 0, 0, 0.97)');
    assert.equal(el.color, 'rgb(255, 255, 255)');
    assert.equal(el.align, 'center');
    assert.ok(Math.abs(el.rectLeft - (0.1 - 0.004) * W) < 1, JSON.stringify(el));
    assert.equal(el.font, Math.round(0.025 * H * 0.95));
    assert.deepEqual(tv.errors, []);
  } finally { await tv.close(); }
});

test('fill/ink: Türkçe oyunun balonunun tam üstüne aynı renklerle sığdırılır', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('screen', { duration: 10000, items: [
      item('Ama teslimat bana, Brian’a değil. Karavanıma getir, anladın mı?', 0.40, 0.30, 0.52, 0.36, { fill: '#e9e9ec', ink: '#111111' }),
      item('Tamam', 0.40, 0.40, 0.46, 0.43, { fill: '#5b8def' }),
      item('Geçersiz renk', 0.1, 0.1, 0.2, 0.13, { fill: 'red' }),
    ] });
    const [bubble, noInk, invalid] = await measure(tv.page);
    assert.equal(bubble.cls, 'item bubble');
    assert.equal(bubble.bg, 'rgb(233, 233, 236)');
    assert.equal(bubble.color, 'rgb(17, 17, 17)');
    assert.equal(bubble.dataText, 'Ama teslimat bana, Brian’a değil. Karavanıma getir, anladın mı?');
    // Kutu tam oyunun balonu kadar: pay yok.
    assert.ok(Math.abs(bubble.left - 0.40 * W) < 1 && Math.abs(bubble.top - 0.30 * H) < 1, JSON.stringify(bubble));
    assert.ok(Math.abs(bubble.width - 0.12 * W) < 1 && Math.abs(bubble.height - 0.06 * H) < 1, JSON.stringify(bubble));
    // Uzun Türkçe balondan taşmaz (yazı küçülür, en az 11 px).
    assert.ok(bubble.scrollHeight <= bubble.clientHeight + 1, JSON.stringify(bubble));
    assert.ok(bubble.font >= 11 && bubble.font <= Math.round(0.025 * H * 0.98));
    // ink yoksa koyu yazı.
    assert.equal(noInk.color, 'rgb(28, 28, 30)');
    // Geçersiz renk: sıradan öğe.
    assert.equal(invalid.cls, 'item');
  } finally { await tv.close(); }
});

test('alpha, angle ve side', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('screen', { duration: 10000, items: [
      item('Eğik balon', 0.40, 0.30, 0.52, 0.34, { fill: '#e9e9ec', angle: -6.5 }),
      item('Çok eğik', 0.40, 0.40, 0.52, 0.44, { fill: '#e9e9ec', angle: 45 }),
      item('Yandaki balon', 0.62, 0.30, 0.80, 0.34, { fill: '#ffffff', alpha: 0.85, side: true }),
      item('Opak', 0.62, 0.40, 0.80, 0.44, { fill: '#ffffff', alpha: 1, side: true }),
    ] });
    const [tilted, tooTilted, side, opaque] = await measure(tv.page);
    assert.equal(tilted.transform, 'rotate(-6.5deg)');
    assert.equal(tooTilted.transform, '');
    assert.equal(side.cls, 'item bubble side');
    assert.equal(side.bg, 'rgba(255, 255, 255, 0.85)');
    assert.equal(side.delay, '120ms');
    assert.equal(opaque.bg, 'rgb(255, 255, 255)');
    assert.equal(opaque.delay, '180ms');
  } finally { await tv.close(); }
});

test('backdrop: yazısız panel, başlığı gönderenin adı, sağ altta GTA6 Altyazı rozeti', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('screen', { duration: 10000, items: [
      item('Donnie', 0.60, 0.15, 0.82, 0.70, { backdrop: true, fill: '#f2f2f7', alpha: 0.9 }),
      item('', 0.60, 0.75, 0.82, 0.80, { backdrop: true, fill: '#f2f2f7' }),
      item('Yazısız, renksiz zemin çizilmez', 0.1, 0.1, 0.2, 0.15, { backdrop: true }),
    ] });
    const [panel, plainPanel, noFill] = await measure(tv.page);
    assert.equal(panel.cls, 'item backdrop');
    assert.equal(panel.bg, 'rgba(242, 242, 247, 0.9)');
    assert.equal(panel.title, 'Donnie');
    assert.equal(panel.images, 1);
    assert.equal(panel.dataText, '');
    assert.ok(Math.abs(panel.width - 0.22 * W) < 1 && Math.abs(panel.height - 0.55 * H) < 1, JSON.stringify(panel));
    assert.equal(plainPanel.bg, 'rgb(242, 242, 247)');
    assert.equal(plainPanel.title, null);
    // fill'siz backdrop sıradan yazı olarak çizilir (Nino'daki gibi).
    assert.equal(noFill.cls, 'item');
  } finally { await tv.close(); }
});

test('plain, italic, card ve paragraphs', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('screen', { duration: 10000, items: [
      item('Lucia ile buluş', 0.03, 0.10, 0.30, 0.13, { plain: true }),
      item('Paradise Taxi aranıyor…', 0.40, 0.10, 0.60, 0.13, { italic: true }),
      item('KARAVAN\nDonnie’nin karavanına git.', 0.65, 0.10, 0.90, 0.20, { card: true, paragraphs: true }),
      item('Başlık\nMadde', 0.10, 0.50, 0.40, 0.60, { paragraphs: true }),
    ] });
    const [plain, italic, card, paragraphs] = await measure(tv.page);
    assert.equal(plain.cls, 'item plain');
    assert.equal(plain.bg, 'rgba(0, 0, 0, 0.38)');
    assert.equal(plain.align, 'left');
    // Genişlik yazı kadar (en çok ekranın %46'sı).
    assert.ok(plain.width < 0.27 * W && plain.width <= 0.46 * W, JSON.stringify(plain));
    assert.equal(italic.cls, 'item italic');
    assert.equal(italic.fontStyle, 'italic');
    assert.equal(card.cls, 'item paragraphs card');
    assert.equal(card.bg, 'rgba(38, 38, 50, 0.92)');
    assert.equal(card.align, 'left');
    assert.equal(card.borderTop, '4px');
    assert.match(card.borderImage, /linear-gradient/);
    assert.equal(paragraphs.align, 'start');
  } finally { await tv.close(); }
});

test('overlay: köşe çevirisi altyazıyı silmez, sıradan ekran çevirisi siler', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('subtitle', { text: 'Buraya öylece girip benim olanı alabileceğini mi sanıyorsun?', duration: 60000 });
    assert.equal((await state(tv.page)).subtitle, '');
    await tv.send('screen', { duration: 10000, overlay: true, items: [item('Araca binmek için X', 0.03, 0.04, 0.25, 0.08)] });
    let s = await state(tv.page);
    assert.equal(s.subtitle, '');
    assert.equal(s.screen, '');
    await tv.send('screen', { duration: 10000, items: [item('Araca binmek için X', 0.03, 0.04, 0.25, 0.08)] });
    s = await state(tv.page);
    assert.equal(s.subtitle, 'hidden');
  } finally { await tv.close(); }
});

test('aynı balonlar yeniden gelince yeniden çizilmez, yalnız yeri değişir; panel yumuşakça kalkar', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    const items = top => [
      item('Donnie', 0.60, top, 0.82, top + 0.5, { backdrop: true, fill: '#f2f2f7', alpha: 0.9 }),
      item('Selam', 0.62, top + 0.1, 0.70, top + 0.13, { fill: '#e9e9ec', side: true }),
    ];
    await tv.send('screen', { duration: 10000, items: items(0.15) });
    await tv.page.evaluate(() => { window.__first = document.querySelector('#screen .item.side'); });
    await tv.send('screen', { duration: 10000, items: items(0.20) });
    // Panelin yazısı (gönderen) data-text'te tutulmaz: Nino'daki gibi panel varken baştan çizilir ve 'steady' kalır.
    assert.equal((await state(tv.page)).screen, 'steady');
    // Yalnız balonlar: aynı öğe yerinde kayar.
    const bubbles = top => [item('Selam', 0.62, top, 0.70, top + 0.03, { fill: '#e9e9ec' })];
    await tv.send('screen', { duration: 10000, items: bubbles(0.3) });
    await tv.page.evaluate(() => { window.__first = document.querySelector('#screen .item.bubble'); });
    await tv.send('screen', { duration: 10000, items: bubbles(0.35) });
    const moved = await tv.page.evaluate(() => {
      const el = document.querySelector('#screen .item.bubble');
      return { same: el === window.__first, top: el.style.top };
    });
    assert.equal(moved.same, true);
    assert.equal(moved.top, '35%');
    // Panel/yan balon varken kapanış önce solar, sonra gizlenir.
    await tv.send('screen', { duration: 10000, items: items(0.15) });
    await tv.send('screen-clear', {});
    assert.equal((await state(tv.page)).screen, 'leaving');
    await tv.page.waitForTimeout(400);
    assert.equal((await state(tv.page)).screen, 'hidden');
    // Sıradan öğeler eskisi gibi hemen kalkar.
    await tv.send('screen', { duration: 10000, items: [item('Kaydet', 0.1, 0.2, 0.3, 0.23)] });
    await tv.send('screen-clear', {});
    assert.equal((await state(tv.page)).screen, 'hidden');
  } finally { await tv.close(); }
});

test('yeni altyazı stili: zemin %90 ve üstünde, glass alanı ezer, diğer body sınıfları korunur', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.page.evaluate(() => { document.body.className += ' overlay'; });
    await tv.send('style', { placement: 'cover', fontSize: 58, background: 100, backgroundShape: 'band' });
    let s = await state(tv.page);
    assert.deepEqual(s.body.split(' ').sort(), ['band', 'glass', 'overlay']);
    await tv.send('subtitle', { text: 'Selam, Lucia’nın telefonuna ulaştın.', duration: 60000, box: { left: 0.3, top: 0.85, right: 0.7, bottom: 0.92 }, line: 0.03 });
    s = await state(tv.page);
    assert.ok(s.body.split(' ').includes('covering'), s.body);
    const look = await tv.page.evaluate(() => {
      const text = getComputedStyle(document.getElementById('subtitle-text'));
      const cover = getComputedStyle(document.getElementById('subtitle-cover'));
      return { textBg: text.backgroundImage + '|' + text.backgroundColor, family: text.fontFamily, coverBg: cover.backgroundColor };
    });
    assert.match(look.family, /Altyazi Rounded/);
    assert.equal(look.coverBg, 'rgb(10, 10, 10)');
    assert.equal(look.textBg, 'none|rgba(0, 0, 0, 0)');
    await tv.send('style', { placement: 'fixed', background: 60, backgroundShape: 'fit' });
    s = await state(tv.page);
    assert.deepEqual(s.body.split(' ').filter(Boolean), ['overlay']);
    await tv.send('style', { background: 60, glass: true });
    assert.ok((await state(tv.page)).body.split(' ').includes('glass'));
    await tv.send('style', { background: 100, glass: false });
    assert.ok(!(await state(tv.page)).body.split(' ').includes('glass'));
    assert.deepEqual(tv.errors, []);
  } finally { await tv.close(); }
});

test('yazı tipi Aksiyon ve konuşana göre renk', { skip: skip() }, async () => {
  const tv = await openTv(browser, { width: W, height: H });
  try {
    await tv.send('style', { placement: 'fixed', background: 60, font: 'aksiyon', speakerColors: true, textColor: 'cyan' });
    await tv.send('subtitle', { text: 'LUCIA: Arabaya bin, gitmemiz gerek.', duration: 60000, box: { left: 0.3, top: 0.85, right: 0.7, bottom: 0.92 }, line: 0.03 });
    const look = await tv.page.evaluate(() => {
      const el = document.getElementById('subtitle-text');
      const sp = el.querySelector('.speaker');
      return { family: getComputedStyle(el).fontFamily, speaker: sp ? sp.textContent : null, color: el.style.color,
               body: document.body.className, text: el.textContent };
    });
    assert.match(look.family, /Altyazi Condensed/);
    assert.equal(look.speaker, 'LUCIA: ');
    assert.ok(look.color && look.color !== '', look.color);
    assert.ok(look.text.startsWith('LUCIA: Arabaya'), look.text);
    await tv.send('style', { font: 'yuvarlak', speakerColors: false });
    await tv.send('subtitle', { text: 'JASON: Tamam.', duration: 60000, box: { left: 0.3, top: 0.85, right: 0.7, bottom: 0.92 }, line: 0.03 });
    const plain = await tv.page.evaluate(() => ({ sp: !!document.querySelector('#subtitle-text .speaker'),
                                                  body: document.body.className }));
    assert.ok(!plain.sp && !plain.body.includes('font-action') && plain.body.includes('font-round'));
    await tv.send('style', { font: 'sade' });
    const sade = await tv.page.evaluate(() => getComputedStyle(document.getElementById('subtitle-text')).fontFamily);
    assert.match(sade, /LG Smart UI/);
    await tv.send('style', { font: 'modern' });
    const modern = await tv.page.evaluate(() => ({ f: getComputedStyle(document.getElementById('subtitle-text')).fontFamily,
                                                   body: document.body.className }));
    assert.match(modern.f, /Altyazi Modern/);
    assert.ok(!/font-(action|round|plain)/.test(modern.body) && modern.body.includes('font-modern'));
    assert.deepEqual(tv.errors, []);
  } finally { await tv.close(); }
});
