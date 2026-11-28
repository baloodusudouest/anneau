# L'Anneau 0.22.0 — les applis en veille

Mode Évolution (VisionQuest). Cadrage avec Julien le 28/11/2026, au réveil.

## 1. But

Pouvoir éteindre les applis qu'on n'utilise pas sans qu'elles passent en rouge dans l'Anneau, et sans qu'elles se rallument au prochain redéploiement de la stack. Les rallumer depuis l'Anneau en un clic.

Aujourd'hui (0.17 à 0.21), « Éteindre » existe dans la fiche d'une tuile marquée `conteneur:`. Mais seules les tuiles du Bac à sable et du QNAP en ont un, et un redéploiement de la stack `homelab` rallume l'appli (le coffre l'a noté le 21/11/2026).

## 2. Utilisateurs et écrans

Julien seul (session de l'Anneau).

- **Réglages › Services › « Applis en veille »** (nouvelle section) : une ligne par tuile marquée `conteneur:`, rangée par famille, avec une case « en veille ». La case est grisée, avec sa raison, quand l'Anneau ne peut pas toucher la tuile (interdite, QNAP pas réglé, conteneur inconnu de Portainer, ordre déjà en cours). Chaque ligne donne aussi l'état lu chez Portainer (tourne, arrêtée, en cours).
- **Anneau** : une appli en veille reste à sa place, en gris (`--eteint`), avec la phrase « en veille ». Un clic sur la tuile grise ouvre une petite fenêtre « Démarrer Comptoir ? ». Après « Démarrer », la tuile tourne jusqu'au vert. L'appli **sort de la veille** : elle tourne jusqu'à sa prochaine mise en veille.
- **Fiche de la tuile** : « Éteindre » devient « Mettre en veille » et « Allumer » devient « Démarrer ». Il n'y a plus qu'un seul état « éteint », celui de la liste, donc plus d'arrêt qui ne tient pas.
- **À traiter** : une appli en veille qui tourne sans ordre de l'Anneau (démarrée à la main dans Portainer, ou par un redéploiement de la stack : l'Anneau ne sait pas distinguer les deux) donne la tuile « Revenue de veille : Comptoir » avec deux boutons, « Remettre en veille » et « La laisser allumée » (qui la retire de la liste). Tant que tu n'as pas choisi, elle tourne et s'affiche normalement.
- **Mettre à jour** reste possible sur une appli en veille (fiche de la tuile) : Watchtower la met à jour sans la rallumer.
- **Journal** (Réglages › Connexions › Portainer, `journal-ecritures.jsonl`) : mise en veille, démarrage, retour sans ordre, choix fait sur ce retour.

## 3. Données et flux

- **Liste voulue** : le réglage `veille` de l'Anneau (`reglages.json`, clés de tuile séparées par des virgules). Il entre donc dans la sauvegarde de nuit des réglages et dans la restauration.
- **Compagnons** : nouveau champ de tuile `compagnons: [appli-api, appli-db]` dans `services.yaml`, au même format Docker que `conteneur:`, avec les mêmes interdits et la même machine que la tuile. Ordre de mise en veille : l'appli, puis ses compagnons. Ordre de démarrage : les compagnons (attente de « running », 120 s au plus), puis l'appli. Un compagnon encore utilisé par une autre tuile hors veille n'est pas arrêté.
- **Retour sans ordre** (choix de Julien du 28/11/2026 : prévenir, ne jamais réarrêter seul) : à chaque tour de veille (60 s), après `relire`, une tuile de la liste dont le conteneur tourne sans ordre de l'Anneau en cours est notée `revenues` dans `veille.json` (avec la date) et donne une tuile « À traiter ». Rien n'est arrêté sans un clic. Au redémarrage du NAS, rien ne revient : la stack est en `restart: unless-stopped`, donc Docker laisse arrêté un conteneur arrêté.
- **Mise à jour d'une appli arrêtée** (choix de Julien) : `WATCHTOWER_INCLUDE_STOPPED=true` et `WATCHTOWER_REVIVE_STOPPED=false` dans le service `watchtower` des deux stacks (`homelab yml`, `media yml`). Watchtower met alors à jour aussi les conteneurs arrêtés, la nuit et à la demande de l'Anneau, sans les rallumer (options lues dans le code de nickfedor/watchtower, `internal/settings/flags/client/register.go`, réglage du client valable aussi pour l'API). L'Anneau n'attend plus « running » après la mise à jour d'une appli en veille, mais seulement une nouvelle image.
- **Sondes** : une tuile de la liste est un « arrêt attendu » (`Veille.eteints` reçoit la liste voulue, en plus des `exited` lus). Elle n'est jamais rouge, même si Portainer est injoignable.
- **Flux** : aucun nouveau. Les flux restent ceux de l'Anneau vers Portainer (Synology) et vers Portainer (QNAP).

Les tuiles à marquer (`conteneur:`, `compagnons:`) sont listées dans le coffre (note « Tuiles de l'Anneau »), jamais dans ce dépôt public. Restent impossibles : les conteneurs interdits (`INTERDITS`), les services hors d'une stack Portainer, les machines. Un conteneur qui porte le réseau d'un autre (`network_mode: service:…`) n'est le compagnon de personne : l'arrêter couperait les autres.

## 4. Architecture

- `app/services.py` : champ `compagnons` (liste ; valeur fausse ou interdite signalée et ignorée, la tuile reste).
- `app/conteneurs.py` : `relire` lit aussi les compagnons ; gestes `eteindre` (appli puis compagnons) et `allumer` (compagnons puis appli) par la même `barriere` et le même `_executer` ; `revenues(voulue)` → tuiles de la liste qui tournent sans ordre en cours ; compagnon partagé jamais arrêté ; mise à jour d'une appli arrêtée sans attente de « running ».
- `app/main.py` : `un_tour` = relire → revenues → veille → suivre ; routes `GET /api/veille`, `POST /api/veille/{cle}` (`{"veille": true|false}`), `POST /api/veille/{cle}/laisser` ; `POST /api/conteneurs/{cle}/eteindre|allumer` mettent et sortent de la veille ; tuile « À traiter » `veille-revenue`.
- `app/sauvegardes.py` : `veille.json` dans la collecte de l'Anneau.
- Écran : `lib/reglages/Services.svelte` (section « Applis en veille »), `pages/Anneau.svelte` et `Cercle.svelte` (clic sur une tuile grise → `lib/Demarrer.svelte`), `lib/Conteneur.svelte` (libellés).

## 5. Sécurité

- Les interdits de `INTERDITS` valent aussi pour les compagnons. Un compagnon doit porter l'étiquette de projet de sa machine (`homelab` ou `media`), sinon la case est grisée.
- Aucune route sans session. Les écritures passent par la garde https et `Origin`, comme les ordres de la 0.17.
- La veille ne fait que `stop` et `start` par Portainer ; rien n'est arrêté sans un clic de Julien.
- Portainer injoignable : on garde la liste, on ne fait aucun ordre, et la tuile reste grise avec « état non relu ».

## 6. Critères de fin (testables)

1. Cocher Comptoir dans Réglages arrête `comptoir` (faux Portainer), et la tuile passe en gris « en veille », jamais en rouge, même après 5 tours sans réponse de sa sonde.
2. Rallumer `comptoir` dans le faux Portainer (comme un redéploiement) donne au tour suivant la tuile « À traiter » « Revenue de veille », sans aucun arrêt ; « Remettre en veille » l'arrête, « La laisser allumée » la retire de la liste.
2 bis. « Mettre à jour » sur une appli en veille passe par Watchtower et la laisse arrêtée ; la fiche dit la date de la nouvelle image.
3. Un clic sur la tuile grise, puis « Démarrer », allume l'appli et la retire de la liste ; elle passe au vert.
4. Appli à compagnons : mise en veille = l'appli puis ses compagnons arrêtés ; démarrage dans l'ordre inverse. Un compagnon partagé avec une tuile active n'est pas arrêté.
5. Une tuile interdite, sans conteneur ou du QNAP non réglé a sa case grisée, avec sa raison ; la route refuse aussi (409).
6. Portainer injoignable : aucune tuile de la liste en rouge, aucun ordre lancé.
7. `veille.json` est dans la sauvegarde de nuit et revient à la restauration.
8. Tests d'écran PC et iPhone : section Réglages, fenêtre « Démarrer », aucune erreur de page, aucun débordement horizontal.

Hors de cette version : démarrer pour un temps donné, prévenir Home Assistant, réarrêter seul.

## Arbitrages (Ultron, puis Julien, 28/11/2026)

| Point | Verdict |
|---|---|
| Démarrage à la main dans Portainer réarrêté par erreur | Changé par Julien : jamais de réarrêt seul, tuile « À traiter » |
| Appli en veille jamais mise à jour | Changé par Julien : Watchtower `INCLUDE_STOPPED`, sans la rallumer |
| Conteneur réseau d'un autre comme compagnon | Rejeté : l'arrêter couperait les autres |
| Compagnon partagé avec une appli active | Retenu : jamais arrêté |
| Case cochée pendant une mise à jour | Retenu : refusée (409) |
| Appli appelée par Home Assistant | Reporté |

