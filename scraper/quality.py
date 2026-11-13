"""Kvalitetsscore 0–100 per TV-familie.

Skjønnsmessig rangering basert på tester (RTINGS, What Hi-Fi, Tek.no, Lyd & Bilde m.fl.)
for 55" der ikke annet er nevnt. Brukes til «pris mot kvalitet»-plottet. Justeres
for størrelse (mindre LCD-modeller har ofte svakere panel, 42" OLED mangler lysforsterker).
Rekkefølgen betyr noe: første mønster som treffer familienavnet vinner.
"""
import re

TIERS = [
    # --- OLED, toppsjikt ---
    (r"SAMSUNG S9[59]\b|SAMSUNG S95|SAMSUNG S99", 93, "Samsung S95/S99 QD-OLED"),
    (r"BRAVIA 8 II|XR8M2", 92, "Sony Bravia 8 II"),
    (r"LG (?:OLED )?[GM][5-9]\b", 92, "LG G/M-serie"),
    (r"PHILIPS OLED(\+)?9[15]", 90, "Philips OLED+ 9xx"),
    (r"LG (?:OLED )?C[5-9]E\b", 88, "LG C Pro (C5E/C6E)"),
    (r"LG (?:OLED )?C6H|LG OLED C6\b", 87, "LG C6"),
    (r"SAMSUNG S90", 86, "Samsung S90"),
    (r"BRAVIA 8\b|XR80", 86, "Sony Bravia 8"),
    (r"LG (?:OLED )?C5\b", 85, "LG C5"),
    (r"PHILIPS OLED8|PHILIPS OLED81", 84, "Philips OLED8xx"),
    (r"LG (?:OLED )?C4\b", 82, "LG C4"),
    (r"LG (?:OLED )?B[6-9]E?\b", 80, "LG B6"),
    (r"SONY A80|BRAVIA 6\b|K\d+A65", 78, "Sony A80/Bravia 6"),
    (r"LG (?:OLED )?B5", 78, "LG B5"),
    (r"SAMSUNG S8[5-9]", 78, "Samsung S85"),
    (r"PHILIPS OLED7", 77, "Philips OLED7xx"),
    # --- Mini-LED / RGB ---
    (r"BRAVIA 9", 88, "Sony Bravia 9"),
    (r"BRAVIA 7 II|XR7\dM2", 82, "Sony Bravia 7 II (True RGB)"),
    (r"SAMSUNG QN9\d", 82, "Samsung QN90"),
    (r"TCL (C8|X\d|C9)", 80, "TCL C8/X"),
    (r"SAMSUNG R8\d|MICRO RGB", 78, "Samsung Micro RGB"),
    (r"HISENSE (UR|U8|UX)", 77, "Hisense U8/UR8"),
    (r"BRAVIA 7\b|XR70|XR75", 76, "Sony Bravia 7"),
    (r"TCL C7", 76, "TCL C7"),
    (r"SAMSUNG QN8\d", 74, "Samsung QN80"),
    (r"HISENSE U7.*PRO", 72, "Hisense U7 Pro"),
    (r"PHILIPS (MLED9|THE ONE.*9|PML9)", 70, "Philips Mini-LED 9xx"),
    (r"HISENSE U7", 68, "Hisense U7"),
    (r"TCL C6KS", 60, "TCL C6KS"),
    (r"TCL (C6|Q6C|T8D)", 68, "TCL C6"),
    (r"SAMSUNG QN7\d|SAMSUNG QN1", 66, "Samsung QN70"),
    (r"LG MRGB|LG QNED9", 70, "LG Mini RGB/QNED9x"),
    (r"LG QNED8[5-9]", 63, "LG QNED85/86 Mini-LED"),
    (r"SAMSUNG M\d", 46, "Samsung M-serie («Mini-LED» uten lokal dimming, RTINGS)"),
    (r"HISENSE E8", 62, "Hisense E8"),
    (r"PHILIPS MLED|PHILIPS PML", 62, "Philips Mini-LED"),
    (r"LG QNED8", 56, "LG QNED80/82"),
    (r"BRAVIA 5\b|XR50", 62, "Sony Bravia 5"),
    # --- QLED / LED ---
    (r"SAMSUNG Q8\d?F?|SAMSUNG Q80", 56, "Samsung Q80"),
    (r"PHILIPS PQS9", 52, "Philips PQS9 (120 Hz QLED, Ambilight)"),
    (r"BRAVIA 3 II", 52, "Sony Bravia 3 II (120 Hz, HDMI 2.1, Dolby Vision, men lav lysstyrke)"),
    (r"BRAVIA 2 II", 34, "Sony Bravia 2 II (HDMI 2.0, 60 Hz)"),
    (r"THE FRAME|LS03", 55, "Samsung The Frame"),
    (r"TCL P8", 55, "TCL P8"),
    (r"SAMSUNG Q7", 48, "Samsung Q7 (60 Hz, ingen lokal dimming, ingen Dolby Vision)"),
    (r"HISENSE E7.*PRO", 55, "Hisense E7 Pro"),
    (r"PHILIPS (PUS9|PUS8[5-9]|THE ONE)", 50, "Philips Ambilight 8/9xxx"),
    (r"LG QNED7", 46, "LG QNED7x"),
    (r"HISENSE E7", 48, "Hisense E7"),
    (r"PHILIPS (PUS8|PQS8)", 45, "Philips Ambilight PUS8"),
    (r"BRAVIA 3|K\d+S3\d", 44, "Sony Bravia 3"),
    (r"TCL (P7|P6|T6|T69|C69B)", 40, "TCL P6/P7/T6"),
    (r"SAMSUNG Q6", 42, "Samsung Q6"),
    (r"LG (NU|NANO)9", 40, "LG Nano 9x"),
    (r"HISENSE A7", 40, "Hisense A7"),
    (r"SAMSUNG CRYSTAL U8|SAMSUNG U8|HU8", 38, "Samsung Crystal U8"),
    (r"LG (NU|NANO)8|\dNU8", 38, "LG Nano 8x"),
    (r"PHILIPS (PUS7|PQS7)", 37, "Philips PUS7"),
    (r"HISENSE A6", 34, "Hisense A6"),
    (r"SAMSUNG (CRYSTAL )?U7|SAMSUNG U7", 33, "Samsung Crystal U7"),
    (r"LG (UA|UT|UR)7|LG UHD", 33, "LG UHD 7x"),
    (r"OLED", 74, "Annen OLED"),
]


ADJUST = [
    "42\" OLED: −4 (mangler lysforsterker, svakere lysstyrke enn 48\"+)",
    "50\" LCD: −4 (bruker ofte svakere panel enn 55\" i samme serie)",
    "43\" og mindre LCD: −6 (enklere panel, færre dimmesoner, ofte 60 Hz)",
    "Hotell-/bedrifts-TV: −6 (forenklet programvare og bilde)",
    "Ukjent serie: grunnverdi etter paneltype (OLED 72, Mini-LED 58, QLED 42, LED 30), −8 for HD/Full HD",
    "Egenskaper (vektet for primær-TV med fotball, strømming og PS4, se config.json): ekte 100/120 Hz +6, 50/60 Hz −4, Dolby Vision +2 (ellers HDR10+ +1), kantbelyst −3, VRR/HDMI 2.1 +1",
]


def _fallback(p):
    s = ((p.get("panel") or "") + " " + p["name"]).upper()
    if "OLED" in s and "QNED" not in s:
        base, why = 72, "OLED (heuristikk)"
    elif re.search(r"MINI.?LED|RGB", s):
        base, why = 58, "Mini-LED (heuristikk)"
    elif re.search(r"QLED|QNED|NANO", s):
        base, why = 42, "QLED (heuristikk)"
    else:
        base, why = 30, "LED (heuristikk)"
    if re.search(r"HD READY|1366|HD LED|FULL HD|FHD", s):
        base -= 8
    return base, why


DEFAULT_PROFILE = {"hz_100_pluss": 6, "hz_60_eller_lavere": -4, "dolby_vision": 2, "hdr10_pluss": 1,
                   "kantbelysning": -3, "vrr_hdmi21": 1}


def features(p, prof):
    """Justering ut fra TV-ens faktiske egenskaper (Prisjakt-spesifikasjoner), vektet etter bruk."""
    prof = {**DEFAULT_PROFILE, **(prof or {})}
    sp = p.get("specs") or {}
    adj, why = 0, []
    hzs = re.findall(r"(\d{2,3})\s*Hz", (p.get("hz") or "") + " " + sp.get("Oppdateringsfrekvens", ""))
    nm = (p.get("family_label", "") + " " + p.get("name", "") + " " + (p.get("panel") or "")).upper()
    if not hzs and "OLED" in nm and "QNED" not in nm:
        hzs = ["120"]  # alle aktuelle OLED-TV-er har ekte 120 Hz
    if hzs:
        hz = max(int(x) for x in hzs)
        if hz >= 100:
            adj += prof["hz_100_pluss"]; why.append(f"{hz} Hz {prof['hz_100_pluss']:+d}")
        else:
            adj += prof["hz_60_eller_lavere"]; why.append(f"{hz} Hz {prof['hz_60_eller_lavere']:+d}")
    hdr = sp.get("HDR-format", "").upper()
    if "DOLBY VISION" in hdr:
        adj += prof["dolby_vision"]; why.append(f"Dolby Vision {prof['dolby_vision']:+d}")
    elif "HDR10+" in hdr:
        adj += prof["hdr10_pluss"]; why.append(f"HDR10+ {prof['hdr10_pluss']:+d}")
    bl = sp.get("Bakbelysningsteknologi", "").upper()
    if re.search(r"EDGE|KANT", bl):
        adj += prof["kantbelysning"]; why.append(f"kantbelyst {prof['kantbelysning']:+d}")
    sync = (sp.get("Type synkronisering", "") + " " + sp.get("HDMI-standarder", "")).upper()
    if re.search(r"VRR|FREESYNC|G-SYNC|HDMI 2\.1", sync):
        adj += prof["vrr_hdmi21"]; why.append(f"VRR/HDMI 2.1 {prof['vrr_hdmi21']:+d}")
    return adj, why


def score(p, profile=None):
    """Returnerer (score, grunnlag). Grunnpoeng per serie (bildekvalitet i tester), justert for
    størrelse og for TV-ens egne egenskaper vektet etter bruksprofilen i config.json."""
    label = (p["family_label"] + " " + p["name"]).upper()
    for pat, sc, why in TIERS:
        if re.search(pat, label):
            break
    else:
        sc, why = _fallback(p)
    size = int(round(p.get("size") or 55))
    nm = (p.get("family_label", "") + " " + p.get("name", "") + " " + (p.get("panel") or "")).upper()
    is_oled = "OLED" in nm and "QNED" not in nm
    if is_oled and size <= 42:
        sc -= 4; why += ", 42\" svakere"
    elif not is_oled and size == 50:
        sc -= 4; why += ", 50\" ofte svakere panel"
    elif not is_oled and size <= 43:
        sc -= 6; why += ", liten LCD"
    if re.search(r"HOTEL|HG\d|BEDRIFT|BE\d\d", label):
        sc -= 6; why += ", hotell-/bedrifts-TV"
    adj, fw = features(p, profile)
    if fw:
        sc += adj
        why += "; " + ", ".join(fw)
    return max(5, min(100, sc)), why
