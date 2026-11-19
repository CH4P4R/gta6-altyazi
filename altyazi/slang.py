"""Sokak dilini yerel çeviri modeli için düzgün İngilizceye çevirir.

OPUS-MT düzgün metinlerle eğitildiği için "gonna", "ain't", "homie" gibi ifadeleri kötü çevirir.
Bu dönüşüm sadece yerel modele giden metne uygulanır; Claude'a orijinal metin gider.
Anlamı bağlama göre değişen kelimeler ("dope", "ride", "piece", "heat") bilerek dışarıda bırakıldı.
"""

from __future__ import annotations

import re

# Kısaltmalar ve ağız (konuşma dili yazımları)
_CONTRACTIONS = {
    "gonna": "going to", "wanna": "want to", "gotta": "have to", "hafta": "have to", "hasta": "has to",
    "gimme": "give me", "lemme": "let me", "kinda": "kind of", "sorta": "sort of", "outta": "out of",
    "lotta": "lot of", "lotsa": "lots of", "dunno": "don't know", "tryna": "trying to", "finna": "going to",
    "imma": "I am going to", "i'mma": "I am going to", "ima": "I am going to", "ain't": "is not",
    "aint": "is not", "y'all": "you all", "ya'll": "you all", "cuz": "because", "'cause": "because",
    "coz": "because", "c'mon": "come on", "cmon": "come on", "y'know": "you know", "ya know": "you know",
    "whatcha": "what are you", "watcha": "what are you", "gotcha": "got you", "betcha": "bet you",
    "dontcha": "don't you", "didja": "did you", "wassup": "what is up", "whassup": "what is up",
    "sup": "what is up", "innit": "isn't it", "oughta": "ought to", "coulda": "could have",
    "shoulda": "should have", "woulda": "would have", "mighta": "might have", "musta": "must have",
    "'em": "them", "em'": "them", "'bout": "about", "'til": "until", "til": "until", "'round": "around",
    "nothin'": "nothing", "somethin'": "something", "everythin'": "everything", "ol'": "old",
    "aight": "alright", "ight": "alright", "a'ight": "alright", "nah": "no", "naw": "no", "yeah": "yes",
    "yea": "yes", "yup": "yes", "yep": "yes", "nope": "no", "ya": "you", "yo'": "your", "u": "you",
    "ur": "your", "thru": "through", "tho": "though", "prolly": "probably", "def": "definitely",
}

# Sokak dili kelimeleri (anlamı net olanlar)
_SLANG = {
    "homie": "friend", "homies": "friends", "homeboy": "friend", "homeboys": "friends", "dawg": "buddy",
    "bruh": "brother", "bro": "brother", "bros": "brothers", "fam": "family", "shawty": "girl", "bae": "baby",
    "cops": "police", "cop": "police officer", "five-o": "police", "5-0": "police", "po-po": "police",
    "popo": "police", "feds": "federal agents", "pigs": "police", "snitch": "informant", "snitches": "informants",
    "hella": "very", "deadass": "seriously", "no cap": "no lie", "for real": "seriously", "fr": "seriously",
    "my bad": "my mistake", "strapped": "armed", "bucks": "dollars", "moolah": "money", "dough": "money",
    "OG": "veteran", "wifey": "girlfriend", "boo": "darling", "lowkey": "secretly", "highkey": "obviously",
    "sus": "suspicious", "salty": "upset", "beef": "conflict", "squad": "crew", "crib": "house",
    "whip": "car", "wheels": "car", "kicks": "shoes", "grub": "food", "chill out": "calm down",
}

# Tek başına söylenen cevaplar
_UTTERANCES = {"bet": "Okay", "word": "Agreed", "facts": "That is true", "say less": "Understood"}


# Özneye göre değişen kalıplar (tablodan önce uygulanır)
_PHRASES = [
    (r"\bain'?t nobody\b", "nobody is"), (r"\bain'?t nothing\b", "nothing is"), (r"\bain'?t no\b", "there is no"),
    (r"\bain'?t got\b", "do not have"), (r"\bI ain'?t\b", "I am not"),
    (r"\b(you|we|they) ain'?t\b", r"\1 are not"), (r"\b(he|she|it|that|this) ain'?t\b", r"\1 is not"),
    (r"\bI (gonna|finna)\b", "I am going to"), (r"\b(you|we|they) (gonna|finna|tryna)\b",
                                                    lambda m: f"{m.group(1)} are {'trying' if m.group(2).lower() == 'tryna' else 'going'} to"),
    (r"\b(he|she|it) (gonna|finna)\b", r"\1 is going to"),
    (r"\b(you|we|they) (gotta)\b", r"\1 have to"), (r"\b(he|she|it) gotta\b", r"\1 has to"),
    # Oyun ve aksiyon deyimleri: makine çevirisi kelimesi kelimesine çevirip saçmalıyor
    # (fikir CouchSubs'ın GameEnglish listesinden: https://github.com/yorulmazsinan/couchsubs, AGPL-3.0)
    (r"\b(I've|I) got your (six|back)\b", "I am protecting you"), (r"\bgot your six\b", "got your back"),
    (r"\bwatch your six\b", "watch behind you"), (r"\bon your six\b", "behind you"),
    (r"\bwe('ve| have)? got company\b", "enemies are coming"), (r"\bheads up\b", "watch out"),
    (r"\bfriendlies\b", "allies"), (r"\bhostiles\b", "enemies"), (r"\btangos?\b", "enemy"),
    (r"\blay low\b", "hide for a while"), (r"\blie low\b", "hide for a while"),
    (r"\bhit the road\b", "leave"), (r"\bbail\b(?! out)", "run away"), (r"\bfloor it\b", "drive faster"),
    (r"\bstep on it\b", "drive faster"), (r"\bshake (them|'em|the cops|the police)\b", "lose \\1"),
    (r"\blose the heat\b", "escape the police"), (r"\bwe're toast\b", "we are finished"),
    (r"\bpiece of cake\b", "very easy"), (r"\bcut it out\b", "stop it"), (r"\bknock it off\b", "stop it"),
    (r"\bgo dark\b", "stop all communication"), (r"\btake (him|her|them) out\b", "kill \\1"),
    (r"\bsmoke (him|her|them)\b", "kill \\1"), (r"\bpop (him|her|them)\b", "shoot \\1"),
    # "long guns" kelimesi kelimesine "uzun kollu silahlar" çıkıyordu
    (r"\blong guns\b", "rifles"), (r"\blong gun\b", "rifle"),
]
_PHRASES_RE = [(re.compile(p, re.IGNORECASE), r) for p, r in _PHRASES]


def _build(table: dict[str, str]) -> re.Pattern:
    keys = sorted(table, key=len, reverse=True)
    alt = "|".join(re.escape(k) for k in keys)
    return re.compile(rf"(?<![\w'])({alt})(?![\w'])", re.IGNORECASE)


_TABLE = {**_CONTRACTIONS, **_SLANG}
_LOWER = {k.lower(): v for k, v in _TABLE.items()}
_RE = _build(_TABLE)
_ING = re.compile(r"\b(\w{2,})in'(?![\w'])", re.IGNORECASE)   # talkin' -> talking


def _keep_case(src: str, dst: str) -> str:
    if src.isupper() and len(src) > 1 and not dst.isupper():
        return dst.upper()
    if src[:1].isupper():
        return dst[:1].upper() + dst[1:]
    return dst


def normalize(text: str) -> str:
    stripped = text.strip()
    bare = stripped.rstrip(".!?").lower()
    if bare in _UTTERANCES:
        return _UTTERANCES[bare] + stripped[len(bare):] if stripped[len(bare):] else _UTTERANCES[bare] + "."
    out = _ING.sub(lambda m: m.group(1) + "ing", text)
    for rx, rep in _PHRASES_RE:
        out = rx.sub(lambda m, r=rep: _keep_case(m.group(0), r(m) if callable(r) else m.expand(r)), out)
    out = _RE.sub(lambda m: _keep_case(m.group(0), _LOWER[m.group(0).lower()]), out)
    return re.sub(r"\s+", " ", out).strip()
