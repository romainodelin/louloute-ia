# Auto-post Instagram — gratuit via l'API Meta Graph + GitHub Actions

Ce kit publie automatiquement des posts sur Instagram depuis une file d'attente,
selon un planning récurrent, sans frais d'hébergement.

Page : **@louloute.ia** — l'IA générative et la productivité, expliquées par Louloutre 🦦✦

## Structure du projet

```
instagram_bot/
├── post_to_instagram.py      # publie le prochain post "pending"
├── content_queue.json        # file d'attente (image + légende)
├── post_log.json             # historique (généré automatiquement)
├── images/                   # visuels des posts (post-001.jpg…), servis via raw.githubusercontent.com
├── branding/
│   ├── charte-louloute.html  # charte de marque (ouvrir dans un navigateur)
│   ├── louloutre-profil.png  # photo de profil 1080×1080
│   ├── louloutre-en-pied.png # mascotte détourée (fond transparent)
│   └── louloutre-*.png       # poses : étincelle, pouce levé, émerveillée, clavier
├── PROJET_CLAUDE.md          # instructions à coller dans un projet Claude
└── .github/workflows/post.yml # planning lun/mer/ven 9h
```

## Étape 1 — Convertir ton compte Instagram

1. Dans l'app Instagram : Paramètres → Compte → passe en compte **Professionnel** (Créateur ou Entreprise).
2. Relie ce compte à une **Page Facebook** (créée gratuitement si tu n'en as pas).

## Étape 2 — Créer l'app Meta Developer

1. Va sur https://developers.facebook.com/apps et crée une app de type "Business".
2. Ajoute le produit **Instagram Graph API** à l'app.
3. Dans les paramètres de l'app, lie ta Page Facebook (et donc ton compte Instagram).

## Étape 3 — Obtenir un access token longue durée

1. Utilise le **Graph API Explorer** (https://developers.facebook.com/tools/explorer/) avec ton app.
2. Génère un token utilisateur avec les permissions : `instagram_basic`, `instagram_content_publish`,
   `pages_show_list`, `pages_read_engagement`.
3. Échange ce token court (1h) contre un **token longue durée (60 jours)** via l'endpoint :
   `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=...&client_secret=...&fb_exchange_token=...`
4. Récupère ton **IG_USER_ID** via : `GET /me/accounts` puis `GET /{page-id}?fields=instagram_business_account`.

⚠️ Le token expire après 60 jours : il faudra le régénérer périodiquement (mets-toi un rappel,
ou automatise le renouvellement plus tard si tu veux aller plus loin).

## Étape 4 — Stocker les secrets dans GitHub

Dans ton repo GitHub : Settings → Secrets and variables → Actions → New repository secret :

- `IG_USER_ID` = l'ID récupéré à l'étape 3
- `IG_ACCESS_TOKEN` = le token longue durée

**Ne jamais mettre ces valeurs en clair dans le code ou dans le chat.**

## Étape 5 — Héberger les images publiquement

L'API Graph exige une URL d'image **publique** (pas un fichier local). Solution simple et gratuite :
mets tes images dans un dossier `images/` de ton repo GitHub **public**, et référence-les dans
`content_queue.json` via leur URL `raw.githubusercontent.com` (voir l'exemple dans le fichier).

## Étape 6 — Remplir la file de contenu

Ajoute des entrées dans `content_queue.json` avec `status: "pending"`. Le script publie toujours
la première entrée "pending" de la liste, puis la passe en `"published"`.

Je peux t'aider à générer les idées de posts et légendes en lot pour remplir cette file.

## Étape 7 — Activer le planning

Le workflow est déjà en place dans `.github/workflows/post.yml`. Le planning
par défaut publie lundi/mercredi/vendredi à 9h (heure Paris, approx.). Modifie la ligne `cron`
si tu veux un autre rythme.

Tu peux aussi déclencher une publication manuelle depuis l'onglet **Actions** du repo
(bouton "Run workflow").

## Limites à connaître

- Token à renouveler tous les 60 jours.
- Meta peut faire évoluer l'API Graph ; surveille les dépréciations dans leur changelog développeur.
- Respecte les règles de contenu Instagram/Meta (pas de spam, pas de posts automatisés trompeurs).
- Teste d'abord avec `workflow_dispatch` (déclenchement manuel) avant de laisser tourner le planning automatique.

## Mettre le projet sur GitHub

Le dossier est déjà un dépôt git avec un premier commit. Crée un repo **public** vide sur GitHub
(ex. `louloute-ia`), puis :

```
git remote add origin https://github.com/<ton-user>/louloute-ia.git
git push -u origin main
```

Remplace ensuite `<ton-user>/<ton-repo>` dans `content_queue.json` par ton vrai chemin.
