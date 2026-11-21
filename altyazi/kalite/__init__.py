# SPDX-License-Identifier: AGPL-3.0-only
"""Çeviri kalitesi yardımcıları: OCR temizliği, altyazı kararlılığı, terim koruma, Türkçe ekler ve son düzeltmeler.

Bu paketteki modüller Nino Game Translator'ın (https://github.com/yunusdemirbag/nino-game-translator, AGPL-3.0;
CouchSubs tabanlı, Copyright (C) 2026 Sinan Yorulmaz, https://github.com/yorulmazsinan/couchsubs) Swift çekirdeğinden
(core/Sources/CouchSubsCore/) Python'a taşınmıştır; davranış, eşikler, sözcük listeleri ve düzenli ifadeler korunmuştur.
Taşıma tarihi: 2026-11-21. Her modülün başında kaynak dosyası yazılıdır:

- son_duzelti      ← TurkishPostEdit.swift   (çevirinin Türkçe biçim düzeltmeleri, sen/siz emir uyumu)
- ek               ← TurkishSuffix.swift     (terime Türkçe ek: ünlü uyumu, kaynaştırma, yumuşama)
- terim            ← TermProtection.swift    (sözlük terimlerini yer tutucu adla koruma)
- konusan          ← SpeakerPrefix.swift     (baştaki konuşan adı: "ARTHUR: ...")
- dengeleyici      ← SubtitleStabilizer.swift (kare kare OCR'dan çevir/sil/geri getir kararı)
- satir            ← SubtitleWrap.swift      (uzun çeviriyi dengeli satırlara bölme)
- ocr_gurultu      ← OcrNoise.swift          (OCR çöp sözcüklerini ayıklama, okuma puanı)
- oyun_ingilizce   ← GameEnglish.swift       (oyun deyimlerini düz İngilizceye çevirme)
- metin_eslesme    ← TextMatch.swift         (gürültüye dayanıklı benzerlik, yeniden okuma kararları)
- bolucu           ← SubtitleSegmenter.swift (altyazıyı cümlelere/etiketlere bölme, büyük harf düzeni)
- sozluk           ← Glossary.swift          (terim sözlüğü, hazır satırlar, argo kalıpları)

Hattaki çağrı sırası için `README_entegrasyon` modülüne bakın.
"""
