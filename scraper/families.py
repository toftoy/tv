"""Familienøkler for TV-modeller: grupperer butikk-/regionvarianter av samme TV.

Regler per merke (LG, Samsung, Sony, Philips, TCL, Hisense). Faller tilbake på
Prisjakts serienavn i produktnavnet når koden ikke gjenkjennes.
"""
import re
def clean(s):
    s = s.upper().strip()
    s = re.sub(r'\.(A[EU][A-Z]|[A-Z]{3})$', '', s)      # LG .AEU/.AEK
    s = re.sub(r'/\d{2}$', '', s)                      # Philips /12
    return re.sub(r'[\s_]', '', s)

# ---------- LG ----------
LG_OLED = re.compile(r'OLED(?P<size>\d{2,3})(?P<ser>[ABCGMWZRE])(?P<gen>\d)(?P<var>[0-9A-Z])?(?P<sfx>[A-Z]{2,3})?$')
def lg(code):
    c = clean(code)
    m = LG_OLED.search(c)
    if m:
        size, ser, gen, var, sfx = m['size'], m['ser'], m['gen'], m['var'], m['sfx']
        if sfx is None:                       # OLED55C6V / OLED55B6J = 2016 scheme
            return f'LG OLED {ser}{gen} {size}" {2010+int(gen)}'
        year = 2020 + int(gen)
        fam = ser + gen
        if var == 'E': fam += 'E'             # Elkjøp "C5 Pro"/"C6 Pro" – brighter variant, NOT identical
        if (ser, gen) == ('C', '6') and int(size) >= 77: fam = 'C6H'   # tandem panel
        return f'LG OLED {fam} {size}" {year}'
    m = re.match(r'(?P<size>\d{2,3})QNED(?P<ser>\d{2})(?P<yr>[A-Z])', c)
    if m:
        y = {'R':2023,'T':2024,'A':2025,'B':2026}.get(m['yr'])
        return f'LG QNED{m["ser"]} {m["size"]}" {y}'
    m = re.match(r'(?P<size>\d{2,3})(?P<yr>U[NPQRTAB])(?P<ser>\d{2})', c)
    if m:
        y = {'UN':2020,'UP':2021,'UQ':2022,'UR':2023,'UT':2024,'UA':2025}.get(m['yr'])
        return f'LG UHD {m["yr"]}{m["ser"]} {m["size"]}" {y}'

# ---------- Samsung ----------
SAM_Y = {'R':2019,'T':2020,'A':2021,'B':2022,'C':2023,'D':2024,'F':2025,'H':2026}
SAM_ALIAS = {'Q64':'Q60','Q65':'Q60','Q67':'Q60','Q68':'Q60','Q72':'Q70','Q74':'Q70','Q77':'Q70',
             'QN74':'QN70','QN77':'QN70','QN92':'QN90','QN93':'QN90','S92':'S90','S93':'S90','S94':'S90'}
SAM = re.compile(r'^(?:QE|GQ|TQ|QN|QA|UE|GU|TU|UN|UA)?(?P<size>\d{2,3})'
                 r'(?:(?P<cy>[A-Z])?U(?P<cu>\d{4})(?P<cy2>[A-Z])?'          # Crystal: DU7100 / U8000F
                 r'|(?P<ser>S\d{2}|QN\d{2,3}|Q\d{1,2}|LS\d{2}|MR\d{2}|R\d{2}|M\d{1,2}E?)(?P<yr>[A-Z])(?P<v>\d)?)'
                 r'(?P<rest>[A-Z0-9]*)$')
def samsung(code):
    m = SAM.match(clean(code).replace('-', ''))
    if not m: return None
    size = m['size']
    if m['cu']:
        y = SAM_Y.get(m['cy'] or m['cy2'])
        return f'Samsung Crystal U{m["cu"][:2]} {size}" {y}'   # U8092 -> U80, DU7172 -> U71
    ser = SAM_ALIAS.get(m['ser'], m['ser'])
    fam = ser + (m['v'] or '')                                 # keep Q7F3 apart until verified
    if ser.startswith('S') and m['yr'] == 'F' and m['rest'][:2] in ('AE', 'AT'):  # kun dokumentert for 2025
        fam += ' WOLED' if m['rest'][1] == 'E' else ' QD-OLED'
    return f'Samsung {fam} {size}" {SAM_Y.get(m["yr"])}'

# ---------- Sony ----------
def sony(code):
    c = clean(code).replace('-', '')
    m = re.match(r'^K(?P<size>\d{2,3})(?P<line>XR|S)(?P<num>\d{1,2})(?P<var>[A-Z])?(?P<gen>M\d)?(?:[A-Z]{1,2})?$', c)
    if m:
        tier = m['num'][0]
        gen = m['gen']
        year = {None: 2024, ('2','M2'):2025, ('8','M2'):2025, ('7','M2'):2026, ('9','M2'):2026}
        y = 2024 if gen is None else year.get((tier, gen))
        return f'Sony Bravia {tier}{" II" if gen=="M2" else ""} {m["size"]}" {y}'
    m = re.match(r'^(?:KD|KE|XR|FWD)(?P<size>\d{2,3})(?P<ser>[AXZ]\d{2,4})(?P<yr>[GHJKL])$', c)
    if m:
        s = m['ser']; s = s[:2] + '0' if s[0] == 'A' and len(s) == 3 else s   # A83L/A84L -> A80
        return f'Sony {s} {m["size"]}" {dict(G=2019,H=2020,J=2021,K=2022,L=2023)[m["yr"]]}'

# ---------- Philips ----------
PHI_Y = dict(zip('5678901', range(2020, 2027)))
def philips(code):
    m = re.match(r'^(?P<size>\d{2,3})(?P<line>OLED\+?|PUS|PML|MLED|PFS|PHS)(?P<num>\d{3,4})$', clean(code))
    if not m: return None
    num, line = m['num'], m['line'].rstrip('+')
    y = PHI_Y[num[-1]]
    ser = num[:-1] if line == 'OLED' else num[:2]
    if line == 'OLED' and y <= 2024 and ser[1] == '1': ser = ser[0] + '0'  # OLED819 == OLED809
    return f'Philips {line}{ser}x {m["size"]}" {y}'

# ---------- TCL ----------
TCL_NORDIC = {'MQLED85K':('C7',2025),'MQLED75K':('C6',2025),'MQLED70K':('C6KS',2025),
              'QLED810K':('P8',2025),'MSQLED85L':('C7',2026)}
TCL_2324 = {'C645':('C64',2023),'C745':('C74',2023),'C845':('C84',2023),'C655':('C65',2024),
            'C755':('C75',2024),'C765':('C76',2024),'C805':('C80',2024),'C855':('C85',2024)}
def tcl(code):
    c = clean(code).replace('-UK', '').replace('-', '')
    m = re.match(r'^(?P<size>\d{2,3})(?P<name>M?S?Q?LED\d{2,3}[A-Z]?|NXTVISION\w*)$', c)
    if m and m['name'] in TCL_NORDIC:
        s, y = TCL_NORDIC[m['name']]; return f'TCL {s} {m["size"]}" {y}'
    m = re.match(r'^(?P<size>\d{2,3})(?P<line>[CPQT])(?P<tier>\d)(?P<var>\d)?(?P<yr>[KL])(?P<s>S)?(?:PRO)?$', c)
    if m:
        return f'TCL {m["line"]}{m["tier"]}{"KS" if m["s"] else ""} {m["size"]}" {dict(K=2025,L=2026)[m["yr"]]}'
    m = re.match(r'^(?P<size>\d{2,3})(?P<n>[CP]\d{3})', c)
    if m and m['n'] in TCL_2324:
        s, y = TCL_2324[m['n']]; return f'TCL {s} {m["size"]}" {y}'

# ---------- Hisense ----------
def hisense(code):
    c = clean(code).replace('-', '')
    m = re.match(r'^(?P<size>\d{2,3})(?P<line>UR|UX|U|E|A|Q)(?P<tier>\d)(?P<var>\d)?(?P<yr>[HKNQS])(?P<tech>Q)?(?P<se>E)?(?P<pro>PRO)?(?:T?UK|AU|DS)?$', c)
    if not m: return None
    fam = m['line'] + m['tier'] + (' SE' if m['se'] else '') + (' Pro' if m['pro'] else '')
    return f'Hisense {fam} {m["size"]}" {dict(H=2022,K=2023,N=2024,Q=2025,S=2026)[m["yr"]]}'


BRAND_FN = {"LG": lg, "SAMSUNG": samsung, "SONY": sony, "PHILIPS": philips, "TCL": tcl, "HISENSE": hisense}


def _codes(name, extra=()):
    """Kandidat-modellkoder fra Prisjakt-navnet og butikkenes titler/varenr."""
    out = []
    if " - " in name:
        out.append(name.rsplit(" - ", 1)[-1])
    for s in [name, *extra]:
        if s:
            out += re.findall(r"\b(?:[A-Z]{1,4}-?)?\d{2,3}[A-Z][A-Z0-9+\-/.]{2,}\b", s)
    return [c for c in out if c]


def _name_family(brand, name, size):
    year = re.search(r"\((20\d\d)\)", name)
    year = year.group(1) if year else ""
    rest = name[len(brand):].strip() if name.lower().startswith(brand.lower()) else name
    m = re.match(r"(.*?)\s*\d{2,3}(?:[.,]\d)?\s*[\"”'″]", rest)
    series = re.sub(r"\s+", " ", (m.group(1) if m else "").strip()) or "?"
    if brand.upper() == "LG" and re.fullmatch(r"[ABCGMZ]\d[A-Z]?", series):
        series = "OLED " + series  # «LG C5» -> «LG OLED C5», samme nøkkel som kodebasert
    sz = int(round(size)) if size else ""
    return f"{brand} {series} {sz}\"" + (f" {year}" if year else "")


def family(brand, name, size, extra=()):
    """Returnerer (nøkkel, visningsnavn, kilde)."""
    fn = BRAND_FN.get((brand or "").upper())
    if fn:
        for c in _codes(name, extra):
            try:
                r = fn(c)
            except Exception:
                r = None
            if r and re.search(r"\d{2,3}\"", r):
                y = re.search(r"\((20\d\d)\)", name)
                cy = re.search(r"(20\d\d)$", r)
                # Årstall fra koden når merket koder det sikkert; Sony og manglende kode-år: Prisjakts årstall
                if y and (not cy or (brand or "").upper() == "SONY"):
                    r = re.sub(r"\s*(None|20\d\d)?$", "", r) + f" {y.group(1)}"
                else:
                    r = re.sub(r"\s*None$", "", r)
                return r.upper(), r, "kode"
    r = _name_family(brand, name, size)
    return r.upper(), r, "navn"
