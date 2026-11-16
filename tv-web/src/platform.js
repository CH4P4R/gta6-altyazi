/* LG webOS / Samsung Tizen / tarayıcı farkları. Hepsi aynı arayüzü sunar. (ES5) */
var Platform = (function () {
  function parse(s) { try { return typeof s === 'string' ? JSON.parse(s || '{}') : (s || {}); } catch (e) { return {}; } }

  function luna(uri, params, cb) {
    try {
      var b = new PalmServiceBridge();
      b.onservicecallback = function (msg) { cb && cb(parse(msg)); };
      b.call(uri, JSON.stringify(params || {}));
    } catch (e) { cb && cb({}); }
  }

  var webos = {
    name: 'webos',
    keys: { back: [461, 8, 27], red: [403], ok: [13], left: [37], right: [39] },
    launchParams: function () { return parse(window.PalmSystem && window.PalmSystem.launchParams); },
    onRelaunch: function (cb) { document.addEventListener('webOSRelaunch', function (e) { cb(parse(e.detail)); }); },
    showHdmi: function (port, host, onStatus) {
      host.innerHTML = '';
      var v = document.createElement('video'), s = document.createElement('source');
      v.autoplay = true;
      s.setAttribute('type', 'service/webos-external');
      s.setAttribute('src', 'ext://hdmi:' + port);
      v.appendChild(s);
      v.addEventListener('playing', function () { onStatus('playing'); });
      v.addEventListener('error', function () { onStatus('error'); });
      s.addEventListener('error', function () { onStatus('error'); });
      host.appendChild(v);
    },
    deviceIp: function (cb) {
      luna('luna://com.webos.service.connectionmanager/getStatus', {}, function (r) {
        var ip = (r.wired && r.wired.state === 'connected' && r.wired.ipAddress) ||
                 (r.wifi && r.wifi.state === 'connected' && r.wifi.ipAddress) || null;
        cb(ip);
      });
    },
    keepAwake: function () {},
    exit: function () { if (window.PalmSystem && window.PalmSystem.platformBack) window.PalmSystem.platformBack(); }
  };

  var tizenP = {
    name: 'tizen',
    keys: { back: [10009, 8, 27], red: [403], ok: [13], left: [37], right: [39] },
    launchParams: function () {
      var out = {};
      try {
        var ac = tizen.application.getCurrentApplication().getRequestedAppControl().appControl;
        for (var i = 0; i < ac.data.length; i++) out[ac.data[i].key] = ac.data[i].value[0];
      } catch (e) {}
      return out;
    },
    onRelaunch: function (cb) {
      document.addEventListener('visibilitychange', function () { if (!document.hidden) cb(tizenP.launchParams()); });
    },
    showHdmi: function (port, host, onStatus) {
      host.innerHTML = '';
      host.className = 'tizen';                 // TV görüntüsü sayfanın arkasında, sayfa saydam
      try {
        tizen.tvwindow.setSource({ type: 'HDMI', number: port }, function () {
          tizen.tvwindow.show(function () { onStatus('playing'); }, function () { onStatus('error'); },
                              ['0px', '0px', '1920px', '1080px'], 'MAIN');
        }, function () { onStatus('error'); }, 'MAIN');
      } catch (e) { onStatus('error'); }
    },
    deviceIp: function (cb) {
      try {
        tizen.systeminfo.getPropertyValue('ETHERNET_NETWORK', function (e) {
          if (e && e.ipAddress && e.ipAddress !== '0.0.0.0') return cb(e.ipAddress);
          tizen.systeminfo.getPropertyValue('WIFI_NETWORK', function (w) { cb(w && w.ipAddress || null); },
                                            function () { cb(null); });
        }, function () {
          tizen.systeminfo.getPropertyValue('WIFI_NETWORK', function (w) { cb(w && w.ipAddress || null); },
                                            function () { cb(null); });
        });
      } catch (e) { cb(null); }
    },
    keepAwake: function () {
      try { tizen.power.request('SCREEN', 'SCREEN_NORMAL'); } catch (e) {}
      var names = ['ColorF0Red', '0', '1', '2', '3', '4'];
      for (var i = 0; i < names.length; i++) { try { tizen.tvinputdevice.registerKey(names[i]); } catch (e) {} }
    },
    exit: function () { try { tizen.application.getCurrentApplication().exit(); } catch (e) {} }
  };

  var browser = {
    name: 'tarayici',
    keys: { back: [27], red: [82], ok: [13], left: [37], right: [39] },
    launchParams: function () {
      var out = {}, q = location.search.replace(/^\?/, '').split('&');
      for (var i = 0; i < q.length; i++) { var p = q[i].split('='); if (p[0]) out[p[0]] = decodeURIComponent(p[1] || ''); }
      return out;
    },
    onRelaunch: function () {},
    showHdmi: function (port, host, onStatus) { host.innerHTML = ''; onStatus('playing'); },
    deviceIp: function (cb) { cb(null); },
    keepAwake: function () {},
    exit: function () {}
  };

  if (window.PalmSystem || /Web0S|webOS/i.test(navigator.userAgent)) return webos;
  if (window.tizen) return tizenP;
  return browser;
})();
