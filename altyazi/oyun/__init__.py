# SPDX-License-Identifier: AGPL-3.0-only
"""Oyun algısı ve altyazı yeri öğrenimi.

Bu paketteki modüller Nino Game Translator'dan (CouchSubs türevi, AGPL-3.0-only;
core/Sources/CouchSubsCore) Python'a taşındı. Eşikler ve kurallar Swift sürümüyle birebir aynıdır:

- oyun_algi        GameSense.swift + RunningGame.swift + GameChoice.swift (oynanan oyun ve paket eşlemesi)
- altyazi_yeri     Pipeline/SubtitleLayout.swift (oyun başına altyazı şeridi; JSON'da saklanır)
- olcu             LineMetrics.swift (satır ölçümleri)
- yeniden_okuma    Pipeline/Rereads.swift (aynı satırın farklı okumaları)
- kare_kapisi      Pipeline/FrameGate.swift (okuma hattına tek kare)
- okuma_zamanlayici ReadScheduler.swift (hangi karede yazı tanıma yapılacağı)
- paket_bulanik    PackFuzzy.swift (OCR'ın bozduğu satırı paketin bulanık dizininde bulma)
- metin            TextMatch.swift + OcrNoise.swift (yalnız yukarıdakilerin kullandığı parçalar)

Teşekkürler: Nino Game Translator ve CouchSubs geliştiricileri.
"""
