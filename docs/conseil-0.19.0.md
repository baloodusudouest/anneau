# L'Anneau 0.19.0 — passage au Conseil (26/11/2026)

Dossier : `claude/anneau-0.19.0-dossier.md`. Cinq conseillers (Contrarian, Premiers principes, Expansionniste, Outsider, Exécutant), relecture croisée anonyme (5), synthèse du président.

## Où le conseil s'accorde
- **Trois versions, pas une** (5/5) : mélanger la refonte d'écran (~890 lignes) et des gardes de sécurité rend une régression impossible à attribuer.
- **Le réveil du PC ne se code qu'après un réveil réussi à la main depuis HA** (5/5, sauf l'ordre chez l'Expansionniste) : BIOS, carte réseau, « démarrage rapide » de Windows, adresse MAC, HA OS capable d'émettre le paquet sur le réseau local — rien n'a été essayé.
- **Le secret du webhook n'est pas le sujet** : `local_only` + identifiant long suffit ; au pire un PC s'allume. À écrire tel quel.
- **La barre de thèmes compense le clic en plus.**

## Où il se divise
- **Lecture des exports chiffrés en http** : 3 conseillers + 4 relecteurs veulent la laisser libre (que du chiffré ; c'est en http qu'on dépanne quand Tailscale tombe ; seule l'écriture de la clé publique est dangereuse). L'Exécutant et un relecteur gardent le choix de Julien (bloquer aussi la lecture). **À trancher par Julien.**
- **Pastilles et chiffres sur les tuiles** : Premiers principes les retire (second « À traiter » à côté de celui de l'anneau, `resume.js` = la partie qui traîne) ; un relecteur rappelle que c'est un choix explicite de Julien. **À trancher par Julien.**
- **Ordre** : B → A → C pour quatre conseillers ; l'Expansionniste veut C d'abord (le gain senti chaque jour), rejeté par les relecteurs (matériel non prouvé).

## Angles morts relevés à la relecture
- **`en_https` croit `X-Forwarded-Proto` et, à défaut, `Origin`, de n'importe quel expéditeur** (vérifié dans `app/auth.py`). Conséquence réelle, une fois le modèle de menace posé : la garde protège Julien de ses propres erreurs (page ouverte en http), pas d'un attaquant (qui aurait déjà besoin du cookie de session). Le vrai risque est l'inverse : **un GET de même origine n'envoie pas `Origin`** ; si Tailscale Serve n'envoie pas `X-Forwarded-Proto`, le 403 frappe aussi en https. → Étape zéro sur la vraie installation : voir ce que reçoit le serveur derrière Tailscale Serve. Prévoir une variable de secours qui coupe la garde.
- Le test « curl en https » proposé ne prouve rien (l'en-tête est cru) : le test doit passer par la vraie adresse Tailscale depuis un navigateur.
- La même fonction règle `Secure` des cookies : toute correction se teste en http **et** en https (connexion).
- Table des routes : y inclure les **GET de secret** et la future route `/api/reveil`.
- Le doute sur `/api/stack`, `/api/recharger`, `/api/carte/relire` est levé : elles n'écrivent que dans les fichiers de l'Anneau ou lisent GitHub. L'écart « lecture seule » se réduit bien au réveil + affichage + tests.
- Mots et couleurs : « tuile » désigne deux choses ; l'or veut dire « à faire », « thème courant » et « Anneau ». Choisir un mot (« thème ») et une couleur distincte pour le thème courant.
- Disques, pannes et carte sont des **états**, consultés souvent : les ranger sous Réglages les éloigne.
- Réveil à deux endroits : état « réveil en cours » partagé, bouton masqué pendant les 3 min de suivi ; l'identifiant du webhook ne sort jamais dans la page Stack & variables ni dans `services.yaml`.
- Le lien « À traiter » doit arriver sur la **section** exacte (ancre `#/reglages/stack#exports`).
- Quand Tailscale est tombé, le 403 doit dire quoi faire, pas seulement refuser.
- Pistes de l'Expansionniste notées pour plus tard (hors 0.19) : mécanisme générique « action HA par webhook », réveil automatique par Millésime, capteur HA « santé de la maison », table des routes dans le socle.

## Recommandation du président
1. **0.18.5 = écarts (B)**, après l'étape zéro (en-têtes réels derrière Tailscale Serve), avec variable de secours ; garde https sur l'**écriture** de la clé publique et des exports, lecture selon l'arbitrage de Julien ; table des routes avec GET de secret.
2. **0.19.0 = réglages unifiés (A)**, sans aucune route nouvelle ; ancres de section ; mot « thème » ; couleur du thème courant distincte de l'or d'alerte.
3. **0.20.0 = réveil (C)**, seulement après un réveil réussi à la main depuis HA (outils de développement › `wake_on_lan.send_magic_packet`).

## Premier geste
Julien ouvre l'Anneau par son adresse https Tailscale ; une route de diagnostic temporaire (ou le journal) montre les en-têtes reçus (`X-Forwarded-Proto`, `X-Forwarded-For`, adresse source). Tout le reste de B en dépend.

↑ [[L'Anneau]]

## Arbitrages de Julien (26/11/2026)
1. **Une seule version 0.19.0** (contre l'avis du conseil) : écarts, réglages unifiés et réveil livrés ensemble. Garde-fous retenus : trois étapes de code séparées et testées une à une (commits distincts), et le bouton de réveil ne sera annoncé « fonctionne » qu'après un réveil réussi à la main depuis HA.
2. **En http, seule l'écriture est refusée** (clé publique, rangement d'un export) ; la lecture et le téléchargement des exports chiffrés restent permis (previously : tout bloquer).
3. **Pastilles gardées** : état + chiffre + pastille sur les 5 thèmes ; couleur du thème courant distincte de l'or d'alerte.
4. **Thème Maison gardé + raccourci « Maison » depuis la vue de l'anneau** (disques, pannes, carte à un clic).
Retenus aussi de la relecture : étape zéro (en-têtes reçus derrière Tailscale Serve), variable de secours qui coupe la garde https, GET de secret et `/api/reveil` dans la table des routes, ancres de section, mot « thème », état « réveil en cours » partagé, identifiant du webhook jamais affiché.
