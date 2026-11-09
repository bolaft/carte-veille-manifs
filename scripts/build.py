#!/usr/bin/env python3
"""Merge the research JSON files, geocode, dedupe, and inject into the HTML template.

Usage: python3 -I build.py [--local] [--sample]
  --local   use vendored d3/topojson files (for local screenshot tests)
  --sample  build from data/sample_*.json only
"""
import json, os, re, sys, glob, unicodedata, hashlib, datetime, subprocess, urllib.parse
for _s in (sys.stdout, sys.stderr):  # never crash on a console that cannot show a character (Windows cp1252)
    try: _s.reconfigure(errors='replace')
    except Exception: pass

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
D = os.path.join(S, 'data')
DIST = os.path.join(S, 'dist')
LOCAL = '--local' in sys.argv
SAMPLE = '--sample' in sys.argv
STANDALONE = '--standalone' in sys.argv  # single file, remote thumbnails, embedded players
PAGES = '--pages' in sys.argv  # GitHub Pages build: local sprites and photos, embedded players
MEDIA_DIR = os.path.join(S, 'media')

OVERSEAS = {'971', '972', '973', '974', '976', '988', '987', '975', '978', '977', '986'}
DAY0, DAY1 = datetime.date(2026, 8, 31), datetime.date(2026, 11, 9)
KEYDAYS = {
    '2026-08-31': 'Début du mouvement à Mayotte', '2026-09-18': 'Grève au lycée Saint-Exupéry de Créteil',
    '2026-09-29': 'Grève de la fonction publique', '2026-10-01': 'Acte II lycéen', '2026-10-06': 'Acte III lycéen',
    '2026-10-08': 'Journée d’action de l’éducation', '2026-10-13': 'Acte V lycéen', '2026-10-17': 'Journée « vie chère »',
    '2026-10-24': 'Acte II « vie chère »', '2026-10-31': 'Acte III « vie chère »', '2026-11-03': 'Journée noire des lycées',
    '2026-11-05': 'Grève interprofessionnelle', '2026-11-07': 'Acte IV « vie chère »',
}
TYPE_ALIASES = {'manif': 'manifestation', 'manifestation': 'manifestation', 'rassemblement': 'rassemblement', 'grève': 'grève', 'greve': 'grève',
                'blocage': 'blocage', 'blocus': 'blocage', 'occupation': 'occupation', 'émeute': 'émeute', 'emeute': 'émeute', 'pillage': 'émeute', 'autre': 'autre'}
CAT_ALIASES = {'lbd': 'lbd', 'grenade': 'grenade', 'coups': 'coups', 'véhicule': 'véhicule', 'vehicule': 'véhicule', 'gaz': 'gaz', 'garde-à-vue': 'garde-à-vue', 'garde-a-vue': 'garde-à-vue', 'gav': 'garde-à-vue',
               'interpellation': 'interpellation', 'entrave-presse': 'entrave-presse', 'presse': 'entrave-presse', 'nasse-dispersion': 'nasse-dispersion', 'nasse': 'nasse-dispersion',
               'extrême-droite': 'extrême-droite', 'extreme-droite': 'extrême-droite', 'décès': 'décès', 'deces': 'décès', 'répression': 'répression', 'repression': 'répression', 'propagande': 'propagande', 'fake-news': 'propagande', 'désinformation': 'propagande', 'desinformation': 'propagande', 'autre': 'autre'}

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

def fix_dept(d):
    d = str(d or '').strip().upper()
    if re.match(r'^\d$', d): d = '0' + d
    return d if re.match(r'^(\d{2,3}|2A|2B)$', d) else ''

def terr_of(dept):
    return dept if dept in OVERSEAS else 'metro'

def clean_sources(srcs):
    out, seen = [], set()
    for s in srcs or []:
        if not isinstance(s, dict): continue
        u = str(s.get('url') or s.get('u') or '').strip()
        if not u.startswith('http') or 'wikipedia.org' in u: continue
        if u in seen: continue
        seen.add(u)
        out.append({'o': str(s.get('outlet') or s.get('o') or outlet_from_url(u))[:60], 't': str(s.get('title') or s.get('t') or '')[:200], 'u': u, 'd': norm_date(s.get('date') or s.get('d') or '')})
    return out

def outlet_from_url(u):
    h = urllib.parse.urlparse(u).netloc.replace('www.', '')
    return h

def norm_date(d):
    d = str(d or '').strip()
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})', d)
    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}' if m else ''

def to_int(v):
    if v is None or v == '': return None
    if isinstance(v, (int, float)): return int(v)
    m = re.sub(r'[^\d]', '', str(v))
    return int(m) if m else None

# ---------- geocoding ----------
CACHE_PATH = os.path.join(D, 'geocode.json')
cache = json.load(open(CACHE_PATH, encoding='utf-8')) if os.path.exists(CACHE_PATH) else {}
MANUAL = json.load(open(os.path.join(D, 'geocode_manual.json'), encoding='utf-8')) if os.path.exists(os.path.join(D, 'geocode_manual.json')) else {}

def api(city, dept):
    params = {'nom': city, 'fields': 'nom,code,codeDepartement,centre,population', 'boost': 'population', 'limit': '5'}
    if dept: params['codeDepartement'] = dept
    url = 'https://geo.api.gouv.fr/communes?' + urllib.parse.urlencode(params)
    try:
        out = subprocess.run(['curl', '-sS', '--max-time', '20', url], capture_output=True, text=True, timeout=30).stdout
        res = json.loads(out)
    except Exception:
        return None
    if not isinstance(res, list) or not res: return None
    n = norm(city)
    exact = [r for r in res if norm(r['nom']) == n]
    r = (exact or res)[0]
    c = r['centre']['coordinates']
    return {'lat': c[1], 'lon': c[0], 'nom': r['nom'], 'dept': r['codeDepartement'], 'pop': r.get('population')}

GAZ = {}
for f in glob.glob(os.path.join(S, 'dl', 'geo', 'depts', '*.json')):
    try:
        for c in json.load(open(f, encoding='utf-8')):
            if 'centre' not in c: continue
            GAZ.setdefault(norm(c['nom']), []).append({'lat': c['centre']['coordinates'][1], 'lon': c['centre']['coordinates'][0], 'nom': c['nom'], 'dept': c['codeDepartement'], 'pop': c.get('population') or 0})
    except Exception:
        pass
def gaz(city, dept):
    cands = GAZ.get(norm(city)) or GAZ.get(norm(re.sub(r'\s*\(.*?\)', '', city).split(',')[0]))
    if not cands: return None
    if dept:
        c = [x for x in cands if x['dept'] == dept]
        if c: return c[0]
        if len(cands) == 1: return cands[0]
        return None
    return sorted(cands, key=lambda x: -x['pop'])[0]

def geocode(city, dept):
    k = f'{city}|{dept}'
    if k in MANUAL: return MANUAL[k]
    g = gaz(city, dept)
    if g: cache[k] = g; return g
    if k in cache and cache[k]: return cache[k]
    k2 = next((kk for kk in cache if kk.split('|')[0] == city and cache[kk] and (not dept or cache[kk].get('dept') == dept)), None)
    if k2: cache[k] = cache[k2]; return cache[k]
    r = api(city, dept) or (api(city, '') if dept else None)
    if r is None:
        c2 = re.sub(r'\s*\(.*?\)', '', city).split(',')[0].strip()
        if c2 != city: r = api(c2, dept) or api(c2, '')
    cache[k] = r
    return r

# ---------- load ----------
def load(pattern):
    items = []
    for f in sorted(glob.glob(os.path.join(D, pattern))):
        if ('sample_' in os.path.basename(f)) != SAMPLE: continue
        try:
            arr = json.load(open(f, encoding='utf-8'))
        except Exception as e:
            print('!! cannot read', f, e); continue
        if isinstance(arr, dict): arr = arr.get('events') or arr.get('incidents') or arr.get('stats') or []
        for it in arr:
            if isinstance(it, dict): it['_file'] = os.path.basename(f); items.append(it)
        print(f'{os.path.basename(f)}: {len(arr)} items')
    return items

ev_raw = load('events_*.json') + load('sample_events*.json')
inc_raw = load('incidents_*.json') + load('sample_incidents*.json')
st_raw = load('stats*.json') + load('sample_stats*.json')

# ---------- overrides ----------
OVR = json.load(open(os.path.join(D, 'overrides.json'), encoding='utf-8')) if os.path.exists(os.path.join(D, 'overrides.json')) else []
def apply_overrides(kind, it):
    for o in OVR:
        if o.get('kind') != kind or o.get('stage') == 'merged': continue
        m = o['match']
        if m.get('date') and m['date'] != norm_date(it.get('date')): continue
        if m.get('city') and norm(m['city']) != norm(it.get('city')): continue
        if m.get('title_prefix') and not str(it.get('title', '')).startswith(m['title_prefix']): continue
        if m.get('metric') and m['metric'] != it.get('metric'): continue
        if m.get('value') is not None and float(m['value']) != float(it.get('value') or -1): continue
        if o.get('drop'): return False
        it.update(o.get('set', {}))
    return True
ev_raw = [e for e in ev_raw if apply_overrides('event', e)]
inc_raw = [x for x in inc_raw if apply_overrides('incident', x)]

# ---------- events ----------
def in_window(d):
    try:
        dd = datetime.date.fromisoformat(d)
    except Exception:
        return False
    return DAY0 <= dd <= DAY1

events = {}
for e in ev_raw:
    date = norm_date(e.get('date')); city = str(e.get('city') or '').strip(); dept = fix_dept(e.get('dept'))
    if not date or not city or not in_window(date): continue
    typ = TYPE_ALIASES.get(norm(e.get('type')).replace(' ', '-'), None) or TYPE_ALIASES.get(str(e.get('type') or '').strip().lower(), 'autre')
    key = (date, norm(city), dept or '')
    # merge same city + date + dept (different types kept separate only if both are substantive? keep one record per city/day; combine types in summary)
    rec = events.get(key)
    src = clean_sources(e.get('sources'))
    po, pg = to_int(e.get('participants_official')), to_int(e.get('participants_organizers'))
    arrests = to_int(e.get('arrests'))
    if rec is None:
        events[key] = {'date': date, 'city': city, 'dept': dept, 'place': str(e.get('place') or '')[:160], 'type': typ, 'title': str(e.get('title') or '').strip()[:160],
                       'summary': str(e.get('summary') or '').strip(), 'po': po, 'pg': pg, 'pnote': str(e.get('participants_note') or '')[:120], 'arrests': arrests, 'src': src, 'types': {typ}, 'files': {e['_file']}}
    else:
        rec['types'].add(typ); rec['files'].add(e['_file'])
        # participants: keep max of official and organizers separately
        if po is not None: rec['po'] = max(rec['po'], po) if rec['po'] is not None else po
        if pg is not None: rec['pg'] = max(rec['pg'], pg) if rec['pg'] is not None else pg
        if arrests is not None: rec['arrests'] = max(rec['arrests'], arrests) if rec['arrests'] is not None else arrests
        if not rec['pnote'] and e.get('participants_note'): rec['pnote'] = str(e.get('participants_note'))[:120]
        s2 = str(e.get('summary') or '').strip()
        if s2 and norm(s2)[:60] not in norm(rec['summary']):
            rec['summary'] = (rec['summary'] + ' ' + s2).strip() if len(rec['summary']) < 700 else rec['summary']
        t2 = str(e.get('title') or '').strip()
        if len(t2) > len(rec['title']) and len(t2) < 120: rec['title'] = t2
        seen = {s['u'] for s in rec['src']}
        rec['src'] += [s for s in src if s['u'] not in seen]
        if not rec['place'] and e.get('place'): rec['place'] = str(e.get('place'))[:160]

NOTE_RE = re.compile(r"\s*\([^()]*(?:r[ée]f(?:[ée]rence)?s?\b|\[\d+\])[^()]*\)")
for rec in events.values():
    rec['summary'] = NOTE_RE.sub('', rec['summary']).strip()
# priority of displayed type when several merged
TYPE_PRIO = ['manifestation', 'émeute', 'grève', 'rassemblement', 'blocage', 'occupation', 'autre']
ev_list = []
for rec in events.values():
    rec['type'] = next(t for t in TYPE_PRIO if t in rec['types'])
    rec['src'] = rec['src'][:6]
    ev_list.append(rec)

# ---------- incidents ----------
incidents = []
for x in inc_raw:
    date = norm_date(x.get('date')); city = str(x.get('city') or '').strip(); dept = fix_dept(x.get('dept'))
    if not date or not city or not in_window(date): continue
    cat = CAT_ALIASES.get(str(x.get('category') or x.get('cat') or '').strip().lower(), 'autre')
    srcs = clean_sources(x.get('sources'))
    if not srcs: continue  # an incident card without a press source is not shown
    incidents.append({'date': date, 'city': city, 'dept': dept, 'place': str(x.get('place') or '')[:160], 'cat': cat, 'title': str(x.get('title') or '').strip()[:170],
                      'summary': str(x.get('summary') or '').strip(), 'victim': str(x.get('victim') or '')[:160], 'inv': str(x.get('investigation') or '').strip()[:500],
                      'sd': norm_date(x.get('status_date')), 'src': srcs, 'files': {x['_file']}, 'mk': x.get('_mk', ''),
                      'stmt': ({'org': str(x['statement'].get('org') or '')[:80], 'kind': str(x['statement'].get('kind') or '')[:40]} if isinstance(x.get('statement'), dict) and x['statement'].get('org') else None)})

def tokens(s):
    return {w for w in norm(s).split() if len(w) > 3}

merged = []
for x in sorted(incidents, key=lambda r: (r['date'], r['city'])):
    hit = None
    for m in merged:
        if m['date'] != x['date'] or norm(m['city']) != norm(x['city']): continue
        same_cat = m['cat'] == x['cat']
        tt = tokens(m['title'] + ' ' + m['victim']); tx = tokens(x['title'] + ' ' + x['victim'])
        jac = len(tt & tx) / max(1, len(tt | tx))
        vic = m['victim'] and x['victim'] and norm(m['victim'])[:12] == norm(x['victim'])[:12]
        samekey = m['mk'] and m['mk'] == x['mk']
        onepercity = same_cat and x['cat'] in ('extrême-droite', 'véhicule') and x['city'] != 'France'
        if samekey or onepercity or (same_cat and jac >= 0.25) or vic or jac >= 0.45:
            hit = m; break
    if hit is None:
        merged.append(x); continue
    hit['files'] |= x['files']
    if not hit['mk']: hit['mk'] = x['mk']
    if not hit.get('stmt') and x.get('stmt'): hit['stmt'] = x['stmt']
    if len(x['src']) > len(hit['src']) or (len(x['src']) == len(hit['src']) and len(x['summary']) > len(hit['summary'])):
        hit['title'], hit['summary'] = x['title'], x['summary']
        if x['cat'] != 'autre': hit['cat'] = x['cat']
    elif len(x['summary']) > len(hit['summary']) * 1.6: hit['summary'] = x['summary']
    if len(x['inv']) > len(hit['inv']) or (x['sd'] and x['sd'] > (hit['sd'] or '')):
        if len(x['inv']) > len(hit['inv']): hit['inv'] = x['inv']
        if x['sd'] and x['sd'] > (hit['sd'] or ''): hit['sd'] = x['sd']
    if not hit['victim'] and x['victim']: hit['victim'] = x['victim']
    if not hit['place'] and x['place']: hit['place'] = x['place']
    if hit['cat'] == 'autre' and x['cat'] != 'autre': hit['cat'] = x['cat']
    seen = {s['u'] for s in hit['src']}
    hit['src'] += [s for s in x['src'] if s['u'] not in seen]
for m in merged:
    m['src'] = m['src'][:6]; m['summary'] = NOTE_RE.sub('', m['summary']).strip(); m['inv'] = NOTE_RE.sub('', m['inv']).strip()

# ---------- stats ----------
METRICS = {'munitions_lacrymo', 'munitions_desencerclement', 'munitions_assourdissantes', 'munitions_lbd', 'incarcerations', 'peines_emprisonnement', 'alternatives_poursuites', 'interpellations', 'gardes_a_vue', 'poursuites', 'deferrements', 'comparutions_immediates', 'condamnations', 'detentions_provisoires', 'mandats_de_depot', 'classements_sans_suite',
           'assignations_a_residence', 'interdictions_de_manifester', 'enquetes_igpn_iggn', 'blesses_forces_ordre', 'blesses_manifestants', 'blesses_eleves', 'blesses_personnels', 'deces', 'mineurs_part_gav', 'couvre_feux_villes', 'autre'}
stats = {}
for s in st_raw:
    date = norm_date(s.get('date')); metric = str(s.get('metric') or '').strip(); val = s.get('value')
    if not date or metric not in METRICS or not in_window(date): continue
    scope = str(s.get('scope') or 'cumul').strip().lower()
    if scope not in ('cumul', 'jour', 'ville'): scope = 'cumul'
    try:
        v = float(val)
    except Exception:
        continue
    quote = str(s.get('quote') or '')[:260]; auth = str(s.get('authority') or '')[:80]
    ql = norm(quote); al = norm(auth)
    # remap some 'autre' figures to dedicated metrics
    if metric == 'autre':
        if ql.startswith('incarcerations') or ql.startswith('incarceration'): metric = 'incarcerations'
        elif ql.startswith('mesures d emprisonnement'): metric = 'peines_emprisonnement'
        elif ql.startswith('alternatives aux poursuites'): metric = 'alternatives_poursuites'
    nc = (v == 0 and ('aucun decompte' in ql or 'non chiffre' in ql))
    OFFICIAL_RE = re.compile(r'^(pr[e]f|minist|parquet|procureur|tribunal|dgpn|dggn|gouvernement|premier ministre|garde des sceaux|conseil d.?etat|autorit|laurent nu|gerald darmanin|edouard geffray|sebastien lecornu|beauvau|place beauvau|igpn|rectorat|education nationale|justice|interieur|president|elysee|matignon|entourage du premier|chancellerie|cour d|juge|direction (generale|nationale|departementale)|police nationale \(|gendarmerie nationale \(|bilan officiel|source policiere|source proche)')
    official = ('calcul' not in ql) and bool(OFFICIAL_RE.match(al)) and not any(w in al for w in ('syndicat', 'alliance', 'unsa police', 'un1te', 'estimation'))
    # a daily figure must carry the date of the day it describes, not of its publication
    if scope == 'jour':
        MM = {'septembre': '09', 'octobre': '10', 'novembre': '11'}
        mref = re.search(r"(?:journ[eé]e du|journ[eé]e de|pour le|week-end du|week-end des|pour la journ[eé]e du|sur la seule journ[eé]e du|bilan du)\s+(?:samedi|dimanche|lundi|mardi|mercredi|jeudi|vendredi)?\s*(\d{1,2})(?:er)?\s+(septembre|octobre|novembre)", quote.lower())
        if not mref and 'depuis' not in ql:
            mref = re.search(r"\b(?:le|du)\s+(\d{1,2})(?:er)?\s+(septembre|octobre|novembre)\b", quote.lower())
        if mref and not quote.lower().startswith('bilan du'):
            nd = f"2026-{MM[mref.group(2)]}-{int(mref.group(1)):02d}"
            if nd < date and (datetime.date.fromisoformat(date) - datetime.date.fromisoformat(nd)).days <= 10:
                date = nd
    _st = {'date': date, 'metric': metric, 'value': v, 'scope': scope, 'city': str(s.get('city') or ''), 'title': quote}
    if not apply_overrides('stat', _st): continue
    scope = _st['scope']; date = _st['date']; metric = _st['metric']; v = float(_st['value'])
    if _st.get('city') is not None: s['city'] = _st['city']
    # series: lyceen (cumul since 28 Sept / since the movement began) vs oct17 (cumul since 17 Oct)
    series = ''
    if scope == 'cumul':
        if 'depuis le debut' in ql or 'depuis le 28' in ql or date < '2026-10-17': series = 'lyceen'
        elif any(w in ql + ' ' + al for w in ('17 octobre', 'depuis samedi', 'week end', 'depuis le 17', 'violences du week')): series = 'oct17'
        elif metric in ('gardes_a_vue', 'poursuites', 'deferrements', 'incarcerations', 'peines_emprisonnement', 'mineurs_part_gav', 'alternatives_poursuites', 'detentions_provisoires'): series = 'oct17'
        else: series = 'lyceen'
    src = clean_sources(s.get('sources'))
    key = (date, metric, scope, str(s.get('city') or ''), auth, series)
    rec = stats.get(key)
    if rec is None or (len(src) and not rec['src']):
        stats[key] = {'date': date, 'metric': metric, 'value': int(v) if v == int(v) else v, 'scope': scope, 'city': str(s.get('city') or ''), 'authority': auth,
                      'quote': quote, 'src': src[0]['u'] if src else '', 'outlet': src[0]['o'] if src else '', 'series': series, 'nc': nc, 'official': official}
    else:
        if v > rec['value'] and scope == 'cumul': rec['value'] = int(v) if v == int(v) else v; rec['quote'] = quote
st_list = sorted(stats.values(), key=lambda r: (r['date'], r['metric']))

# ---------- merged-stage overrides (admin tool): match the cards as displayed ----------
def post_overrides(kind, records):
    out = []
    for r in records:
        keep = True
        for o in OVR:
            if o.get('stage') != 'merged' or o.get('kind') != kind: continue
            m = o.get('match', {})
            if m.get('date') and m['date'] != r.get('date'): continue
            if m.get('city') and norm(m['city']) != norm(r.get('city')): continue
            if m.get('title_prefix') and not norm(r.get('title', '')).startswith(norm(m['title_prefix'])): continue
            if m.get('metric') and m['metric'] != r.get('metric'): continue
            if m.get('value') is not None and float(m['value']) != float(r.get('value') or -1): continue
            if m.get('scope') and m['scope'] != r.get('scope'): continue
            if o.get('drop'): keep = False; break
            for k, v in (o.get('set') or {}).items():
                if k in ('po', 'pg', 'arrests', 'value'): v = to_int(v) if k != 'value' else (float(v) if v not in (None, '') else r.get('value'))
                if k == 'dept': v = fix_dept(v)
                if k == 'type': v = TYPE_ALIASES.get(norm(v).replace(' ', '-'), r.get('type'))
                if k == 'cat': v = CAT_ALIASES.get(str(v).strip().lower(), r.get('cat'))
                r[k] = v
        if keep: out.append(r)
    return out
ev_list = post_overrides('event', ev_list)
merged = post_overrides('incident', merged)
st_list = post_overrides('stat', st_list)
MEDIA_DROPS = {(norm_date(o['match'].get('date')), norm(o['match'].get('city')), str(o['match'].get('url') or '')) for o in OVR if o.get('stage') == 'merged' and o.get('kind') == 'media' and o.get('drop')}

# ---------- status updates on existing incident cards ----------
for f in sorted(glob.glob(os.path.join(D, 'updates_*.json'))):
    try:
        ups = json.load(open(f, encoding='utf-8'))
    except Exception as e:
        print('!! cannot read', f, e); continue
    napp = 0
    for u in ups:
        if not isinstance(u, dict): continue
        d_, c_, tp = norm_date(u.get('date')), norm(u.get('city')), norm(u.get('title_prefix') or '')
        for x in merged:
            if x['date'] == d_ and norm(x['city']) == c_ and (not tp or norm(x['title']).startswith(tp)):
                sd = norm_date(u.get('status_date'))
                if sd and sd >= (x['sd'] or ''):
                    x['inv'] = str(u.get('investigation') or x['inv'])[:500]; x['sd'] = sd
                    for s in clean_sources(u.get('sources')):
                        if s['u'] not in {q['u'] for q in x['src']}: x['src'].append(s)
                    napp += 1
                break
    print(f'{os.path.basename(f)}: {len(ups)} updates, {napp} applied')

# ---------- media attachments ----------
import base64
def yt_id(m):
    if m.get('id'): return str(m['id']).strip()
    u = str(m.get('url') or '')
    mm = re.search(r'(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{6,})', u)
    return mm.group(1) if mm else ''
def dm_id(m):
    if m.get('id'): return str(m['id']).strip()
    mm = re.search(r'dailymotion\.com/(?:video|embed/video)/([A-Za-z0-9]+)', str(m.get('url') or ''))
    return mm.group(1) if mm else ''
def fetch(url, path, maxtime=40):
    if os.path.exists(path) and os.path.getsize(path) > 500: return True
    try:
        r = subprocess.run(['curl', '-sS', '-L', '--max-time', str(maxtime), '-o', path, '-w', '%{http_code}', url], capture_output=True, text=True, timeout=maxtime + 10)
        ok = r.stdout.strip() == '200' and os.path.exists(path) and os.path.getsize(path) > 500
    except Exception:
        ok = False
    if not ok and os.path.exists(path): os.remove(path)
    return ok
def shrink(path, maxw=720):
    try:
        from PIL import Image
        im = Image.open(path); im = im.convert('RGB')
        if im.width > maxw: im = im.resize((maxw, int(im.height * maxw / im.width)))
        im.save(path, 'JPEG', quality=74, optimize=True)
    except Exception:
        pass
media_raw = []
for f in sorted(glob.glob(os.path.join(D, 'media_*.json'))):
    try:
        arr = json.load(open(f, encoding='utf-8'))
        media_raw += [m for m in arr if isinstance(m, dict)]
        print(f'{os.path.basename(f)}: {len(arr)} attachments')
    except Exception as e:
        print('!! cannot read', f, e)
os.makedirs(os.path.join(MEDIA_DIR, 'yt'), exist_ok=True); os.makedirs(os.path.join(MEDIA_DIR, 'dm'), exist_ok=True); os.makedirs(os.path.join(MEDIA_DIR, 'img'), exist_ok=True)
media_files = {}   # published path -> local path
def prep_media(m):
    typ = str(m.get('type') or '').lower().strip()
    out = {'type': typ, 'title': str(m.get('title') or '')[:160], 'caption': str(m.get('caption') or '')[:300], 'outlet': str(m.get('outlet') or '')[:80], 'credit': str(m.get('credit') or '')[:160], 'url': str(m.get('url') or '')[:400], 'page': str(m.get('page') or '')[:400], 'thumb': ''}
    if typ == 'youtube':
        vid = yt_id(m)
        if not re.match(r'^[A-Za-z0-9_-]{6,}$', vid): return None
        out['id'] = vid; out['url'] = f'https://www.youtube.com/watch?v={vid}'
        st = to_int(m.get('start')); out['start'] = st or 0
        local = os.path.join(MEDIA_DIR, 'yt', vid + '.jpg')
        out['remote'] = f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg'
        if fetch(f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg', local) or fetch(f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg', local):
            out['thumb'] = f'media/yt/{vid}.jpg'; media_files[out['thumb']] = local
    elif typ == 'dailymotion':
        vid = dm_id(m)
        if not re.match(r'^[A-Za-z0-9]{4,}$', vid): return None
        out['id'] = vid; out['url'] = f'https://www.dailymotion.com/video/{vid}'
        local = os.path.join(MEDIA_DIR, 'dm', vid + '.jpg')
        out['remote'] = f'https://www.dailymotion.com/thumbnail/video/{vid}'
        if fetch(f'https://www.dailymotion.com/thumbnail/video/{vid}', local):
            out['thumb'] = f'media/dm/{vid}.jpg'; media_files[out['thumb']] = local
    elif typ == 'image':
        u = out['url']
        if not (u.startswith('https://upload.wikimedia.org/') or u.startswith('https://thumb.wikimedia.org/') or u.startswith('https://commons.wikimedia.org/')): return None
        h = hashlib.md5(u.encode()).hexdigest()[:12]
        local = os.path.join(MEDIA_DIR, 'img', h + '.jpg')
        out['remote'] = u
        fresh = not os.path.exists(local)
        if fetch(u, local):
            if fresh: shrink(local)
            out['thumb'] = f'media/img/{h}.jpg'; media_files[out['thumb']] = local
        else: return None
    elif typ == 'link':
        if not out['url'].startswith('http'): return None
    elif typ == 'reddit':
        if not out['url'].startswith('https://www.reddit.com/'): return None
        out['id'] = str(m.get('id') or '')[:12]; out['vid'] = str(m.get('vid') or '')[:20]
        if re.search(r'[^A-Za-z0-9]', out['vid']): out['vid'] = ''
        out['remote'] = str(m.get('thumb_remote') or '')[:400] if str(m.get('thumb_remote') or '').startswith('https://preview.redd.it/') else ''
        out['score'] = to_int(m.get('score')) or 0
    else:
        return None
    return out
att_ev = {}; att_inc = {}
for a in media_raw:
    date = norm_date(a.get('date')); city = norm(a.get('city')); kind = str(a.get('kind') or 'event')
    raw_items = [m for m in (a.get('media') or []) if isinstance(m, dict)]
    if kind == 'incident':  # a context photo that does not show the incident does not belong on an incident card
        raw_items = [m for m in raw_items if not (str(m.get('type')) == 'image' and norm(str(m.get('caption') or '')).startswith('contexte'))]
    items = [x for x in (prep_media(m) for m in raw_items) if x]
    if not items or not date or not city: continue
    tp = str(a.get('title_prefix') or '').strip()
    if kind == 'incident':
        cands = [x for x in merged if x['date'] == date and norm(x['city']) == city and (not tp or norm(x['title']).startswith(norm(tp)))]
        if not cands: cands = [x for x in merged if x['date'] == date and norm(x['city']) == city]
        if not cands:  # a card may have been re-dated by a fact-check: look one day either side
            d0 = datetime.date.fromisoformat(date)
            cands = [x for x in merged if norm(x['city']) == city and abs((datetime.date.fromisoformat(x['date']) - d0).days) <= 1 and (not tp or norm(x['title']).startswith(norm(tp)) or 'lacoste' in norm(x['title']))]
    else:
        cands = [e for e in ev_list if e['date'] == date and norm(e['city']) == city]
        if not cands: cands = [x for x in merged if x['date'] == date and norm(x['city']) == city]
    if not cands: print('   media: no card for', kind, date, a.get('city'), tp[:30]); continue
    tgt = cands[0]
    seen = {m['url'] for m in tgt.setdefault('media', [])}
    for it in items:
        if (tgt['date'], norm(tgt['city']), it['url']) in MEDIA_DROPS: continue
        if it['url'] not in seen and len(tgt['media']) < 7: tgt['media'].append(it); seen.add(it['url'])
# keep only the thumbnails of media actually attached to a card
_used = {m['thumb'] for it in ev_list + merged for m in it.get('media', []) if m.get('thumb')}
media_files = {k: v for k, v in media_files.items() if k in _used}
# pack video thumbnails into sprite sheets (the hosted artifact may hold at most ~500 files)
if not STANDALONE:
    from PIL import Image
    os.makedirs(os.path.join(MEDIA_DIR, 's'), exist_ok=True)
    vids = []
    for it in ev_list + merged:
        for m in it.get('media', []):
            if m['type'] in ('youtube', 'dailymotion') and m['thumb'] and m['thumb'] in media_files: vids.append(m)
    uniq = {}
    for m in vids: uniq.setdefault(m['thumb'], []).append(m)
    keys = sorted(uniq.keys()); COLS, CW, CH, PER = 6, 320, 180, 36
    for si in range(0, len(keys), PER):
        chunk = keys[si:si + PER]; rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new('RGB', (COLS * CW, rows * CH), (40, 44, 48))
        for j, k in enumerate(chunk):
            try:
                im = Image.open(media_files[k]).convert('RGB')
                # center-crop to 16:9 then resize
                w, h = im.size; tw = w; th = int(w * 9 / 16)
                if th > h: th = h; tw = int(h * 16 / 9)
                im = im.crop(((w - tw) // 2, (h - th) // 2, (w - tw) // 2 + tw, (h - th) // 2 + th)).resize((CW, CH))
                sheet.paste(im, ((j % COLS) * CW, (j // COLS) * CH))
            except Exception:
                pass
            for m in uniq[k]:
                m['sprite'] = {'f': f'media/s/{si // PER}.jpg', 'c': j % COLS, 'r': j // COLS, 'cols': COLS, 'rows': rows}
        sp = os.path.join(MEDIA_DIR, 's', f'{si // PER}.jpg'); sheet.save(sp, 'JPEG', quality=80, optimize=True)
        media_files[f'media/s/{si // PER}.jpg'] = sp
    for k in keys: media_files.pop(k, None)   # individual video thumbnails are no longer published
    for m in vids: m['thumb'] = ''
if STANDALONE:  # outside the sandbox the page can load thumbnails from YouTube, Dailymotion and Commons directly
    for it in ev_list + merged:
        for m in it.get('media', []):
            if m.get('remote'): m['thumb'] = m['remote']
if PAGES:  # local sprites and photos; Reddit previews stay remote (they cannot be fetched from here)
    for it in ev_list + merged:
        for m in it.get('media', []):
            if m['type'] == 'reddit' and m.get('remote'): m['thumb'] = m['remote']
for it in ev_list + merged:
    for m in it.get('media', []): m.pop('remote', None)
os.makedirs(DIST, exist_ok=True)
json.dump(sorted(media_files.keys()), open(os.path.join(DIST, 'media_files.json'), 'w', encoding='utf-8', newline='\n'))

# ---------- geocode + finalize ----------
missing = set()
def finalize(it, kind):
    city, dept = it['city'], it['dept']
    if city == 'France':
        it['lat'] = it['lon'] = None; it['terr'] = 'metro'; it['ck'] = 'France|'
    else:
        g = geocode(city, dept)
        if g:
            it['lat'], it['lon'] = g['lat'], g['lon']
            if not it['dept'] and g.get('dept'): it['dept'] = g['dept']
        else:
            it['lat'] = it['lon'] = None; missing.add((city, dept))
        it['terr'] = terr_of(it['dept']); it['ck'] = f"{city}|{it['dept']}"
    it['id'] = kind + hashlib.md5(f"{it['date']}|{it['ck']}|{it.get('title','')}".encode()).hexdigest()[:8]
    it['orig'] = sorted(it.get('files') or [])
    it.pop('types', None); it.pop('files', None); it.pop('mk', None)

for e in ev_list: finalize(e, 'e')
for x in merged: finalize(x, 'i')
json.dump(cache, open(CACHE_PATH, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=0)

cities = {}
for it in ev_list + merged:
    if it['lat'] is not None and it['ck'] not in cities: cities[it['ck']] = {'lat': it['lat'], 'lon': it['lon'], 'terr': it['terr']}

national = {}
for e in ev_list:
    if e['ck'] == 'France|': national[e['date']] = {'po': e['po'], 'pg': e['pg'], 'title': e['title']}

days = []
d = DAY0
while d <= DAY1:
    days.append(d.isoformat()); d += datetime.timedelta(days=1)

data = {'days': days, 'keydays': KEYDAYS, 'defaultDay': '2026-10-17', 'events': ev_list, 'incidents': merged, 'stats': st_list, 'national': national, 'cities': cities,
        'built': datetime.date.today().isoformat()}
json.dump(data, open(os.path.join(D, 'merged.json'), 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=0)
topo = open(os.path.join(D, 'france.topo.json'), encoding='utf-8').read()
tpl = open(os.path.join(S, 'app', 'template.html'), encoding='utf-8').read()
out = tpl.replace('__TOPO__', topo).replace('__DATA__', json.dumps(data, ensure_ascii=False, separators=(',', ':'))).replace('__EMBED__', 'true' if (STANDALONE or PAGES) else 'false')
if LOCAL:
    out = out.replace('https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js', 'file://' + os.path.join(S, 'app', 'vendor', 'd3.min.js'))
    out = out.replace('https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js', 'file://' + os.path.join(S, 'app', 'vendor', 'topojson-client.min.js'))  # vendored copies for offline checks (not committed)
os.makedirs(DIST, exist_ok=True)
name = ('index' if PAGES else ('automne-2026-standalone' if STANDALONE else 'automne-2026')) + ('-local' if LOCAL else '') + '.html'
outpath = os.path.join(S, 'index.html') if (PAGES and not LOCAL) else os.path.join(DIST, name)
open(outpath, 'w', encoding='utf-8', newline='\n').write(out)
nm = sum(len(it.get('media', [])) for it in ev_list + merged); nc = sum(1 for it in ev_list + merged if it.get('media'))
print(f'events {len(ev_list)} (from {len(ev_raw)} raw) | incidents {len(merged)} (from {len(inc_raw)} raw) | stats {len(st_list)} | cities {len(cities)} | media {nm} on {nc} cards, {len(media_files)} files | output {len(out)/1e6:.2f} MB -> {name}')
if missing: print('MISSING GEOCODES:', sorted(missing))
