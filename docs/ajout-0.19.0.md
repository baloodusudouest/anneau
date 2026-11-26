# L'Anneau 0.19.0 — réglages unifiés en tuiles, écarts de l'audit, réveil du PC de calcul — dossier (26/11/2026)

> Copie du dossier pour le dépôt public (26/11/2026) : adresses du réseau local remplacées par des exemples. Le coffre fait foi.

Demande de Julien du 26/11/2026 (17 h 04), captures des pages « Réglages » et « Variables » à l'appui : « il faudrait unifier les réglages ». Cadrage par questions à choix le même jour (grill), puis ajout, à sa demande, des deux écarts de l'audit et du réveil du PC de calcul (repris d'une autre conversation du 26/11, qui ne garde rien de ce périmètre).

Point de départ lu : coffre `coffre-maison` (commit 4ecb30d du 24/11), dépôt `anneau` 0.18.4 (23/11), note « Tuiles de l'Anneau ». **Code : rien tant que Julien n'a pas dit « go ».**

## 1. Besoin et choix de Julien

### A. Réglages unifiés
Aujourd'hui, quatre pages qui se renvoient l'une à l'autre :
- **Réglages** (`#/reglages`, 11 sections) : Fichier des services, Carte de la maison (résumé + bouton), Connexion, Bac à sable, Versions, Sauvegarde (+ résumé des exports chiffrés), Restaurer les réglages, Disques, Home Assistant, Dernières pannes closes ;
- **Variables** (`#/variables`, 5 sections) : Fichiers de la stack, Clé de chiffrement, Chiffrer l'export de Portainer, Exports chiffrés, Variables de la stack (+ téléchargement de `services.yaml`) ;
- **Sauvegardes** (`#/sauvegardes`) : réglages de chaque appli et ce qui a changé ;
- **Carte de la maison** (`#/carte`).

Choix :
1. **Un seul écran Réglages**, qui regroupe les quatre pages.
2. **Accueil en 5 tuiles par thème**, chacune avec son **état + un chiffre clé** et une **pastille** (or = à faire, bleu = action, rouge lave = en panne, comme sur l'anneau) :
   - **Services** — fichier des services (import **et** téléchargement), versions, bac à sable ;
   - **Stack & variables** — `homelab.yml`, variables de la stack, clé de chiffrement, chiffrer, exports chiffrés ;
   - **Sauvegardes** — collecte (heure, maintenant, dernière), liste des sauvegardes et différences, restaurer les réglages de l'Anneau ;
   - **Connexions** — Portainer, GitHub, Watchtower, **Home Assistant** (état reçu, veille, nouveau webhook de réveil) ;
   - **Maison** — carte pleine largeur en haut, puis disques et dernières pannes closes.
3. **Clic sur une tuile = sous-page** `#/reglages/<thème>` (`services`, `stack`, `sauvegardes`, `connexions`, `maison`), avec « ← Réglages », « Revenir à l'anneau » **et une barre des 5 thèmes** pour passer de l'un à l'autre.
4. **Un seul endroit par chose** : plus de renvois croisés ni de résumés en double.
5. **Anciennes adresses redirigées** : `#/variables` → `#/reglages/stack`, `#/sauvegardes` → `#/reglages/sauvegardes`, `#/carte` → `#/reglages/maison` (favoris, tuile « À traiter » `export-variables`, lien « Ouvrir cette page en https »).
6. **Avertissement HTTPS** dans le thème Stack & variables (avec le lien « Ouvrir en https ») ; en http, la tuile affiche « https requis pour chiffrer ».

### B. Écarts de l'audit
7. **Lecture seule** (`MAISON_LECTURE_SEULE`, `ANNEAU_LECTURE_SEULE`) : l'Anneau bloque **tout ce qui écrit chez une autre appli ou un autre service** ; ce qui n'écrit que dans ses propres fichiers reste permis (import de `services.yaml` et `homelab.yml`, collecte, heure, clé publique, exports rangés, restauration de ses propres réglages) — même règle que le socle.
8. **« Secrets en HTTPS seulement » vérifié par le serveur** : en http, le serveur **refuse (403, message clair « ouvre l'Anneau en https »)** l'**écriture** de la clé publique et le rangement d'un export ; la lecture et le téléchargement des exports chiffrés restent permis (arbitrage après le conseil ; previously : lecture bloquée aussi).

### C. Réveil du PC de calcul
9. **Chemin** : l'Anneau appelle un **webhook Home Assistant** ; HA envoie le paquet Wake-on-LAN. Aucun jeton HA dans l'Anneau.
10. **Boutons** : dans la fiche « État » de la tuile existante **« Pc de calcul »** (famille Machines) et dans la fiche de **Millésime**, **seulement quand le PC est éteint**.
11. **Réveiller seulement** (pas d'extinction), avec fenêtre de confirmation, puis suivi jusqu'à « répond ».
12. **Voyant** : la **sonde existante** de la tuile (`http://192.0.2.12:3003/ping`, `arret_attendu: true`) ; rien de nouveau côté état. `sensor.millesime_pc` reste pour les rappels HA.
13. **Lecture seule** : bouton bloqué (ordre envoyé à un autre service).
14. **Secret** : identifiant du webhook dans une **variable de stack** `ANNEAU_HA_WEBHOOK_REVEIL` (jamais dans une note) ; fiche « Home Assistant » du thème Connexions.

## 2. Contexte

- Faits lus dans le code (0.18.4) :
  - `_lecture_seule()` = `maison.lecture_seule("ANNEAU_LECTURE_SEULE")`, qui retombe sur `MAISON_LECTURE_SEULE`. Elle protège **déjà** les gestes sur les conteneurs (Portainer) et les mises à jour (Watchtower) — les seuls gestes qui écrivent ailleurs aujourd'hui. « Restaurer » de l'Anneau ne restaure que **ses propres** réglages (chaque appli tire sa copie elle-même) : rien à bloquer. L'écart 1 se réduit donc à : appliquer la règle au **réveil du PC**, l'**afficher** dans les Réglages, et l'**écrire dans des tests** (aucun test ne parcourt aujourd'hui toutes les routes d'écriture).
  - `en_https(request)` existe (`app/auth.py`) mais n'est utilisé que pour l'attribut `Secure` des cookies. `PUT /api/cle-publique`, `POST /api/variables-chiffrees` et `GET /api/variables-chiffrees[/{nom}]` ne le vérifient pas : seul le navigateur (`isSecureContext`) bloque. C'est l'écart 2.
  - Routes d'écriture : `/api/conteneurs/{cle}/{geste}`, `/api/majs/…`, `/api/recharger`, `/api/services/importer`, `/api/reglages`, `/api/cle-publique`, `/api/sauvegardes`, `/api/restaurer`, `/api/variables-chiffrees`, `/api/stack`, `/api/carte/relire`, `/api/…/vu(es)`.
- HA : paquet `systeme/anneau.yaml` (HA pousse l'état des machines vers `/api/ha/etat` avec `X-Anneau-Secret`) ; paquet `systeme/millesime.yaml` (`sensor.millesime_pc`, rappel « PC à allumer ») marqué « à installer ». **Aucune entité Wake-on-LAN** aujourd'hui.
- PC de calcul : Windows, hors Tailscale, pare-feu limité à le réseau local. Le Wake-on-LAN demande un réglage du BIOS et de la carte réseau Windows, et l'adresse MAC (à fournir par Julien, à ranger dans `secrets.yaml` de HA, jamais dans une note).
- Pages actuelles : `Reglages.svelte` (363 lignes), `Variables.svelte` (317), `Sauvegardes.svelte` (136), `Carte.svelte` (74) ; routeur à plat dans `App.svelte` (`PAGES`).

## 3. Technique

### Écran (A)
- `App.svelte` : routeur `#/reglages` et `#/reglages/<thème>` ; table de redirections des anciennes adresses (`location.replace`, pas d'entrée d'historique en plus).
- Découpage en composants (sans changer la logique métier ni les routes) :
  - `pages/Reglages.svelte` → accueil (grille bento de 5 tuiles) + cadre commun des sous-pages (fil, barre de thèmes, « Revenir à l'anneau ») ;
  - `lib/reglages/Services.svelte`, `Stack.svelte` (reprend `Variables.svelte`), `Sauvegardes.svelte` (fusion de la section Sauvegarde/Restaurer et de la page Sauvegardes), `Connexions.svelte`, `Maison.svelte` (reprend `Carte.svelte` + Disques + Pannes closes) ;
  - `lib/reglages/resume.js` : calcul **pur** de l'état/chiffre/pastille de chaque tuile à partir de ce que l'écran lit déjà (`/api/etat`, `/api/sauvegardes`, `/api/stack`, `/api/connexions`, `/api/carte`), testable seul.
- Une seule lecture par thème, à l'ouverture de sa sous-page ; l'accueil lit le minimum pour les tuiles (pas de nouvelle route : si une route manque pour un chiffre, la tuile dit « — » plutôt que d'ajouter une route).
- Pastilles : Services (lignes écartées → rouge ; versions en retard → bleu) ; Stack (http → « https requis pour chiffrer » ; export de plus de 30 j → or) ; Sauvegardes (dernière ratée ou applis non lues → or) ; Connexions (fiche en échec → rouge ; HA muet → rouge) ; Maison (disque ≥ 99,8 % → rouge ; carte en erreur → or).
- Sur iPhone : tuiles en une colonne, barre des thèmes défilante en haut ; sur PC : grille 3 + 2.
- `pages/Variables.svelte`, `pages/Sauvegardes.svelte`, `pages/Carte.svelte` retirés.

### Écarts (B)
- `app/main.py` : garde commune `_exiger_https(request)` → `HTTPException(403, "Les secrets ne passent qu'en https : ouvre l'Anneau par son adresse https.")` sur `PUT /api/cle-publique`, `POST/GET /api/variables-chiffrees[/{nom}]`. Lecture de `en_https` derrière Tailscale Serve (en-tête `X-Forwarded-Proto`) : même fonction que pour les cookies.
- Lecture seule : garde commune `_exiger_ecriture()` appliquée à toute route qui écrit ailleurs (conteneurs, majs, réveil) ; la vue `/api/etat` rend déjà `lecture_seule` → bandeau « lecture seule » dans l'accueil des Réglages et boutons grisés avec la raison.
- Test « table des routes » : chaque route POST/PUT/DELETE est classée (ailleurs / chez soi / secret) ; un test échoue si une route nouvelle n'est pas classée.

### Réveil (C)
- Variable `ANNEAU_HA_WEBHOOK_REVEIL` (identifiant du webhook, vide = pas de bouton) ; adresse de HA reprise de la variable existante de l'Anneau pour HA si elle existe, sinon `ANNEAU_HA_URL` (à vérifier au code : aujourd'hui HA pousse, l'Anneau ne l'appelle pas).
- Champ de tuile `reveil: true` sur « Pc de calcul » (note « Tuiles de l'Anneau ») ; la fiche de Millésime montre le bouton si la tuile `reveil` est éteinte (lien par `machine:` ou champ `besoin: Pc de calcul` à trancher au code, sans nouvelle règle pour Julien).
- Route `POST /api/reveil/{cle}` : session, `Origin`, lecture seule, tuile marquée `reveil`, tuile actuellement éteinte ; appel `POST <HA>/api/webhook/<id>` (sans corps) ; anti-rebond 60 s ; journal des écritures.
- Suivi : ronde pressée (5 s) pendant 3 min ; fin = sonde « répond » ; sinon « pas réveillé après 3 min : vérifier le Wake-on-LAN ».
- Fiche Connexions › Home Assistant › « Vérifier » : **ne déclenche jamais le webhook** ; vérifie la variable et que HA répond (`GET /api/` → 401 attendu = joignable).
- HA (coffre `2 Home Assistant`) : paquet `systeme/reveil_pc.yaml` — intégration `wake_on_lan`, automatisation déclenchée par le webhook (`local_only: true`, méthode POST) → `wake_on_lan.send_magic_packet` (MAC dans `secrets.yaml`) ; notification si le PC ne répond pas 3 min après.

## 4. Écrans

- **Accueil Réglages** : titre « Réglages », bandeau « lecture seule » si actif, 5 tuiles (nom, icône du thème, phrase d'état, chiffre clé, pastille). Exemples : « Services · 40 services, 6 familles · 2 versions à installer » ; « Stack & variables · 28 services, 63 variables · https requis pour chiffrer » ; « Sauvegardes · cette nuit 03:30, 12 applis lues » ; « Connexions · 4 sur 4 répondent » ; « Maison · Synology 61 % · aucune panne ».
- **Sous-page** : fil « L'Anneau › Réglages › Stack & variables », barre des 5 thèmes (le thème courant en or), « Revenir à l'anneau » ; sections du thème dans l'ordre ci-dessus.
- **Tuile Pc de calcul / fiche Millésime** : « Éteint » + bouton « Réveiller le PC » → fenêtre « Réveiller le PC de calcul ? Home Assistant envoie le signal ; il répond d'habitude en une minute. » → « Réveil en cours… » → « répond ».
- Charte : celle du socle (sombre par défaut, or réservé à l'Anneau, plume fine pour les titres).

## 5. Données

- Aucune nouvelle donnée côté écran. Journal des écritures : entrée `reveil` (tuile, quand, résultat).
- Nouvelle variable de stack : `ANNEAU_HA_WEBHOOK_REVEIL` (+ `ANNEAU_HA_URL` si absente). Nouveau champ de tuile : `reveil: true`.
- HA : `secrets.yaml` (`pc_calcul_mac`, `reveil_pc_webhook`), paquet `reveil_pc.yaml`.

## 6. Plan (étapes livrables et testées)

1. **0.19.0-a — Écran** : routeur, redirections, accueil en tuiles, 5 sous-pages, `resume.js` + tests ; tests d'écran (PC et iPhone) : chaque ancienne adresse arrive au bon thème, rien en double, la barre de thèmes marche, aucun lien vers une page retirée.
2. **0.19.0-b — Écarts** : `_exiger_https`, `_exiger_ecriture`, table des routes classées ; tests http/https et lecture seule.
3. **0.19.0-c — Réveil** : route, suivi, boutons, fiche HA ; faux HA (webhook) dans les tests ; paquet HA dans le coffre.
4. **Coffre** : note de version, Tuiles (`reveil: true`), Variables de la stack, `homelab yml` en entier, flux « L'Anneau → Home Assistant (réveil) », paquet HA, journal `HA — 11.`, Plan de tests.
5. **Gestes de Julien** : BIOS + Windows (Wake-on-LAN), MAC dans `secrets.yaml`, installer le paquet, variable dans Portainer, redéployer.

**Jamais essayé sur la vraie installation** (tout ce dossier) : l'en-tête `X-Forwarded-Proto` réellement envoyé par Tailscale Serve ; le paquet magique depuis HA OS vers le PC (même réseau le réseau local) ; le PC qui se réveille depuis l'état « arrêté » (Windows « démarrage rapide » le bloque souvent) ; la durée réelle du réveil.

## Après le conseil (26/11/2026)
Voir `anneau-0.19.0-conseil.md` : une seule version gardée par Julien, lecture des exports libre en http, pastilles gardées, raccourci « Maison » depuis l'anneau ; étape zéro sur les en-têtes de Tailscale Serve, variable de secours de la garde https, réveil annoncé « fonctionne » seulement après un essai manuel dans HA.

## Questions ouvertes pour le Conseil (posées)
- Un écran en tuiles ajoute un clic par rapport à l'ancienne page Réglages : la barre de thèmes suffit-elle ?
- Bloquer aussi la **lecture** des exports chiffrés en http (choix de Julien) : risque de se priver d'un export en dépannage ?
- Le webhook HA (identifiant seul, `local_only`) est-il un secret assez solide pour un geste physique (allumer une machine) ?
- Trois chantiers dans une version : faut-il livrer en trois versions (0.19.0, 0.19.1, 0.20.0) ?

↑ [[L'Anneau]]
