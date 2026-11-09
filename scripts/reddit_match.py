import json, re, html, datetime, unicodedata, collections, zoneinfo
S='/tmp/claude-0/-home-user/a19e4210-3cc5-511a-88da-ecdc6e7af354/scratchpad'
D=S+'/data/'
TZ=zoneinfo.ZoneInfo('Europe/Paris')
m=json.load(open(D+'merged.json'))
def norm(s):
    s=unicodedata.normalize('NFKD', str(s or '')).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()
KEY=set(m['keydays'].keys())
events={}
for e in m['events']: events.setdefault((e['date'], norm(e['city'])), e)
cities=sorted({norm(e['city']) for e in m['events'] if e['city']!='France'}, key=len, reverse=True)
city_display={norm(e['city']): e['city'] for e in m['events']}
PLACES={'republique':'paris','bastille':'paris','chatelet':'paris','magenta':'paris','elysee':'paris','vauban':'paris','place d italie':'paris','montparnasse':'paris','gare du nord':'paris','brav':'paris','canebiere':'marseille','vieux port':'marseille','jaude':'clermont ferrand','capitole':'toulouse','bellecour':'lyon','part dieu':'lyon','quinconces':'bordeaux','au mans':'le mans','du mans':'le mans','au havre':'le havre','du havre':'le havre'}
incs=collections.defaultdict(list)
for x in m['incidents']: incs[norm(x['city'])].append(x)
FOOT=re.compile(r"manif|lyc[eé]|blocus|bloqu|gr[eè]ve|polic|\bcrs\b|brav|gendarm|\blbd\b|flashball|grenade|lacrymo|[eé]meut|pillage|casseur|cort[eè]ge|interpell|garde [aà] vue|barricade|nasse|matraqu|charg|mortier|incendi|black bloc|identitaire|ultradroite|extr[eê]me droite|milice|antifa|mayotte|vie ch[eè]re|mobilisation|r[eé]pression|violences|t[eé]moignage|blessé|bless[eé]|street medic|m[eé]dic|journaliste|photographe|couvre-feu|couvre feu", re.I)
COMM=re.compile(r"[eé]mission|podcast|\bina\b|archive|d[eé]bat|[eé]ditorial|interview|plateau|c [aà] vous|\bt18\b|viktorovitch|bardella|m[eé]lenchon|\bcnrs\b|\barte\b|france culture|face [aà] |analyse|explique|pourquoi|comment |documentaire|porte.parole|interrog|s.excuse|fake news|propagande|lacoste|br[eé]sil|serbie|\b(19\d\d|200\d|201\d|202[0-5])\b|complot|bordélisation|dominants|rmc|cnews|hanouna|bfm\b.*(plateau|invit)|entretien|commission|[eé]ditocrat|wriggles|chanson|\bchant\b|royaume|riposte|omiri|vieux cons|co[uû]t de|avocat|narratif|matinale|procureur|scandale d.[eé]tat|armes de guerre|nous raconte|passe du rn|éditocratie|cellules de d[eé]ontologie", re.I)
PRESS=re.compile(r"m6 info|franceinfo|france info|bfmtv|bfm tv|france 3|france 2|brut\b|streetpress|blast|mediapart|le monde|lib[eé]ration|konbini|hugod[eé]crypte|quotidien|\bafp\b|l.humanit[eé]|le parisien|tf1|lci|ici |france t[eé]l[eé]visions|r[eé]my buisine|loopsider|le m[eé]dia|politis|rue89|image @|images? [a-z@]", re.I)
ACTION=re.compile(r"assign|micas|r[eé]quisitionn|commissariat|rafle|polici|\bcrs\b|\bgaz|grenade|matraqu|charg|nasse|lacrymo|\blbd\b|flashball|frapp|tabass|interpell|plaqu|lynch|bless|tir[eé]?s?\b|pousse|percut|fonce|brav|gendarm|identitaire|fascis|nazi|ultradroite|extr[eê]me droite|milice|brassard", re.I)
VD={'v.redd.it','youtube.com','youtu.be','m.youtube.com','x.com','twitter.com','streamable.com','dailymotion.com','tiktok.com','instagram.com','vimeo.com'}
STOP=set('dans avec pour sans sous chez cette cest comme plus tout tous toute toutes leur leurs apres avant pendant entre contre depuis aussi encore mais donc alors ainsi etre sont etait font fait faire pris prise video vidéo images image direct live aujourd hui hier jour journee soir matin police policier policiers policiere manifestation manifestants manifestant lyceens lyceen lycee lycees france french paris octobre septembre novembre violences violence personne personnes homme femme jeune jeunes groupe forces ordre'.split())
STRONG={'matraq','grenad','genou','lbd','flashb','lacrym','fesses','oeil','taser','tase','etrang','nasse','charge','artere','femora','photog','journa','medic','boucli','plaqu','lynch','frapp','coups','brule','mutil','amput','ventr','placag','voitur','4x4','moto','motard','gaz','gazes','gazee'}
def stems(s):
    return {w[:6] for w in norm(s).split() if len(w)>=4 and w not in STOP}
MONTHS={'septembre':9,'octobre':10,'novembre':11}
def parse_date(title):
    mm=re.search(r'(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?', title)
    if mm:
        try:
            d_,mo=int(mm.group(1)),int(mm.group(2))
            if 1<=d_<=31 and mo in (9,10,11): return datetime.date(2026,mo,d_)
        except Exception: pass
    mm=re.search(r'(\d{1,2})(?:er)?\s+(septembre|octobre|novembre)', title, re.I)
    if mm:
        try: return datetime.date(2026, MONTHS[mm.group(2).lower()], int(mm.group(1)))
        except Exception: pass
    return None
SUBCITY={'paris':'paris','lyon':'lyon','marseille':'marseille','toulouse':'toulouse','bordeaux':'bordeaux','lille':'lille','nantes':'nantes','rennes':'rennes','strasbourg':'strasbourg','montpellier':'montpellier','nice':'nice','grenoble':'grenoble','rouen':'rouen','nancy':'nancy','metz':'metz','dijon':'dijon','clermontferrand':'clermont ferrand','brest':'brest','caen':'caen','tours':'tours','orleans':'orleans','limoges':'limoges','reims':'reims','saintetienne':'saint etienne','besancon':'besancon','toulon':'toulon','perpignan':'perpignan','mulhouse':'mulhouse','amiens':'amiens','poitiers':'poitiers','avignon':'avignon','nimes':'nimes','bayonne':'bayonne','annecy':'annecy','mayotte':'mamoudzou','guyane':'cayenne','tahiti':'papeete','aix':'aix en provence','cannes':'cannes','calais':'calais','belfort':'belfort','quimper':'quimper','saintnazaire':'saint nazaire','angouleme':'angouleme','bourges':'bourges'}
import glob, os
out=[]; stats=collections.Counter(); seen_urls={}
def iter_posts():
    for f in sorted(glob.glob(S+'/dl/reddit/posts_*.jsonl')):
        sub=os.path.basename(f)[6:-6]
        for line in open(f):
            yield sub, json.loads(line)
for sub, p in iter_posts():
    p['_sub']=sub
    if p.get('removed_by_category') or p.get('over_18'): continue
    dom=(p.get('domain') or '').lower(); title=html.unescape(p.get('title') or '')
    if not (p.get('is_video') or dom in VD): continue
    if not FOOT.search(title) or COMM.search(title): stats['filtered']+=1; continue
    score=p.get('score') or 0
    isr = dom=='v.redd.it' or bool(p.get('is_video'))
    dt=datetime.datetime.fromtimestamp(int(p['created_utc']), TZ); date=dt.date()
    nt=norm(title)
    city=None
    for c in cities:
        if re.search(r'\b'+re.escape(c)+r'\b', nt): city=c; break
    if not city:
        for k,v in PLACES.items():
            if k in nt: city=v; break
    sub=p['_sub']; subl=sub.lower()
    if not city and subl in SUBCITY and SUBCITY[subl] in city_display: city=SUBCITY[subl]
    if subl=='france': minscore = (30 if city else 100) if isr else 20
    elif subl=='quefaitlapolice': minscore = 15   # a subreddit dedicated to police conduct: every post is on topic, votes are fewer
    else: minscore = 30 if isr else 20
    key_url=(p.get('url') or '').split('?')[0]
    if key_url in seen_urls and seen_urls[key_url] >= (p.get('score') or 0): stats['dup']+=1; continue
    seen_urls[key_url]=p.get('score') or 0
    if score < minscore: stats['lowscore']+=1; continue
    explicit=parse_date(title)
    anchored = bool(city) or bool(explicit) or bool(PRESS.search(title))
    if not anchored or ((not isr or not city) and not ACTION.search(title)): stats['unanchored']+=1; continue
    cand=[explicit] if explicit else ([date-datetime.timedelta(days=1), date] if (dt.hour<12 or ' hier ' in f' {nt} ') else [date, date-datetime.timedelta(days=1)])
    target=None
    for cd in cand:
        ds=cd.isoformat()
        if city and (ds, city) in events: target=(ds, city); break
    if not target and not city:
        for cd in cand:
            ds=cd.isoformat()
            if (ds,'france') in events: target=(ds,'france'); break
    inc_only=None
    if not target and city:
        # no event card that day: an incident card of that city on those dates can carry the clip
        for cd in cand:
            for x in incs.get(city, []):
                if abs((datetime.date.fromisoformat(x['date'])-cd).days)<=1: inc_only=(cd.isoformat(), city); break
            if inc_only: break
    if not target and not inc_only and city:
        for delta in (1,-1,2,-2,3,-3):
            ds=(cand[0]+datetime.timedelta(days=delta)).isoformat()
            if (ds, city) in events: target=(ds, city); break
    if not target and not inc_only:
        # a victim's first name in the title points to one incident card, whatever the city
        hits=[x for x in m['incidents'] if any(n in nt.split() for n in {w for w in norm(x['victim']).split() if len(w)>=5 and w not in STOP})]
        if len(hits)==1: inc_only=(hits[0]['date'], norm(hits[0]['city'])); city=norm(hits[0]['city']); explicit=None  # the date in such titles is usually the article's
    if not target and not inc_only: stats['nocard']+=1; continue
    ds, cn = target or inc_only
    # incident matching: same city (or any city if a victim's first name appears), within 5 days before the post
    kind='event'; best=None; bests=0
    pt=stems(title)-{cn[:6]}
    lo=(datetime.date.fromisoformat(ds)-datetime.timedelta(days=5)).isoformat(); hi=(datetime.date.fromisoformat(ds)+datetime.timedelta(days=1)).isoformat()
    pool=incs.get(cn,[]) if cn!='france' else [x for x in m['incidents'] if x['city']!='France']
    national = (cn=='france')
    FR=re.compile(r"identitaire|fascis|nazi|ultradroite|extr[eê]me.droite|milice|brassard|fachos?", re.I)
    post_fr=bool(FR.search(title))
    for x in pool:
        if not (lo <= x['date'] <= hi): continue
        if explicit and abs((datetime.date.fromisoformat(x['date'])-explicit).days)>1: continue
        if (x['cat']=='extrême-droite') != post_fr: continue
        ts_=stems(x['title']); it=ts_|stems(x['summary'][:400]); ov=pt & it
        names={w for w in norm(x['victim']).split() if len(w)>=4 and w not in STOP}
        name_hit=any(n in nt.split() for n in names)
        sc=len(ov)+len(pt&ts_)+(3 if name_hit else 0)+(1 if (ov & STRONG) else 0)
        if national and not name_hit and (sc<6 or len(pt&ts_)<2): continue
        if sc>bests: best,bests=x,sc
    if target is None and best: kind='incident'
    if best and (kind=='incident' or bests>=4 or (bests>=3 and (stems(best['title'])&pt&STRONG))):
        kind='incident'; tdate=best['date']; tcity=best['city']; tp=best['title'][:40]
    elif target is None: stats['nocard']+=1; continue
    else:
        tdate=ds; tcity=city_display.get(cn,'France') if cn!='france' else 'France'; tp=''
    url='https://www.reddit.com'+p['permalink']; author=p.get('author') or ''
    posted=dt.strftime('%d/%m à %Hh%M')
    base={'outlet': f'r/{sub} · u/{author}', 'title': title[:160], 'caption': f'{title[:220]} — publié sur r/{sub} le {posted} ({score} votes).'}
    if isr:
        vid=''; mv=re.search(r'v\.redd\.it/([A-Za-z0-9]+)', p.get('url') or '')
        if mv: vid=mv.group(1)
        thumb=''
        try:
            res=p['preview']['images'][0]['resolutions']; r=[r for r in res if r['width']>=320] or res; thumb=html.unescape((r[0] if r else res[-1])['url'])
        except Exception: pass
        if not thumb.startswith('https://preview.redd.it/'): thumb=''
        media={'type':'reddit','id':p['id'],'vid':vid,'url':url,'thumb_remote':thumb,'score':score, **base}
    elif dom in ('youtube.com','youtu.be','m.youtube.com'):
        my=re.search(r'(?:v=|youtu\.be/|/shorts/)([A-Za-z0-9_-]{6,})', p.get('url') or '')
        if not my: continue
        media={'type':'youtube','id':my.group(1),'url':f'https://www.youtube.com/watch?v={my.group(1)}', **base, 'outlet': f'YouTube, partagé sur r/{sub} par u/{author}'}
    else:
        media={'type':'link','url':p.get('url'), **base, 'outlet': f'{dom}, partagé sur r/{sub}'}
    out.append({'kind':kind,'date':tdate,'city':tcity,'title_prefix':tp,'media':[media],'_score':score})
    stats[kind]+=1
MANUAL={
 'près de toulouse, une jeune lycéenne': ('incident','2026-10-01','Tournefeuille','Leïla'),
 '[paris 8 octobre] après la manifestation': ('event','2026-10-08','Paris',''),
 '[17/10/2026] paris - violences policières - coups de matraque': ('incident','2026-10-17','Paris','Soirée du 17 octobre'),
 '[paris 17 octobre] des policiers de la 41ci': ('incident','2026-10-17','Paris','Soirée du 17 octobre'),
 '[rennes] lors d\'un contrôle': ('event','2026-10-01','Rennes',''),
 'après les pillages, les commerçants lyonnais': ('event','2026-10-17','Lyon',''),
 'un policier en civil tente en vain de briser la vitre': ('incident','2026-10-02','Aubervilliers','Un homme en civil'),
 '[05/11/2026] - paris - violences policières - la police charge la tête': ('event','2026-11-05','Paris',''),
 '[manifestation contre syngenta': None,
 '[17/10/2026] besançon - lynchage': ('incident','2026-10-17','Besançon','Un jeune homme plaqué'),
 '[marseille 17 octobre] des policiers lancent des grenades lacrymogènes depuis le balcon': ('event','2026-10-17','Marseille',''),
 "[17/10/2026] paris, alors qu’ils cherchaient": ('event','2026-10-17','Paris',''),
 "[17/10/2026] paris, alors qu'ils cherchaient": ('event','2026-10-17','Paris',''),
 '[rouen 24 octobre] un groupe de fascistes': ('incident','2026-10-24','Rouen','Des identitaires masqués'),
 '[dijon 24 octobre] un groupe de néo-nazis': ('incident','2026-10-24','Dijon','Une vingtaine de supporters'),
 'dijon - un groupe de néo-nazis': ('incident','2026-10-24','Dijon','Une vingtaine de supporters'),
 "[clermont-ferrand 24 octobre] le moment précis": ('incident','2026-10-24','Clermont-Ferrand','Un manifestant grièvement blessé'),
 'grenade lancée près d\'enfants à rouen': ('incident','2026-10-24','Rouen','Un motard de la police'),
 '[toulouse 1er octobre] leïla': ('incident','2026-10-01','Tournefeuille','Leïla'),
 '[29/09/2026] - alençon': ('incident','2026-10-01','Alençon','Aïna'),
 '[belfort] une voiture de la bac': ('incident','2026-10-02','Belfort','Une voiture banalisée de la BAC'),
}
_keep=[]
for a in out:
    tl=a['media'][0]['title'].lower(); drop=False
    for k,v in MANUAL.items():
        if tl.startswith(k):
            if v is None: drop=True
            else: a['kind'],a['date'],a['city'],a['title_prefix']=v
    if not drop: _keep.append(a)
out=_keep
import sys
if '--trace' in sys.argv:
    for a in out:
        if 'Mohammed' in a['media'][0]['title']: print('TRACE', a)
out.sort(key=lambda a:-a['_score'])
per=collections.Counter(); final=[]
for a in out:
    k=(a['kind'],a['date'],a['city'],a['title_prefix'])
    if per[k]>=4: continue
    per[k]+=1; a.pop('_score'); final.append(a)
json.dump(final, open(D+'media_reddit.json','w'), ensure_ascii=False, indent=0)
print('attachments', len(final), dict(stats), '| cards', len(per))
