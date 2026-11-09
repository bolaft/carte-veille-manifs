import json, subprocess, time, sys, os, datetime
S='/tmp/claude-0/-home-user/a19e4210-3cc5-511a-88da-ecdc6e7af354/scratchpad'
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
start=int(datetime.datetime(2026,9,17,0,0,tzinfo=datetime.timezone.utc).timestamp())
end=int(datetime.datetime(2026,11,9,23,59,tzinfo=datetime.timezone.utc).timestamp())
KEEP=('id','title','created_utc','score','num_comments','is_video','domain','url','permalink','link_flair_text','thumbnail','post_hint','removed_by_category','author','media','secure_media','preview','selftext','over_18','is_gallery','media_metadata','subreddit')
def harvest(sub, out):
    seen=set(); after=start; n=0
    if os.path.exists(out):
        for line in open(out):
            try: p=json.loads(line); seen.add(p['id']); after=max(after, int(p['created_utc'])+1)
            except Exception: pass
    with open(out,'a') as f:
        fails=0
        while after < end:
            url=f'https://arctic-shift.photon-reddit.com/api/posts/search?subreddit={sub}&after={after}&before={end}&limit=100&sort=asc'
            d=None
            for attempt in range(4):
                r=subprocess.run(['curl','-sS','-A',UA,'--max-time','60',url],capture_output=True,text=True)
                try: d=json.loads(r.stdout)['data']; break
                except Exception: time.sleep(3*(attempt+1))
            if d is None:
                fails+=1; print(sub,'FAIL at',after, flush=True)
                if fails>3: break
                after+=3600; continue   # skip one hour and keep going
            if not d: break
            for p in d:
                if p['id'] in seen: continue
                seen.add(p['id']); n+=1
                f.write(json.dumps({k:p.get(k) for k in KEEP},ensure_ascii=False)+'\n')
            f.flush()
            last=max(int(p['created_utc']) for p in d)
            if last < after: break
            after=last+1; time.sleep(0.5)
    print(sub,'done',n, flush=True)
subs=sys.argv[1:]
for sub in subs:
    harvest(sub, f'{S}/dl/reddit/posts_{sub}.jsonl')
print('ALL DONE')
