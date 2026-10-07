#!/usr/bin/env python3
"""
publish_reel.py — génère puis publie le prochain Reel de la file (reels/file_reels.json)
sur Instagram (Reel) et Facebook (Reel de Page), via l'API Meta Graph.

Envoi direct du fichier vidéo (upload « resumable » de Meta) : pas besoin d'héberger la vidéo.

Variables d'environnement (secrets GitHub, les mêmes que pour les posts photo) :
  IG_USER_ID, IG_ACCESS_TOKEN, FB_PAGE_ID (optionnel), FB_DISABLED=1 pour couper Facebook.
Options : DRY_RUN=1 -> génère la vidéo sans publier.
"""
import json, os, re, sys, time
from pathlib import Path
from urllib import request, parse, error

ICI = Path(__file__).parent
sys.path.insert(0, str(ICI))
import make_reel

GRAPH = "https://graph.facebook.com/v21.0"
FILE = ICI / "file_reels.json"
LOG = ICI / "journal_reels.json"

def _req(url, data=None, headers=None, method=None):
    if isinstance(data, dict): data = parse.urlencode(data).encode()
    r = request.Request(url, data=data, headers=headers or {}, method=method or ("POST" if data is not None else "GET"))
    try:
        with request.urlopen(r, timeout=300) as resp: return json.loads(resp.read().decode())
    except error.HTTPError as e:
        raise RuntimeError(f"Erreur API ({e.code}) sur {url.split('?')[0]} : {e.read().decode()[:500]}") from e

def get(url, **params): return _req(f"{url}?{parse.urlencode(params)}")

def envoyer_fichier(url, token, chemin, prefixe="OAuth"):
    taille = os.path.getsize(chemin)
    with open(chemin, "rb") as f:
        return _req(url, data=f.read(), headers={"Authorization": f"{prefixe} {token}", "offset": "0",
                                                  "file_size": str(taille), "Content-Type": "application/octet-stream"})

# ---------- Instagram ----------
def publier_instagram(ig_id, token, video, legende):
    cont = _req(f"{GRAPH}/{ig_id}/media", {"media_type": "REELS", "upload_type": "resumable",
                                           "caption": legende, "share_to_feed": "true", "access_token": token})
    cid, uri = cont["id"], cont.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v21.0/{cont['id']}"
    print(f"  IG : conteneur {cid}, envoi de la vidéo...", flush=True)
    envoyer_fichier(uri, token, video)
    for _ in range(60):                                   # traitement côté Meta (jusqu'à ~10 min)
        st = get(f"{GRAPH}/{cid}", fields="status_code,status", access_token=token)
        code = st.get("status_code")
        if code == "FINISHED": break
        if code == "ERROR": raise RuntimeError(f"Traitement IG en erreur : {st}")
        time.sleep(10)
    else:
        raise RuntimeError("Délai dépassé pendant le traitement Instagram")
    pub = _req(f"{GRAPH}/{ig_id}/media_publish", {"creation_id": cid, "access_token": token})
    return pub["id"]

# ---------- Facebook ----------
def jeton_page(token, page_id, ig_id):
    pages = get(f"{GRAPH}/me/accounts", fields="id,name,access_token,instagram_business_account", access_token=token).get("data", [])
    p = next((x for x in pages if x.get("id") == (page_id or "").strip()), None) or \
        next((x for x in pages if (x.get("instagram_business_account") or {}).get("id") == ig_id), None)
    if not p: raise RuntimeError(f"Page Facebook introuvable : {[(x.get('id'), x.get('name')) for x in pages]}")
    return p["id"], p["access_token"]

def publier_facebook(token, page_id, ig_id, video, legende):
    pid, ptoken = jeton_page(token, page_id, ig_id)
    debut = _req(f"{GRAPH}/{pid}/video_reels", {"upload_phase": "start", "access_token": ptoken})
    vid = debut["video_id"]
    envoyer_fichier(debut.get("upload_url") or f"https://rupload.facebook.com/video-upload/v21.0/{vid}", ptoken, video)
    texte = re.sub(r"(?m)^\s*(#\S+\s*)+$", "", legende).strip()
    _req(f"{GRAPH}/{pid}/video_reels", {"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                        "description": texte, "access_token": ptoken})
    return vid

# ---------- Orchestration ----------
def journal(e):
    h = json.load(open(LOG, encoding="utf-8")) if LOG.exists() else []
    h.append({**e, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    json.dump(h, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def main():
    file = json.load(open(FILE, encoding="utf-8"))
    suivant = next((x for x in file if x.get("status") == "pending"), None)
    if not suivant: print("Aucun Reel en attente."); return 0
    script = ICI / "scripts" / f"{suivant['id']}.json"
    print(f"🎞  Reel : {suivant['id']}", flush=True)
    video = make_reel.fabriquer(str(script))
    legende = json.load(open(script, encoding="utf-8")).get("legende", "")
    if os.environ.get("DRY_RUN") == "1": print("DRY_RUN : pas de publication."); return 0

    ig_id, token = os.environ.get("IG_USER_ID", "").strip(), os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not ig_id or not token: print("ERREUR : IG_USER_ID / IG_ACCESS_TOKEN manquants."); return 1
    try:
        suivant["instagram_media_id"] = publier_instagram(ig_id, token, video, legende)
        suivant["status"] = "published"
        print(f"✅ Instagram : {suivant['instagram_media_id']}")
    except Exception as e:
        print(f"ÉCHEC Instagram : {e}"); journal({"reel": suivant["id"], "status": "failed", "error": str(e)[:500]})
        suivant["tentatives"] = suivant.get("tentatives", 0) + 1
        if suivant["tentatives"] >= 3: suivant["status"] = "failed"   # on passe au suivant la prochaine fois
        json.dump(file, open(FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 1
    if os.environ.get("FB_DISABLED") != "1":
        try:
            suivant["facebook_video_id"] = publier_facebook(token, os.environ.get("FB_PAGE_ID", ""), ig_id, video, legende)
            print(f"✅ Facebook : {suivant['facebook_video_id']}")
        except Exception as e:
            suivant["facebook_error"] = str(e)[:300]; print(f"AVERTISSEMENT Facebook : {e}")
    json.dump(file, open(FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    journal({"reel": suivant["id"], "status": "published", "instagram_media_id": suivant["instagram_media_id"]})
    return 0

if __name__ == "__main__":
    sys.exit(main())
