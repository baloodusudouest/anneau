# L'Anneau

Une seule porte pour les machines, les services et les applis de la maison : un anneau porte les familles de services, dit ce qui est en panne et ce qui est à faire, et ouvre n'importe quel service d'un geste.

Depuis la 0.1 : **la vue**. L'Anneau lit (une demande par service, chaque minute) et reçoit (Home Assistant lui envoie l'état des machines). Il n'écrit nulle part hors de son dossier et ne détient aucun jeton d'un autre service, hors le jeton commun des applis maison et, pour Atlas, un jeton GitHub en lecture seule.

Depuis la 0.8 : **la sauvegarde des réglages** des applis maison (voir plus bas).

## Mise en place

1. Ajouter le service de [`docker-compose.yml`](docker-compose.yml) à la stack, avec les variables de [`.env.example`](.env.example).
2. Écrire `services.yaml` sur le modèle de [`app/services.exemple.yaml`](app/services.exemple.yaml) : familles, machines, services (adresse locale, adresse du réseau privé, icône ; `cadre: false` pour un service qui doit toujours s'ouvrir à côté ; `depot:` et `version_url:` pour les versions, voir plus bas). Sans ce fichier, l'Anneau montre l'exemple.
3. Ouvrir `http://<NAS>:8094`, se connecter avec le mot de passe commun, puis Réglages › « Importer un fichier » (ou poser le fichier dans le dossier de données, puis « Recharger le fichier »).

## Variables

| Variable | Rôle |
|---|---|
| `MAISON_PASSWORD` | mot de passe commun, obligatoire (12 caractères au moins). `ANNEAU_PASSWORD` n'est plus lu depuis la 0.8. |
| `MAISON_JETON` | jeton commun des applis maison : annuaire, collecte et portes des sauvegardes. Vide : portes fermées. |
| `ANNEAU_SECRET_HA` | secret joint par Home Assistant à ses envois. |
| `ANNEAU_ATLAS_DEPOT`, `ANNEAU_GITHUB_JETON` | Atlas relu chaque jour depuis sa publication GitHub. |

Les réglages d'usage (heure de la collecte, clé publique de l'export chiffré) se changent dans Réglages › Sauvegarde et sont gardés dans `reglages.json`.

## Sauvegarde des réglages (0.8)

Chaque jour à l'heure réglée (03:30 par défaut), ou par « Sauvegarder maintenant », l'Anneau demande à chaque appli maison de `services.yaml` — une tuile dont la `sonde` finit par `/health`, sauf `sauvegarde: false` — ses réglages : `GET <sonde sans /health>/externe/sauvegarde` avec `Authorization: Bearer <MAISON_JETON>`, 10 s au plus. Une réponse sans `contrat == 1`, ou qui porte une clé qui ressemble à un secret, est refusée.

- Sauvegarde automatique : `sauvegardes/AAAA-MM-JJ.json` (`contrat`, `le`, `applis`, `ratees`) ; 30 dernières, plus la première de chaque trimestre pour les 3 derniers trimestres (depuis 0.9.1).
- « Sauvegarder maintenant » : `sauvegardes/AAAA-MM-JJ-HHMMSS-manuelle.json`, même contenu ; 5 dernières gardées, et jamais de remplacement de l'automatique (depuis 0.9).
- Tuile « Sauvegarde ratée » (rang « À traiter », en or) : dernière collecte avec des ratées, fichier non écrit, ou rien de réussi depuis 36 h. Rien n'est envoyé à Home Assistant.
- Pour « Restaurer » dans chaque appli (jeton commun) : `GET /externe/sauvegardes/{appli}` → `{"dates": [...]}` ; `?le=AAAA-MM-JJ` → `{"le", "version", "reglages"}`.
- Pour Atlas (même origine, session) : `GET /api/sauvegardes`, `GET /api/sauvegardes/{date}`, `GET/PUT /api/cle-publique`, `POST /api/variables-chiffrees` (seulement un fichier chiffré par age, 1 Mo au plus ; rangé dans `sauvegardes/variables/`, 30 gardés), `GET /api/variables-chiffrees[/{nom}]`.
- L'Anneau rend aussi sa propre sauvegarde (`GET /externe/sauvegarde`, sans la clé publique) et restaure ses réglages depuis Réglages › Restaurer.

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
- **Réglages › Versions** : tableau tuile, en service, dernière publiée, mise à jour le (`GET /api/versions`, session).
- **Journal** : quand la veille voit la version d'une tuile changer, elle l'ajoute à `journal-versions.json` (tuile, de, vers, le ; 200 entrées au plus).
- **Fenêtre « Mis à jour depuis votre dernière visite »** : à l'ouverture de l'Anneau après une connexion (ou au premier chargement avec une session valide), s'il y a des changements depuis le dernier « Vu » : « Carnet 2.32.0 → 2.33.0 (cette nuit, 05:04) ». Plusieurs changements d'une même tuile font une ligne. « Vu » enregistre l'heure dans `versions-vues.json` (une pour l'Anneau, pas par navigateur). Routes (session) : `GET /api/versions/nouveautes` → `{"vu_le", "changements": [{"tuile", "cle", "de", "vers", "le"}]}`, `POST /api/versions/vues` (`{"jusqu_a": <le du plus récent montré>}`, facultatif).

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
