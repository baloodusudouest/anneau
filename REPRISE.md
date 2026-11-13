# Reprise — L'Anneau

Fichier à lire en premier dans une nouvelle session, et à mettre à jour à chaque fin de session, dans le même commit que le code.

## État (13/11/2026)

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
- `app/main.py` : `/api/etat`, `/api/pannes/vue`, `/api/recharger`, `/api/ha/etat` (ouverte par le secret).
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

- Temps 1 et 2 sans aucun jeton : ni Portainer, ni Home Assistant (c'est lui qui envoie).
- Disques : seuil fixe, 99,8 % par défaut, dans le fichier.
- Cadre si le service l'accepte, sinon fenêtre réutilisée.
- L'anneau porte les familles en texte seul ; rouge lave pour une panne, bleu spectral pour une action ; l'état est aussi dit en mots.
- Sombre seulement, pour l'instant.
- La liste des services est un fichier tenu à la main ; pas d'éditeur dans l'interface.

## Limites connues

- Un service mort derrière une page de connexion qui répond encore reste « or ».
- La sonde ne teste que l'adresse locale, pas celle du réseau privé.
- Pas de version claire.
- Les notifications sont préparées (réponse de `/api/ha/etat`) mais rien n'est branché côté Home Assistant.
