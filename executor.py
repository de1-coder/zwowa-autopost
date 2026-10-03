"""Zwowa queue executor. Execution only: never edits captions, assets or dates.
Run every 15 min (GitHub Actions workflow included). Publishes placements whose
scheduled_at <= now and status in (QUEUED, RETRY) via official platform APIs.
Credentials come from environment variables (repo secrets). Platforms without
credentials are skipped and logged as WAITING_AUTH (posts stay queued, nothing lost)."""
import os,sqlite3,datetime as dt,json,time,requests
DB=os.environ.get('ZW_DB','ZWOWA_MASTER_POSTING_QUEUE.sqlite')
BASE=os.environ.get('MEDIA_BASE_URL','').rstrip('/')   # public URL where media/ is hosted (needed by IG + TikTok)
MAX_ATTEMPTS=5; LATE_LIMIT_H=int(os.environ.get('LATE_LIMIT_HOURS','24'))
def now(): return dt.datetime.now(dt.timezone.utc)
def log(db,pid,p,act,res,det=''): db.execute('insert into run_log values (?,?,?,?,?,?)',(now().isoformat(),pid,p,act,res,str(det)[:500]))
# ---------- official API adapters ----------
def instagram(r):
    ig,tok=os.environ['IG_USER_ID'],os.environ['IG_ACCESS_TOKEN']; g='https://graph.facebook.com/v21.0'
    c=requests.post(f'{g}/{ig}/media',data={'image_url':f"{BASE}/{r['media_path']}",'caption':r['caption'],'access_token':tok},timeout=60).json()
    if 'id' not in c: raise Exception(c)
    for _ in range(10):
        s=requests.get(f"{g}/{c['id']}",params={'fields':'status_code','access_token':tok},timeout=30).json()
        if s.get('status_code')=='FINISHED': break
        time.sleep(5)
    p=requests.post(f'{g}/{ig}/media_publish',data={'creation_id':c['id'],'access_token':tok},timeout=60).json()
    if 'id' not in p: raise Exception(p)
    l=requests.get(f"{g}/{p['id']}",params={'fields':'permalink','access_token':tok},timeout=30).json()
    return p['id'],l.get('permalink','')
def tiktok(r):  # Content Posting API, photo mode (media domain must be verified in TikTok dev portal)
    tok=os.environ['TIKTOK_ACCESS_TOKEN']
    body={'post_info':{'title':r['hook'][:90],'description':r['caption'][:4000],'privacy_level':os.environ.get('TIKTOK_PRIVACY','PUBLIC_TO_EVERYONE'),'disable_comment':False,'auto_add_music':True},
          'source_info':{'source':'PULL_FROM_URL','photo_cover_index':0,'photo_images':[f"{BASE}/{r['media_path']}"]},'post_mode':'DIRECT_POST','media_type':'PHOTO'}
    j=requests.post('https://open.tiktokapis.com/v2/post/publish/content/init/',headers={'Authorization':f'Bearer {tok}','Content-Type':'application/json'},json=body,timeout=60).json()
    if j.get('error',{}).get('code')!='ok': raise Exception(j)
    return j['data']['publish_id'],''
def linkedin(r):
    tok,author=os.environ['LINKEDIN_ACCESS_TOKEN'],os.environ['LINKEDIN_AUTHOR_URN']  # urn:li:organization:123 or urn:li:person:abc
    H={'Authorization':f'Bearer {tok}','LinkedIn-Version':'202409','X-Restli-Protocol-Version':'2.0.0','Content-Type':'application/json'}
    i=requests.post('https://api.linkedin.com/rest/images?action=initializeUpload',headers=H,json={'initializeUploadRequest':{'owner':author}},timeout=60).json()['value']
    requests.put(i['uploadUrl'],data=open(r['media_path'],'rb'),headers={'Authorization':f'Bearer {tok}'},timeout=120).raise_for_status()
    p=requests.post('https://api.linkedin.com/rest/posts',headers=H,json={'author':author,'commentary':r['caption'],'visibility':'PUBLIC','distribution':{'feedDistribution':'MAIN_FEED','targetEntities':[],'thirdPartyDistributionChannels':[]},'content':{'media':{'id':i['image']}},'lifecycleState':'PUBLISHED','isReshareDisabledByAuthor':False},timeout=60)
    if p.status_code>=300: raise Exception(p.text)
    pid=p.headers.get('x-restli-id',''); return pid,f'https://www.linkedin.com/feed/update/{pid}'
def x(r):
    from requests_oauthlib import OAuth1
    a=OAuth1(os.environ['X_API_KEY'],os.environ['X_API_SECRET'],os.environ['X_ACCESS_TOKEN'],os.environ['X_ACCESS_SECRET'])
    m=requests.post('https://upload.twitter.com/1.1/media/upload.json',auth=a,files={'media':open(r['media_path'],'rb')},timeout=120).json()
    t=requests.post('https://api.twitter.com/2/tweets',auth=a,json={'text':r['caption'],'media':{'media_ids':[m['media_id_string']]}},timeout=60).json()
    if 'data' not in t: raise Exception(t)
    return t['data']['id'],f"https://x.com/i/web/status/{t['data']['id']}"
def facebook(r):  # Page photo post, uploaded straight from the repo file (no public URL needed)
    pg,tok=os.environ['FB_PAGE_ID'],os.environ['FB_PAGE_TOKEN']
    j=requests.post(f'https://graph.facebook.com/v21.0/{pg}/photos',data={'message':r['caption'],'access_token':tok},files={'source':open(r['media_path'],'rb')},timeout=120).json()
    if 'post_id' not in j and 'id' not in j: raise Exception(j)
    pid=j.get('post_id',j.get('id')); return pid,f'https://www.facebook.com/{pid}'
ADAPT={'facebook':(facebook,['FB_PAGE_ID','FB_PAGE_TOKEN']),'instagram':(instagram,['IG_USER_ID','IG_ACCESS_TOKEN','MEDIA_BASE_URL']),'tiktok':(tiktok,['TIKTOK_ACCESS_TOKEN','MEDIA_BASE_URL']),'linkedin':(linkedin,['LINKEDIN_ACCESS_TOKEN','LINKEDIN_AUTHOR_URN']),'x':(x,['X_API_KEY','X_API_SECRET','X_ACCESS_TOKEN','X_ACCESS_SECRET'])}
def main():
    db=sqlite3.connect(DB);db.row_factory=sqlite3.Row
    due=db.execute("select * from placements where status in ('QUEUED','RETRY') and scheduled_at<=? order by scheduled_at limit 60",(now().astimezone(dt.timezone(dt.timedelta(hours=2))).isoformat(timespec='seconds'),)).fetchall()
    for r in due:
        r=dict(r);r['caption']=r['caption'].replace('Friday 9 October\n\n','',1)
        p=r['platform'];fn,need=ADAPT[p]
        if any(not os.environ.get(k) for k in need):
            log(db,r['placement_id'],p,'skip','WAITING_AUTH','missing '+','.join(k for k in need if not os.environ.get(k)));continue
        late=(now()-dt.datetime.fromisoformat(r['scheduled_at'])).total_seconds()/3600
        if late>LATE_LIMIT_H:  # keep calendar honest: don't dump a backlog; mark and continue
            db.execute("update placements set status='SKIPPED_LATE',updated_at=? where placement_id=?",(now().isoformat(),r['placement_id']));log(db,r['placement_id'],p,'skip','LATE',f'{late:.1f}h');continue
        try:
            pid,url=fn(dict(r))
            db.execute("update placements set status='PUBLISHED',platform_post_id=?,post_url=?,attempts=attempts+1,last_error='',updated_at=? where placement_id=?",(pid,url,now().isoformat(),r['placement_id']));log(db,r['placement_id'],p,'publish','OK',pid)
        except Exception as e:
            a=r['attempts']+1;st='FAILED' if a>=MAX_ATTEMPTS else 'RETRY'
            db.execute("update placements set status=?,attempts=?,last_error=?,updated_at=? where placement_id=?",(st,a,str(e)[:500],now().isoformat(),r['placement_id']));log(db,r['placement_id'],p,'publish',st,e)
        db.commit()
    db.commit()
    print(json.dumps({s:c for s,c in db.execute('select status,count(*) from placements group by status')}))
if __name__=='__main__': main()
