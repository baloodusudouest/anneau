# Journal des versions

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
