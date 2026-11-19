# Reprise — L'Anneau

Fichier à lire en premier dans une nouvelle session, et à mettre à jour à chaque fin de session, dans le même commit que le code.

## État (19/11/2026)

- **0.15.0** (19/11/2026) : section « Bac à sable » dans Réglages (`Reglages.svelte`, `tuileBac`/`adresseBac` : adresse de la tuile `bac-a-sable`, sinon `http://<hôte>:8104/`). Test : `test_015_lien_vers_le_bac_a_sable`. Jamais essayé sur la vraie installation (le Bac à sable n'est pas encore déployé).
- **0.14.0** (19/11/2026) : bouton « Ouvrir en grand » (`.bouton-grand`, dans `.actions-service` avec « État », `Anneau.svelte`) pour un service affiché dans le cadre ; appelle `dehors()`. Tuile Coffre Maison passée en cadre « essayer » (coffre). Test : `test_014_ouvrir_en_grand_depuis_le_cadre`. Jamais essayé sur la vraie installation : SilverBullet dans le cadre (connexion sur iPhone, raccourcis clavier ; l'Anneau ouvert en http local et le coffre en https Tailscale ne sont pas « du même site »).

- **0.13.0** (18/11/2026) : versions et nouveautés de la nuit (E1 ; décisions de Julien du 18/11 après grill et conseil ; Watchtower met tout à jour chaque nuit à 05:00).
  - `app/versions.py` : `lire_depot`/`plus_haute` (étiquettes `v<semver>` de `baloodusudouest/<depot>`, API publique sans jeton, 403/429/injoignable → `Injoignable`), `relire` (`versions.json`, ancienne lecture gardée), `version_lue` (`{"version"}` ou Immich `{"major","minor","patch"}`), `lire_version_url`, `EnService` (`versions-en-service.json` + `journal-versions.json`, 200 entrées, `depuis()` fusionne par tuile), `vu_le`/`marquer_vu` (`versions-vues.json`, ne recule jamais), `phrase`, `a_jour`.
  - `app/services.py` : champs de tuile `depot:` (validé `[A-Za-z0-9._-]+`, ni `.` ni `..`) et `version_url:` ; une valeur fausse est signalée et ignorée, la tuile reste.
  - `app/veille.py` : `_versions()` à chaque tour (tuiles « ok » seulement ; `versionner` injectable), `versions_des_tuiles()` ; `etat()` rend par service `version`, `version_publiee`, `a_jour`, `version_phrase` (jamais `surveiller` pour un retard).
  - `app/main.py` : tâche `versions-publiees` (déclarée dans `maison.TACHES`, regardée toutes les 5 min, lancée si la dernière lecture a plus d'une heure ; `ETAT["transport_versions"]` pour un faux GitHub) ; routes `/api/versions`, `/api/versions/nouveautes`, `/api/versions/vues`.
  - Écran : `lib/Nouveautes.svelte` (montée dans `App.svelte` une fois par ouverture connectée), ligne de version dans la fiche « État » (`.version-tuile`, bouton « État » aussi sans santé), section « Versions » de Réglages.
  - **Jamais essayé sur la vraie installation** : l'API GitHub depuis le conteneur (proxy, limite de 60 demandes/h par adresse sans jeton : une par dépôt et par heure), le vrai `/api/server/version` d'Immich (sans jeton : à vérifier qu'il ne demande pas de clé), la fenêtre après une vraie nuit de Watchtower. Les champs `depot:` et `version_url:` ne sont pas encore dans la note « Tuiles de l'Anneau » du coffre.
- **0.12.0** (18/11/2026) : santé des tâches de fond (E2 ; dossier et conseil « santé et copies » du 18/11).
  - `app/sante.py` : `lire` (nettoie `taches`, `copie_base`, `version_socle` du /health), `defauts` (règle de l'orange), `phrase`, `empreinte`, `Vus` (`vus.json`).
  - `app/veille.py` : sonde `repond_avec_sante` (JSON du /health, jeton commun seulement pour `sauvegarde: true` + sonde /health : `_jeton_pour`) ; une fausse sonde sans paramètre `jeton` marche encore (`_accepte_jeton`) ; `Veille.sante`, `marquer_vu`, `veille_anneau()` (`boucle_a`, 10 min) ; `etat()` rend par service `sante`, `defauts`, `surveiller`, `vu`, `phrase`, et au total `surveiller`, `veille`.
  - `app/main.py` : `/health` (via `maison.sante()` s'il existe, sinon repli), `/api/sante/vu`, tâches `veille`, `collecte-de-nuit`, `relecture-de-la-carte` déclarées dans `maison.TACHES` (si présent : `getattr`).
  - Écran : rang « À surveiller », phrase sur les pastilles, « à surveiller » sur l'anneau (`text.phrase-service`), fiche « État » (`.fiche-etat`), bandeau (`.bandeau`), couleur `--braise`.
  - **Jamais essayé sur la vraie installation** : la lecture des vrais /health (taille, type `application/json`), le jeton envoyé aux vraies tuiles `sauvegarde: true`, le bandeau après un vrai arrêt de la veille. Le `maison.py` 0.9.0 n'est pas encore diffusé dans ce dépôt (tests passés aussi avec la copie du socle 0.9.0).
- **0.11.0** (18/11/2026) : la carte de la maison (ex-Atlas) dans Réglages (`#/carte`, `frontend/src/lib/carte/`, `app/carte.py`) ; relue toutes les heures dans le dépôt atlas (carte.json fabriquée par le coffre, `.github/scripts/carte.py`), copie locale, voyants des tuiles ; page atlas.html et `documents.py` retirés.
- **0.10.1** (17/11/2026) : lien « Ouvrir cette page en https » dans l'avertissement de la page Variables, adresse tirée des tuiles (`services.adresse_https`).
- **0.10.0** (17/11/2026) : la sauvegarde regroupée dans l'Anneau (décision du 17/11 ; dossier et conseil dans le projet Claude, `anneau-regroupement-*.md`).
  - `app/stack.py` : `homelab.yml` déposé dans le dossier (`verifier` refuse valeur en clair, balisage Markdown, absence de services ; `services_et_variables` rend défaut `None` = à remplir) ; routes `/api/stack`, `/api/stack/fichier`, `/api/services/fichier` dans `main.py`.
  - `sauvegardes.py` : réglage `coffre_obsidian` (DEFAUTS, `valider`) ; `a_traiter(..., cle_publique=)` ajoute la tuile `export-variables` (date lue dans le nom du `.age`, 30 jours) ; `main._a_traiter()` la passe.
  - Interface : `pages/Sauvegardes.svelte`, `pages/Variables.svelte` ; `lib/chiffre.js` (repris d'Atlas ; `sur()` = `isSecureContext`, `empreinte`), `lib/environnement.js` (valeurs en mémoire de page seulement, `pourPortainer`, `lienNote`), `lib/sauvegardes.js` (`normaliser`, `differences`, `libelle`) ; dépendance `age-encryption` 0.3.1 (exacte).
  - Réglages allégé : plus de liste des fichiers ni de saisie de clé (liens vers les pages).
  - **Jamais essayé sur la vraie installation** : la page en https://…:9094 (contexte sûr), la génération de paire sur iPhone, l'ouverture d'un export rangé par Atlas avec la clé actuelle (même format age : doit marcher), l'import de `homelab.yml` exporté d'Obsidian.
  - **Bascule** (après 7 jours sans écart avec Atlas) : retirer `app/documents.py`, la section Atlas de Réglages, la tuile Atlas, `ANNEAU_ATLAS_DEPOT` et `ANNEAU_GITHUB_JETON` ; critère d'abandon : un export existant ne s'ouvre pas.

- **0.9.1** (16/11/2026) : rétention révisée. `retention` garde les 30 dernières automatiques, la première automatique de chacun des 3 derniers trimestres (`GARDES_TRIMESTRES`), et les 5 dernières « à la demande » (`GARDES_MANUELLES`). Le premier de chaque mois est retiré. Tests : 80.
- **0.9.0** (16/11/2026) : deux familles de sauvegardes (décision du 16/11 : garder les 5 dernières à la demande et les 30 dernières automatiques). `sauvegardes/AAAA-MM-JJ.json` (automatique, remplacée le même jour) et `sauvegardes/AAAA-MM-JJ-HHMMSS-manuelle.json` (« Sauvegarder maintenant », jamais écrasée). `identifiant_valide` remplace `date_valide` pour les routes de lecture et de restauration ; `retention` range les deux familles. Tests : 79.
- **0.8.0** (16/11/2026) : sauvegarde des réglages (contrat de sauvegarde 1, module commun contrat 2 copié tel quel).
  - `app/sauvegardes.py` : collecte (`collecter`, `applis_maison`, `base`, `examiner_reponse`), rétention, état et journal (`sauvegardes/etat.json`, gardé en mémoire si le disque refuse), tuile `a_traiter`, exports chiffrés (`ranger_variables`). Réglages de l'Anneau : `maison.Reglages(<données>/reglages.json)` — `heure_sauvegarde` (« HH:MM », 03:30), `cle_publique` (« age1… », vide) ; aucune ancienne variable à reprendre.
  - `app/main.py` : tâche `_sauvegarde_quotidienne` (toutes les 30 s, lance si l'heure est passée et pas encore faite ce jour : rattrapée au démarrage) ; routes `/api/reglages`, `/api/cle-publique`, `/api/sauvegardes[/{date}]`, `/api/restaurer`, `/api/variables-chiffrees[/{nom}]` (session) ; `/externe/sauvegarde`, `/externe/sauvegardes/{appli}` (jeton commun, `_jeton_commun`). `/api/etat` rend `a_traiter`.
  - Tuile maison = sonde qui finit par `/health` ; adresse de base = sonde sans `/health`. `Service.sauvegarde` (`sauvegarde: false` dans services.yaml) l'en retire. **À trancher dans le coffre** : la tuile Chambre noire a une sonde `/health` de nginx sans `/externe/sauvegarde` → elle sera « ratée » chaque jour tant qu'elle n'a pas `sauvegarde: false`. La tuile Atlas (sonde `/health` de l'Anneau) renvoie l'Anneau lui-même : ignorée (déjà sauvegardé sans réseau).
  - Écran : `Reglages.svelte` (sections Sauvegarde et Restaurer), `Anneau.svelte` (rang « À traiter », `.rang.traiter`, or `--app`). `api.put`, `api.postTexte` dans `lib/api.js`.
  - `ANNEAU_PASSWORD` n'est plus lu (`config.charger` : `maison.mot_de_passe()` seul).
  - **Déploiement en deux temps** : d'abord la nouvelle image avec la stack actuelle (les réglages sont repris des anciennes variables au premier démarrage ; pour l'Anneau il n'y en a aucune, mais `MAISON_PASSWORD` et `MAISON_JETON` doivent déjà être remplis), vérifier Réglages, puis la nouvelle stack sans les anciennes lignes (`ANNEAU_PASSWORD`).
  - **Jamais essayé sur la vraie installation** : la collecte depuis le conteneur vers les autres applis (adresses des sondes), l'heure du conteneur (TZ), l'écriture de `sauvegardes/`, les téléchargements depuis l'iPhone, le dépôt d'un export par Atlas.
- **0.7.0** (16/11/2026) : `/externe/services` (annuaire, jeton commun) et module commun `app/maison.py` (socle 0.5.0 ; ne pas le modifier ici, le rediffuser depuis le socle). Jamais essayé sur la vraie installation : poser `MAISON_JETON` dans la stack.
- **0.6.0** (15/11/2026) : import de `services.yaml` depuis Réglages (`services.importer`, `services.comprendre`, route `/api/services/importer`, corps JSON `{texte}` — pas d'envoi de formulaire, donc pas de dépendance de plus). Écriture à côté puis `os.replace` ; l'ancien devient `services.precedent.yaml`. **Jamais essayé sur la vraie installation** : à vérifier que le dossier de données accepte l'écriture (il le fait déjà pour `pannes.json`), et le choix du fichier depuis l'app Fichiers sur iPhone. Pas de bouton « revenir au précédent » : renommer le fichier à la main, puis Recharger.

- **0.5.1** : bouton Réglages en bas de la colonne des familles de la vue réduite (`.colonne .reglages`, `margin-top: auto` ; au bout de la ligne sur téléphone). Test `test_3d`.
- **0.5.0** (14/11/2026) : Atlas relu chaque jour depuis GitHub (`app/documents.py`), servi derrière la session à `/documents/atlas.html`, section Réglages › Atlas. Variables `ANNEAU_ATLAS_DEPOT`, `ANNEAU_GITHUB_JETON`. La tuile se pose dans services.yaml (famille Machines).

- **0.4.2** (13/11/2026) : `pour_ha` écrit chaque ligne « nom : avant → après » (champs `avant`, `etat`, `etat_fin` posés par `_ouvrir` et `_clore`) ; une panne ouverte et close dans le même lot ne fait qu'une ligne close « (coupure brève) ». Les pannes gardées sur disque par une version plus ancienne n'ont pas ces champs : elles gardent l'ancienne phrase.
- **0.4.1** (13/11/2026) : `silence_ha` (minutes, 90 par défaut) remplace la constante de 300 s ; Home Assistant envoie chaque heure (package `systeme/anneau.yaml` v1.1).
- **0.4.0** (13/11/2026) : cadres gardés (`gardes`, `garder`, `affichable` dans `Anneau.svelte`) ; la vue réduite reste montée, cachée par `.absente`, derrière l'anneau. À surveiller sur la vraie installation : la mémoire du navigateur avec huit applis chargées, surtout sur iPhone, qui peut décharger les cadres de lui-même.
- **0.3.1** (13/11/2026) : vu sur le vrai iPhone, une appli coupée dans le cadre (trop étroit à côté de la colonne). Sous 900 px, la vue réduite passe en trois rangées : anneau et familles, services, cadre pleine largeur. Autre chose vue sur la même capture, non traitée : l'appli du cadre suit le thème du téléphone (clair) alors que l'Anneau est toujours sombre.
- **0.3.0** (13/11/2026) : connexion commune avec l'Anneau — cookie `maison_session` (posé à la connexion ; `Sessions.connecte`, `commun_valide` dans `app/auth.py`). Jamais essayée sur la vraie installation.
- **0.2.2** (13/11/2026) : `reglages.hote_local` et `Veille._adresse` — les services de l'hôte de la maison sont donnés sous l'hôte par lequel l'Anneau est ouvert, pour que leur cookie (`SameSite=Strict`, et le blocage des cookies tiers de Safari) passe dans le cadre. Cause supposée d'après une capture, **pas encore confirmée** par l'utilisateur. En https il faut une adresse `privee` par service.
- **0.2.1** (13/11/2026) : sur iPhone (vu sur capture), un texte courbe avec `opacity` est rogné à sa boîte ; les familles en retrait sont assombries par `fill`. **À surveiller : l'état « panne » utilise `filter: drop-shadow` sur le même texte, jamais vu sur un vrai iPhone ; il pourrait rogner de la même façon.**
- **0.2.0** (13/11/2026) : le cadre par défaut. `Service.cadre` vaut oui, non ou vide ; `veille.examiner` lit les en-têtes de la page d'accueil (renvois suivis), `Veille.refus` garde la raison, `etat()` rend `cadre` et `hors_cadre`. **Jamais essayé sur les vrais services** : un service peut interdire le cadre par un moyen que les en-têtes ne disent pas (script), ou mal marcher dedans ; dans ce cas `cadre: false`.
- **0.1.2** (13/11/2026) : le cadre porte `allow="camera; fullscreen; clipboard-write"` (numérisation dans l'Anneau ; caméra en direct seulement si l'Anneau et le service sont en HTTPS).
- **0.1.1** (13/11/2026) : le bouton du milieu ouvre un service dans un nouvel onglet (`Anneau.svelte` : `milieu`, `onglet` ; `Cercle.svelte` : `onmilieu`).
- **0.1.0 sur `main`** : le temps 1, « la vue ». Codée et testée contre un **faux réseau** (15 tests du serveur, 14 tests d'écran sur PC et iPhone). **Jamais lancée sur la vraie installation.**
- Dossier : `docs/dossier.md` (version 2 et décisions). Avis du conseil : `docs/conseil.md`, `docs/conseil-2.md`.
- La maquette cliquable et l'inventaire réel des services ne sont pas dans ce dépôt (il est public) : voir `.gitignore`.

## Où est quoi

- `app/services.py` : lecture de `services.yaml` (une ligne fausse est écartée et signalée). `app/services.exemple.yaml` : l'exemple inventé, servi si le fichier manque.
- `app/veille.py` : la sonde et les règles d'une panne (trois échecs, trois réussites, machine qui emporte ses services, arrêt attendu, seuil des disques, Home Assistant muet). Mémoire : `pannes.json` dans le dossier de données, rien d'autre.
- `app/main.py` : `/api/etat`, `/api/pannes/vue`, `/api/recharger`, `/api/ha/etat` (ouverte par le secret), les routes de sauvegarde (0.8).
- `app/sauvegardes.py` (0.8) : collecte des réglages des applis maison, fichiers `sauvegardes/`, tuile « Sauvegarde ratée », exports chiffrés.
- `frontend/src/lib/Cercle.svelte` : l'anneau (arcs, dépliage). `pages/Anneau.svelte` : l'écran et la vue réduite. `lib/icones.js` : les pictogrammes que le fichier appelle par leur nom.
- `tests/interface/serveur.py` : l'Anneau de démonstration ; `morts.txt` dit quelles adresses ne répondent plus.

## À vérifier sur la vraie installation

1. Depuis le conteneur, les adresses locales des services du même NAS répondent-elles ? (La sonde part du conteneur, pas du navigateur.)
2. Le cadre sur un vrai iPhone, Anneau installé sur l'écran d'accueil : les services gardent-ils leur session ?
3. « Ouvrir » sur iPhone : où s'ouvre le service, et comment on revient.
4. La police de plume et les halos sur un écran réel (lisibilité au soleil).
5. Preuve de vie : arrêter un service sans enjeu, voir la panne s'ouvrir en trois minutes, puis se clore.

## Prochaines étapes

1. Écrire le vrai `services.yaml` avec l'utilisateur (adresses du réseau privé, ports du second NAS), déployer.
2. Côté Home Assistant : l'automatisation qui envoie l'état chaque minute et notifie ; le réglage qui autorise le cadre. **À inscrire dans le document maître de Home Assistant.**
3. Un mois d'usage, puis décider du temps 2 (file de travail des applis maison) et du temps 3 (mises à jour).

## Décisions à ne pas rouvrir sans raison

- Temps 1 et 2 sans aucun jeton : ni Portainer, ni Home Assistant (c'est lui qui envoie). Le jeton commun `MAISON_JETON` (0.7) sert seulement entre applis maison.
- Sauvegarde (0.8) : jamais de secret dans une sauvegarde ; l'export des variables n'arrive que chiffré (age, clé publique ici, clé privée hors de la maison) ; pas de notification Home Assistant pour une sauvegarde ratée.
- Sauvegarde (0.10) : tout dans l'Anneau, rien dans Atlas ; générer, chiffrer et ouvrir seulement en contexte sûr (HTTPS) ; liste des variables = noms seuls (pas de jeton sur le coffre), note dans Obsidian par lien.
- Disques : seuil fixe, 99,8 % par défaut, dans le fichier.
- Cadre si le service l'accepte, sinon fenêtre réutilisée.
- L'anneau porte les familles en texte seul ; rouge lave pour une panne, bleu spectral pour une action ; l'état est aussi dit en mots.
- Sombre seulement, pour l'instant.
- La liste des services est un fichier tenu hors de l'Anneau (le coffre fait foi, note « Tuiles de l'Anneau ») ; pas d'éditeur dans l'interface. Depuis la 0.6 il s'importe en entier depuis Réglages (demande du 15/11/2026).

## Limites connues

- Un service mort derrière une page de connexion qui répond encore reste « or ».
- La sonde ne teste que l'adresse locale, pas celle du réseau privé.
- Pas de version claire. (0.13 : version en service et dernière publiée dans la fiche et Réglages › Versions, pour les tuiles qui ont un `/health` avec `version`, un `version_url:` ou un `depot:`.)
- Les notifications sont préparées (réponse de `/api/ha/etat`) mais rien n'est branché côté Home Assistant.
