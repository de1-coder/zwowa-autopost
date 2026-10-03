# Zwowa auto-poster (Facebook + Instagram), free

Posts the 159 remaining posts (24 Oct to 16 Dec, 08:00 / 12:30 / 18:30 SAST) to Facebook and Instagram automatically. It runs on GitHub Actions every 15 minutes and uses Meta's official Graph API.

## 1. Get a Page token (about 5 minutes)
1. Go to developers.facebook.com, then My Apps, then Create App. Choose "Other", then "Business", and name it "Zwowa Poster".
2. Open Tools, then Graph API Explorer, and select the app.
3. Add these permissions: pages_manage_posts, pages_read_engagement, pages_show_list, instagram_basic, instagram_content_publish.
4. Click Generate Access Token and approve for Zwowa.dev and zwowa.dev.
5. Under "User or Page", pick **Zwowa.dev**. This gives you a Page token.
6. Make the token long-lived: click the (i) next to it, then "Open in Access Token Tool", then "Extend Access Token". Use the Page token from me/accounts after extending; it never expires.

## 2. Create the repo
1. Create a **public** GitHub repo called zwowa-autopost. It must be public so Instagram can fetch the images.
2. Upload this folder's contents, including the hidden .github folder.

## 3. Add the secrets
Go to Settings, then Secrets and variables, then Actions, then New secret, and add:
- FB_PAGE_TOKEN: the Page token
- IG_ACCESS_TOKEN: the same Page token
- FB_PAGE_ID and IG_USER_ID: run `python3 check_meta.py <token>` to print both
- MEDIA_BASE_URL: https://raw.githubusercontent.com/<your-user>/zwowa-autopost/main

## 4. Turn it on
Open the Actions tab, enable workflows, then go to zwowa-publish and click "Run workflow" once.
Each post goes out on time, and the repo saves a log in the database after every run.

Posts already scheduled in Meta Business Suite (up to 24 Oct 12:30) are marked as done, so they won't be posted twice.
