# Journal des versions

## 0.16.2 — 20 novembre 2026 (« Ouvrir » qui ne faisait rien)
- **« Ouvrir <service> »** (service qui s'ouvre à côté, ex. Bac à sable) et « Ouvrir en grand » : quand l'onglet de ce service était déjà ouvert quelque part (autre fenêtre, onglet du fond), le navigateur le rechargeait sans le montrer : « rien ne se passe » (signalé par Julien le 20/11/2026, Anneau en https Tailscale sur le PC). Désormais cet onglet est fermé puis rouvert : il passe devant. Toujours un seul onglet par service ; fenêtre refusée par le navigateur : un onglet à part.
- Test : `test_3_un_service_dans_le_cadre_un_autre_a_cote` (second clic : l'ancienne fenêtre fermée, la nouvelle devant), `test_014`. Tests : 170.
- **Jamais essayé sur la vraie installation.**

## 0.16.1 — 20 novembre 2026 (socle 0.11.1)
- Copies communes du socle 0.11.1 : sur une fiche « Connexion », le titre devient « Pour le relier » quand le réglage se fait dans Réglages de l'appli (et non dans la stack).
- **Jamais essayé sur la vraie installation.**

## 0.16.0 — 20 novembre 2026 (fiches « Connexion » des applis dans la fiche « État »)
- La fiche « État » d'une appli maison montre ses fiches « Connexion » (contrat 3, socle 0.11.0) au même format que dans l'appli : de 1 à 3 services, fiches dépliées ; à partir de 4, tuiles puis la fiche ; guide (réglages lus, « Allumer normalement », « En cas de problème ») quand l'appli en donne un.
- Lues une seule fois, à l'ouverture de la fiche (jamais en boucle), par `/api/applis/{cle}/services` ; « Vérifier » relayé par `/api/applis/{cle}/services/{service}/verifier`. Les deux partent du serveur avec **`ANNEAU_CLE`** (nouvelle variable, la même que dans les applis) : la clé ne va jamais au navigateur. Aucun geste qui écrit (ils restent dans l'appli).
- Réponse de l'appli relue champ par champ, détail et guide nettoyés une seconde fois. Une appli d'avant le contrat 3 : « n'a pas encore les fiches communes » (jamais « en panne »). `ANNEAU_CLE` vide : une phrase le dit.
- `/api/etat` : chaque tuile porte `fiches` (vrai pour une appli maison, l'Anneau lui-même exclu). Module `app/fiches.py`, composant `lib/FichesAppli.svelte`, interface commune `lib/services/` copiée du socle.
- `maison.py` du socle 0.11.0. Tests : `tests/test_fiches.py`, écran `test_016`.
- Revient sur l'écart « pas d'écran Connexion dans l'Anneau » (format commun § 7) : décision du 20/11/2026.
- **Jamais essayé sur la vraie installation.**

## 0.15.0 — 19 novembre 2026 (lien vers le Bac à sable)
- **Réglages › Bac à sable** : bouton « Ouvrir le bac à sable », dans un nouvel onglet. Adresse de la tuile « Bac à sable » si elle existe ; sinon le même hôte que l'Anneau, port 8104, en http. Le Bac à sable (nouvelle appli, dépôt `bac-a-sable`) lance les applis maison sur une fausse maison (décision de Julien du 19/11/2026). Test : `test_015_lien_vers_le_bac_a_sable`.

## 0.14.0 — 19 novembre 2026 (ouvrir en grand depuis le cadre)
- Un service affiché dans le cadre de l'Anneau a un bouton **« Ouvrir en grand »** (à côté de « État ») : il l'ouvre dans sa propre fenêtre, toujours la même, comme « Ouvrir ». Sert au coffre Maison (SilverBullet), affiché désormais dans l'Anneau (décision de Julien du 19/11/2026 ; tuile sans `cadre: false`).

## 0.13.0 — 18 novembre 2026 (versions et nouveautés de la nuit)
- **Versions publiées** (E1) : nouvelle tâche régulière horaire `versions-publiees` (registre `maison.TACHES`) qui lit les étiquettes Git de chaque dépôt donné par le nouveau champ de tuile `depot:` (ex. `depot: carnet`), sur l'API publique de GitHub, sans jeton, et garde la plus haute étiquette `v<semver>`. Dernière lecture gardée dans `/data/versions.json` ; GitHub injoignable ou limite atteinte (403/429) : l'ancienne reste, seule la tâche passe en erreur.
- **Version en service** : lue dans le `/health` (`version`) comme avant ; pour une tuile tierce, nouveau champ `version_url:` (Immich : `/api/server/version`, `{"major", "minor", "patch"}` → « 3.x.y » ; accepte aussi `{"version": "…"}`), lu sans jeton.
- **Fiche de la tuile** : « Version 0.12.0 — dernière publiée 0.12.0 (à jour) » ou « … dernière publiée 0.13.0 : pas encore en service » ; jamais d'orange pour un retard. Le bouton « État » apparaît aussi pour une tuile dont on ne connaît que la version.
- **Réglages › Versions** : tableau tuile, en service, dernière publiée, mise à jour le.
- **Journal des changements de version** : la veille ajoute chaque changement vu (tuile, de, vers, le) à `/data/journal-versions.json`, 200 entrées au plus ; la dernière version connue de chaque tuile est gardée dans `versions-en-service.json`, pour voir un changement fait pendant que l'Anneau redémarrait (Watchtower le met à jour aussi).
- **Fenêtre « Mis à jour depuis votre dernière visite »** à l'ouverture de l'Anneau (après une connexion, ou premier chargement avec une session valide) quand des versions ont changé depuis le dernier « Vu » : « carnet 2.32.0 → 2.33.0 (cette nuit, 05:04) ». « Vu » enregistre l'heure côté Anneau (`versions-vues.json`), pas par navigateur. Routes `GET /api/versions`, `GET /api/versions/nouveautes`, `POST /api/versions/vues` (session).
- Tests : 119 (dont 12 dans `test_versions.py`) et 37 tests d'écran (2 de plus : PC et iPhone).
- La mise à jour de l'Anneau lui-même entre aussi au journal (au démarrage), même sans tuile qui le sonde.

## 0.12.0 — 18 novembre 2026 (santé des tâches de fond)
- **Tuile « à surveiller »** (orange braise, distincte de « en panne ») : la veille lit en plus `taches`, `copie_base` et `version_socle` dans le `/health` des applis (socle 0.9.1). Orange si une tâche régulière est « en retard » ou « bloquée », ou si la copie des bases a raté ou a plus de 36 h ; une tâche à la demande ne rend jamais orange ; une appli sans ces champs ne change rien. La phrase (« synchro-icloud n'a pas réussi depuis 3 h ») est écrite sur la pastille de la tuile et dans le nouveau rang « À surveiller » ; sur l'anneau, « à surveiller » au-dessus du nom.
- **Fiche « État »** d'une tuile (vue réduite, bouton « État », ou « Voir » du rang) : chaque tâche (période, état, dernière réussite, dernière erreur et son message), la dernière copie des bases, la version du socle.
- **Bouton « Vu »** : la tuile redevient normale (petit signe « vu ») jusqu'au prochain changement — une autre tâche qui casse, ou celle-ci qui se répare puis recasse. Gardé dans `vus.json` ; route `POST /api/sante/vu` (session).
- **Jeton commun seulement vers les applis maison** : il part avec la sonde `/health` des seules tuiles `sauvegarde: true` (pour avoir les messages d'erreur), jamais ailleurs.
- **L'Anneau se surveille** : sans boucle de veille finie depuis plus de 10 min, bandeau orange en haut « La veille de l'Anneau est arrêtée depuis … » (le serveur le calcule à chaque lecture de l'écran ; le navigateur aussi quand l'API ne répond plus).
- **`/health` de l'Anneau** : `version_socle`, `taches` (veille, collecte de nuit, relecture de la carte, suivies par `maison.TACHES`) et `copie_base: null` ; messages d'erreur seulement avec le jeton commun ou une session. Passe par `maison.sante()` du socle 0.9.0 ; avec un `maison.py` plus ancien, l'Anneau tourne comme avant (tâches vides).
- Tests : 107 (dont 21 dans `test_sante.py`) et 35 tests d'écran (4 de plus : PC et iPhone).

## 0.11.2 — 18 novembre 2026 (constats moyens de l'audit)
- **Collecte des sauvegardes sur accord explicite** (M5) : dès qu'une tuile porte `sauvegarde: true` (ou `oui`), seules ces tuiles reçoivent le jeton commun à 03:30. Un fichier de tuiles sans aucun `true` garde l'ancienne règle (toute sonde finissant par `/health`, sauf `sauvegarde: false`) : rien ne casse avant la mise à jour du fichier.
- **Remplacer la clé publique se confirme** (M7) : une fois une clé posée, la changer ou la retirer exige la clé actuelle (case « Remplacer la clé actuelle » dans Variables ; sinon 409). Un export rangé doit porter l'en-tête d'age (`age-encryption.org/v1`) sous son enveloppe, plus seulement les lignes BEGIN/END.
- **Mémoire de l'ancien Atlas effacée** (M49) : au chargement, l'Anneau efface `atlas-environnement` de la mémoire du navigateur (là où Atlas avait été ouvert à l'adresse de l'Anneau).
- `maison.py` du socle 0.8.2 (réglages secrets reconnus par mots, champ `ecartes` dans la sauvegarde).

## 0.11.1 — 18 novembre 2026 (voyants de la carte)
- Les voyants de la carte retrouvent leur tuile quand la clé de la tuile a des tirets (« kit-d-urgence ») ou que le nom du service porte une parenthèse (« Éphéméride (vérification des dates) ») : comparaison sans accents, espaces ni tirets. Vu sur la vraie installation à la mise en service de la 0.11.0 (Kit d'urgence, Douze points, Chambre noire, Home Assistant, Éphéméride sans voyant).
- « Tuiles hors carte » ne liste plus les machines (Synology, QNAP, PC de calcul).

## 0.11.0 — 18 novembre 2026 (la carte de la maison, Atlas basculé)
- **Carte de la maison dans Réglages** (décision du 18/11/2026, avis du conseil) : la carte d'Atlas (machines, quartiers, services, flux) s'ouvre par Réglages › Carte de la maison (`#/carte`). Graphe sur les écrans larges (Svelte Flow + dagre, ordre stable), liste machine › services sur téléphone. Chaque service porte le **voyant de sa tuile** (en service, en panne, éteint, sans tuile) ; filtre « En panne » ; panneau d'un service : rôle, ce qui le nourrit, ce qu'il fournit, ce qu'il échange, lien vers sa note dans le coffre Obsidian.
- La carte est **fabriquée par le coffre** à chaque envoi (action GitHub « carte » du coffre) et poussée dans le dépôt privé d'Atlas, réduit à `carte.json`. L'Anneau la relit **toutes les heures** et sur « Relire la carte », avec le jeton en lecture seule `ANNEAU_GITHUB_JETON` (côté serveur seulement, jamais envoyé au navigateur), vérifie son format (`schema` 1, flux vers des services connus) et garde la dernière carte valide dans `/data/documents/carte.json` : GitHub ou Internet en panne, la carte reste, avec son âge.
- Routes `/api/carte` et `/api/carte/relire` (derrière la session). **Retirés** : la page `/documents/atlas.html`, `/api/documents`, le téléchargement de la publication d'Atlas (`app/documents.py`). Variables inchangées (`ANNEAU_ATLAS_DEPOT`, `ANNEAU_GITHUB_JETON`).

## 0.10.6 — 18 novembre 2026 (cookies Secure)
- **Cookies `Secure` en https** (audit du 17/11/2026, même correctif dans toutes les applis maison) : ouverte en https (directement, derrière Tailscale Serve qui le dit par `X-Forwarded-Proto`, ou d'après l'origine de la page), l'appli pose ses cookies de session avec l'attribut `Secure` : ils ne partent jamais en clair. En http (adresse locale), rien ne change.
- `entrypoint.sh` refuse de lancer l'appli en root quand `/data` appartient à root (dossier créé par Docker) et dit le remède ; dépannage seulement : `MAISON_ROOT_ACCEPTE=oui`.

## 0.10.5 — 18 novembre 2026 (révocation du cookie commun)
- **« Se déconnecter » dans l'Anneau ferme vraiment la connexion commune** (audit du 17/11/2026, même correctif dans toutes les applis maison) : le cookie commun `maison_session` porte maintenant la génération tenue par l'Anneau (« génération.expiration.signature ») ; « Se déconnecter » l'augmente, et chaque appli la lit dans l'annuaire de l'Anneau (`/externe/services`, au plus une minute de retard) : un cookie commun d'avant la déconnexion ne vaut plus nulle part. Si l'Anneau ne répond pas, le cookie reste accepté comme avant (rien ne se bloque). **Toutes les applis doivent être à jour ensemble** ; une seule reconnexion est demandée après la mise à jour.
- Module commun `maison.py` (socle 0.8.0) : `generation_commune()`, `definir_generation_commune()` ; l'annuaire lit aussi `generation_commune` (une ancienne réponse de l'Anneau, liste seule, reste lue).
- L'Anneau publie `generation_commune` dans `/externe/services` et sa génération des sessions sert aussi au cookie commun.

## 0.10.4 — 17 novembre 2026 (corrections de l'audit, suite)
- Import de `homelab.yml` : la détection d'une valeur en clair reconnaît aussi `PASSWD`, `PWD`, les clés (`TS_AUTHKEY`…), `WEBHOOK`, `DSN`, et les valeurs courtes ou avec ponctuation ; aucun faux positif sur le `homelab.yml` du coffre (vérifié).
- Un pourcentage de disque `NaN` envoyé par Home Assistant ne casse plus `/api/etat`.

## 0.10.3 — 17 novembre 2026 (connexion plus sûre)
- **Connexion plus sûre** (audit du 17/11/2026, même correctif dans toutes les applis maison) :
  - un cookie portant un caractère non ASCII donnait une erreur 500 sur toute l'API ; il est maintenant simplement refusé ;
  - les clés qui signent les cookies (celui de l'appli et le cookie commun `maison_session` posé par l'Anneau) sont tirées du mot de passe par PBKDF2 : un cookie capté sur le réseau local ne permet plus de chercher le mot de passe à grande vitesse. **Toutes les applis doivent être à jour ensemble** ; une seule reconnexion est demandée après la mise à jour ;
  - des essais de mot de passe lancés en parallèle ne contournent plus le délai : au-delà de 30 essais en 5 minutes, tout est refusé sans comparer.
- Module commun `maison.py` (socle 0.7.0) : l'annuaire de l'Anneau est relu 30 s après un échec (avant : 10 min sans adresses après un redémarrage de la stack) ; un réglage `nan` ou infini est refusé ; un `reglages.json` abîmé est mis de côté (`.corrompu`) au lieu d'être écrasé.

## 0.10.2 — 17 novembre 2026 (corrections de l'audit)
- **Bug** : une seule tuile avec une adresse au port invalide (ex. `http://nas:80a/health`) arrêtait toute la veille, sans rien afficher. Le port est contrôlé à la lecture de `services.yaml` (la ligne est signalée et écartée), et une sonde qui plante compte comme « ne répond pas » sans priver les autres de leur résultat.
- **Bug** : un `services.yaml` illisible (modifié à la main) empêchait l'Anneau de démarrer. L'exemple s'affiche alors à la place, avec l'erreur en tête des Réglages ; réimporter le bon fichier suffit.
- Exemples d'adresses du journal remplacés par des adresses inventées (règle des dépôts publics).
- Tests : 103 (dont `test_veille_robuste.py`).

## 0.10.1 — 17 novembre 2026
- **Lien vers l'adresse https dans la page Variables.** Ouverte en http (adresse locale), la page Variables donne maintenant un lien cliquable « Ouvrir cette page en https ». L'adresse est tirée des tuiles : les applis du NAS dont la tuile ouvre en https et sonde en http sur l'hôte de la maison donnent le nom Tailscale et l'écart de port (+1000). Exemple : `http://192.0.2.90:8094` mène à `https://nas.exemple.ts.net:9094/#/variables`. Sans tuile qui le permette, le texte d'avant reste.
- Serveur : `GET /api/stack` rend aussi `adresse_https`. Aucune variable nouvelle.
- Vérifié le 17/11 sur le PC de Julien : en https, la page ne charge rien en http (ni ressource, ni image, ni cadre) et Edge la tient pour un contexte sûr. L'alerte « connexion non sécurisée » vue une fois venait de l'état d'avant le rechargement.
- Tests : 99 (dont la page ouverte par un nom non sûr, avec et sans tuile https).

## 0.10.0 — 17 novembre 2026
**Toute la sauvegarde dans l'Anneau** (décision du 17/11, après le conseil) : ce qu'Atlas faisait pour la sauvegarde passe ici.
- **Page Sauvegardes** (`#/sauvegardes`, lien depuis Réglages) : chaque sauvegarde se déplie — par appli, version et réglages, ce qui a changé depuis la précédente, applis ratées ; « Seulement les applis qui ont changé » ; Télécharger. Réglages ne garde que l'heure, « Sauvegarder maintenant », la dernière collecte et un lien.
- **Page Variables** (`#/variables`) :
  - **Fichiers de la stack** : importer `homelab.yml` (refusé en entier s'il porte une valeur en clair ou du balisage Markdown), le télécharger, télécharger le `services.yaml` actuel.
  - **Clé de chiffrement** : générer une paire age dans la page (clé privée montrée une fois, à cocher « rangée hors de la maison », jamais gardée ni envoyée) ; empreinte de la clé publique à comparer avec la copie du coffre.
  - **Chiffrer l'export de Portainer** (coller ou choisir un fichier) puis le ranger ; seul le texte chiffré part ; le texte clair est effacé.
  - **Exports chiffrés** : ouvrir un export avec la clé privée (déchiffré dans la page, compatible avec l'outil `age`) ; valeurs masquées avec « Afficher », variables à remplir manquantes, variables que la stack n'utilise plus ; « Copier toutes les variables (avec valeurs) », « Télécharger homelab.env », « Voir le texte », « Oublier ».
  - **Variables de la stack** : liste pliable avec recherche, défaut ou « à remplir », services qui la lisent, lien vers sa note dans Obsidian (nom du coffre réglable, « Maison » au départ).
- **HTTPS seulement pour les secrets** : générer, chiffrer et ouvrir sont désactivés quand la page n'est pas en contexte sûr (http par l'adresse locale) ; la page renvoie à l'adresse https (Tailscale, :9094) ou à `age` en ligne de commande.
- **Tuile « Export des variables ancien »** (À traiter) quand une clé publique est posée et que le dernier export a plus de 30 jours, ou qu'il n'y en a aucun ; « Voir » mène à Variables.
- Serveur : routes `/api/stack` (lire, importer), `/api/stack/fichier`, `/api/services/fichier` ; réglage `coffre_obsidian`. Aucune variable nouvelle.
- Atlas et sa relecture restent en service jusqu'à la bascule (après 7 jours d'essai sans écart) ; `ANNEAU_ATLAS_DEPOT` et `ANNEAU_GITHUB_JETON` partiront à ce moment-là.
- Tests : 96 (dont l'aller-retour de chiffrement avec l'outil `age`, clé privée et texte clair jamais envoyés ni gardés).

## 0.9.1 — 16 novembre 2026
- **Rétention des sauvegardes** (décision du 16/11 au soir) : fini le premier de chaque mois. On garde les **30 dernières sauvegardes automatiques**, la **première de chaque trimestre pour les 3 derniers trimestres**, et les **5 dernières sauvegardes à la demande**.
- Tests : 80.

## 0.9.0 — 16 novembre 2026
- **Deux familles de sauvegardes.** « Sauvegarder maintenant » écrit désormais son propre fichier, horodaté (`AAAA-MM-JJ-HHMMSS-manuelle.json`) : il n'écrase plus la sauvegarde automatique du jour. On garde les **5 dernières sauvegardes à la demande** et les **30 dernières automatiques** (plus la première de chaque mois, comme avant).
- Les routes `/api/sauvegardes/{...}`, `/api/restaurer` et `/externe/sauvegardes/{appli}` acceptent les deux formes d'identifiant ; une restauration se fait à partir de l'une ou l'autre.
- Tests : 79 (dont la rétention des deux familles et le non-écrasement de l'automatique).

## 0.8.0 — 16 novembre 2026
- **Sauvegarde des réglages des applis maison.** Chaque jour à l'heure choisie (03:30 au départ), l'Anneau demande ses réglages à chaque appli maison du fichier des services et les range dans son dossier, un fichier par jour (les 30 derniers jours, plus le premier de chaque mois). Une appli qui ne répond pas, ou qui enverrait un secret, est notée « ratée » sans gêner les autres. Bouton « Sauvegarder maintenant ».
- **Tuile « Sauvegarde ratée »**, en or, dans un nouveau rang « À traiter » de l'écran d'accueil, quand la dernière collecte a raté une appli, quand le fichier n'a pas pu être écrit, ou quand rien n'a réussi depuis 36 heures. Ce n'est pas une panne, et rien ne part vers Home Assistant.
- **Réglages › Sauvegarde** : l'heure, la dernière collecte (applis lues, ratées et pourquoi), les fichiers à télécharger, la clé publique où Atlas chiffre l'export des variables, et les exports chiffrés reçus. Une clé privée est refusée dès le navigateur. **Réglages › Restaurer** : remettre les réglages de l'Anneau d'une sauvegarde.
- Les applis maison relisent leurs sauvegardes chez l'Anneau pour leur bouton « Restaurer » (jeton commun).
- Atlas peut déposer un export **chiffré** des variables (jamais de texte clair accepté) ; les 30 derniers sont gardés et partent avec Hyper Backup.
- Une tuile peut se retirer de la collecte par `sauvegarde: false` dans le fichier des services.
- **Ancien nom retiré** : `ANNEAU_PASSWORD` n'est plus lu, seulement `MAISON_PASSWORD`.
- Tests : 53 du serveur, 24 d'écran.

## 0.7.0 — 16 novembre 2026
- **Annuaire pour les applis maison** : `GET /externe/services` (jeton commun `MAISON_JETON` ; vide : adresse fermée ; `MAISON_JETON_ANCIEN` accepté pendant un changement) rend le nom, la famille, l'adresse locale et l'adresse privée de chaque tuile. Les applis y lisent les liens vers les autres au lieu d'une IP et d'un port codés chez elles (module commun du socle 0.5.0). Rien d'autre n'en sort : ni sonde, ni état, ni secret.
- Module commun `app/maison.py` (contrat 1) ; le mot de passe se lit dans `MAISON_PASSWORD`, avec repli sur `ANNEAU_PASSWORD`.
- Tests : annuaire fermé, jeton refusé, contenu limité ; copie du module non retouchée.

## 0.6.0 — 15 novembre 2026
- **Importer le fichier des services depuis Réglages**, au lieu de le déposer dans le dossier de données : « Importer un fichier », choisir le `services.yaml` (celui qu'Atlas donne dans Fichiers), « Remplacer ». L'Anneau le lit en entier avant d'écrire : un fichier illisible, ou sans aucun service valable, est refusé et rien ne change. L'ancien fichier est gardé à côté sous le nom `services.precedent.yaml` (un seul secours : celui d'avant le dernier import).
- Le fichier peut toujours se poser à la main, puis « Recharger le fichier ». L'Anneau écrit désormais `services.yaml` dans son dossier de données, et seulement à cet import ; toujours pas d'éditeur dans l'interface.
- Tests : 33 du serveur, 22 d'écran.

## 0.5.1 — 14 novembre 2026
- Un service ouvert, les **réglages** restent à portée : une icône tout en bas de la colonne des familles, à gauche (au bout de la ligne des familles sur téléphone).

## 0.5.0 — 14 novembre 2026
- **Atlas dans l'Anneau.** L'Anneau relit chaque jour la carte de la maison (le fichier `atlas.html` de la publication « derniere » du dépôt privé d'Atlas) et la garde dans son dossier (`documents/`). Elle s'ouvre par une tuile, comme un service, à l'adresse `/documents/atlas.html` — seulement avec une session de l'Anneau ou le cookie commun.
- Deux variables nouvelles, facultatives : `ANNEAU_ATLAS_DEPOT` (« baloodusudouest/atlas ») et `ANNEAU_GITHUB_JETON` (jeton GitHub en lecture seule sur ce dépôt). Vides : pas d'Atlas, rien d'autre ne change.
- **Réglages › Atlas** : reçue quand, dernier essai, l'erreur s'il y en a une (jeton refusé, publication introuvable…), « Relire Atlas maintenant » et « Ouvrir Atlas à côté ». Un échec garde l'ancienne carte ; le jeton n'est jamais montré et ne part pas vers le stockage où GitHub redirige.

## 0.4.2 — 13 novembre 2026
- **Les notifications disent le passage d'un état à l'autre**, avec une flèche : « Grimmory : répond → ne répond plus », « Grimmory : ne répond plus → répond de nouveau », « Volume 1 de Synology : plein à 99,9 % → 99,1 % », « Home Assistant : muet → envoie de nouveau son état ».
- **Une panne ouverte puis close entre deux envois de Home Assistant ne fait plus qu'une ligne** : « Grimmory : ne répond plus → répond de nouveau (coupure brève) », au lieu d'une ligne rouge puis d'une verte, et le titre ne la compte plus comme une panne.
- L'écran de l'Anneau ne change pas. Rien à changer dans Home Assistant.

## 0.4.1 — 13 novembre 2026
- **Home Assistant n'envoie plus qu'une fois par heure** (et dès qu'un état de volume ou la mise à jour de DSM change). L'Anneau le dit muet après 90 minutes sans envoi, au lieu de 5. Réglable dans le fichier des services : `reglages: silence_ha: <minutes>`.
- Tests : 20 du serveur, 18 d'écran.

## 0.4.0 — 13 novembre 2026
- **Les services ouverts restent chargés.** Passer d'un service à l'autre, ou revenir à l'anneau, ne recharge plus rien : on retrouve chaque service où on l'avait laissé. Huit au plus restent ouverts, le plus ancien cède sa place. Un point sur la pastille dit qu'un service est resté ouvert. Toucher le service déjà affiché le recharge.
- Tests : 19 du serveur, 18 d'écran.

## 0.3.1 — 13 novembre 2026
- **iPhone : le service ouvert prend toute la largeur de l'écran.** Les icônes des familles passent en ligne en haut, à côté de l'anneau ; les services de la famille dessous ; le cadre en dessous, bord à bord. À côté de la colonne d'icônes, le cadre n'avait que les trois quarts de l'écran : les applis y débordaient et se lisaient coupées. Sur PC, rien ne change.

## 0.3.0 — 13 novembre 2026
- **Connexion commune.** À la connexion, l'Anneau pose un cookie « maison_session » que les applis de la maison acceptent : elles s'ouvrent dans le cadre sans redemander le mot de passe, quand elles sont servies par la même adresse que lui (voir `hote_local`). Les services qui ont leurs propres comptes ne sont pas concernés. Le cookie est signé avec le mot de passe commun : une appli qui a un autre mot de passe continue de demander le sien. Il vaut trente jours, ou jusqu'au changement du mot de passe ; « Se déconnecter » le retire du navigateur.

## 0.2.2 — 13 novembre 2026
- **Se connecter à un service dans le cadre.** Quand l'Anneau était ouvert par un autre nom ou une autre adresse que celle des services (nom du NAS, adresse Tailscale), le navigateur traitait le service comme un site tiers et refusait son cookie : le mot de passe était accepté mais la page de connexion revenait. Réglage `hote_local` : l'Anneau donne alors les services de cet hôte sous le nom par lequel il est lui-même ouvert, port gardé (en http seulement).
- Tests : 18 du serveur, 16 d'écran.

## 0.2.1 — 13 novembre 2026
- **iPhone : les noms de famille ne sont plus rognés** quand une autre famille est dépliée (le « M » de Médias, le « n » de Maison perdaient un morceau). Les familles en retrait changent de couleur au lieu de devenir translucides.

## 0.2.0 — 13 novembre 2026
- **Tout s'ouvre dans l'Anneau, sauf refus.** Un service sans réglage `cadre` est désormais affiché dans l'Anneau. L'Anneau lit ce que chaque service dit de son affichage dans une autre page (`X-Frame-Options`, `Content-Security-Policy : frame-ancestors`) : s'il l'interdit, il s'ouvre à côté et la fiche dit pourquoi. Relu tous les dix tours et à « Recharger le fichier ».
- Dans le fichier : `cadre: true` force le cadre, `cadre: false` l'interdit, rien (ou `auto`) laisse l'Anneau essayer.
- Un service éteint exprès n'est pas affiché dans un cadre vide.
- Tests : 17 du serveur, 16 d'écran.

## 0.1.2 — 13 novembre 2026
- **Le cadre laisse passer l'appareil photo**, le plein écran et la copie : une appli de numérisation peut s'ouvrir dans l'Anneau. L'appareil photo en direct demande que l'Anneau et le service soient tous deux ouverts en HTTPS ; le navigateur demande toujours l'accord.
- Tests : 15 du serveur, 16 d'écran.

## 0.1.1 — 13 novembre 2026
- **Le bouton du milieu de la souris** sur un service (sur l'anneau ou dans les pastilles) l'ouvre dans un nouvel onglet du navigateur, sans quitter l'anneau ni changer le service affiché.
- Tests : 15 du serveur, 16 d'écran.

## 0.1.0 — 13 novembre 2026
Première version : la vue, sans aucun pouvoir d'écrire.

- **L'anneau** : les familles écrites à la plume le long du cercle, en texte seul. Toucher une famille la déplie ; toucher un service l'ouvre.
- **La vue réduite** : l'anneau d'or en haut à gauche (retour), une colonne d'icônes par famille, les services en pastilles, et le service — dans un cadre s'il l'accepte, sinon son état et « Ouvrir », qui réutilise toujours la même fenêtre.
- **La veille** : chaque service interrogé toutes les minutes ; trois échecs ouvrent une panne, trois réussites la closent ; une machine qui tombe fait une seule panne ; un arrêt attendu n'en est pas une.
- **Deux rangs** : « en panne » (rouge lave) et « à faire quand tu veux » (bleu spectral), avec « Pris en compte ».
- **Home Assistant envoie** l'état des machines (volumes, mises à jour) ; l'Anneau ne détient aucun jeton. Un volume est en panne à partir du seuil du fichier (99,8 %). Sans envoi depuis cinq minutes : « Home Assistant est muet ».
- **Adresses** : ouvert par le réseau privé, l'Anneau donne les adresses du réseau privé ; sinon les locales.
- **Fraîcheur** affichée : dernière vérification, dernier envoi de Home Assistant, date du fichier des services.
- Le fichier des services se pose à la main dans le dossier de données ; sans lui, l'Anneau montre un exemple inventé.
- Tests : 15 du serveur, 14 d'écran (PC et iPhone).
