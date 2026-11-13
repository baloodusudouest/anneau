# Reprise — L'Anneau

Fichier à lire en premier dans une nouvelle session, et à mettre à jour à chaque fin de session, dans le même commit que le code.

## État (13/11/2026)

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
