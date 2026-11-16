/* Altyazı çizimi: bilgisayardaki katman ve OBS sayfasıyla aynı yerleşim (ES5, eski TV tarayıcıları için). */
var Render = (function () {
  var cv, ctx, items = {}, cal = { x: 0, y: 0, w: 1, h: 1 };
  var FONT = '600 {px}px "LG Smart UI","SamsungOne","Segoe UI",sans-serif';

  function init(canvas) { cv = canvas; ctx = cv.getContext('2d'); draw(); }

  function wrap(text, maxW) {
    var words = String(text).replace(/^\s+|\s+$/g, '').split(/\s+/), out = [], cur = '';
    for (var i = 0; i < words.length; i++) {
      var tr = cur ? cur + ' ' + words[i] : words[i];
      if (cur && ctx.measureText(tr).width > maxW) { out.push(cur); cur = words[i]; } else { cur = tr; }
    }
    if (cur) out.push(cur);
    return out.length ? out : [''];
  }

  function rrect(x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); ctx.fill();
  }

  function one(it) {
    var W = cv.width * cal.w, H = cv.height * cal.h, X = cv.width * cal.x, Y = cv.height * cal.y;
    var r = it.rect, z = it.zone_rect || it.rect;
    var R = { l: X + r[0] * W, t: Y + r[1] * H, r: X + r[2] * W, b: Y + r[3] * H };
    R.w = R.r - R.l; R.h = R.b - R.t;
    var zoneW = (z[2] - z[0]) * W, line = Math.max(14, (it.line_h || 0.035) * H), pad = line * 0.28;
    ctx.font = FONT.replace('{px}', Math.round(line * 0.92 * (it.font_scale || 1)));
    var maxW = it.align === 'orta' ? Math.max(R.w, zoneW * 0.96) : Math.min(zoneW, Math.max(R.w * 1.15, line * 12));
    var lines = wrap(it.text, maxW - 2 * pad), fh = line * 0.92 * (it.font_scale || 1) * 1.15, asc = fh * 0.78;
    var sp = fh * 1.05, tw = 0;
    for (var i = 0; i < lines.length; i++) tw = Math.max(tw, ctx.measureText(lines[i]).width);
    tw += 2 * pad;
    var th = sp * lines.length + 2 * pad - (sp - fh);
    var bx = it.align === 'sol' ? R.l - pad : it.align === 'sag' ? R.r + pad - tw : (R.l + R.r) / 2 - tw / 2;
    var by = th <= R.h + 2 * pad ? (R.t + R.b) / 2 - th / 2 : (it.anchor === 'alt' ? R.b + pad - th : R.t - pad);
    var cl = Math.min(bx, R.l - pad), ct = Math.min(by, R.t - pad), cr = Math.max(bx + tw, R.r + pad), cb = Math.max(by + th, R.b + pad);
    var op = it.box_opacity === undefined ? 255 : it.box_opacity;
    ctx.fillStyle = 'rgba(0,0,0,' + (op / 255) + ')';
    rrect(cl, ct, cr - cl, cb - ct, pad * 0.8);
    ctx.lineJoin = 'round'; ctx.lineWidth = Math.max(2, line * 0.10); ctx.strokeStyle = '#000'; ctx.fillStyle = '#fff';
    var y = by + pad + asc;
    for (var k = 0; k < lines.length; k++) {
      var w = ctx.measureText(lines[k]).width;
      var x = it.align === 'sol' ? bx + pad : it.align === 'sag' ? bx + tw - pad - w : bx + tw / 2 - w / 2;
      ctx.strokeText(lines[k], x, y); ctx.fillText(lines[k], x, y); y += sp;
    }
  }

  function draw() {
    if (!ctx) return;
    ctx.clearRect(0, 0, cv.width, cv.height);
    for (var k in items) if (items.hasOwnProperty(k)) one(items[k]);
  }

  function handle(d) {
    if (d.type === 'show') { if (d.tv) cal = d.tv; items[d.zone] = d; }
    else if (d.type === 'clear') { delete items[d.zone]; }
    else if (d.type === 'clear_all') { items = {}; }
    else return;
    draw();
  }

  function clearAll() { items = {}; draw(); }
  return { init: init, handle: handle, clearAll: clearAll };
})();
