/* Tanıtım görselleri: ortak yardımcılar (tarayıcıda çalışır).
 * - sehir(): gün batımında kurgusal sahil şehri (SVG; oyun görüntüsü/karakteri yok)
 * - ayYildiz(): Türk bayrağı oranlarına uygun beyaz ay-yıldız (SVG)
 * - kart(): 800×1000 tanıtım kartı iskeleti (üst satır, büyük kart, alt bilgi)
 * - cipler(): telefondaki [data-tr] öğelerinin yanına Türkçe çeviri çipi koyar
 */
const MARKA = "../../altyazi/ui/marka/";

function rastgele(tohum) {           // mulberry32
  let a = tohum >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

let _svgNo = 0;

/* Palmiye silueti: (x,y) gövde dibi, H yükseklik, egim gövdenin yatay kayması (H oranı). */
function palmiye(x, y, H, egim, renk, r) {
  const tx = x + egim * H, ty = y - H;
  const cx = x + egim * H * 0.15, cy = y - H * 0.55;
  let s = "";
  // gövde: incelen dolu şekil
  const w0 = H * 0.034, w1 = H * 0.016;
  s += `<path d="M${x - w0} ${y} Q${cx - w0 * 0.8} ${cy} ${tx - w1} ${ty} L${tx + w1} ${ty} Q${cx + w0 * 0.8} ${cy} ${x + w0} ${y} Z" fill="${renk}"/>`;
  // yapraklar
  const acilar = [-172, -150, -128, -100, -72, -48, -22, 0, 160, 18];
  for (const a0 of acilar) {
    const a = (a0 + (r() - 0.5) * 12) * Math.PI / 180;
    const L = H * (0.30 + r() * 0.12);
    const ex = tx + Math.cos(a) * L, ey = ty + Math.sin(a) * L + L * 0.42;
    const mx = tx + Math.cos(a) * L * 0.55, my = ty + Math.sin(a) * L * 0.55 - L * 0.16;
    // orta damar boyunca yaprakçıklar
    const n = 17;
    let pts1 = [], pts2 = [];
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const px = (1 - t) * (1 - t) * tx + 2 * (1 - t) * t * mx + t * t * ex;
      const py = (1 - t) * (1 - t) * ty + 2 * (1 - t) * t * my + t * t * ey;
      const dx = 2 * (1 - t) * (mx - tx) + 2 * t * (ex - mx);
      const dy = 2 * (1 - t) * (my - ty) + 2 * t * (ey - my);
      const d = Math.hypot(dx, dy) || 1;
      const nx = -dy / d, ny = dx / d;
      const g = L * 0.15 * Math.sin(Math.PI * Math.min(1, t * 1.12)) * (i % 2 ? 1 : 0.3);
      pts1.push([px + nx * g + L * 0.03 * t, py + ny * g + g * 0.6]);
      pts2.push([px - nx * g + L * 0.03 * t, py - ny * g + g * 0.6]);
    }
    const yol = pts1.concat(pts2.reverse()).map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    s += `<path d="${yol} Z" fill="${renk}"/>`;
    s += `<path d="M${tx} ${ty} Q${mx} ${my} ${ex} ${ey}" stroke="${renk}" stroke-width="${Math.max(1.5, H * 0.008)}" fill="none"/>`;
  }
  s += `<circle cx="${tx}" cy="${ty + H * 0.02}" r="${H * 0.03}" fill="${renk}"/>`;
  return s;
}

/* Gün batımında kurgusal sahil şehri. */
function sehir(w, h, o = {}) {
  const id = "s" + (++_svgNo);
  const r = rastgele(o.tohum || 7);
  const ufuk = Math.round(h * (o.ufuk || 0.66));
  const gx = w * (o.gunesX ?? 0.62);
  const gr = o.gunesR || h * 0.21;
  const gy = ufuk - gr * 0.25;
  let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${o.gok0 || "#22195a"}"/><stop offset=".32" stop-color="#55278a"/>
      <stop offset=".6" stop-color="#c2468f"/><stop offset=".82" stop-color="#ff7a68"/><stop offset="1" stop-color="#ffc47a"/>
    </linearGradient>
    <linearGradient id="${id}s" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff4b4"/><stop offset=".55" stop-color="#ffb36b"/><stop offset="1" stop-color="#ff5f8f"/>
    </linearGradient>
    <linearGradient id="${id}d" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#b8488e"/><stop offset=".3" stop-color="#6d2c7f"/><stop offset="1" stop-color="#1b0f35"/>
    </linearGradient>
    <radialGradient id="${id}p" cx=".5" cy=".5" r=".5">
      <stop offset="0" stop-color="#ffd59a" stop-opacity=".85"/><stop offset="1" stop-color="#ff7a9a" stop-opacity="0"/>
    </radialGradient>
    <mask id="${id}m"><rect x="0" y="0" width="${w}" height="${h}" fill="#fff"/>`;
  for (let i = 0; i < 6; i++) {                         // güneşte retro şeritler
    const yy = gy + gr * (0.05 + i * 0.16), kal = 2 + i * 2.2;
    s += `<rect x="0" y="${yy}" width="${w}" height="${kal}" fill="#000"/>`;
  }
  s += `</mask><clipPath id="${id}c"><rect x="0" y="0" width="${w}" height="${ufuk}"/></clipPath></defs>
  <rect width="${w}" height="${ufuk + 2}" fill="url(#${id}g)"/>`;
  // yıldızlar
  for (let i = 0; i < 26; i++) s += `<circle cx="${r() * w}" cy="${r() * ufuk * 0.35}" r="${0.6 + r()}" fill="#fff" opacity="${0.25 + r() * 0.5}"/>`;
  s += `<circle cx="${gx}" cy="${gy}" r="${gr * 2.3}" fill="url(#${id}p)"/>
  <g clip-path="url(#${id}c)"><circle cx="${gx}" cy="${gy}" r="${gr}" fill="url(#${id}s)" mask="url(#${id}m)"/></g>`;
  // bulut şeritleri
  for (let i = 0; i < 4; i++) {
    const cy = ufuk * (0.25 + r() * 0.4), cx = r() * w, cw = w * (0.18 + r() * 0.2);
    s += `<rect x="${cx}" y="${cy}" width="${cw}" height="${3 + r() * 4}" rx="3" fill="#ffd2c8" opacity="${0.18 + r() * 0.2}"/>`;
  }
  // uzak silüet
  let x = -10;
  while (x < w) {
    const bw = w * (0.02 + r() * 0.035), bh = h * (0.06 + r() * 0.13);
    s += `<rect x="${x}" y="${ufuk - bh}" width="${bw}" height="${bh + 2}" fill="#8c3c8f" opacity=".55"/>`;
    x += bw + r() * 4;
  }
  // yakın silüet + pencereler
  x = -6;
  const yakin = o.yakin ?? 1;
  while (x < w) {
    const bw = w * (0.03 + r() * 0.05);
    let bh = h * (0.08 + r() * 0.26) * yakin;
    if (Math.abs(x + bw / 2 - gx) < gr * 0.9) bh *= 0.5;
    const top = ufuk - bh;
    s += `<rect x="${x}" y="${top}" width="${bw}" height="${bh + 2}" fill="#2a1244"/>`;
    if (r() < 0.3) s += `<rect x="${x + bw * 0.2}" y="${top - bh * 0.08}" width="${bw * 0.6}" height="${bh * 0.08 + 1}" fill="#2a1244"/>`;
    if (r() < 0.2) s += `<rect x="${x + bw * 0.48}" y="${top - bh * 0.22}" width="1.5" height="${bh * 0.22}" fill="#2a1244"/><circle cx="${x + bw * 0.48 + 0.75}" cy="${top - bh * 0.22}" r="1.6" fill="#ff5a6e"/>`;
    const ps = Math.max(2, w * 0.004), ara = ps * 2.6;
    for (let wy = top + ara; wy < ufuk - ara; wy += ara)
      for (let wx = x + ara * 0.6; wx < x + bw - ps; wx += ara)
        if (r() < 0.28) s += `<rect x="${wx}" y="${wy}" width="${ps}" height="${ps * 1.2}" fill="#ffc77a" opacity="${0.55 + r() * 0.45}"/>`;
    x += bw + r() * 3;
  }
  // deniz + yansıma
  s += `<rect x="0" y="${ufuk}" width="${w}" height="${h - ufuk}" fill="url(#${id}d)"/>`;
  for (let i = 0; i < 18; i++) {
    const yy = ufuk + 4 + i * (h - ufuk) / 20;
    const ww = gr * (1.2 - i / 20) * (0.6 + r() * 0.5);
    s += `<rect x="${gx - ww / 2}" y="${yy}" width="${ww}" height="${1.5 + i * 0.25}" rx="1" fill="#ffc08a" opacity="${0.7 - i * 0.03}"/>`;
  }
  // ön plan: sahil şeridi
  const kum = h * (o.kum ?? 0.93);
  s += `<path d="M0 ${kum} Q${w * 0.3} ${kum - h * 0.03} ${w * 0.55} ${kum} T${w} ${kum - h * 0.01} L${w} ${h} L0 ${h} Z" fill="#170b26"/>`;
  // palmiyeler
  if (o.palmiye !== false) {
    const P = o.palmiyeler || [[0.04, 0.98, 0.78, 0.18], [0.13, 1.0, 0.6, 0.1], [0.95, 0.99, 0.72, -0.16]];
    for (const [px, py, ph, pe] of P) s += palmiye(w * px, h * py, h * ph, pe, "#140822", r);
  }
  s += `</svg>`;
  return s;
}

/* Türk bayrağı ay-yıldızı. G = bayrak yüksekliği; (x0,y0) = dış ay dairesinin merkezi. */
function ayYildiz(x0, y0, G, renk = "#fff") {
  const R1 = G / 4, R2 = G * 0.2, d = G / 16;
  const xs = x0 + d + R2 + G / 3 + G / 8, Rs = G / 8, rs = Rs * 0.381966;
  let p = "";
  for (let i = 0; i < 10; i++) {
    const a = Math.PI + i * Math.PI / 5;            // bir uç bayrak direğine (sola) bakar
    const rr = i % 2 ? rs : Rs;
    p += (i ? "L" : "M") + (xs + Math.cos(a) * rr).toFixed(2) + " " + (y0 + Math.sin(a) * rr).toFixed(2);
  }
  const m = "ay" + (++_svgNo);
  return `<mask id="${m}" maskUnits="userSpaceOnUse" x="${x0 - G}" y="${y0 - G}" width="${2 * G}" height="${2 * G}"><circle cx="${x0}" cy="${y0}" r="${R1}" fill="#fff"/><circle cx="${x0 + d}" cy="${y0}" r="${R2}" fill="#000"/></mask>` +
    `<circle cx="${x0}" cy="${y0}" r="${R1}" fill="${renk}" mask="url(#${m})"/><path d="${p}Z" fill="${renk}"/>`;
}

function kart(o) {
  const kahramanSag = o.sag ?? `<img class="bot" src="${MARKA}bot.png">`;
  document.body.innerHTML = `
  <div class="ust"><img src="${MARKA}simge_yazisiz.png"><div class="ad">GTA6 Altyazı</div>
    <div class="surum"><i></i>v0.9.3 yayında</div></div>
  <div class="kart">
    <div class="kahraman"><div class="arka">${sehir(700, 318, o.sehir || {})}</div><div class="ortu"></div>
      <div class="yazi"><h1>${o.baslik}</h1><p>${o.alt}</p></div>${kahramanSag}</div>
    <div class="ui" id="ui">${o.oyunArka === false ? "" : `<div class="oyun">${sehir(700, 318, o.oyun || { tohum: 31, gunesX: 0.3 })}</div>`}${o.ui}</div>
  </div>
  ${altbilgi()}`;
}

function altbilgi() {
  return `<div class="alt">
    <div class="dil"><img src="${MARKA}rozet.png">Yalnız Türkçe, en doğal Türkçe</div>
    <div class="plat"><b>Windows · Mac</b> · Altyazı TV'de: <b>Android TV · LG · Samsung</b></div>
    <div class="acik">Ücretsiz ve açık kaynak</div></div>`;
}

/* Telefondaki [data-tr] öğelerinin yanına çip (renk = uygulamanın vurgu rengi). */
function cipler(renk, o = {}) {
  const ui = document.getElementById("ui");
  const ub = ui.getBoundingClientRect();
  const tel = ui.querySelector(".tel");
  const tb = tel.getBoundingClientRect();
  const solX = (o.x ?? (tb.right - ub.left + 48));
  let sonAlt = -1e9;
  for (const el of ui.querySelectorAll("[data-tr]")) {
    const b = el.getBoundingClientRect();
    const c = document.createElement("div");
    c.className = "cip"; c.textContent = el.dataset.tr; c.style.background = renk;
    if (o.yazi) c.style.color = o.yazi;
    if (o.kenar) c.style.boxShadow = `0 0 0 1.5px ${o.kenar}, 0 8px 18px rgba(0,0,0,.4)`;
    ui.appendChild(c);
    const ch = c.offsetHeight;
    let top = b.top + b.height / 2 - ub.top - ch / 2;
    if (top < sonAlt + 6) top = sonAlt + 6;
    sonAlt = top + ch;
    c.style.left = solX + "px"; c.style.top = top + "px";
    const bag = document.createElement("div");
    bag.className = "bag"; bag.style.borderTopColor = o.cizgi || renk; bag.style.setProperty("--r", o.cizgi || renk);
    el.style.outline = `1.5px solid ${o.cizgi || renk}`; el.style.outlineOffset = "2px"; el.style.borderRadius = el.style.borderRadius || "4px";
    const x1 = tb.right - ub.left - 3, y1 = b.top + b.height / 2 - ub.top;
    const x2 = solX - 8, y2 = top + ch / 2;
    const L = Math.hypot(x2 - x1, y2 - y1), a = Math.atan2(y2 - y1, x2 - x1);
    Object.assign(bag.style, { left: x1 + "px", top: y1 + "px", width: L + "px", transformOrigin: "0 0", transform: `rotate(${a}rad)` });
    ui.insertBefore(bag, c);
  }
}
