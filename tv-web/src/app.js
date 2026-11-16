/* GTA6 Altyazı TV uygulaması: HDMI'yı tam ekran gösterir, bilgisayardan gelen Türkçe altyazıyı üstüne çizer. (ES5) */
(function () {
  var PORT = 8787;
  var $ = function (id) { return document.getElementById(id); };
  function load(k) { try { return localStorage.getItem('gta6.' + k); } catch (e) { return null; } }
  function save(k, v) { try { localStorage.setItem('gta6.' + k, v); } catch (e) {} }

  var params = Platform.launchParams();
  var host = params.host || load('host');
  var hdmi = Number(params.hdmi || load('hdmi') || 1);
  var es = null, failures = 0, scanning = false, toastTimer = null, panelTimer = null;

  function toast(msg, ms) {
    var t = $('toast'); t.textContent = msg; t.className = '';
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.className = 'hidden'; }, ms || 3000);
  }
  function panel(show, ms) {
    $('panel').className = show ? '' : 'hidden';
    clearTimeout(panelTimer);
    if (show && ms) panelTimer = setTimeout(function () { $('panel').className = 'hidden'; }, ms);
  }
  function status(id, text) { $(id).textContent = text; }

  // --- HDMI ---
  function showHdmi(port) {
    hdmi = port; save('hdmi', port);
    status('st-hdmi', 'HDMI ' + port);
    Platform.showHdmi(port, $('video-host'), function (st) {
      if (st === 'error') toast('HDMI ' + port + ' açılamadı. ◀ ▶ ile başka girişi dene.', 5000);
    });
  }

  // --- bilgisayara bağlantı ---
  function connect(h) {
    if (es) { try { es.close(); } catch (e) {} }
    host = h; save('host', h);
    status('st-server', 'Bilgisayar: ' + h);
    es = new EventSource('http://' + h + '/olaylar');
    es.onopen = function () { failures = 0; status('st-server', 'Bağlı: ' + h); };
    es.onmessage = function (m) {
      var d; try { d = JSON.parse(m.data); } catch (e) { return; }
      Render.handle(d);
    };
    es.onerror = function () {
      Render.clearAll();
      failures++;
      status('st-server', 'Bağlantı yok, tekrar deneniyor... (' + h + ')');
      if (failures >= 5 && !scanning) { try { es.close(); } catch (e) {} discover(); }
    };
  }

  function probe(ip, cb) {
    var x = new XMLHttpRequest(), done = false;
    function fin(ok) { if (!done) { done = true; cb(ok); } }
    try {
      x.open('GET', 'http://' + ip + ':' + PORT + '/kim', true);
      x.timeout = 900;
      x.onload = function () { fin(x.status === 200 && /gta6-altyazi/.test(x.responseText)); };
      x.onerror = x.ontimeout = function () { fin(false); };
      x.send();
    } catch (e) { fin(false); }
  }

  function discover() {
    scanning = true;
    status('st-server', 'Bilgisayar ağda aranıyor...');
    panel(true);
    Platform.deviceIp(function (ip) {
      var bases = [];
      if (ip) bases.push(ip.split('.').slice(0, 3).join('.'));
      ['192.168.1', '192.168.0', '10.0.0'].forEach(function (b) { if (bases.indexOf(b) < 0) bases.push(b); });
      var queue = [];
      bases.forEach(function (b) { for (var i = 1; i < 255; i++) queue.push(b + '.' + i); });
      var found = false, running = 0;
      function next() {
        if (found) return;
        if (!queue.length) {
          if (running === 0) { scanning = false; status('st-server', 'Bilgisayar bulunamadı. GTA6 Altyazı açık mı?'); setTimeout(discover, 15000); }
          return;
        }
        var target = queue.shift(); running++;
        probe(target, function (ok) {
          running--;
          if (ok && !found) { found = true; scanning = false; connect(target + ':' + PORT); panel(true, 4000); return; }
          next();
        });
      }
      for (var k = 0; k < 24; k++) next();
    });
  }

  // --- kumanda ---
  function inList(code, list) { return list.indexOf(code) >= 0; }
  document.addEventListener('keydown', function (e) {
    var c = e.keyCode, K = Platform.keys;
    if (inList(c, K.back)) { Platform.exit(); return; }
    if (inList(c, K.ok)) { panel($('panel').className === 'hidden'); return; }
    if (inList(c, K.left)) { showHdmi(hdmi <= 1 ? 4 : hdmi - 1); panel(true, 3000); return; }
    if (inList(c, K.right)) { showHdmi(hdmi >= 4 ? 1 : hdmi + 1); panel(true, 3000); return; }
    if (c >= 49 && c <= 52) { showHdmi(c - 48); panel(true, 3000); return; }
    if (inList(c, K.red)) {
      Render.handle({ type: 'show', zone: 'test', text: 'Bu bir deneme altyazısı. Yazı burada görünecek.',
                      rect: [0.33, 0.86, 0.67, 0.93], zone_rect: [0.1, 0.76, 0.9, 0.97], line_h: 0.031,
                      align: 'orta', anchor: 'alt', box_opacity: 255, font_scale: 1.3 });
      setTimeout(function () { Render.handle({ type: 'clear', zone: 'test' }); }, 4000);
    }
  });

  Platform.onRelaunch(function (p) {
    if (p.hdmi) showHdmi(Number(p.hdmi));
    if (p.host && p.host !== host) connect(p.host);
  });

  Render.init($('subs'));
  Platform.keepAwake();
  showHdmi(hdmi);
  panel(true, 6000);
  if (host) connect(host); else discover();
})();
