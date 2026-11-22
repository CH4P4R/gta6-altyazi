/* GTA6 Altyazı TV kurulum görsellerinin içeriği (marka başına başlık, 6 adım, uyarı).
   Adımlar altyazi/rehber.py'deki GOOGLE_TV / LG_TV / SAMSUNG_TV ile ve Bağlantı › TV bölümündeki gerçek düğme
   adlarıyla (Ağda ara, Bağlan, kur ve başlat, Resimli anlat) aynı olmalı; rehber değişirse burayı da güncelle.
   Yardımcılar (screen, crumb, row, tag, ntag, appTv, I) sablon.html'dedir.
   Yeniden üretmek için:  NODE_PATH=$(npm root -g) node tools/kurulum_gorsel/ciz.js */

const caret = '<span class="car">▾</span>';
const sideTag = (t) => `<span class="tag side">${t}</span>`;

const DATA = {
  /* ------------------------------------------------------------------ Android TV / Google TV */
  android: {
    title: "Android TV / Google TV'ye<br><em>GTA6 Altyazı TV</em> kurulumu",
    chips: [["clock", "3 dakika"], ["remote", "Kumanda + bilgisayar"]],
    intro: `<span class="brands">TCL · iFFALCON · Sony · Philips · Xiaomi · Hisense · Vestel · Arçelik · Beko · Grundig ·
      Toshiba</span> gibi markaların <b>Android TV / Google TV</b> modellerinde adımlar aynıdır: TV'de geliştirici
      seçeneklerini ve USB hata ayıklamayı açarsınız. Bunu bir kez yaparsınız; sonra <b>GTA6 Altyazı</b>, TV uygulamasını
      bilgisayardan kurar ve günceller.`,
    steps: [
      {
        screen: screen(crumb("Ayarlar") + row("Ağ ve İnternet") + row("Hesaplar ve oturum açma") + row("Uygulamalar") +
          row("Sistem", { hl: true, tag: "OK'a basın" }), "glow"),
        title: "Ayarlar › Sistem › Hakkında",
        text: "Kumandayla <b>Ayarlar</b>'ı açın; <b>Sistem</b>'e, oradan da <b>Hakkında</b>'ya girin.",
      },
      {
        screen: screen(crumb("Ayarlar", "Sistem", "Hakkında") + row("Android TV OS sürümü") +
          row("Android TV OS derlemesi", { hl: true, tag: "OK × 7 kez" }) +
          '<div class="toast">Artık geliştiricisiniz!</div>', "glow"),
        title: "Derleme satırına 7 kez basın",
        text: "<b>Android TV OS derlemesi</b> satırında <b>OK</b>'a arka arkaya 7 kez basın. TCL'de adı " +
          "<b>Derleme / Yapı numarası</b> olabilir.",
      },
      {
        screen: screen(crumb("Ayarlar", "Sistem") + row("Hakkında") + row("Tarih ve saat") + row("Dil") +
          row("Geliştirici seçenekleri", { hl: true, tag: "OK'a basın" }), "glow"),
        title: "Geliştirici seçeneklerine girin",
        text: "Geri tuşuyla <b>Sistem</b>'e dönün. Listede artık <b>Geliştirici seçenekleri</b> var; içine girin.",
      },
      {
        screen: screen(crumb("Sistem", "Geliştirici seçenekleri") + '<div class="hint sect">Hata ayıklama</div>' +
          row("USB hata ayıklama", { hl: true, toggle: true, tag: "Açın" }) +
          row("Kablosuz hata ayıklama", { dim: true, toggle: false }) +
          '<div class="hint">Kablosuz hata ayıklama ve eşleştirme kodu <b>gerekmez</b>.</div>', "glow"),
        title: "USB hata ayıklamayı açın",
        text: "<b>USB hata ayıklama</b>'yı açın (düz olanı). Program TV'ye ağdan doğrudan bağlanır; kablo gerekmez.",
      },
      {
        screen: screen(appTv(
          `<div class="r"><span class="lb">TV markası</span><span class="in"><span class="t">Google TV / Android TV (TCL, Sony, Philips, Xiaomi, Hisense...)</span>${caret}</span>` +
          `<span class="b">Resimli anlat</span></div>` +
          `<div class="r"><span class="in">192.168.1.40</span><span class="b ring">Ağda ara${ntag(1)}</span></div>` +
          `<div class="r"><span class="b p ring">Bağlan, kur ve başlat${ntag(2)}</span>` +
          `</div>`)),
        title: "Programda bulun ve kurun",
        text: "GTA6 Altyazı'da <b>Bağlantı › TV</b> bölümünde markayı seçin. <b>Ağda ara</b>'ya basıp TV'yi seçin, " +
          "sonra <b>Bağlan, kur ve başlat</b>'a basın.",
      },
      {
        screen: screen(`<div class="dlg"><h4>USB hata ayıklamaya izin verilsin mi?</h4>
          <div class="small">Bilgisayarın RSA anahtarı parmak izi:<br>4F:9A:21:C7:5E:08:B3:D2:6A:11:…</div>
          <div class="row ring dlgrow"><span class="cb">${I.check}</span>Bu bilgisayardan her zaman izin ver
            ${tag("İşaretleyin")}</div>
          <div class="btns"><span class="btn">İptal</span><span class="btn hl">İzin ver</span></div></div>`),
        title: "TV'de izin verin",
        text: "TV'de çıkan soruda <b>Bu bilgisayardan her zaman izin ver</b>'i işaretleyip <b>İzin ver</b>'e basın. " +
          "Uygulama kurulur ve açılır.",
      },
    ],
    warn: `<b>TV ile bilgisayar aynı modeme bağlı olmalı.</b> Ağda ara TV'yi bulamazsa IP'yi elle yazın: TV'de
      <b>Ayarlar › Ağ ve İnternet</b>'te bağlı olduğunuz Wi-Fi'ye girin, IP adresi orada yazar. TV'de USB hata ayıklama
      hiç yoksa programdaki <b>Gelişmiş</b> bölümünden kablosuz eşleştirme yapılır.`,
    ask: "Örn: TV'mde USB hata ayıklama yok",
  },

  /* ------------------------------------------------------------------ LG webOS */
  lg: {
    title: "LG TV'ye<br><em>GTA6 Altyazı TV</em> kurulumu",
    chips: [["clock", "10 dakika"], ["laptop", "Bilgisayar + kumanda"]],
    intro: `<b>LG webOS</b> TV'lerde, LG'nin ücretsiz <b>Developer Mode</b> uygulamasıyla TV'yi geliştirici moduna
      alırsınız; bunun için LG'nin geliştirici sitesinden açılan ücretsiz bir hesap gerekir. Bunu bir kez yaparsınız;
      sonra <b>GTA6 Altyazı</b>, TV uygulamasını bilgisayardan kurar ve günceller.`,
    steps: [
      {
        screen: screen(`<div class="browser"><div class="bar"><span class="url">${I.lock}webostv.developer.lge.com</span></div>
          <div class="nav"><span class="brand">webOS TV Developer</span><span style="flex:1"></span>
            <span class="lnk">Sign In</span><span class="su ring">Sign Up${tag("Tıklayın")}</span></div>
          <div class="body"><div class="ln" style="width:62%"></div><div class="ln" style="width:88%"></div>
            <div class="ln" style="width:74%"></div>
            <div class="mail">${I.check}E-postadaki onay bağlantısına tıklayın</div></div></div>`),
        title: "Ücretsiz LG geliştirici hesabı açın",
        text: "Bilgisayarda LG'nin geliştirici sitesinde <b>Sign Up</b> ile hesap açın, e-postadaki onayı tamamlayın. " +
          "Normal LG hesabı değil, geliştirici hesabı gerekir.",
      },
      {
        screen: screen(crumb("LG Content Store") +
          `<div class="field search">${I.search}Developer Mode</div>
          <div class="store"><span class="ico">&lt;/&gt;</span><div><div class="nm">Developer Mode</div>
            <div class="hint">Ücretsiz</div></div><span class="btn hl">Yükle${tag("OK'a basın")}</span></div>`, "glow"),
        title: "Developer Mode'u yükleyin",
        text: "TV'de <b>LG Content Store</b>'u (Uygulamalar) açın, <b>Developer Mode</b> diye aratın ve ücretsiz " +
          "uygulamada <b>Yükle</b>'ye basın.",
      },
      {
        screen: screen(crumb("Developer Mode") +
          `<div class="hint lbl">ID</div><div class="field">gelistirici_adiniz</div>
          <div class="hint lbl">Password</div><div class="field">••••••••••</div>
          <div class="btns left"><span class="btn hl">SIGN IN${sideTag("OK'a basın")}</span></div>`, "glow"),
        title: "Geliştirici hesabıyla girin",
        text: "<b>Developer Mode</b> uygulamasını açın ve 1. adımda açtığınız kullanıcı adı ve şifreyle girin.",
      },
      {
        screen: screen(crumb("Developer Mode") + row("Dev Mode Status", { hl: true, toggle: true, tag: "Açın" }) +
          row("Key Server", { toggle: false }) +
          `<div class="restart">${I.refresh}<div><b>TV yeniden başlar</b><br>Açılınca uygulamayı tekrar açın</div></div>`,
          "glow"),
        title: "Dev Mode Status'u açın",
        text: "<b>Dev Mode Status</b>'u açın; TV kendiliğinden yeniden başlar. Açılınca <b>Developer Mode</b> " +
          "uygulamasını tekrar açın.",
      },
      {
        screen: screen(crumb("Developer Mode") + row("Dev Mode Status", { toggle: true }) +
          row("Key Server", { hl: true, toggle: true, tag: "Açın" }) +
          `<div class="info ring"><div><span>IP</span><b>192.168.1.40</b></div>
            <div><span>Passphrase</span><b>A1B2C3</b></div></div>`, "glow"),
        title: "Key Server'ı açın",
        text: "<b>Key Server</b>'ı da açın. Ekranda <b>IP</b> ve <b>Passphrase</b> görünür; bu ekranı açık bırakın.",
      },
      {
        screen: screen(appTv(
          `<div class="r"><span class="lb">TV markası</span><span class="in"><span class="t">LG (webOS)</span>${caret}</span>` +
          `<span class="b">Resimli anlat</span></div>` +
          `<div class="r"><span class="in ring">192.168.1.40${ntag(1)}</span><span class="b">Ağda ara</span></div>` +
          `<div class="r"><span class="lb">LG parola (passphrase)</span><span class="in ring">A1B2C3${ntag(2)}</span></div>` +
          `<div class="r"><span class="b p ring">Bağlan, kur ve başlat${ntag(3)}</span>` +
          `</div>`)),
        title: "IP ve Passphrase'i yazıp kurun",
        text: "GTA6 Altyazı'da <b>Bağlantı › TV</b> bölümünde <b>LG (webOS)</b>'u seçin, IP'yi ve Passphrase'i " +
          "yazın, <b>Bağlan, kur ve başlat</b>'a basın.",
      },
    ],
    warn: `<b>LG başka uygulamanın üstüne yazı çizmeye izin vermez:</b> PS5 görüntüsü GTA6 Altyazı TV uygulamasının
      içinde açılır. Kumandada <b>◀ ▶</b> ile PS5'in takılı olduğu HDMI girişini seçin. Geliştirici modu en çok 1000 saat
      açık kalır; program her bağlanışta süreyi kendisi baştan başlatır.`,
    ask: "Örn: LG'de Key Server açılmıyor",
  },

  /* ------------------------------------------------------------------ Samsung Tizen */
  samsung: {
    title: "Samsung TV'ye<br><em>GTA6 Altyazı TV</em> kurulumu",
    chips: [["clock", "5 dakika"], ["remote", "Kumanda + bilgisayar"]],
    intro: `<b>Samsung Tizen</b> TV'lerde <b>Tizen Studio gerekmez</b>: TV'de gizli <b>Developer mode</b> penceresini
      açıp bu bilgisayarın IP'sini yazarsınız. Bunu bir kez yaparsınız; sonra <b>GTA6 Altyazı</b>, TV uygulamasını
      bilgisayardan kurar ve günceller. İlk kurulumda ücretsiz bir Samsung hesabıyla giriş istenir.`,
    steps: [
      {
        screen: screen(`<div class="crumb">Kumandada <b>ev tuşu</b></div>
          <div class="hint mid">Uygulamalar'ın üstünde durmak yetmez:<br>OK'a basıp sayfayı açın.</div>
          <div class="hbar"><span class="tile">${I.input}Kaynaklar</span>
            <span class="tile hl">${I.apps}Uygulamalar${tag("OK'a basın")}</span>
            <span class="tile">${I.gear}Ayarlar</span><span class="tile e"></span><span class="tile e"></span></div>`,
          "glow"),
        title: "Uygulamalar sayfasını açın",
        text: "Kumandada <b>ev</b> tuşuna basın, alttaki şeritte <b>Uygulamalar</b>'a gelip <b>OK</b>'a basın. " +
          "Uygulamaların kareler halinde dizildiği tam sayfa açılmalı.",
      },
      {
        screen: screen(crumb("Uygulamalar") + `<div class="tiles">${"<span></span>".repeat(10)}</div>
          <div class="digits"><div class="grp ring">${[1, 2, 3, 4, 5].map((n) => `<span class="on">${n}</span>`).join("")}
            ${tag("Sırayla, her birinde OK")}</div>${[6, 7, 8, 9, 0].map((n) => `<span>${n}</span>`).join("")}</div>
          <div class="hint below">Rakam tuşu yoksa: <b>123</b> / renkli nokta tuşu</div>`, "glow"),
        title: "1 2 3 4 5 yazın",
        text: "Sırayla <b>1 2 3 4 5</b>'e basın. İnce kumandada <b>123</b> ya da 4 renkli nokta tuşu ekranda " +
          "rakamları açar: her rakama gelip <b>OK</b>'a basın.",
      },
      {
        screen: screen(`<div class="dlg tight"><div class="dh"><h4>Developer mode</h4>
            <div class="seg"><span class="on">On</span><span>Off</span></div>${tag("On yapın")}</div>
          <div class="hint lbl">Host PC IP</div>
          <div class="field ring">192.168.1.25${tag("Bu bilgisayarın IP'si")}</div>
          <div class="btns"><span class="btn blue">OK</span><span class="btn">Cancel</span></div></div>`),
        title: "Developer mode'u açın",
        text: "<b>Developer mode</b>'u <b>On</b> yapın, <b>Host PC IP</b>'ye bu bilgisayarın IP'sini yazıp " +
          "<b>OK</b>'a basın. IP, programda <b>Bağlantı › TV</b> bölümünde yazar.",
      },
      {
        screen: screen(`<div class="remote"><div class="pwr ring">${I.power}${sideTag("2 sn basılı tutun")}</div>
            <div class="okring"><span>OK</span></div><div class="rkeys"><span></span><span></span><span></span></div>
            <div class="rkeys"><span></span><span></span><span></span></div></div>
          <div class="minitv">${I.refresh}<div>TV kapanıp<br>kendiliğinden açılır</div></div>`, "glow"),
        title: "Güç tuşunu 2 saniye basılı tutun",
        text: "Kapatıp açmak yetmez: <b>güç</b> tuşunu yaklaşık <b>2 saniye</b> basılı tutun; TV kapanıp " +
          "kendiliğinden açılır. Uygulamalar sayfasının üstünde <b>Developer mode</b> yazar.",
      },
      {
        screen: screen(crumb("Ayarlar", "Genel", "Harici Aygıt Yöneticisi") +
          row("Anynet+ (HDMI-CEC)", { hl: true, toggle: false, tag: "Kapatın", tagEdge: true }) +
          row("Otomatik Kaynak Değiştirme", { ring: true, toggle: false }) +
          '<div class="hint">Açık kalırsa PS5 açılınca TV <b>doğrudan HDMI\'ya geçer</b>, altyazı görünmez.</div>',
          "glow"),
        title: "Anynet+ (HDMI-CEC)'yi kapatın",
        text: "<b>Ayarlar › Genel › Harici Aygıt Yöneticisi</b>'nde <b>Anynet+ (HDMI-CEC)</b>'yi, varsa " +
          "<b>Otomatik Kaynak Değiştirme</b>'yi de kapatın.",
      },
      {
        screen: screen(appTv(
          `<div class="r"><span class="lb">TV markası</span><span class="in"><span class="t">Samsung (Tizen)</span>${caret}</span>` +
          `<span class="b">Resimli anlat</span></div>` +
          `<div class="note">Bu bilgisayarın IP'si (Host PC IP): <b>192.168.1.25</b></div>` +
          `<div class="r"><span class="in">192.168.1.50</span><span class="b ring">Ağda ara${ntag(1)}</span></div>` +
          `<div class="r"><span class="b p ring">Bağlan, kur ve başlat${ntag(2)}</span>` +
          `</div>`)),
        title: "Programdan kurun",
        text: "<b>Ağda ara</b>'ya basıp TV'yi seçin, <b>Bağlan, kur ve başlat</b>'a basın. İlk seferde tarayıcıda " +
          "Samsung hesabınızla girin; program uygulamayı bu TV'ye özel imzalatıp kurar.",
      },
    ],
    warn: `<b>Samsung başka uygulamanın üstüne yazı çizmeye izin vermez:</b> PS5 görüntüsü GTA6 Altyazı TV uygulamasının
      içinde açılır. Kumandada <b>◀ ▶</b> ile PS5'in takılı olduğu HDMI girişini seçin. 12345 tutmazsa Uygulamalar
      sayfasından çıkıp yeniden girin ve baştan yazın; TV'nin USB girişine takılan bir klavye de olur.`,
    ask: "Örn: Samsung TV'de 12345 yazamıyorum",
  },
};
