# SPDX-License-Identifier: AGPL-3.0-only
"""Entegrasyon notu: kalite modüllerinin çeviri hattındaki çağrı sırası (kod içermez).

Kaynak: Nino Game Translator'ın FreeTranslation.swift (FreeTranslation.translate, FreeLineTranslator, RecentLines),
SubtitlePipeline.swift, Reading.swift (withoutOcrNoise) ve AITranslation.swift dosyalarındaki sıra. Aşağıdaki adlar
bu paketin modülleridir (`from altyazi.kalite import ...`).

====================================================================================================================
0. Ortak: her karede (pipeline.py, okuma → çeviri isteği)
====================================================================================================================
 1. `ocr_gurultu.clean(satir)` — her OCR satırına AYRI AYRI, satırlar birleştirilmeden ve `pipeline.clean_ocr`'dan
    ÖNCE (clean_ocr "|" → "I" yaptığı için sonra çağrılırsa "|" kenar/zamir ayrımı kaybolur). Boş kalan satır atılır.
    (Nino: Reading.withoutOcrNoise, satırlar joiningRows'tan önce.)
 2. `SubtitleStabilizer.feed(metin, signature=bölge_izi, box=TextBox)` → `StabilizerAction`:
      - `translate(kaynak)` → çeviri isteği aç (aşağıdaki 3. adım);
      - `restore(kaynak)`   → çevirmene gitmeden o kaynağın son çevirisini yeniden göster;
      - `CLEAR`              → bölgeyi temizle;  - `NONE` → bir şey yapma.
    `stabilizer.note` (worse_reread / garbled_dropped) yalnız günlük içindir. Bu adım `pipeline.worse_reread`'in ve
    "aynı metin mi" kontrolünün yerini alır (içinde metin_eslesme.is_same_subtitle / is_worse_reread / adds_meaning
    ve ocr_gurultu.looks_garbled var). İz verilmiyorsa (signature=None) eski kural: 800 ms boşlukta silinir.
 3. İstek: `onek = konusan.split(kaynak)`. Paket araması önce `kaynak` ile, bulunmazsa `onek.body` ile yapılır.
 4. Motora giden metin: `girdi = onek.body if onek else kaynak` (konuşan adı çeviriye GİTMEZ).
 5. Motor (aşağıda A ya da B) → `cumle`.
 6. `stabilizer.should_send(girdi, cumle)` False ise metin zaten Türkçedir: gösterme. Çeviri hata verdiyse ve satır
    hâlâ ekrandaysa `stabilizer.forget_sent()` (en erken 1 sn sonra yeniden dener).
 7. Gösterim: `metin = konusan.present(cumle, source=kaynak, show=ayar_konusan_adi)`; katman/TV için
    `satir.fit(metin)` → (text, scale). TV'de "yerine koy" kararı: `metin_eslesme.is_revision(kaynak, onceki_kaynak)`.

====================================================================================================================
A. Yerel MT motoru (OPUS-MT, `LocalMT`; translate.py `_run_fast` ve `translate_now`'daki hızlı yol)
====================================================================================================================
Satır düzeyi (Nino: FreeLineTranslator.translate):
 A1. `onceki_satir`: bu satırdan önce gösterilen satır (Nino RecentLines: aynı satır yeniden okunursa aynı bağlam;
     önceki satır 20 sn'den eskiyse bağlam yok).
 A2. `parcalar = bolucu.split(girdi)`; `konusanlar.learn(parcalar)` (`bolucu.SpeakerNames`, oturum boyu tek nesne).
 A3. `onceki = onceki_satir'ın son translate=True parçası` (bolucu.split ile).
 A4. Her `translate=True` parça için: `baglam = onceki if kisa_mi(parca) else None`; `ceviri = cumle_cevir(parca,
     baglam)`; `onceki = parca.text`. translate=False parçalar (etiket "ATREUS: ", tire "- ", " ", "\\n") aynen kalır.
     kisa_mi: harf içeren sözcük sayısı 1..3 (Nino shortLineWords = 4, "kelime < 4").
 A5. `son_duzelti.register(ceviriler)` — sen/siz emir uyumu satırın bütününe bakar (önbellekteki cümleler değişmez).
 A6. Parçaları sırayla birleştir (None olanın yerine parçanın kendi metni).

Cümle düzeyi `cumle_cevir(cumle, baglam)` (Nino: FreeTranslation.translate; sıra birebir):
 a. `hazir = sozluk.line(cumle)` varsa → `son_duzelti.apply(cumle, hazir)` döner; MOTORA GİTMEZ.
 b. `kesme = son_duzelti.apostrophe(cumle)`
 c. `hazirla(t) = oyun_ingilizce.plain(sozluk.plain(bolucu.normalize_case(t, names=konusanlar.all | sozluk.capital_words)))`
    Bizim `slang.normalize` (argo_duzelt açıksa) `sozluk.plain`'den SONRA, `oyun_ingilizce.plain`'den ÖNCE girmeli:
    hazirla(t) = oyun_ingilizce.plain(slang.normalize(sozluk.plain(normalize_case(t)))). slang.py "got your six",
    "heads up", "friendlies", "hostiles" gibi kalıpları zaten farklı karşılıklarla çeviriyor; önce o çalışınca
    oyun_ingilizce'deki aynı kalıp eşleşmez (çakışma yok, yalnız slang'ın karşılığı kazanır).
 d. Bağlam varsa:
      koruyucu = terim.TermProtector(sozluk, [cumle, baglam])
      baglam_m = koruyucu.protect(hazirla(baglam))[0]
      cumle_m, yuvalar = koruyucu.protect(hazirla(cumle))
      cikti = motor(baglam_m + " *** " + cumle_m)
      sonra = ayractan_sonra(cikti, cumle)       # kurallar aşağıda
      geri = TermProtector.restore(sonra, yuvalar, koruyucu.all_slots, kesme) if sonra else None
      geri varsa → son_duzelti.apply(cumle, geri) döner.
 e. Tek başına:
      tek = terim.TermProtector(sozluk, [cumle]); girdi_m, kullanilan = tek.protect(hazirla(cumle))
      cevrilen = motor(girdi_m)
      kullanilan boşsa → son_duzelti.apply(cumle, cevrilen)
      geri = TermProtector.restore(cevrilen, kullanilan, tek.all_slots, kesme); varsa → son_duzelti.apply(cumle, geri)
 f. Yer tutucu düştüyse: son_duzelti.apply(cumle, motor(hazirla(cumle)))  (terimsiz ama eksiksiz çeviri).

`ayractan_sonra(cikti, kaynak)` (Nino: FreeTranslation.afterSeparator): "***" tam bir kez geçmeli; ayraçtan sonrası
`.strip()`; sonrası "*" ile başlıyor ya da öncesi "*" ile bitiyorsa None; iki yanda da harf yoksa None; sonrası
UTF-16 uzunluğu `3 * len(kaynak) + 20`'yi aşıyorsa None. Ayraç sabiti " *** " (OPUS-MT sözlüğünde "▁***" tek parça).

Önbellek (Nino: FreeTranslation.cacheKey): anahtar = (bağlam + "\\x1f" + cümle) ya da cümle; sözlük metne dokunuyorsa
(`sozluk.matches(temel) or sozluk.rewrites(cumle) or sozluk.rewrites(baglam)`) başına `sozluk.fingerprint + "\\x1f"`
eklenir. Kurallar değişince eski hızlı çevirilerin yeniden çevrilmesi için Nino motor adına sürüm koyar
("apple-p3"); bizde `Cache.put(..., FAST, "yerel-k1")` gibi bir ad kullanılabilir.

Sözlük kaynağı: `sozluk.Glossary.merge([Glossary.built_in(), Glossary.from_dict({"terms": cfg.sozluk,
"keep": gta_terms.KEEP}), GlossaryStore(klasör).glossary])` — sonraki kazanır. Bu, `terms.protect/restore`'un ve
`TranslationEngine._post`'taki düz `str.replace` sözlüğünün yerini alır (terim.TermProtector tam sözcük eşleşir, ekleri
ek.attach kurar; cümle başındaki cins adı büyük harfle başlatır). Kullanıcı sözlük klasörü için öneri:
`paths.data("sozluk")` (Nino: ~/Library/Application Support/Nino/Glossary/*.json).

====================================================================================================================
B. Yapay zekâ motoru (Claude / Gemini / DeepL / yerel AI; translate.py `_run_refine` ve `translate_now`'daki kalite yolu)
====================================================================================================================
Nino'da (AITranslation.swift) yapay zekâ çıktısına terim koruma, ek kurma ve TurkishPostEdit UYGULANMAZ: sözlük ve
üslup modelin sistem talimatında verilir (bizde gta_terms.style_guide()); DeepL'de terimler etiketle korunur.
 B1. 0. bölümün 1–4. adımları (girdi = konuşan adsız cümle).
 B2. `parcalar = bolucu.split(girdi)`; `konusanlar.learn(parcalar)`.
 B3. Önbellekte olmayan translate=True parçalar için kaynak: `bolucu.normalize_case(parca.text, names=konusanlar.all)`
     (tümü büyük harfli satır cümle düzenine gelir; adlar büyük kalır). Etiket ve tireler modele GİTMEZ.
 B4. Model yanıtı her parça için alınır.
 B5. Yankı denetimi: `metin_eslesme.is_similar(normalize(parca), normalize(yanit), threshold=0.90)` ise model cümleyi
     çevirmeden geri vermiştir → bu parça bir kez yerel motorla (A yolu) çevrilir; o sonuç yapay zekâ önbelleğine
     YAZILMAZ. Yerel motor da aynısını verirse (ad, Türkçe menü) modelin yanıtı kalır.
 B6. Parçaları birleştir (translate=False parçalar aynen), önbelleğe yaz.
 B7. 0. bölümün 6–7. adımları (should_send, konusan.present, satir.fit, is_revision).
İsteğe bağlı: `son_duzelti.apply` yalnız biçim düzeltir (noktalama boşluğu, kaynağın !/?/… sonu, tırnak türü) ve
yapay zekâ çıktısına da zarar vermez; Nino bunu yapay zekâ yolunda kullanmıyor, eklemek bizim kararımız olur.

====================================================================================================================
Mevcut koddaki karşılıklar
====================================================================================================================
- pipeline.clean_ocr      → önce ocr_gurultu.clean (satır başına), sonra clean_ocr kalabilir.
- pipeline.looks_like_text→ değişmez; ocr_gurultu.looks_garbled ayrıca dengeleyicinin içinde kullanılıyor.
- pipeline.worse_reread   → dengeleyici.SubtitleStabilizer (ya da doğrudan metin_eslesme.is_worse_reread).
- pipeline.normalize_text → metin_eslesme.normalize (biraz farklı: kesme işaretini de boşluğa çevirir).
- terms.protect/restore   → terim.TermProtector + sozluk.Glossary (A, cümle düzeyi d–f).
- slang.normalize         → A, cümle düzeyi c'deki sırada kalır.
- TranslationEngine._post → yerel yolda son_duzelti.apply + son_duzelti.register; düz sözlük değişimi gerekmez.
"""
