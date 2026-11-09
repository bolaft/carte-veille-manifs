import json, sys, os, subprocess, urllib.parse, re, unicodedata
D='/tmp/claude-0/-home-user/a19e4210-3cc5-511a-88da-ecdc6e7af354/scratchpad/data'
CACHE=os.path.join(D,'geocode.json')
cache=json.load(open(CACHE)) if os.path.exists(CACHE) else {}
MANUAL={
 'Nouméa|988':(-22.2758,166.4580),'Papeete|987':(-17.5350,-149.5696),'Saint-Pierre|975':(46.7792,-56.1773),
 'Marigot|978':(18.0675,-63.0825),'Gustavia|977':(17.8962,-62.8498),'Mata-Utu|986':(-13.2825,-176.1764),
 'Faaa|987':(-17.5569,-149.5995),"Faa'a|987":(-17.5569,-149.5995),'Punaauia|987':(-17.6333,-149.6000),'Koné|988':(-21.0597,164.8617),'Dumbéa|988':(-22.1500,166.4500),'Le Mont-Dore|988':(-22.2667,166.5833),'Mont-Dore|988':(-22.2667,166.5833),'Païta|988':(-22.1333,166.3500),
 'France|':(None,None),
}
def norm(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+',' ',s).strip()
def query(city, dept):
    params={'nom':city,'fields':'nom,code,codeDepartement,centre,population','boost':'population','limit':'5'}
    if dept and re.match(r'^(\d{2,3}|2A|2B)$',dept): params['codeDepartement']=dept
    url='https://geo.api.gouv.fr/communes?'+urllib.parse.urlencode(params)
    try:
        out=subprocess.run(['curl','-sS','--max-time','20',url],capture_output=True,text=True,timeout=30).stdout
        res=json.loads(out)
    except Exception as e:
        return None
    if not res: return None
    # prefer exact name match
    n=norm(city)
    exact=[r for r in res if norm(r['nom'])==n]
    r=(exact or res)[0]
    c=r['centre']['coordinates']
    return {'lat':c[1],'lon':c[0],'nom':r['nom'],'dept':r['codeDepartement'],'pop':r.get('population')}
def key(city,dept): return f"{city}|{dept or ''}"
def geocode(city,dept):
    k=key(city,dept)
    if k in cache: return cache[k]
    if k in MANUAL:
        la,lo=MANUAL[k]; cache[k]={'lat':la,'lon':lo,'nom':city,'dept':dept,'manual':True}; return cache[k]
    r=query(city,dept)
    if r is None and dept:
        r=query(city,'')
    if r is None:
        # try stripping arrondissement / parentheses
        c2=re.sub(r'\s*\(.*?\)','',city).split(',')[0].strip()
        if c2!=city: r=query(c2,dept) or query(c2,'')
    cache[k]=r
    return r
def main():
    pairs=set()
    for a in sys.argv[1:]:
        if a.endswith('.json'):
            for it in json.load(open(a)):
                pairs.add((it.get('city','').strip(), str(it.get('dept','') or '').strip()))
        else:
            for line in open(a):
                line=line.strip()
                if not line or line.startswith('#'): continue
                c,_,d=line.partition('|'); pairs.add((c.strip(),d.strip()))
    miss=[]
    for city,dept in sorted(pairs):
        if not city: continue
        r=geocode(city,dept)
        if r is None: miss.append((city,dept))
    json.dump(cache,open(CACHE,'w'),ensure_ascii=False,indent=0)
    print('cached',len(cache),'missing',len(miss)); 
    for m in miss: print('  MISSING', m)
main()
