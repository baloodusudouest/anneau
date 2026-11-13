# Journal des versions

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
