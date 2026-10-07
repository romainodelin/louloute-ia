#!/usr/bin/env python3
"""
post_to_instagram.py

Publie automatiquement le prochain post de la file d'attente (content_queue.json)
sur un compte Instagram Business/Creator, via l'API officielle Meta Graph.

Flux Graph API (obligatoire en 2 temps) :
  1. Créer un "media container" (POST /{ig-user-id}/media) avec l'URL de l'image et la légende.
  2. Publier ce container (POST /{ig-user-id}/media_publish).

Pré-requis (voir README.md) :
  - Compte Instagram converti en compte Business ou Creator.
  - Compte relié à une Page Facebook.
  - App Meta for Developers avec le produit "Instagram Graph API".
  - Un access token longue durée (60 jours, à renouveler) avec les scopes :
    instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement.

Variables d'environnement attendues (stockées en secrets GitHub Actions) :
  - IG_USER_ID        : l'ID du compte Instagram Business (pas le @pseudo)
  - IG_ACCESS_TOKEN   : le token d'accès longue durée
  - FB_PAGE_ID        : (optionnel) l'ID de la Page Facebook. Si présent, le post est
                        aussi publié sur la Page (nécessite pages_manage_posts).

Usage :
  python post_to_instagram.py
"""

import json
import re
import os
import sys
import time
from pathlib import Path
from urllib import request, parse, error

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

QUEUE_FILE = Path(__file__).parent / "content_queue.json"
LOG_FILE = Path(__file__).parent / "post_log.json"


def http_post(url: str, payload: dict) -> dict:
    data = parse.urlencode(payload).encode()
    req = request.Request(url, data=data, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Erreur API ({e.code}): {body}") from e


def load_queue() -> list:
    if not QUEUE_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {QUEUE_FILE}")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(queue: list) -> None:
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def log_result(entry: dict) -> None:
    history = []
    if LOG_FILE.exists():
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def publish_post(ig_user_id: str, access_token: str, image_url: str, caption: str) -> str:
    # Étape 1 : créer le container média
    container_resp = http_post(
        f"{GRAPH_BASE}/{ig_user_id}/media",
        {
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
    )
    creation_id = container_resp.get("id")
    if not creation_id:
        raise RuntimeError(f"Pas d'ID de container reçu : {container_resp}")

    # Petit délai pour laisser Meta traiter le média (surtout pour les vidéos/reels)
    time.sleep(5)

    # Étape 2 : publier le container
    publish_resp = http_post(
        f"{GRAPH_BASE}/{ig_user_id}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": access_token,
        },
    )
    media_id = publish_resp.get("id")
    if not media_id:
        raise RuntimeError(f"Échec de publication : {publish_resp}")
    return media_id


def http_get(url: str, params: dict) -> dict:
    try:
        with request.urlopen(f"{url}?{parse.urlencode(params)}", timeout=30) as resp:
            return json.loads(resp.read().decode())
    except error.HTTPError as e:
        raise RuntimeError(f"Erreur API ({e.code}): {e.read().decode()}") from e


def facebook_caption(caption: str) -> str:
    """Retire les hashtags (peu utiles sur Facebook) et les lignes vides en trop."""
    text = re.sub(r"(?m)^\s*(#\S+\s*)+$", "", caption)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def publish_facebook(page_id: str, user_token: str, image_url: str, caption: str) -> str:
    # Le token utilisateur permet d'obtenir le token de la Page, requis pour publier
    # On passe par /me/accounts : renvoie les Pages accessibles avec leur token.
    # La Page est retrouvée par son ID, ou à défaut par le compte Instagram qui lui est relié.
    accounts = http_get(
        f"{GRAPH_BASE}/me/accounts",
        {"fields": "id,name,access_token,instagram_business_account", "access_token": user_token},
    )
    pages = accounts.get("data", [])
    wanted = (page_id or "").strip().strip('"').strip("'")
    ig_user_id = os.environ.get("IG_USER_ID", "").strip()
    page = next((pg for pg in pages if pg.get("id") == wanted), None) or next(
        (pg for pg in pages if (pg.get("instagram_business_account") or {}).get("id") == ig_user_id), None
    )
    if not page or not page.get("access_token"):
        visibles = [(pg.get("id"), pg.get("name")) for pg in pages]
        raise RuntimeError(f"Page introuvable parmi les Pages accessibles par le token : {visibles}")
    page_id, page_token = page["id"], page["access_token"]
    resp = http_post(
        f"{GRAPH_BASE}/{page_id}/photos",
        {"url": image_url, "message": facebook_caption(caption), "access_token": page_token},
    )
    post_id = resp.get("post_id") or resp.get("id")
    if not post_id:
        raise RuntimeError(f"Échec de publication Facebook : {resp}")
    return post_id


def main() -> int:
    ig_user_id = os.environ.get("IG_USER_ID")
    access_token = os.environ.get("IG_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        print("ERREUR: variables d'environnement IG_USER_ID et IG_ACCESS_TOKEN requises.")
        return 1

    queue = load_queue()
    pending = [item for item in queue if item.get("status") == "pending"]

    if not pending:
        print("Aucun post en attente dans la file. Rien à publier.")
        return 0

    next_post = pending[0]
    print(f"Publication du post : {next_post.get('id', '(sans id)')}")

    try:
        media_id = publish_post(
            ig_user_id=ig_user_id,
            access_token=access_token,
            image_url=next_post["image_url"],
            caption=next_post["caption"],
        )
    except Exception as exc:
        print(f"ÉCHEC : {exc}")
        log_result({
            "post_id": next_post.get("id"),
            "status": "failed",
            "error": str(exc),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        return 1

    # Marquer le post comme publié et sauvegarder
    next_post["status"] = "published"
    next_post["instagram_media_id"] = media_id
    save_queue(queue)

    log_result({
        "post_id": next_post.get("id"),
        "status": "published",
        "instagram_media_id": media_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    print(f"Publié avec succès. ID média Instagram : {media_id}")

    # Facebook : un échec ici ne bloque pas Instagram (déjà publié)
    page_id = os.environ.get("FB_PAGE_ID", "")
    if os.environ.get("FB_DISABLED") != "1":
        try:
            fb_id = publish_facebook(page_id, access_token, next_post["image_url"], next_post["caption"])
            next_post["facebook_post_id"] = fb_id
            print(f"Publié aussi sur Facebook : {fb_id}")
        except Exception as exc:
            next_post["facebook_error"] = str(exc)[:300]
            print(f"AVERTISSEMENT Facebook : {exc}")
        save_queue(queue)
    return 0


if __name__ == "__main__":
    sys.exit(main())
