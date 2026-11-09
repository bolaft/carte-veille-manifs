import re, sys, json, html, os

KEEP = {'citation','unité','unite','nombre','formatnum:','nobr','date','date-','lang','nb','souligner','citation bloc','heure','pourcentage','nombre','numéro','n°','abréviation','abr','1er','1re','exp','e','er','re','s','mois','siècle','date de naissance','date de décès','dunité','dunite','référence nécessaire','refnec','refsou','quand','qui','lequel','où','pas clair','incise','ép.','nobr'}

def split_args(inner):
    parts=[]; depth=0; cur=''; i=0
    while i < len(inner):
        two=inner[i:i+2]
        if two in ('[[','{{'): depth+=1; cur+=two; i+=2; continue
        if two in (']]','}}'): depth-=1; cur+=two; i+=2; continue
        if inner[i]=='|' and depth==0: parts.append(cur); cur=''; i+=1; continue
        cur+=inner[i]; i+=1
    parts.append(cur)
    return parts

def parse_ref_body(body):
    d={}
    m=re.search(r'\{\{\s*(Lien web|Article|Ouvrage|Lien brisé|Chapitre|Cite web|Cite news)\s*\|(.*)\}\}', body, re.S|re.I)
    if m:
        for p in split_args(m.group(2)):
            if '=' in p:
                k,v=p.split('=',1); d[k.strip().lower()]=v.strip()
    else:
        m2=re.search(r'https?://[^\s\]\|<]+', body)
        if m2: d['url']=m2.group(0)
        d['raw']=re.sub(r'\s+',' ',body)[:300]
    return {
        'url': d.get('url') or d.get('lire en ligne') or '',
        'title': d.get('titre') or d.get('title') or d.get('raw','') ,
        'site': d.get('site') or d.get('périodique') or d.get('éditeur') or d.get('journal') or d.get('périodique') or '',
        'date': d.get('date') or '',
        'author': (' '.join(x for x in [d.get('prénom1',''), d.get('nom1','')] if x) or d.get('auteur') or d.get('auteur1') or ''),
    }

def process(path):
    src=open(path,encoding='utf-8').read()
    refs=[]; byname={}
    pat=re.compile(r'<ref(\s+[^>/]*)?(?:\s*/>|>(.*?)</ref>)', re.S|re.I)
    # pass 1: collect bodies in order
    for m in pat.finditer(src):
        attrs=m.group(1) or ''; body=m.group(2)
        nm=re.search(r'name\s*=\s*"?([^"/>]+)"?', attrs)
        name=nm.group(1).strip() if nm else None
        if body is not None and body.strip():
            r=parse_ref_body(body); r['name']=name; r['n']=len(refs)+1
            refs.append(r)
            if name: byname[name]=r['n']
    def repl(m):
        attrs=m.group(1) or ''; body=m.group(2)
        nm=re.search(r'name\s*=\s*"?([^"/>]+)"?', attrs)
        name=nm.group(1).strip() if nm else None
        if body is not None and body.strip():
            # find the ref with this body (sequential)
            repl.i+=1
            return f'[{repl.i}]'
        if name and name in byname: return f'[{byname[name]}]'
        return f'[ref:{name}]'
    repl.i=0
    txt=pat.sub(repl, src)
    txt=re.sub(r'<!--.*?-->','',txt,flags=re.S)
    # templates innermost first
    def tpl(m):
        inner=m.group(1)
        parts=split_args(inner)
        name=parts[0].strip().lower()
        if name.startswith('formatnum:'): return name.split(':',1)[1]
        if name in KEEP or name.startswith('date'):
            args=[p for p in parts[1:] if '=' not in p.split('|')[0][:30] or p.strip().startswith('http')]
            args=[p.strip() for p in parts[1:] if not re.match(r'^\s*[\w\s]+=',p)]
            if name=='citation': return '« '+' '.join(args)+' »'
            if name=='lang': return ' '.join(args[1:]) if len(args)>1 else ' '.join(args)
            return ' '.join(args)
        return ''
    for _ in range(12):
        new=re.sub(r'\{\{([^{}]*)\}\}', tpl, txt, flags=re.S)
        if new==txt: break
        txt=new
    txt=re.sub(r'\[\[(?:Fichier|File|Image):[^\]]*\]\]','',txt)
    txt=re.sub(r'\[\[([^\]|]*)\|([^\]]*)\]\]', r'\2', txt)
    txt=re.sub(r'\[\[([^\]]*)\]\]', r'\1', txt)
    txt=re.sub(r'\[(https?://[^\s\]]+)\s+([^\]]*)\]', r'\2 (\1)', txt)
    txt=re.sub(r"'''?",'',txt)
    txt=re.sub(r'<br\s*/?>','\n',txt)
    txt=re.sub(r'<[^>]+>','',txt)
    txt=re.sub(r'^\{\|.*$','',txt,flags=re.M)
    txt=re.sub(r'^\|\}.*$','',txt,flags=re.M)
    txt=re.sub(r'^\|-.*$','',txt,flags=re.M)
    txt=re.sub(r'^[!|]\s?','',txt,flags=re.M)
    txt=txt.replace('||',' | ').replace('!!',' | ')
    txt=re.sub(r'^(=+)\s*(.*?)\s*=+\s*$', lambda m: '#'*len(m.group(1))+' '+m.group(2), txt, flags=re.M)
    txt=html.unescape(txt)
    txt=re.sub(r'\n{3,}','\n\n',txt)
    return txt, refs

base=sys.argv[1]; out=sys.argv[2]
for f in sorted(os.listdir(base)):
    if not f.endswith('.wiki'): continue
    txt,refs=process(os.path.join(base,f))
    stem=f[:-5]
    open(os.path.join(out,stem+'.txt'),'w',encoding='utf-8').write(txt)
    json.dump(refs, open(os.path.join(out,stem+'.refs.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=0)
    with open(os.path.join(out,stem+'.refs.md'),'w',encoding='utf-8') as fh:
        for r in refs:
            fh.write(f"[{r['n']}] {r['site']} | {r['date']} | {r['title'][:140]} | {r['url']}\n")
    print(stem, len(txt), 'chars,', len(refs), 'refs,', sum(1 for r in refs if r['url']), 'with url')
