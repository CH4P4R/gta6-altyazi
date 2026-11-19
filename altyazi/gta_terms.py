"""GTA için yerleşik Türkçe karşılıklar (Claude'a üslup rehberi olarak verilir).

CouchSubs'ın GTA 6 sözlüğünden (tools/packs/glossary/gta6.json; https://github.com/yorulmazsinan/couchsubs,
AGPL-3.0, Sinan Yorulmaz). Karşılıklar topluluğun GTA V Türkçe yamasındaki yaygın kullanımdan derlenmiştir.
"""

from __future__ import annotations

KEEP = ["Lucia", "Jason", "Vice City", "Leonida", "Leonida Keys", "Grassrivers", "Port Gellhorn", "Ambrosia", "Mount Kalaga", "Los Santos", "Liberty City", "San Andreas", "Rockstar", "FIB", "IAA", "LSPD", "VCPD", "Ammu-Nation", "Lifeinvader", "Pay 'n' Spray", "Cluckin' Bell", "Burger Shot", "Sprunk", "eCola"]

TERMS: dict[str, list[tuple[str, str]]] = {
    "address": [("dude", "ahbap"), ("man", "dostum"), ("bro", "kardeş"), ("homie", "kardeşim"), ("buddy", "dostum"), ("my friend", "dostum"), ("nigga", "kanka"), ("sir", "efendim"), ("ma'am", "hanımefendi"), ("boss", "patron"), ("honey", "canım"), ("baby", "bebeğim"), ("partner", "ortak"), ("kid", "evlat"), ("son", "evlat")],
    "insults": [("fuck", "siktir"), ("shit", "siktir"), ("damn", "lanet olsun"), ("what the fuck", "bu da ne amına koyayım"), ("holy shit", "ha siktir"), ("son of a bitch", "orospunun evladı"), ("fuck you", "siktir git"), ("fuck off", "siktir git"), ("motherfucker", "orospu çocuğu"), ("asshole", "orospu çocuğu"), ("bitch", "orospu"), ("pussy", "korkak"), ("idiot", "geri zekalı"), ("fool", "salak"), ("jerk", "lavuk"), ("punk", "serseri"), ("snitch", "muhbir"), ("rat", "sıçan")],
    "crime": [("cops", "polisler"), ("pigs", "domuzlar"), ("feds", "federaller"), ("heist", "soygun"), ("crew", "ekip"), ("gang", "çete"), ("job", "iş"), ("score", "vurgun"), ("getaway car", "kaçış aracı"), ("stash", "zula"), ("weed", "ot"), ("meth", "met"), ("coke", "kokain"), ("dealer", "satıcı"), ("armored truck", "zırhlı araç"), ("safehouse", "sığınak"), ("ammo", "mühimmat"), ("shotgun", "pompalı tüfek"), ("pistol", "tabanca"), ("rifle", "tüfek"), ("long guns", "uzun namlulu silahlar"), ("lawyer", "avukat"), ("prison", "hapishane"), ("bail", "kefalet"), ("parole", "şartlı tahliye"), ("cartel", "kartel")],
    "game_ui": [("wasted", "ÖLDÜN"), ("busted", "YAKALANDIN"), ("mission passed", "Görev Başarılı"), ("mission failed", "Görev Başarısız"), ("wanted level", "Aranma Seviyesi"), ("lose the cops", "Polislerden kurtul."), ("get in the car", "Arabaya bin."), ("checkpoint", "Kontrol Noktası"), ("destination", "Varış Yeri"), ("waypoint", "Varış Noktası"), ("objective", "Hedef")],
    "phrases": [("come on", "hadi"), ("let's go", "gidelim"), ("hurry up", "acele et"), ("watch out", "dikkat"), ("shut up", "kapa çeneni"), ("calm down", "sakinleş"), ("take it easy", "ağır ol"), ("get down", "yere yat"), ("freeze", "olduğun yerde kal"), ("copy that", "anlaşıldı"), ("you got it", "tamamdır"), ("see ya", "görüşürüz"), ("follow me", "beni takip et")],
    "places": [("strip club", "striptiz kulübü"), ("gas station", "benzinci"), ("liquor store", "içki dükkânı"), ("downtown", "şehir merkezi"), ("docks", "rıhtım"), ("swamp", "bataklık"), ("marina", "marina"), ("yacht", "yat"), ("mansion", "malikâne")],
}

LABELS = {"address": "Forms of address", "insults": "Swearing (keep the same strength)", "crime": "Crime slang",
          "game_ui": "Game UI", "phrases": "Common phrases", "places": "Places"}


def style_guide() -> str:
    """Claude sistem talimatına eklenen kısa rehber (önbelleğe alınan kısımda durur)."""
    out = ["", "", "Established Turkish renderings used by Turkish GTA players (from the community GTA V translation). "
           "Prefer them when they fit the context; they are guidance, not word-for-word rules:"]
    for key, pairs in TERMS.items():
        out.append(f"- {LABELS[key]}: " + "; ".join(f"{en} = {tr}" for en, tr in pairs))
    return "\n".join(out)
