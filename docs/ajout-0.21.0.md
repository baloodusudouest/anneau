# L'Anneau 0.21.0 — le QNAP comme le Synology (dossier de cadrage, 27/11/2026)

## Demande de Julien
Que l'Anneau suive les versions et mette à jour les conteneurs de la stack Portainer « media » du QNAP TS-851,
comme il le fait pour la stack « homelab » du Synology.

## Contexte (audit du 27/11/2026)
- Stack « media » reprise en main le 27/11/2026 : déployée depuis le Portainer du Synology sur l'environnement QNAP
  (portainer_agent), projet Compose `media`, 14 conteneurs (gluetun + qbittorrent en `network_mode: service:gluetun`,
  sonarr, radarr, lidarr:develop, bazarr, prowlarr, jackett, flaresolverr, whisparrv3, stash, yt-dlp-webui, auto-m4b,
  watchtower). La plupart en `network_mode: host`.
- Watchtower du QNAP : `nickfedor/watchtower:1`, `WATCHTOWER_SCHEDULE=0 0 5 * * *`, API HTTP publiée sur
  `192.168.1.33:8099`, jeton propre au QNAP, `WATCHTOWER_HTTP_API_PERIODIC_POLLS=true`.
- Anneau 0.20.0 : un seul environnement Portainer (`ANNEAU_PORTAINER_ENV` ou premier Type 1, jamais l'agent du QNAP),
  `majs.py` filtré sur `com.docker.compose.project=homelab`, un seul Watchtower (`ANNEAU_WATCHTOWER_URL/JETON`,
  réseau interne), `INTERDITS` par nom, champ de tuile `conteneur:` sans machine.
- Cause de la panne du 27/11 : l'ancien horaire Watchtower (5 champs) relancé chaque heure ; gluetun recréé à 00:05,
  qbittorrent resté accroché à l'ancien gluetun (Arrêté).

## Choix de Julien (questions à choix, 27/11/2026)
1. **Configuration** : variables dédiées `ANNEAU_QNAP_PORTAINER_ENV`, `ANNEAU_QNAP_WATCHTOWER_URL`
   (`http://192.168.1.33:8099`), `ANNEAU_QNAP_WATCHTOWER_JETON`. Même Portainer et même clé `ANNEAU_PORTAINER_CLE`
   (le Portainer du Synology relaie l'agent). Projet lu : `media`.
2. **« À faire quand tu veux »** : une seule liste, chaque ligne étiquetée Synology ou QNAP.
3. **Fiches des tuiles du QNAP** : Allumer, Éteindre, Mettre à jour, comme le Synology. Une tuile `machine: Qnap`
   avec `conteneur:` est servie par l'environnement et le Watchtower du QNAP.
4. **gluetun + qbittorrent en paire** : mettre à jour gluetun relance aussi qbittorrent (recréation pour rattacher
   son réseau), puis l'Anneau vérifie que qbittorrent répond (tuile Qbittorrent, port 8080). Mettre à jour
   qbittorrent seul reste possible.
5. **Protégés** : aucun conteneur du QNAP en plus de `watchtower` (déjà interdit par son nom).
6. **Registres** : même rythme, toutes les 6 h pour les deux machines, sans compte Docker Hub.
7. **QNAP absent** (agent, Portainer ou Watchtower injoignable) : une ligne « QNAP injoignable » dans
   « À faire quand tu veux », sans bloquer le Synology.
8. **« Mis à jour depuis votre dernière visite »** : liste aussi les changements de la nuit du QNAP, étiquetés.
9. **Droits Portainer** : stack `media` en accès restreint à l'équipe « anneau » ; environnement QNAP avec les mêmes
   réglages que « Syno » (tous les « Hide … for non-administrators », pas de montages de l'hôte ni de mode privilégié
   pour les non-admins).
10. **Tuiles** : `conteneur:` sur toutes les tuiles du QNAP qui ont un conteneur (Sonarr, Radarr, Lidarr, Bazarr,
    Prowlarr, Jackett, Qbittorrent, Yt-dlp, Whisparr, Stash).

## Esquisse technique (à valider par le Conseil)
- `app/config.py` : trois variables, `qnap()`, `qnap_manque()`.
- `app/conteneurs.py` : une « machine » = (nom, Portainer avec env fixé, projet, Watchtower). Le Synology garde
  le comportement actuel ; le QNAP exige un env écrit (pas de découverte automatique).
- `app/majs.py` : parcourt les machines ; identifiant de ligne préfixé par la machine ; `/data/majs.json` migré
  (anciennes lignes = Synology) ; erreur d'une machine isolée en ligne « injoignable ».
- `app/services.py` : routage d'une tuile `conteneur:` par son champ `machine:` ; unicité de `conteneur:` par machine.
- Paire VPN : règle écrite dans le code (pas de champ générique) ou rubrique `paires:` de `services.yaml` ?
- Réglages › Connexion : fiches « Portainer QNAP » et « Watchtower QNAP » avec « Vérifier ».
- Tests : faux Portainer à deux environnements, deux faux Watchtower, cas paire, cas QNAP injoignable.

## Questions ouvertes pour le Conseil
- Paire gluetun/qbittorrent : Watchtower (`depends-on`) suffit-il, ou l'Anneau doit-il recréer qbittorrent par
  Portainer (interdit aux non-admins avec les réglages « Hide ») ? Sinon : demander à Watchtower la mise à jour de
  l'image de qbittorrent juste après, même sans nouvelle image ?
- Sécurité : API Watchtower du QNAP sur le réseau local (jeton seul) ; ouverture de toute la stack media à l'équipe.
- Variables dédiées QNAP plutôt qu'une liste de machines : dette acceptable ?
- Rien de tout cela n'a été essayé sur la vraie installation.

## Avis du Conseil (27/11/2026, cinq conseillers, relecture croisée anonyme, président)
- Accord : la mise à jour en paire par l'Anneau (choix 4) ne peut pas marcher (`network_mode: service:gluetun` devient
  `container:<id>` ; après recréation de gluetun il faut RECRÉER qbittorrent, droit refusé à « anneau ») ; la panne
  vient du Watchtower de 05:00, pas d'un clic : à régler dans la stack media ; éprouver d'abord la 0.17/0.18 ; variables
  dédiées et jeton sur le réseau local acceptables.
- Angles morts : le choix 9 rend `OPENVPN_PASSWORD` lisible par l'API avec la clé de l'Anneau ; réglages de sécurité de
  Portainer par environnement (à refaire pour le QNAP ; `host`, `cap_add`, `devices`) ; `portainer_agent` hors liste
  d'interdits ; ni retour arrière ni alerte de nuit ; vérifier l'IP de sortie après une recréation de gluetun.
- Recommandation du président : 0.21 réduite après une 0.18 validée ; Mettre à jour différé sur les fiches du QNAP ;
  paire coupée ; secret VPN sorti de la stack avant d'ouvrir l'accès.

## Arbitrages de Julien après le Conseil (27/11/2026)
- **Paire VPN** : tester `depends-on` à la main sur le QNAP d'abord (sauvegarde, IP de sortie vérifiée) ; s'il échoue,
  gluetun et qBittorrent sortent de Watchtower (`enable=false`) et se mettent à jour à la main. Rien de spécial codé.
- **Fiches du QNAP** : les trois boutons gardés (Allumer, Éteindre, Mettre à jour).
- **Secret VPN** : risque accepté (accès de l'équipe « anneau » à la stack media sans sortir `OPENVPN_PASSWORD`).
- **Ordre** : la 0.21 est codée en parallèle des essais de la 0.18 sur le Synology.
- Retenu du Conseil sans arbitrage contraire : `portainer_agent` interdit.

## Ce qui a été livré
Voir `CHANGELOG.md` (0.21.0). Jamais essayé sur la vraie installation.
