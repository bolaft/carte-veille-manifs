#!/usr/bin/env python3
"""Outil d'administration local de la carte de veille.

    python3 scripts/admin.py            # ouvre http://127.0.0.1:8765/
    python3 scripts/admin.py --port 9000

Ce serveur ne dépend que de la bibliothèque standard. Il permet de rechercher, créer, modifier
et supprimer des événements, des signalements (violences policières, répression, extrême droite,
propagande, déclarations), des chiffres officiels et des médias, puis de reconstruire index.html
et, si on le souhaite, de committer et pousser le dépôt.

Fonctionnement :
- les créations sont ajoutées à data/{events,incidents,stats,media}_manual.json, lus par build.py
  comme les autres fichiers de recherche ;
- les modifications et suppressions de cartes issues des passes de recherche sont enregistrées
  dans data/overrides.json comme règles « stage: merged », appliquées par build.py aux cartes
  telles qu'elles sont affichées ; les entrées manuelles sont éditées directement ;
- rien n'est visible sur la carte avant la reconstruction (bouton « Reconstruire la page »).
"""
import argparse, json, os, subprocess, sys, datetime, re, unicodedata, webbrowser, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
MANUAL = {'event': 'events_manual.json', 'incident': 'incidents_manual.json', 'stat': 'stats_manual.json', 'media': 'media_manual.json'}
LOCK = threading.Lock()

def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()

def load(name, default):
    p = os.path.join(DATA, name)
    if not os.path.exists(p): return default
    with open(p, encoding='utf-8') as fh: return json.load(fh)

def save(name, obj):
    p = os.path.join(DATA, name)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh: json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)

def now(): return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# ---------- field mapping between the displayed (merged) records and the raw research schema ----------
RAW_FROM_MERGED = {'event': {'po': 'participants_official', 'pg': 'participants_organizers', 'pnote': 'participants_note'},
                   'incident': {'cat': 'category', 'inv': 'investigation', 'sd': 'status_date', 'stmt': 'statement'},
                   'stat': {}}

def to_raw(kind, rec):
    out = {}
    for k, v in rec.items():
        if k in ('orig', 'id', 'ck', 'terr', 'lat', 'lon', 'x', 'y', 'media', 'series', 'nc', 'official', 'outlet', 'src', 'allsrc'): continue
        out[RAW_FROM_MERGED.get(kind, {}).get(k, k)] = v
    if 'src' in rec:
        out['sources'] = [{'outlet': s.get('o', ''), 'title': s.get('t', ''), 'url': s.get('u', ''), 'date': s.get('d', '')} for s in rec['src'] if s.get('u')]
    if kind == 'stat' and rec.get('src') and isinstance(rec['src'], str):
        out['sources'] = [{'outlet': rec.get('outlet', ''), 'title': '', 'url': rec['src'], 'date': rec.get('date', '')}]
    return out

def match_key(kind, rec):
    if kind == 'event': return {'date': rec['date'], 'city': rec['city']}
    if kind == 'incident': return {'date': rec['date'], 'city': rec['city'], 'title_prefix': (rec.get('title') or '')[:50]}
    if kind == 'stat': return {'date': rec['date'], 'metric': rec['metric'], 'value': rec['value'], 'scope': rec.get('scope', '')}
    return {}

def manual_only(rec):
    o = rec.get('orig') or []
    return bool(o) and all(f.endswith('_manual.json') for f in o)

def manual_index(kind, rec):
    """Index of the manual raw entry corresponding to a displayed record, or -1."""
    arr = load(MANUAL[kind], [])
    for i, raw in enumerate(arr):
        if kind == 'stat':
            if raw.get('date') == rec['date'] and raw.get('metric') == rec['metric'] and float(raw.get('value', -1)) == float(rec['value']): return i
        elif raw.get('date') == rec['date'] and norm(raw.get('city')) == norm(rec['city']) and (kind == 'event' or norm(raw.get('title', ''))[:40] == norm(rec.get('title', ''))[:40]): return i
    return -1

def set_dirty(flag=True):
    p = os.path.join(DATA, '.admin_dirty')
    if flag: open(p, 'w').write(now())
    elif os.path.exists(p): os.remove(p)

def state():
    merged = load('merged.json', {'events': [], 'incidents': [], 'stats': [], 'built': ''})
    ovr = load('overrides.json', [])
    admin_rules = [dict(o, _index=i) for i, o in enumerate(ovr) if o.get('stage') == 'merged']
    return {'events': merged.get('events', []), 'incidents': merged.get('incidents', []), 'stats': merged.get('stats', []),
            'built': merged.get('built', ''), 'rules': admin_rules,
            'manual': {k: load(v, []) for k, v in MANUAL.items()},
            'dirty': os.path.exists(os.path.join(DATA, '.admin_dirty'))}

# ---------- operations ----------
def op_create(kind, record):
    arr = load(MANUAL[kind], [])
    record = {k: v for k, v in record.items() if v not in (None, '', [])}
    record['_admin'] = now()
    arr.append(record); save(MANUAL[kind], arr); set_dirty()
    return {'ok': True, 'count': len(arr)}

def op_update(kind, rec, changes):
    changes = {k: v for k, v in changes.items() if k not in ('orig', 'id', 'ck', 'terr', 'lat', 'lon', 'x', 'y')}
    if manual_only(rec):
        i = manual_index(kind, rec)
        if i >= 0:
            arr = load(MANUAL[kind], [])
            raw = to_raw(kind, changes); arr[i].update(raw); arr[i]['_admin'] = now()
            save(MANUAL[kind], arr); set_dirty(); return {'ok': True, 'where': MANUAL[kind]}
    ovr = load('overrides.json', [])
    ovr.append({'kind': kind, 'stage': 'merged', 'match': match_key(kind, rec), 'set': changes, '_admin': now()})
    save('overrides.json', ovr); set_dirty(); return {'ok': True, 'where': 'overrides.json'}

def op_delete(kind, rec):
    if manual_only(rec):
        i = manual_index(kind, rec)
        if i >= 0:
            arr = load(MANUAL[kind], []); arr.pop(i); save(MANUAL[kind], arr); set_dirty(); return {'ok': True, 'where': MANUAL[kind]}
    ovr = load('overrides.json', [])
    ovr.append({'kind': kind, 'stage': 'merged', 'match': match_key(kind, rec), 'drop': True, '_admin': now()})
    save('overrides.json', ovr); set_dirty(); return {'ok': True, 'where': 'overrides.json'}

def op_delete_media(card, url):
    ovr = load('overrides.json', [])
    ovr.append({'kind': 'media', 'stage': 'merged', 'match': {'date': card['date'], 'city': card['city'], 'url': url}, 'drop': True, '_admin': now()})
    save('overrides.json', ovr); set_dirty(); return {'ok': True}

def op_undo(index):
    ovr = load('overrides.json', [])
    if 0 <= index < len(ovr) and ovr[index].get('stage') == 'merged':
        ovr.pop(index); save('overrides.json', ovr); set_dirty(); return {'ok': True}
    return {'ok': False, 'error': 'règle introuvable'}

def op_rebuild():
    r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'build.py'), '--pages'], cwd=ROOT, capture_output=True, text=True, timeout=3600)
    ok = r.returncode == 0
    if ok: set_dirty(False)
    return {'ok': ok, 'output': (r.stdout + r.stderr)[-4000:]}

def op_commit(message):
    msg = (message or '').strip() or f'Mise à jour des données ({now()})'
    cmds = [['git', 'add', '-A'], ['git', 'commit', '-m', msg], ['git', 'push']]
    out = []
    for c in cmds:
        r = subprocess.run(c, cwd=ROOT, capture_output=True, text=True, timeout=600)
        out.append('$ ' + ' '.join(c) + '\n' + r.stdout + r.stderr)
        if r.returncode != 0 and c[1] != 'commit': return {'ok': False, 'output': '\n'.join(out)[-4000:]}
    return {'ok': True, 'output': '\n'.join(out)[-4000:]}

# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/': b = HTML.encode('utf-8'); self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
        elif path == '/api/state': self._json(state())
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get('Content-Length') or 0); body = json.loads(self.rfile.read(n) or b'{}')
        try:
            with LOCK:
                if path == '/api/create': res = op_create(body['kind'], body['record'])
                elif path == '/api/update': res = op_update(body['kind'], body['record'], body['set'])
                elif path == '/api/delete': res = op_delete(body['kind'], body['record'])
                elif path == '/api/delete_media': res = op_delete_media(body['card'], body['url'])
                elif path == '/api/undo': res = op_undo(int(body['index']))
                elif path == '/api/rebuild': res = op_rebuild()
                elif path == '/api/commit': res = op_commit(body.get('message'))
                else: res = {'ok': False, 'error': 'inconnu'}
        except Exception as e:
            res = {'ok': False, 'error': str(e)}
        self._json(res)

HTML = r'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Administration · Carte de veille</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--bg:#f3f4f2;--bg2:#fff;--fg:#16191b;--fg2:#555c62;--line:#d2d6ce;--acc:#1e3a8a;--police:#d1261b;--fr:#5c3a21;--rep:#5b3fb0;--prop:#c2347a;--manif:#0f7f8c;--ok:#2f7d32;--warn:#b45309}
body{margin:0;font:14px/1.45 "IBM Plex Sans",system-ui,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;padding:10px 16px;background:var(--bg2);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
h1{font-size:18px;margin:0 12px 0 0}
button{font:inherit;border:1px solid var(--line);background:var(--bg2);border-radius:4px;padding:5px 10px;cursor:pointer}
button.primary{background:var(--acc);color:#fff;border-color:var(--acc)} button.danger{color:var(--police);border-color:var(--police)} button.small{padding:2px 7px;font-size:12px}
.badge{display:inline-block;border-radius:999px;padding:0 8px;font-size:11px;background:#e7e9e4;color:var(--fg2);margin-left:6px}
.badge.warn{background:#fde68a;color:#7a4b00}
nav{display:flex;gap:4px;padding:8px 16px 0}
nav button[aria-selected=true]{background:var(--acc);color:#fff;border-color:var(--acc)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px}
input,select,textarea{font:inherit;border:1px solid var(--line);border-radius:4px;padding:5px 8px;background:var(--bg2);color:var(--fg)}
input.search{min-width:260px}
table{width:calc(100% - 32px);margin:0 16px 24px;border-collapse:collapse;background:var(--bg2)}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top;font-size:13px}
th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--fg2)}
td.t{max-width:560px} td .sub{color:var(--fg2);font-size:12px}
.tag{font-size:11px;padding:0 6px;border-radius:3px;color:#fff;white-space:nowrap}
.tag.police{background:var(--police)} .tag.fr{background:var(--fr)} .tag.rep{background:var(--rep)} .tag.prop{background:var(--prop)} .tag.ev{background:var(--manif)} .tag.st{background:#4b5563}
.orig{font-size:10px;color:var(--fg2)}
#log{white-space:pre-wrap;font:12px/1.4 ui-monospace,monospace;background:#1b1f23;color:#e6e6e6;margin:0 16px 16px;padding:10px;border-radius:4px;max-height:220px;overflow:auto;display:none}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.45);display:none;align-items:flex-start;justify-content:center;padding:30px 12px;overflow:auto;z-index:10}
.modal.open{display:flex}
.form{background:var(--bg2);border-radius:6px;padding:16px 18px;width:min(820px,100%);display:grid;grid-template-columns:1fr 1fr;gap:10px 14px}
.form h2{grid-column:1/-1;margin:0 0 4px;font-size:16px}
.form label{display:flex;flex-direction:column;gap:3px;font-size:12px;color:var(--fg2)}
.form label.full{grid-column:1/-1} .form textarea{min-height:90px} .form .actions{grid-column:1/-1;display:flex;gap:8px;justify-content:flex-end}
.hint{font-size:11px;color:var(--fg2)}
.more{margin:0 16px 24px}
.pending{color:var(--warn);font-size:12px}
</style></head><body>
<header><h1>Administration · Carte de veille</h1>
 <span id="built" class="hint"></span><span id="dirty" class="badge"></span>
 <span style="flex:1"></span>
 <button id="rebuild" class="primary">Reconstruire la page</button>
 <button id="commit">Commit &amp; push</button>
 <a href="../index.html" target="_blank" style="font-size:12px;margin-left:6px">index.html</a>
</header>
<nav id="tabs"><button data-k="incident" aria-selected="true">Signalements</button><button data-k="event">Événements</button><button data-k="stat">Chiffres officiels</button><button data-k="media">Médias</button><button data-k="rules">Modifications en attente</button></nav>
<div class="bar"><input class="search" id="q" placeholder="Rechercher (ville, date, mots du titre)…"><select id="f1"></select><input id="fdate" type="date"><button id="new" class="primary">Nouveau</button><span id="count" class="hint"></span></div>
<pre id="log"></pre>
<table id="tbl"><thead></thead><tbody></tbody></table>
<button id="more" class="more" style="display:none">Afficher plus</button>
<div class="modal" id="modal"><form class="form" id="form"></form></div>
<script>
const $=s=>document.querySelector(s); const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let S=null, tab='incident', limit=200;
const CATS={lbd:'LBD',grenade:'Grenade',coups:'Coups','véhicule':'Véhicule',gaz:'Gaz lacrymogène','garde-à-vue':'Garde à vue',interpellation:'Interpellation','entrave-presse':'Entrave à la presse','nasse-dispersion':'Nasse / dispersion','décès':'Décès',autre:'Violences policières (autre)','extrême-droite':'Extrême droite','répression':'Répression judiciaire & administrative',propagande:'Propagande, fake news'};
const TYPES={manifestation:'Manifestation',rassemblement:'Rassemblement','grève':'Grève',blocage:'Blocage',occupation:'Occupation','émeute':'Émeute',autre:'Autre'};
const METRICS=['interpellations','gardes_a_vue','poursuites','deferrements','comparutions_immediates','condamnations','detentions_provisoires','incarcerations','peines_emprisonnement','mandats_de_depot','classements_sans_suite','alternatives_poursuites','assignations_a_residence','interdictions_de_manifester','enquetes_igpn_iggn','blesses_forces_ordre','blesses_manifestants','blesses_eleves','blesses_personnels','deces','mineurs_part_gav','couvre_feux_villes','munitions_lacrymo','munitions_desencerclement','munitions_assourdissantes','munitions_lbd','autre'];
const fam=x=>x.cat==='extrême-droite'?'fr':x.cat==='répression'?'rep':x.cat==='propagande'?'prop':'police';
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});return r.json();}
async function refresh(){S=await api('state');$('#built').textContent=S.built?`Dernière construction : ${S.built}`:'';const n=S.rules.length+Object.values(S.manual).reduce((a,b)=>a+b.filter(x=>x._admin).length,0);$('#dirty').textContent=S.dirty?`modifications non reconstruites`:'à jour';$('#dirty').className='badge'+(S.dirty?' warn':'');render();}
function log(t){const l=$('#log');l.style.display='block';l.textContent=t;l.scrollTop=l.scrollHeight;}
function setFilter(){const f=$('#f1');f.innerHTML='';const opts=tab==='incident'?[['','Toutes catégories'],...Object.entries(CATS)]:tab==='event'?[['','Tous types'],...Object.entries(TYPES)]:tab==='stat'?[['','Toutes métriques'],...METRICS.map(m=>[m,m])]:[['','']];f.innerHTML=opts.map(([k,v])=>`<option value="${esc(k)}">${esc(v)}</option>`).join('');f.style.display=tab==='media'||tab==='rules'?'none':'';}
function rows(){const q=$('#q').value.trim().toLowerCase(),f=$('#f1').value,d=$('#fdate').value;const hit=x=>(!q||[x.city,x.title,x.summary,x.date,x.quote,x.authority,x.metric].join(' ').toLowerCase().includes(q))&&(!d||x.date===d);
 if(tab==='incident')return S.incidents.filter(x=>hit(x)&&(!f||x.cat===f)).sort((a,b)=>b.date.localeCompare(a.date));
 if(tab==='event')return S.events.filter(x=>hit(x)&&(!f||x.type===f)).sort((a,b)=>b.date.localeCompare(a.date));
 if(tab==='stat')return S.stats.filter(x=>hit(x)&&(!f||x.metric===f)).sort((a,b)=>b.date.localeCompare(a.date));
 if(tab==='media')return [...S.events,...S.incidents].filter(x=>x.media&&x.media.length&&hit(x)).sort((a,b)=>b.date.localeCompare(a.date));
 return S.rules;}
function render(){setFilter();const R=rows();$('#count').textContent=`${R.length} entrée${R.length>1?'s':''}`;const th=$('#tbl thead'),tb=$('#tbl tbody');
 if(tab==='rules'){th.innerHTML='<tr><th>Date</th><th>Type</th><th>Cible</th><th>Action</th><th></th></tr>';tb.innerHTML=R.map(r=>`<tr><td>${esc(r._admin||'')}</td><td>${esc(r.kind)}</td><td class="t">${esc(JSON.stringify(r.match))}</td><td class="t">${r.drop?'<b>suppression</b>':'modification : '+esc(JSON.stringify(r.set))}</td><td><button class="small danger" data-undo="${r._index}">Annuler</button></td></tr>`).join('')||'<tr><td colspan="5" class="hint">Aucune règle en attente. Les créations manuelles figurent dans data/*_manual.json.</td></tr>';$('#more').style.display='none';bind();return;}
 if(tab==='media'){th.innerHTML='<tr><th>Date</th><th>Ville</th><th>Carte</th><th>Médias</th></tr>';tb.innerHTML=R.slice(0,limit).map(x=>`<tr><td>${esc(x.date)}</td><td>${esc(x.city)}</td><td class="t">${esc(x.title)}</td><td>${x.media.map(m=>`<div><span class="tag st">${esc(m.type)}</span> <a href="${esc(m.url)}" target="_blank">${esc((m.caption||m.title||m.url).slice(0,90))}</a> <button class="small danger" data-dm="${esc(x.id)}" data-url="${esc(m.url)}">retirer</button></div>`).join('')}</td></tr>`).join('');}
 else if(tab==='stat'){th.innerHTML='<tr><th>Date</th><th>Métrique</th><th>Valeur</th><th>Portée</th><th>Autorité / citation</th><th></th></tr>';tb.innerHTML=R.slice(0,limit).map((x,i)=>`<tr><td>${esc(x.date)}</td><td>${esc(x.metric)}</td><td>${esc(x.value)}</td><td>${esc(x.scope)}${x.city?' · '+esc(x.city):''}${x.official===false?' <span class="badge">estimation</span>':''}</td><td class="t">${esc(x.authority)}<div class="sub">${esc(x.quote)}</div></td><td><button class="small" data-edit="${i}">Modifier</button> <button class="small danger" data-del="${i}">Supprimer</button></td></tr>`).join('');}
 else{th.innerHTML='<tr><th>Date</th><th>Ville</th><th>Catégorie</th><th>Carte</th><th>Origine</th><th></th></tr>';tb.innerHTML=R.slice(0,limit).map((x,i)=>`<tr><td>${esc(x.date)}</td><td>${esc(x.city)}</td><td>${tab==='incident'?`<span class="tag ${fam(x)}">${esc(CATS[x.cat]||x.cat)}</span>${x.stmt?`<div class="sub">Déclaration · ${esc(x.stmt.org)}</div>`:''}`:`<span class="tag ev">${esc(TYPES[x.type]||x.type)}</span>`}</td><td class="t">${esc(x.title)}<div class="sub">${esc((x.summary||'').slice(0,160))}${(x.summary||'').length>160?'…':''}</div></td><td class="orig">${(x.orig||[]).map(esc).join('<br>')}</td><td><button class="small" data-edit="${i}">Modifier</button> <button class="small danger" data-del="${i}">Supprimer</button></td></tr>`).join('');}
 $('#more').style.display=R.length>limit?'':'none';bind();}
let confirmBtn=null;
function bind(){const R=rows();
 document.querySelectorAll('[data-edit]').forEach(b=>b.onclick=()=>openForm(tab,R[+b.dataset.edit]));
 document.querySelectorAll('[data-del]').forEach(b=>b.onclick=async()=>{if(confirmBtn!==b){if(confirmBtn)confirmBtn.textContent='Supprimer';confirmBtn=b;b.textContent='Confirmer ?';return;}const res=await api('delete',{kind:tab,record:R[+b.dataset.del]});log(JSON.stringify(res));confirmBtn=null;refresh();});
 document.querySelectorAll('[data-dm]').forEach(b=>b.onclick=async()=>{if(confirmBtn!==b){if(confirmBtn)confirmBtn.textContent='retirer';confirmBtn=b;b.textContent='confirmer ?';return;}const card=[...S.events,...S.incidents].find(x=>x.id===b.dataset.dm);const res=await api('delete_media',{card,url:b.dataset.url});log(JSON.stringify(res));confirmBtn=null;refresh();});
 document.querySelectorAll('[data-undo]').forEach(b=>b.onclick=async()=>{const res=await api('undo',{index:+b.dataset.undo});log(JSON.stringify(res));refresh();});}
const F=(name,label,val,opts)=>opts?`<label>${label}<select name="${name}">${opts.map(([k,v])=>`<option value="${esc(k)}"${String(k)===String(val??'')?' selected':''}>${esc(v)}</option>`).join('')}</select></label>`:`<label>${label}<input name="${name}" value="${esc(val??'')}"></label>`;
const T=(name,label,val,full=true)=>`<label class="${full?'full':''}">${label}<textarea name="${name}">${esc(val??'')}</textarea></label>`;
const srcText=src=>(src||[]).map(s=>typeof s==='string'?s:[s.o??s.outlet??'',s.t??s.title??'',s.u??s.url??'',s.d??s.date??''].join(' | ')).join('\n');
function openForm(kind,rec){const isNew=!rec;rec=rec||{};let h=`<h2>${isNew?'Nouvelle entrée':'Modifier'} · ${kind==='incident'?'signalement':kind==='event'?'événement':kind==='stat'?'chiffre officiel':'média'}</h2>`;
 if(kind==='incident'){h+=F('date','Date (AAAA-MM-JJ)',rec.date)+F('city','Ville (ou France)',rec.city)+F('dept','Département (code)',rec.dept)+F('cat','Catégorie',rec.cat||'autre',Object.entries(CATS))+F('place','Lieu précis',rec.place)+F('victim','Victime',rec.victim)+`<label class="full">Titre<input name="title" value="${esc(rec.title)}"></label>`+T('summary','Résumé (2–4 phrases)',rec.summary)+T('inv','Suites (enquête, plainte, décision)',rec.inv,false)+F('sd','Date des suites',rec.sd)+F('stmt_org','Déclaration : organisation (laisser vide sinon)',rec.stmt?.org)+F('stmt_kind','Déclaration : nature',rec.stmt?.kind||'',[['',''],['ONG','ONG'],['ONU','ONU'],["Conseil de l'Europe","Conseil de l'Europe"],['Union européenne','Union européenne'],['autorité indépendante','autorité indépendante'],['barreau et magistrature','barreau et magistrature'],['médias','médias']])+T('src','Sources, une par ligne : média | titre | url | date',srcText(rec.src));}
 else if(kind==='event'){h+=F('date','Date (AAAA-MM-JJ)',rec.date)+F('city','Ville (ou France)',rec.city)+F('dept','Département (code)',rec.dept)+F('type','Type',rec.type||'manifestation',Object.entries(TYPES))+F('place','Lieu précis',rec.place)+F('arrests','Interpellations',rec.arrests)+F('po','Participants (autorités)',rec.po)+F('pg','Participants (organisateurs)',rec.pg)+`<label class="full">Titre<input name="title" value="${esc(rec.title)}"></label>`+T('summary','Résumé',rec.summary)+F('pnote','Note sur les effectifs',rec.pnote)+T('src','Sources, une par ligne : média | titre | url | date',srcText(rec.src));}
 else if(kind==='stat'){h+=F('date','Date du bilan',rec.date)+F('metric','Métrique',rec.metric||'interpellations',METRICS.map(m=>[m,m]))+F('value','Valeur',rec.value)+F('scope','Portée',rec.scope||'cumul',[['cumul','cumul'],['jour','jour'],['ville','ville']])+F('city','Ville (si portée ville)',rec.city)+F('authority','Autorité',rec.authority)+T('quote','Citation exacte',rec.quote)+T('src','Source : média | titre | url | date',isNew?'':rec.src?[rec.outlet||'','',rec.src,rec.date].join(' | '):'');}
 else{h+=F('kind','Carte visée',rec.kind||'event',[['event','événement'],['incident','signalement']])+F('date','Date de la carte',rec.date)+F('city','Ville de la carte',rec.city)+F('title_prefix','Début du titre de la carte (signalements)',rec.title_prefix)+F('type','Type de média','youtube',[['youtube','YouTube'],['dailymotion','Dailymotion'],['reddit','Vidéo Reddit'],['image','Photo Wikimedia Commons'],['link','Lien (X, presse…)']])+F('id','Identifiant vidéo (YouTube/Dailymotion) ou id de post Reddit','')+F('url','URL (page, post ou image)','')+F('vid','Identifiant v.redd.it (vidéos Reddit)','')+F('outlet','Média / compte','')+`<label class="full">Titre<input name="title"></label>`+T('caption','Légende (une phrase)','')+F('credit','Crédit (photos : auteur, licence)','')+F('page','Page de la photo (Commons)','');}
 h+=`<div class="actions"><span class="hint" style="margin-right:auto">${isNew?'Ajouté à data/'+({incident:'incidents',event:'events',stat:'stats',media:'media'}[kind])+'_manual.json':(rec.orig&&rec.orig.every(f=>f.endsWith('_manual.json'))?'Entrée manuelle : modifiée sur place':'Enregistré comme règle dans data/overrides.json')}</span><button type="button" id="cancel">Annuler</button><button class="primary" type="submit">Enregistrer</button></div>`;
 $('#form').innerHTML=h;$('#modal').classList.add('open');$('#cancel').onclick=()=>$('#modal').classList.remove('open');
 $('#form').onsubmit=async e=>{e.preventDefault();const fd=new FormData($('#form'));const v=Object.fromEntries(fd.entries());const parseSrc=s=>s.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{const [o,t,u,d]=l.split('|').map(x=>(x||'').trim());return {outlet:o,title:t,url:u,date:d};}).filter(s=>s.url);
  let res;
  if(kind==='media'){const item={type:v.type,id:v.id,url:v.url,vid:v.vid,title:v.title,outlet:v.outlet,caption:v.caption,credit:v.credit,page:v.page};Object.keys(item).forEach(k=>{if(!item[k])delete item[k];});res=await api('create',{kind:'media',record:{kind:v.kind,date:v.date,city:v.city,title_prefix:v.title_prefix,media:[item]}});}
  else if(isNew){const r={...v};if(kind==='incident'){r.category=r.cat;delete r.cat;r.investigation=r.inv;delete r.inv;r.status_date=r.sd;delete r.sd;if(r.stmt_org)r.statement={org:r.stmt_org,kind:r.stmt_kind};delete r.stmt_org;delete r.stmt_kind;}
   if(kind==='event'){r.participants_official=r.po?+r.po:null;r.participants_organizers=r.pg?+r.pg:null;r.participants_note=r.pnote;r.arrests=r.arrests?+r.arrests:null;delete r.po;delete r.pg;delete r.pnote;}
   if(kind==='stat'){r.value=+r.value;}
   r.sources=parseSrc(v.src||'');delete r.src;res=await api('create',{kind,record:r});}
  else{const set={};for(const [k,val] of Object.entries(v)){if(k==='src'){set.src=parseSrc(val).map(s=>({o:s.outlet,t:s.title,u:s.url,d:s.date}));continue;}if(k==='stmt_org'||k==='stmt_kind')continue;const before=rec[k];if(String(before??'')!==String(val??''))set[k]=val;}
   if(kind==='incident'){const org=v.stmt_org||'';if(org!==(rec.stmt?.org||'')||(v.stmt_kind||'')!==(rec.stmt?.kind||''))set.stmt=org?{org,kind:v.stmt_kind}:null;}
   if(kind==='stat'&&set.src){const s=set.src[0];set.src=s?s.u:'';if(s)set.outlet=s.o;}
   if(!Object.keys(set).length){$('#modal').classList.remove('open');return;}res=await api('update',{kind,record:rec,set});}
  log(JSON.stringify(res));$('#modal').classList.remove('open');refresh();};}
$('#tabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{tab=b.dataset.k;limit=200;$('#tabs').querySelectorAll('button').forEach(x=>x.setAttribute('aria-selected',x===b));$('#new').style.display=tab==='rules'?'none':'';render();});
$('#q').oninput=render;$('#f1').onchange=render;$('#fdate').onchange=render;$('#more').onclick=()=>{limit+=200;render();};
$('#new').onclick=()=>openForm(tab==='rules'?'incident':tab,null);
$('#rebuild').onclick=async()=>{$('#rebuild').disabled=true;log('Reconstruction en cours… (quelques dizaines de secondes, plus si des vignettes doivent être téléchargées)');const res=await api('rebuild',{});log((res.ok?'Reconstruction terminée.\n':'Échec de la reconstruction.\n')+res.output);$('#rebuild').disabled=false;refresh();};
$('#commit').onclick=async()=>{const m=prompt('Message du commit (laisser vide pour un message par défaut) :');if(m===null)return;log('Commit et push…');const res=await api('commit',{message:m});log(res.output);};
refresh();
</script></body></html>'''

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8765); ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Administration de la carte : {url}  (Ctrl+C pour arrêter)')
    if not a.no_browser:
        try: webbrowser.open(url)
        except Exception: pass
    try: srv.serve_forever()
    except KeyboardInterrupt: print('\nArrêt.')

if __name__ == '__main__':
    main()
