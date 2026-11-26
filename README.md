# L'Anneau

Une seule porte pour les machines, les services et les applis de la maison : un anneau porte les familles de services, dit ce qui est en panne et ce qui est à faire, et ouvre n'importe quel service d'un geste.

Depuis la 0.1 : **la vue**. L'Anneau lit (une demande par service, chaque minute) et reçoit (Home Assistant lui envoie l'état des machines). Il n'écrit nulle part hors de son dossier et ne détient aucun jeton d'un autre service, hors le jeton commun des applis maison et, pour Atlas, un jeton GitHub en lecture seule.

Depuis la 0.17 : **allumer, éteindre et mettre à jour** les seuls conteneurs marqués `conteneur:` dans `services.yaml`, par la clé d'API d'un utilisateur Portainer dédié (voir plus bas) ; c'est sa seule écriture hors de son dossier.

Depuis la 0.8 : **la sauvegarde des réglages** des applis maison (voir plus bas).

## Mise en place

1. Ajouter le service de [`docker-compose.yml`](docker-compose.yml) à la stack, avec les variables de [`.env.example`](.env.example).
2. Écrire `services.yaml` sur le modèle de [`app/services.exemple.yaml`](app/services.exemple.yaml) : familles, machines, services (adresse locale, adresse du réseau privé, icône ; `cadre: false` pour un service qui doit toujours s'ouvrir à côté ; `depot:` et `version_url:` pour les versions, voir plus bas). Sans ce fichier, l'Anneau montre l'exemple.
3. Ouvrir `http://<NAS>:8094`, se connecter avec le mot de passe commun, puis Réglages › Services › « Importer un fichier » (ou poser le fichier dans le dossier de données, puis « Relire le fichier »).

## Variables

| Variable | Rôle |
|---|---|
| `MAISON_PASSWORD` | mot de passe commun, obligatoire (12 caractères au moins). `ANNEAU_PASSWORD` n'est plus lu depuis la 0.8. |
| `MAISON_JETON` | jeton commun des applis maison : annuaire, collecte et portes des sauvegardes. Vide : portes fermées. |
| `ANNEAU_SECRET_HA` | secret joint par Home Assistant à ses envois. |
| `ANNEAU_ATLAS_DEPOT`, `ANNEAU_GITHUB_JETON` | Atlas relu chaque jour depuis sa publication GitHub. |
| `ANNEAU_PORTAINER_URL` | 0.17 : adresse de Portainer. Vide : pas de boutons Allumer / Éteindre / Mettre à jour. |
| `ANNEAU_PORTAINER_CLE` | 0.17 : clé d'API d'un utilisateur Portainer standard « anneau » (en-tête `X-API-Key`). Jamais écrite dans un journal, une page ni la sauvegarde. |
| `ANNEAU_PORTAINER_ENV` | 0.17 : numéro de l'environnement Docker dans Portainer. Vide : le premier environnement Docker local (`Type` 1) de `GET /api/endpoints`. |
| `ANNEAU_LECTURE_SEULE` / `MAISON_LECTURE_SEULE` | « oui » : aucun ordre à un autre service — Portainer, Watchtower, Home Assistant (boutons grisés, routes 403, bandeau dans Réglages). Ce que l'Anneau écrit dans son propre dossier reste permis. |
| `ANNEAU_HA_URL` | 0.19 : adresse de Home Assistant vue depuis la stack (`http://<HA>:8123`). Vide : pas de bouton « Réveiller ». |
| `ANNEAU_HA_WEBHOOK_REVEIL` | 0.19 : identifiant du webhook de réveil du PC dans Home Assistant (long, aléatoire). Jamais affiché, écrit au journal ni sauvegardé. |
| `ANNEAU_GARDE_HTTPS` | 0.19 : « non » coupe la garde https des secrets (dépannage quand Tailscale est en panne). Vide : garde active. |

Les réglages d'usage (heure de la collecte, clé publique de l'export chiffré) se changent dans Réglages › Sauvegardes et Réglages › Stack et variables, et sont gardés dans `reglages.json`.

## Réglages en cinq thèmes (0.19)

Un seul écran Réglages (la roue, en haut à droite de l'anneau). L'accueil montre cinq thèmes, chacun avec son état, un chiffre et, s'il y a lieu, une pastille avec un texte (rouge lave : en panne ; bleu : à faire ; or : à traiter) :

| Thème | Adresse | Contenu |
|---|---|---|
| Services | `#/reglages/services` | fichier des services (importer, relire, télécharger `services.yaml`), versions des tuiles, bac à sable |
| Stack et variables | `#/reglages/stack` | `homelab.yml`, clé de chiffrement, chiffrer l'export de Portainer, exports chiffrés, variables de la stack |
| Sauvegardes | `#/reglages/sauvegardes` | collecte de nuit (heure, « Sauvegarder maintenant », dernière collecte), sauvegardes gardées et ce qui a changé, restaurer les réglages de l'Anneau |
| Connexions | `#/reglages/connexions` | fiches Portainer, Watchtower, GitHub, Home Assistant ; ce que Home Assistant envoie |
| Maison | `#/reglages/maison` | carte de la maison (pleine largeur), disques, dernières pannes closes ; raccourci « Maison » à côté de la roue |

**Stack et variables (0.20)** : le homelab s'importe en fichier ou se colle (bloc Markdown retiré, même vérification) ; sous les valeurs ouvertes (export chiffré ouvert ou export de Portainer collé), « Variables à coller dans Portainer » puis « Homelab avec ses valeurs » (règles de Docker Compose, commentaires intacts, masqué jusqu'à « Afficher », jamais envoyé au serveur).

Dans un thème : le fil, la barre des cinq thèmes (le thème ouvert souligné) et « Revenir à l'anneau ». Une section se vise par un troisième morceau (`#/reglages/stack/exports`, utilisé par la tuile « À traiter »). Les anciennes adresses mènent au bon thème : `#/variables` → Stack et variables, `#/sauvegardes` → Sauvegardes (liste), `#/carte` → Maison.

**Secrets en https, vérifié par le serveur** : `PUT /api/cle-publique` et `POST /api/variables-chiffrees` répondent 403 quand la page n'est pas sûre. Sûre = servie en https, `X-Forwarded-Proto: https` (Tailscale Serve), en-tête `Origin` en `https://` (envoyé par le navigateur à chaque écriture), ou ouverte sur la machine même (`localhost`, `127.0.0.1`, `[::1]`, comme pour le navigateur). Lire et télécharger un export chiffré restent permis en http. `GET /api/https` dit ce que voit le serveur (`https`, `par`, `garde`, `relais`, `lecture_seule`), affiché en haut de Stack et variables. `ANNEAU_GARDE_HTTPS=non` coupe la garde.

## Réveiller le PC de calcul (0.19)

- La tuile marquée `reveil: true` (aujourd'hui « Pc de calcul ») a, quand elle est éteinte, un bouton « Réveiller » dans sa fiche ; une appli marquée `besoin: <nom de cette tuile>` (Millésime) le montre aussi dans sa fiche « État ». Un `besoin:` qui ne désigne aucune tuile `reveil: true` est signalé et ignoré.
- `POST /api/reveil/{tuile}` (session ; en-tête `Origin` de l'Anneau ; jamais en lecture seule ; seulement si la tuile est éteinte ; corps ignoré) appelle `POST {ANNEAU_HA_URL}/api/webhook/{ANNEAU_HA_WEBHOOK_REVEIL}` sans corps. Home Assistant envoie le paquet Wake-on-LAN. L'Anneau n'a aucun jeton de Home Assistant.
- Suivi par la sonde habituelle de la tuile (ronde pressée à 5 s) : « Réveillé : il répond. », ou au-delà de 3 min « Pas réveillé : vérifie le Wake-on-LAN… ». Après un réveil raté, un nouvel ordre attend 1 min.
- Réglages › Connexions › Home Assistant › « Vérifier » : `GET {ANNEAU_HA_URL}/api/` (401 attendu = Home Assistant répond). **N'appelle jamais le webhook.**
- Chaque ordre (refusé, lancé, fini, perdu) va au journal des écritures (`quoi: reveil`).
- Côté Home Assistant : paquet `ha/packages/systeme/reveil_pc.yaml` (intégration `wake_on_lan`, webhook `local_only`, secrets `pc_calcul_mac` et `reveil_pc_webhook`), à recopier dans `/config/packages/systeme/`. Prérequis : Wake-on-LAN dans le BIOS et la carte réseau du PC, démarrage rapide de Windows désactivé ; essayer d'abord à la main (`wake_on_lan.send_magic_packet`).

## Sauvegarde des réglages (0.8)

Chaque jour à l'heure réglée (03:30 par défaut), ou par « Sauvegarder maintenant », l'Anneau demande à chaque appli maison de `services.yaml` — une tuile dont la `sonde` finit par `/health`, sauf `sauvegarde: false` — ses réglages : `GET <sonde sans /health>/externe/sauvegarde` avec `Authorization: Bearer <MAISON_JETON>`, 10 s au plus. Une réponse sans `contrat == 1`, ou qui porte une clé qui ressemble à un secret, est refusée.

- Sauvegarde automatique : `sauvegardes/AAAA-MM-JJ.json` (`contrat`, `le`, `applis`, `ratees`) ; 30 dernières, plus la première de chaque trimestre pour les 3 derniers trimestres (depuis 0.9.1).
- « Sauvegarder maintenant » : `sauvegardes/AAAA-MM-JJ-HHMMSS-manuelle.json`, même contenu ; 5 dernières gardées, et jamais de remplacement de l'automatique (depuis 0.9).
- Tuile « Sauvegarde ratée » (rang « À traiter », en or) : dernière collecte avec des ratées, fichier non écrit, ou rien de réussi depuis 36 h. Rien n'est envoyé à Home Assistant.
- Pour « Restaurer » dans chaque appli (jeton commun) : `GET /externe/sauvegardes/{appli}` → `{"dates": [...]}` ; `?le=AAAA-MM-JJ` → `{"le", "version", "reglages"}`.
- Pour Atlas (même origine, session) : `GET /api/sauvegardes`, `GET /api/sauvegardes/{date}`, `GET/PUT /api/cle-publique`, `POST /api/variables-chiffrees` (seulement un fichier chiffré par age, 1 Mo au plus ; rangé dans `sauvegardes/variables/`, 30 gardés), `GET /api/variables-chiffrees[/{nom}]`.
- L'Anneau rend aussi sa propre sauvegarde (`GET /externe/sauvegarde`, sans la clé publique) et restaure ses réglages depuis Réglages › Sauvegardes › Restaurer.

Le dossier de l'Anneau, et donc `sauvegardes/`, part avec Hyper Backup.

## Santé des tâches de fond (0.12)

La veille lit la réponse JSON de chaque sonde `/health`. Une appli maison à jour (socle 0.9.0) y ajoute `version_socle`, `taches` et `copie_base` ; une appli sans ces champs ne change rien.

- Le jeton commun (`Authorization: Bearer <MAISON_JETON>`, pour avoir les messages d'erreur) ne part qu'avec la sonde des tuiles `sauvegarde: true` dont la sonde finit par `/health`, jamais ailleurs.
- Tuile **« à surveiller »** (orange braise, jamais « en panne ») : une tâche régulière `en_retard` ou `bloquee`, ou une copie des bases `ok: false` ou de plus de 36 h (`le` vide : neutre, la tâche `copie-des-bases` le dira). Phrase écrite sur la pastille de la tuile et dans le rang « À surveiller » (sur l'anneau, « à surveiller » au-dessus du nom). Une tâche à la demande ne rend jamais orange : sa dernière erreur se lit dans la fiche.
- Fiche « État » (bouton de la vue réduite, ou « Voir » du rang) : chaque tâche, la dernière copie, la version du socle. Bouton **« Vu »** (`POST /api/sante/vu`, session) : l'empreinte des défauts est gardée dans `vus.json` ; la tuile n'est plus orange tant qu'elle ne change pas (petit signe « vu »), et le « vu » est oublié dès que la tuile n'a plus de défaut ou que ses défauts changent.
- L'Anneau se surveille : sans boucle de veille finie depuis 10 min, bandeau orange « La veille de l'Anneau est arrêtée depuis … » (calculé par le serveur, et par le navigateur si l'API ne répond plus).
- `/health` de l'Anneau : `version_socle`, `taches` (`veille`, `collecte-de-nuit`, `relecture-de-la-carte`, registre `maison.TACHES` ; messages seulement avec le jeton commun ou une session), `copie_base: null` (pas de base SQLite). Un seul worker uvicorn (registre en mémoire).

## Versions et nouveautés de la nuit (0.13)

Watchtower met à jour tous les conteneurs chaque nuit à 05:00. L'Anneau dit, pour chaque tuile, la version en service et la dernière publiée, et montre à l'ouverture ce qui a changé depuis la dernière visite.

Deux champs facultatifs de tuile dans `services.yaml` :

| Champ | Rôle |
|---|---|
| `depot:` | nom du dépôt GitHub de l'appli sous `baloodusudouest` (ex. `depot: carnet`, `depot: Millesime` ; lettres, chiffres, `.`, `-`, `_`). La tâche **`versions-publiees`** (chaque heure) lit `https://api.github.com/repos/baloodusudouest/<depot>/tags?per_page=100`, sans jeton (en-tête `User-Agent`), et garde la plus haute étiquette `v<majeur>.<mineur>.<correctif>` (les autres sont ignorées). |
| `version_url:` | tuile tierce : adresse lue par la veille, sans jeton, qui rend la version en service. `{"major": 3, "minor": 1, "patch": 4}` (Immich : `http://<NAS>:2283/api/server/version`) donne « 3.1.4 » ; `{"version": "…"}` marche aussi. |

```yaml
  - { nom: Carnet, famille: Proches, locale: "http://192.0.2.10:8096", sonde: "http://192.0.2.10:8096/health", sauvegarde: true, depot: carnet }
  - { nom: Photos, famille: Photos, locale: "http://192.0.2.10:2283", version_url: "http://192.0.2.10:2283/api/server/version" }
```

- **Version en service** : champ `version` du `/health` (applis maison), ou `version_url:`. Une lecture sans version ne change rien (la dernière connue reste, `versions-en-service.json`).
- **Dernière publiée** : gardée dans `versions.json`. GitHub injoignable ou limite atteinte (403/429) : l'ancienne lecture reste ; seule la tâche `versions-publiees` passe en erreur (dans le `/health` de l'Anneau), rien d'autre à l'écran.
- **Fiche de la tuile** (bouton « État ») : « Version 0.12.0 — dernière publiée 0.12.0 (à jour) » ou « … dernière publiée 0.13.0 : pas encore en service ». **Jamais d'orange** pour un retard.
- **Réglages › Services › Versions** : tableau tuile, en service, dernière publiée, mise à jour le (`GET /api/versions`, session).
- **Journal** : quand la veille voit la version d'une tuile changer, elle l'ajoute à `journal-versions.json` (tuile, de, vers, le ; 200 entrées au plus).
- **Fenêtre « Mis à jour depuis votre dernière visite »** : à l'ouverture de l'Anneau après une connexion (ou au premier chargement avec une session valide), s'il y a des changements depuis le dernier « Vu » : « Carnet 2.32.0 → 2.33.0 (cette nuit, 05:04) ». Plusieurs changements d'une même tuile font une ligne. « Vu » enregistre l'heure dans `versions-vues.json` (une pour l'Anneau, pas par navigateur). Routes (session) : `GET /api/versions/nouveautes` → `{"vu_le", "changements": [{"tuile", "cle", "de", "vers", "le"}]}`, `POST /api/versions/vues` (`{"jusqu_a": <le du plus récent montré>}`, facultatif).

## Allumer, éteindre, mettre à jour un conteneur (0.17)

Pour ne pas laisser tourner une appli qui sert peu (le Bac à sable…), et pour la mettre à jour sans attendre Watchtower.

- **Liste blanche** : seules les tuiles marquées `conteneur: <container_name>` dans `services.yaml` ont ces boutons. Format vérifié à la lecture (lettres, chiffres, `_`, `.`, `-`) ; un même conteneur sur deux tuiles : le second est ignoré.
- **Interdits** (insensible à la casse, sur le champ ET sur le nom réel rendu par Portainer) : `anneau`, `immich*`, `portainer`, `watchtower`, `coffre-git`, `silverbullet*`.
- **Étiquette** `com.docker.compose.project=homelab` exigée sur le conteneur.
- **Routes** (session de l'Anneau ; en-tête `Origin` exactement égal à l'adresse de l'Anneau — hôte de la requête, ou locale/privée d'une tuile `anneau` ; jamais en lecture seule) : `POST /api/conteneurs/{tuile}/{allumer|eteindre|mettre-a-jour|allumer-et-mettre-a-jour}` (le corps est ignoré : le nom vient de `services.yaml`), `GET /api/conteneurs/{tuile}/stats`, `GET /api/conteneurs/journal`.
- **Portainer** (allumer, éteindre, lire) : `GET /api/endpoints`, `GET /api/endpoints/{env}/docker/containers/{nom}/json`, `…/stop`, `…/start`, `…/stats?stream=false`, `GET …/docker/images/{id}/json` (date de l'image). Un 403 sur stop/start : « Portainer refuse : vérifier l'accès de l'équipe « anneau » à la stack ».
- **Watchtower** (mettre à jour, 0.17.1 ; dans Portainer CE, un réglage « Hide … for non-administrators » interdit la recréation aux non-admins) : `POST {ANNEAU_WATCHTOWER_URL}/v1/update?image=<dépôt/image sans étiquette>`, en-tête `Authorization: Bearer <ANNEAU_WATCHTOWER_JETON>`, envoyé dans une tâche de fond (la réponse arrive quand Watchtower a fini ; la demande attend son verrou si la mise à jour de 05:00 tourne). Watchtower ne met à jour que les conteneurs **en marche** de cette image (« Allumer et mettre à jour » allume donc d'abord par Portainer). Pas de bouton sans Watchtower relié, ni pour un conteneur étiqueté `com.centurylinklabs.watchtower.enable=false` (la fiche dit pourquoi). 401/403 : « jeton refusé par Watchtower » ; injoignable : « Watchtower ne répond pas », rien ne change.
- **Suivi** : la réponse d'un ordre ne dit pas le résultat ; la veille relit l'état (toutes les 5 s pendant 5 min après un ordre) : fini quand le conteneur tourne et que sa sonde répond (allumer, mettre à jour) ou qu'il est `exited` (éteindre) ; au-delà de 10 min : « pas de réponse, voir Portainer » (15 min pour une mise à jour : « voir Watchtower et Portainer »). Une mise à jour sans nouvelle empreinte d'image n'est dite « déjà à jour » qu'après la réponse de Watchtower. Ordre en cours gardé dans `conteneurs.json` (survit à un redémarrage).
- **Écran** : tuile grise « éteint » (« Ouvrir » remplacé par « Allumer » et « Allumer et mettre à jour », âge de l'image), « démarrage… », « mise à jour en cours… », puis « déjà à jour » ou « image du 20/11 → 21/11 ». Fiche « Conteneur » (fiche de la tuile, ou bouton « État » quand l'appli est dans le cadre) : mémoire et processeur, avertissement si redémarrage `always`, rappel « un redéploiement de la stack le rallume ». Confirmation avant Éteindre et Mettre à jour.
- **Panne et sauvegarde** : un conteneur `exited` n'est jamais « en panne », et n'est pas demandé à la collecte de la nuit (« éteinte, pas sauvegardée cette nuit », pas de « Sauvegarde ratée »).
- **Journal des écritures** : `journal-ecritures.jsonl` (une ligne JSON par ordre refusé, lancé, fini : `quand`, `quoi`, `tuile`, `resultat`, `conteneur`).
- **Réglages › Connexions** : fiches Portainer, Watchtower, GitHub et Home Assistant (0.19) (ce que l'Anneau y lit et y écrit, « Vérifier »). « Vérifier » Watchtower n'envoie jamais `/v1/update` : `GET /v1/containers` puis `/v1/metrics` (s'ils sont activés, le jeton est vérifié), sinon « adresse et jeton présents ».

## Home Assistant (facultatif)

Avec `ANNEAU_SECRET_HA`, Home Assistant peut envoyer chaque minute l'état des machines :

```
POST /api/ha/etat        en-tête X-Anneau-Secret: <le secret>
{"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": 97.1, "etat": "attention"}],
 "mises_a_jour": [{"machine": "Grand NAS", "disponible": true, "version": "8.1"}]}
```

La réponse dit quoi notifier : `{"pannes": 1, "ouvertes": ["…"], "closes": ["…"], "liste": ["…"]}`. Chaque ouverture et chaque clôture n'est donnée qu'une fois.

## Développement

```
pip install -r requirements-dev.txt && python -m pytest -q tests --ignore=tests/interface
cd frontend && npm ci && npx vite build
python -m tests.interface.serveur /tmp/anneau 8094      # Anneau de démonstration, mot de passe « essai-essai-essai »
```

À lire avant de toucher au code : [`REPRISE.md`](REPRISE.md), puis [`docs/dossier.md`](docs/dossier.md).

## Images privées (0.18.2)

Dîme est publiée en image privée sur ghcr.io. Pour la vérifier et la mettre à jour :
- l'Anneau lit `ANNEAU_GHCR_JETON` (jeton GitHub classic, droit `read:packages` ; compte `ANNEAU_GHCR_UTILISATEUR`, `baloodusudouest` par défaut). Il ne l'envoie qu'au service de jetons de ghcr.io, jamais à un autre registre, et ne l'écrit nulle part ;
- Watchtower lit `/config/config.json` (`DOCKER_CONFIG=/config`, dossier `${DOCKER_ROOT}/watchtower` en lecture seule) : `{"auths": {"ghcr.io": {"auth": "<base64 de baloodusudouest:JETON>"}}}`. Un dossier plutôt qu'un fichier monté : un fichier remplacé (nouveau jeton) ne serait pas relu.

