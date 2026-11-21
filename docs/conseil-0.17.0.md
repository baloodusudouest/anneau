# L'Anneau 0.17.0 — avis du conseil (21/11/2026)

Dossier : `anneau-0.17.0-dossier.md`. Cinq conseillers, dont deux qui ont vérifié sur le web (code de Portainer, documentation du contrôle d'accès, options de Watchtower) ; synthèse. Les choix de Julien ne changent pas.

## Arbitrages de Julien (21/11/2026)

- **Accès Portainer : toute la stack `homelab`** est ouverte à l'utilisateur « anneau ». Le risque est accepté : une clé volée pourrait toucher Immich. La liste d'interdits de l'Anneau est la barrière côté Anneau.
- **Tuile éteinte** : « Allumer » et « Allumer et mettre à jour ». Comme un conteneur éteint n'est plus mis à jour la nuit, l'Anneau affiche l'âge de son image.

## Réponses vérifiées

1. **`recreate` + `PullImage` est sûr.** Portainer recopie toute la configuration du conteneur : étiquettes compose, montages, nom, réseaux et leurs réglages. L'ancien est renommé `-old`, puis supprimé quand le nouveau démarre.
   - Ce que ça ne fait pas : relire `homelab.yml` (une variable changée dans la stack n'est pas prise ; c'est le travail d'un redéploiement).
   - L'identifiant change à chaque recréation : on retrouve toujours le conteneur par son nom.
   - L'ancienne image reste sur le NAS.
   - Le repli « pull seul » est retiré : si la route `recreate` manque (Portainer trop ancien), pas de bouton « Mettre à jour », et la fiche dit pourquoi.
2. **Utilisateur standard (CE)** : par défaut, il ne voit rien (une stack créée par l'admin est réservée aux administrateurs).
   - À faire dans Portainer : une équipe « anneau » contenant l'utilisateur « anneau », et la stack `homelab` passée en accès « restreint » à cette équipe (jamais « Public »).
   - **Obligatoire** : dans Réglages de Portainer, interdire aux non-admins les montages de dossiers de l'hôte et le mode privilégié. Sinon la clé pourrait créer un conteneur qui monte tout le NAS.
3. **Watchtower ne rallume pas un conteneur éteint** : `WATCHTOWER_INCLUDE_STOPPED` et `REVIVE_STOPPED` sont absents de la stack. Il ne le met pas à jour non plus.
   - `restart: unless-stopped` (cas du Bac à sable) le laisse éteint après un redémarrage du NAS. Avec `restart: always`, il se rallumerait : l'Anneau vérifie la politique et prévient sur la fiche.
   - **Un redéploiement de la stack `homelab` le rallume** : c'est dit sur la fiche et dans la note.
4. **Barrières** :
   - liste **blanche** : seuls les conteneurs marqués `conteneur:` dans `services.yaml`, au format vérifié à la lecture ;
   - **plus** la liste d'interdits, insensible à la casse, appliquée aussi au nom réel renvoyé par Portainer ;
   - **plus** l'étiquette `com.docker.compose.project=homelab` exigée sur le conteneur.

## Ce que le conseil fait ajouter ou changer

- **Origine stricte** : le cookie est commun à toutes les applis de la maison, donc « même site » ne suffit pas. Un ordre n'est accepté que si l'en-tête `Origin` est exactement l'adresse de l'Anneau (locale ou privée). La garde actuelle ne contrôle que le cookie : à écrire.
- **Journal des écritures** : il n'existe pas dans l'Anneau ; à créer (fichier dans `/data`, qui, quand, quoi, résultat).
- **État gardé sur le disque** : l'état « en cours » survit à un redémarrage de l'Anneau.
- **États lisibles sur la tuile** : « éteint » (gris, « Ouvrir » remplacé par « Allumer »), « démarrage… », « mise à jour en cours… ». Une mise à jour sans nouvelle image dit « déjà à jour ». Sinon : « image du 20/11 → 21/11 » (empreinte avant et après).
- **Panne et sauvegarde** : une appli éteinte (lue chez Portainer, `exited`) n'est ni « en panne » ni comptée dans les sauvegardes de la nuit (« éteinte, pas sauvegardée cette nuit »).
- **Suivi** : la ronde doit pouvoir être réveillée pour relire plus vite pendant 5 min après un ordre. Au-delà de 10 min : « pas de réponse, voir Portainer ».
- **Où sont les boutons** : sur une tuile vivante affichée dans le cadre, il n'y a pas de fiche « Ouvrir ». Les boutons vont aussi dans la barre d'actions du service ou dans la fiche « État ».
- **Petits plus retenus** : la mémoire et le processeur du conteneur sur la fiche (un appel `stats?stream=false`), pour voir ce qu'on libère en éteignant.

## Pour plus tard (souhaits)

- Bouton « Redémarrer » ; « Allumer et ouvrir » sur une tuile grise.
- Extinction programmée (`eteindre_apres`).
- Point sur la tuile quand une image plus récente existe.
- Interrupteurs exposés à Home Assistant.
