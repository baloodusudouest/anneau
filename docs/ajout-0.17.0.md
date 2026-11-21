# L'Anneau 0.17.0 — allumer, éteindre et mettre à jour un conteneur — dossier (21/11/2026)

> Copie du dossier pour le dépôt public (21/11/2026) : seule l'adresse de Portainer est remplacée par un exemple. Le coffre fait foi.

Demande de Julien du 21/11/2026 (10 h 43) : « dans l'Anneau, il faudrait que je puisse activer ou désactiver le Bac à sable pour sauvegarder des ressources », puis « et ajoute du coup la possibilité de mettre à jour aussi ». Cadrage par questions à choix le même jour.

## 1. Besoin et choix de Julien

1. **Éteindre** = arrêter le conteneur pour de bon (aucune mémoire, aucun processeur). **Allumer** le redémarre. Ses données restent sur le disque.
2. **Mettre à jour** = Portainer télécharge la dernière image et recrée ce seul conteneur (comme « Recreate › Pull latest image »). La stack n'est pas redéployée.
3. **Passage par Portainer directement**, avec la clé d'API d'un **utilisateur Portainer dédié** « anneau » (utilisateur standard, accès au seul environnement du Synology). Ce n'est pas la clé admin.
4. **Une liste choisie** : seules les tuiles marquées dans `services.yaml` ont ces boutons (le Bac à sable, et par exemple Transhumance, Scriptorium). Jamais l'Anneau lui-même ni Immich.
5. **Sur la fiche de la tuile**, à côté de « Ouvrir » : « Éteindre » / « Allumer », et « Mettre à jour ». La tuile éteinte apparaît en gris, « éteint ».
6. **Confirmation** avant d'éteindre ou de mettre à jour (« Éteindre Bac à sable ? Ses données restent sur le disque. »). Allumer se fait sans confirmation.
7. **Pendant une mise à jour** : « Mise à jour en cours » sur la tuile. L'Anneau lance, puis surveille ; la tuile repasse au vert avec la nouvelle version quand `/health` répond.

## 2. Contexte

- **Portainer** : http://192.0.2.90:9000 (adresse inventée ici ; la vraie est dans le coffre), hors de la stack `homelab`. Les applis de la stack l'atteignent par l'adresse du NAS (le pare-feu de DSM autorise les plages fixes de la stack). Portainer gère aussi un agent sur le QNAP (hors sujet).
- **Leçon du 13/11/2026** : une mise à jour depuis Home Assistant affichait « An error occurred » alors qu'elle réussissait ; elle dépassait simplement le délai. Il ne faut donc pas se fier à la réponse de l'appel : il faut vérifier l'état réel.
- **Watchtower** met tout à jour chaque nuit à 05:00. Le bouton sert à ne pas attendre.
- **Arrêt attendu** : l'Anneau sait déjà qu'un service « qu'on éteint exprès » n'est jamais « en panne » (`arret_attendu`, PC de calcul). Une tuile éteinte depuis l'Anneau doit suivre la même règle.
- L'Anneau n'a aujourd'hui aucun jeton d'un autre service, sauf `ANNEAU_GITHUB_JETON` (lecture) et `ANNEAU_CLE` (contrat 3 des fiches).

## 3. Technique

- **Nouvelles variables de stack :**
  - `ANNEAU_PORTAINER_URL` (défaut vide = boutons absents ; valeur : `http://<adresse du NAS>:9000`) ;
  - `ANNEAU_PORTAINER_CLE` (clé d'API de l'utilisateur « anneau », en-tête `X-API-Key`) ;
  - `ANNEAU_PORTAINER_ENV` (numéro de l'environnement du Synology dans Portainer ; vide = le premier environnement Docker local trouvé).
- **Marquage dans `services.yaml`** : `conteneur: bac-a-sable` (le `container_name` de la stack) sur la tuile. Sans ce champ, pas de bouton. Les tuiles de l'Anneau et d'Immich sont refusées même marquées : liste d'interdits dans le code (`anneau`, `immich_server`, `immich_postgres`, `immich_redis`, `immich_machine_learning`, `portainer`, `watchtower`, `coffre-git`, `silverbullet-*`).
- **Appels Portainer** (API Docker relayée) :
  - état : `GET /api/endpoints/{env}/docker/containers/{nom}/json` ;
  - arrêt : `POST …/containers/{nom}/stop` ;
  - démarrage : `POST …/containers/{nom}/start` ;
  - mise à jour : `POST /api/docker/{env}/containers/{id}/recreate` avec `{"PullImage": true}` (Portainer ≥ 2.19 ; à vérifier sur la version de Julien, avec repli si absent : pull de l'image, puis recréation impossible, et le dire).
- **Suivi** :
  - après un ordre, l'Anneau garde « en cours » et relit l'état chaque fois qu'il lit les services (chaque minute, plus vite pendant 5 min) ;
  - fin : conteneur `running` et `/health` qui répond (mise à jour, allumage), ou conteneur `exited` (extinction) ;
  - au-delà de 10 min : « pas de réponse, voir Portainer ».
- **Panne** : une tuile éteinte depuis l'Anneau est « éteinte », pas « en panne ». L'état « éteint » vient de Portainer (conteneur `exited`), donc un arrêt fait ailleurs se voit aussi.
- **Journal** : chaque ordre est noté (qui, quand, quoi, résultat) dans le journal des écritures de l'Anneau.
- **Lecture seule** : `MAISON_LECTURE_SEULE=oui` (ou `ANNEAU_LECTURE_SEULE`) désactive les boutons.
- **Sécurité** : seul quelqu'un connecté à l'Anneau (cookie commun) peut donner un ordre. Les routes ordre sont en POST, avec vérification d'origine (même site). Le nom du conteneur vient de `services.yaml`, jamais de la requête.
- **Tests** : faux Portainer écrit d'après la documentation de son API. On vérifie :
  - les boutons absents sans clé, sans marquage, ou sur une tuile interdite ;
  - la confirmation ;
  - la tuile grise « éteint » ;
  - le suivi d'une mise à jour lente, et le délai dépassé ;
  - la lecture seule ;
  - une requête qui nomme un autre conteneur, refusée ;
  - le journal ;
  - les écrans PC et iPhone.

## 4. Écrans

- **Fiche de la tuile** : à côté de « Ouvrir », un bouton « Éteindre » (ou « Allumer » si éteint) et « Mettre à jour ». Sous les boutons, l'image et sa date (« image du 20/11 ») si Portainer la donne.
- **Tuile** : grise avec « éteint » ; avec un petit cercle qui tourne et « mise à jour en cours » pendant une mise à jour.
- **Réglages › Connexion** : une ligne « Portainer » (voyant, ce que l'Anneau y lit et y écrit), comme les autres connexions.

## 5. Questions pour le conseil

1. **Recréer par l'API Portainer** (`recreate` + `PullImage`) : est-ce sûr pour un conteneur d'une stack (réseaux, étiquettes, volumes gardés) ? Faut-il plutôt pull puis recreate par l'API Docker ?
2. **Utilisateur standard Portainer CE** : peut-il arrêter et recréer les conteneurs d'une stack créée par l'admin ? Sinon, que faire ?
3. **Éteindre le Bac à sable alors que Watchtower le met à jour la nuit** : Watchtower le rallume-t-il ?
4. **Liste d'interdits dans le code, plus marquage dans `services.yaml`** : est-ce suffisant ?
