"""Run once: python3 check_meta.py YOUR_PAGE_TOKEN
Prints the FB_PAGE_ID and IG_USER_ID to paste into GitHub secrets, and checks permissions."""
import sys,requests
t=sys.argv[1];g='https://graph.facebook.com/v21.0'
me=requests.get(f'{g}/me',params={'fields':'id,name,instagram_business_account','access_token':t}).json()
print('Page:',me.get('name'),'\nFB_PAGE_ID =',me.get('id'),'\nIG_USER_ID =',(me.get('instagram_business_account') or {}).get('id','NOT LINKED'))
d=requests.get(f'{g}/debug_token',params={'input_token':t,'access_token':t}).json().get('data',{})
print('Expires:', 'never' if d.get('expires_at')==0 else d.get('expires_at'),'\nScopes:',', '.join(d.get('scopes',[])))
need={'pages_manage_posts','pages_read_engagement','instagram_basic','instagram_content_publish'}
miss=need-set(d.get('scopes',[])); print('MISSING:',', '.join(miss) if miss else 'none - ready')
