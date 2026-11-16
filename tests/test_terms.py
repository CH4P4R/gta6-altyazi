from altyazi.terms import harmonize, protect, restore


def test_harmonize_suffixes():
    assert harmonize("Vice City", "a") == "Vice City'ye"
    assert harmonize("Vice City", "dan") == "Vice City'den"
    assert harmonize("Jason", "u") == "Jason'u"
    assert harmonize("Lucia", "un") == "Lucia'nın"
    assert harmonize("Lucia", "la") == "Lucia'yla"
    assert harmonize("Port Gellhorn", "da") == "Port Gellhorn'da"
    assert harmonize("Kalaga", "") == "Kalaga"


def test_protect_and_restore():
    g = {"Vice City": "Vice City", "Jason": "Jason", "Wanted": "Aranıyor"}
    text, mapping = protect("Take Jason to Vice City.", g)
    assert "Jason" not in text and "Vice City" not in text and len(mapping) == 2
    ph_city = next(p for p, t in mapping.items() if t == "Vice City")
    ph_jason = next(p for p, t in mapping.items() if t == "Jason")
    assert restore(f"{ph_jason}'u {ph_city}'a götür.", mapping) == "Jason'u Vice City'ye götür."
    assert restore("Onu götür.", mapping) is None          # model adı kaybetti: korumasız çeviriye dönülür
    assert protect("Nothing here.", g) == ("Nothing here.", {})
