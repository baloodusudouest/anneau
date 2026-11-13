# Journal des versions

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
