# Guide d'écriture des Reels Louloutre

À suivre pour chaque script JSON de `reels/scripts/` (par toi ou par Claude).

## Règles de fond
0. **L'accroche (scène 1) dure 3 secondes maximum** : une seule phrase choc (6 à 9 mots lus), une question ou un problème que le spectateur reconnaît immédiatement. Son texte à l'écran est visible dès la toute première image (c'est aussi la miniature).
1. **Une promesse concrète et mesurable** dans les 2 premières secondes (« Tes mails en 10 min au lieu d'1 h »), jamais un sujet vague (« L'IA c'est génial »).
2. **De la valeur copiable** : chaque astuce montre le prompt EXACT à l'écran (scène `"type": "prompt"`), assez précis pour être utilisé tel quel. C'est ce qui pousse à enregistrer le Reel.
3. **Un résultat visible** après chaque astuce (« En 10 secondes, tu sais par où commencer »).
4. **3 astuces maximum**, 20 à 35 secondes au total.
5. **Pas de chiffre inventé** ni de fausse promesse : on parle de son usage, pas de statistiques.
6. **Fin = appel à l'action** simple : enregistrer + une question pour les commentaires.

## Voix
Voix officielle de Louloutre : preset `loutre_cartoon` (Vivienne Multilingual, timbre « petit animal »). Mots mal prononcés -> `prononciation.json`.

## Règles de forme (texte lu)
- **Écrire comme on parle** pour que la voix sonne humaine : « t'as », « bon... », « allez », « franchement », « et là ». Varier la longueur des phrases.
- Phrases courtes (8 à 14 mots), à l'oral : « Un, le tri. », « Celui-là, presque personne ne l'utilise. »
- `...` = pause dramatique, `,` = respiration. Pas d'emoji ni d'abréviation dans le texte lu.
- Le texte à l'écran (`ecran`) ≠ texte lu : 2 lignes max, la 2ᵉ ligne (en jaune) porte le bénéfice.

## Structure type : UNE idée, bien creusée (7 scènes, 35-45 s)
| # | type | rôle | pose |
|---|------|------|------|
| 1 | titre | Accroche ≤ 3 s : le problème, en question | profil |
| 2 | titre | Pourquoi l'approche habituelle ne marche pas | etincelle |
| 3 | prompt | LE bon prompt, complet et copiable (contexte + objectif + format) | clavier |
| 4 | resultat | Extrait d'exemple de réponse (étiquette « EXEMPLE DE RÉPONSE ») | emerveillee |
| 5 | titre | « Pourquoi ça marche ? » : le principe à retenir | profil |
| 6 | prompt | Le réflexe / prompt bonus | clavier |
| 7 | titre | Appel à l'action (enregistrer, commenter, s'abonner) | pouce-leve |

Scène `resultat` : `{"type": "resultat", "voix": "...", "etiquette": "EXEMPLE DE RÉPONSE", "texte": "..."}`.
La légende reprend l'idée + le principe, pas juste la liste des prompts.

## Idées de sujets
Mails · réunions (compte-rendu en 1 prompt) · préparer un entretien · résumer un PDF · planifier sa semaine · apprendre une notion en 5 min · écrire un post LinkedIn · négocier · cuisiner avec ce qu'il reste dans le frigo · organiser un voyage.
