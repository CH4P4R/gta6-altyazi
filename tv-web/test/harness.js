// SPDX-License-Identifier: AGPL-3.0-only
// TV web uygulamasını (tv-web/src) gerçek Chromium'da, sahte bir bilgisayar sunucusuna (SSE /events) bağlı açar.
// Testler ve ekran görüntüsü betikleri olay gönderip sayfayı ölçer. Ağ ve gerçek TV gerekmez.
'use strict';
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const SRC = path.join(__dirname, '..', 'src');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.ttf': 'font/ttf', '.png': 'image/png', '.txt': 'text/plain; charset=utf-8' };

// TV'ye özgü işlerin (HDMI, kumanda) yerine geçen platform: hiçbir şey yapmaz, sunucu adresini başlatma parametresi verir.
function platformJs(server) {
  return `window.COUCHSUBS_PLATFORM = {
    backKey: 461, init: function () {}, exit: function () {}, onRelaunch: function () {},
    launchParams: function () { return ${JSON.stringify(JSON.stringify({ server }))}; },
    showHdmi: function (port, host, status) { status('playing'); },
    findConsolePort: function (done) { done(1, 'HDMI 1'); }
  };`;
}

function startServer() {
  return new Promise(resolve => {
    const clients = [];
    let base = '';
    const server = http.createServer((req, res) => {
      const url = req.url.split('?')[0];
      if (url === '/events') {
        res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' });
        res.write('retry: 2000\n\n');
        clients.push(res);
        req.on('close', () => { const i = clients.indexOf(res); if (i >= 0) clients.splice(i, 1); });
        return;
      }
      if (url === '/platform.js') {
        res.writeHead(200, { 'Content-Type': TYPES['.js'] });
        return res.end(platformJs(base));
      }
      if (url === '/icon.png' || url === '/largeIcon.png') { res.writeHead(204); return res.end(); }
      const file = path.normalize(path.join(SRC, url === '/' ? 'index.html' : decodeURIComponent(url)));
      if (!file.startsWith(SRC + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        res.writeHead(404); return res.end();
      }
      res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(0, '127.0.0.1', () => {
      base = 'http://127.0.0.1:' + server.address().port;
      resolve({
        base,
        clients,
        send(event, data) { for (const c of clients) c.write('event: ' + event + '\ndata: ' + JSON.stringify(data) + '\n\n'); },
        close() { for (const c of clients) c.end(); return new Promise(r => server.close(r)); },
      });
    });
  });
}

// Sayfayı açar ve EventSource bağlanana kadar bekler. Dönen nesnenin send'i olayı gönderir ve sayfaya işlemesi için
// kısa bir süre tanır.
async function openTv(browser, { width = 1920, height = 1080 } = {}) {
  const srv = await startServer();
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(srv.base + '/index.html');
  for (let i = 0; i < 100 && !srv.clients.length; i++) await page.waitForTimeout(50);
  if (!srv.clients.length) throw new Error('TV sayfası sunucuya bağlanmadı');
  // Panel (yeşil tuş) ölçümlere ve görüntüye karışmasın.
  await page.evaluate(() => { document.getElementById('panel').className = 'hidden'; });
  return {
    page,
    errors,
    async send(event, data) {
      srv.send(event, data);
      await page.waitForTimeout(80);
    },
    async close() { await page.close(); await srv.close(); },
  };
}

module.exports = { openTv, startServer };
