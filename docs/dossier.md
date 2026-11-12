# Dossier de L'Anneau — une seule porte pour les machines, les services et les applis de la maison

Version 2, du 13/11/2026. Elle remplace la version du 12/11 (dans l'historique du dépôt) et intègre le premier avis du conseil (`conseil.md`), la maquette et les sondes. Rien n'est codé.

## 1. Besoin

Aujourd'hui : une trentaine d'onglets ouverts en permanence, rangés par machine, et un passage par Portainer à chaque nouvelle version d'une appli maison. Le but : une seule page, sur iPhone et sur PC, qui dit ce qui ne va pas, ouvre n'importe quel service d'un geste, et plus tard fait quelques gestes d'entretien.

- **Nom : L'Anneau.** Une appli maison au format commun, pour un seul utilisateur, derrière le mot de passe commun.
- **Trois temps de livraison** :
  1. *La vue* : les services, leur état, ce qui cloche. Aucun pouvoir d'écrire.
  2. *La file de travail* : ce qui est « à traiter » dans chaque appli maison, au même endroit.
  3. *Les mises à jour* des applis maison, une par une ; puis redémarrer un conteneur, lancer une synchro, allumer le PC de calcul.
- **Deux rangs d'alerte** : « en panne » (un service ne répond plus, un volume est presque plein, Home Assistant se tait) et « à faire quand tu veux » (mise à jour prête, choses à traiter). « Tout va bien » ne dépend que du premier.
- **Alertes** dans l'Anneau et sur l'iPhone par Home Assistant, qui veille aussi que l'Anneau répond.
- **Adresses** : ouvert par son adresse du réseau privé, l'Anneau ouvre tous les services par leur adresse du réseau privé ; sinon par leur adresse locale.
- **iOS** : l'Anneau s'installe sur l'écran d'accueil ; il affiche quelques données du téléphone remontées par Home Assistant.
- **Critère de réussite**, après un mois : l'Anneau est le seul onglet épinglé, et il a signalé au moins une vraie panne avant que l'utilisateur la voie.

L'inventaire réel (une trentaine de services, six familles) n'est pas dans ce dépôt : il est dans le fichier des services de l'installation.

## 2. Technique

**Pile.** Celle du socle : FastAPI, SQLite, Svelte 5, Tailwind 4. Un conteneur sur le NAS principal, mot de passe commun obligatoire, mise à jour automatique coupée.

**Ce que les sondes ont établi** (lecture seule, par le navigateur ; détail hors dépôt) :

- **Un seul Portainer**, édition gratuite, pilote les deux NAS (le second par un agent). **Un seul compte, administrateur** ; cette édition n'a pas de droits fins. Aucun déclencheur n'est défini.
- **Recréer un seul conteneur avec retéléchargement de l'image marche** (essayé sur le conteneur du squelette : 29 secondes, le conteneur reste dans sa stack). Les mises à jour une par une sont donc faisables sans redéployer la stack. Non vu : le cas d'une image réellement plus récente.
- Sur le second NAS, la plupart des conteneurs sont lancés hors de Portainer : visibles et redémarrables, pas redéployables.
- Deux services ne sont pas des conteneurs (le serveur de médias, Home Assistant).
- **Home Assistant connaît les deux NAS** : pour le principal, la mise à jour du système et la place de chaque volume ; pour le second, l'état et la place, mais pas de mise à jour du système. Il connaît l'iPhone (batterie, stockage, réseau) et sait réveiller le PC.
- **Aujourd'hui les trois volumes du NAS principal dépassent 90 %** (jusqu'à 99,6 %) et sont en état « attention » ; le second NAS est à 85 %, en « avertissement ».
- **Affichage dans un cadre** : quatre services l'acceptent (dont une appli maison), trois le refusent (dont Home Assistant), un reste à tester ; ceux du second NAS n'ont pas pu être testés.
- L'adresse HTTPS de Home Assistant présentait une erreur de certificat depuis le navigateur.

**Le fichier des services** (`/data/services.yaml`, hors dépôt) : familles ; pour chaque service son nom, sa famille, ses deux adresses (locale, réseau privé), sa sonde, son icône, et s'il accepte le cadre. Prérempli depuis la liste des conteneurs, corrigé à la main ; pas d'éditeur dans l'interface au début. Un exemple inventé est dans le dépôt.

**Les sondes de l'Anneau**, toutes les minutes, avec un délai court :

- *répond ou non* : une demande HTTP sur l'adresse locale de chaque service ; une réponse qui demande une connexion compte comme vivante ; **trois échecs de suite** avant d'alerter ;
- *appli maison* : `/health` (version), puis au temps 2 l'adresse d'état commune à jeton (compteurs « à traiter », dernière synchro, traitement en cours) ;
- *machines* : Home Assistant (place des volumes, état, mise à jour du système, iPhone, PC).

**Home Assistant dans l'autre sens** : une adresse d'état de l'Anneau, à jeton, lue par Home Assistant chaque minute (nombre de pannes, liste courte) ; Home Assistant notifie, et s'alarme si l'Anneau se tait.

**Les gestes (temps 3).** Par l'appel de recréation de Portainer pour les mises à jour ; redémarrage par Portainer ; synchro par l'adresse à jeton de chaque appli ; réveil du PC par Home Assistant. Jamais l'Anneau lui-même, jamais la stack entière. Refus si l'appli dit « traitement en cours ». Versions numérotées et geste « revenir ». Sauvegarde des données de l'appli avant sa mise à jour.

**Sécurité.**

- Temps 1 et 2 : l'Anneau ne détient **aucun jeton Portainer**. La liste des services vient du fichier, pas de Portainer.
- Jeton Home Assistant : il donne toute la maison, et Home Assistant n'a pas de jeton en lecture seule. Deux voies : un compte Home Assistant non administrateur pour l'Anneau, ou l'inverse — Home Assistant **pousse** l'état des machines vers l'Anneau, qui ne détient alors aucun jeton (question ouverte).
- Temps 3 : le jeton Portainer est administrateur des deux NAS. Protection : gestes nommés seulement ; liste des conteneurs touchables dans les variables de la stack, jamais modifiable depuis l'appli ; **second mot de passe**, propre à l'Anneau, pour tout geste ; lecture seule par défaut ; protection contre les requêtes forgées ; journal ; un test par geste fige ce qui est demandé à Portainer, un autre prouve qu'un conteneur non listé ne peut pas être touché.
- Les jetons restent dans les variables de la stack. Réseau local et réseau privé seulement.

## 3. Parcours des clics et des écrans

**L'Anneau** (ouverture) — un anneau porte les six familles, en texte. Au centre : le nombre de pannes, puis ce qui est à faire. Sous l'anneau (ou à côté sur PC) : la liste « en panne », puis « à faire quand tu veux », chaque ligne avec son geste (ouvrir ; plus tard redémarrer, mettre à jour).

**Toucher une famille** la déplie : ses services montent de l'anneau et se rangent au-dessus du mot, en arcs. Sur iPhone, ils se déplient sous l'anneau, en pastilles.

**Toucher un service** : l'anneau file en haut à gauche et devient le bouton de retour ; dessous, une colonne d'icônes, une par famille ; en haut, les services de la famille en pastilles (icône et nom) ; au centre, le service — affiché dans un cadre s'il l'accepte, sinon son état (répond, version, depuis quand) et un bouton « Ouvrir ».

**Mises à jour** (temps 3) — une ligne par appli maison : version en place, version disponible, ce qui change, « Mettre à jour » avec le second mot de passe.

**Connexion** — Home Assistant, plus tard Portainer et le registre des images : état, dernière lecture, « Vérifier ». **Réglages** — recharger le fichier des services, seuils d'alerte, journal, version, déconnexion.

## 4. Design

Arrêté sur maquette cliquable (hors dépôt : elle porte la vraie liste).

- Format commun pour les fonds et la structure ; **or** pour la couleur.
- **L'anneau porte les familles en texte seul**, à la plume fine (police calligraphique en lettres latines ; ni l'écriture ni le dessin d'une œuvre existante ne sont repris). La moitié basse est retournée pour se lire à l'endroit.
- **États portés par le texte** : or quand tout répond ; **rouge lave**, avec un halo qui couve, pour une panne ; **bleu spectral** pour une action à faire. Une famille prend l'état de son service le plus mal en point.
- **Vue réduite** : un anneau d'or lisse en haut à gauche, une colonne d'icônes dessous.
- **Noms des services** : première lettre en majuscule.
- **Icônes** : les applis maison gardent la leur ; pour les autres, celle que le service fournit lui-même, sinon un pictogramme générique.
- Animations : le dépliage d'une famille, le déplacement de l'anneau, le halo de la panne. Coupées si l'appareil demande moins d'animations.

## 5. Schéma de données

```
services.yaml   familles ; services (nom, famille, adresse locale, adresse du réseau privé, sonde, icône, cadre oui/non)
sondes          service, le, répond, délai, version — gardées quelques jours
machines        dernière lecture de Home Assistant : volumes (pourcentage, état), mises à jour, iPhone, PC
pannes          cause (service, machine, volume, Home Assistant muet), ouverte_le, close_le, prise_en_compte_le, notifiée
a_faire         sorte, service, depuis
journal         le, geste, service, résultat — sans secret (temps 3)
```

## 6. Plan d'implémentation

**Temps 1 — la vue**

1. Squelette depuis le socle : nom, couleur, icône, mot de passe ; fichier des services et son exemple ; sonde « répond ou non » avec ses trois échecs.
2. L'écran d'ouverture : l'anneau des familles, le dépliage, les deux rangs.
3. La vue réduite : colonne d'icônes, pastilles, cadre ou « état + Ouvrir » ; les deux jeux d'adresses.
4. Home Assistant : place et état des volumes, mise à jour du système, iPhone, PC ; adresse d'état de l'Anneau, notification et veille. Mise à jour du document maître de Home Assistant.
5. Déploiement dans la stack, un mois d'usage.

**Temps 2** — l'état commun des applis maison, écrit dans le socle, branché appli par appli au fil de leurs versions.

**Temps 3** — mises à jour une par une, puis les autres gestes, avec la sécurité décrite plus haut.

Tests : faux services, faux Home Assistant ; le découpage panne / à faire ; les trois échecs ; le choix d'adresse selon l'adresse d'appel ; tests d'écran PC et iPhone (dépliage, vue réduite, cadre refusé).

## Décisions prises après le second passage (13/11/2026)

Avis complet : `conseil-2.md`.

- **Home Assistant envoie son état à l'Anneau** (une automatisation, chaque minute, avec un secret partagé). L'Anneau ne détient aucun jeton de Home Assistant. Sans envoi depuis cinq minutes : « Home Assistant muet ». Une valeur « indisponible » n'est ni une panne ni un vert.
- **Disques : seuil fixe à 99,8 %** (choix de l'utilisateur, contre la recommandation « alerter sur l'aggravation »). En dessous, un volume n'est pas une panne, quel que soit l'état que le NAS lui donne. Le seuil est dans le fichier des services.
- **Cadre si possible, sinon fenêtre.** Chaque service a son mode dans le fichier. En mode fenêtre : son état, et « Ouvrir » qui réutilise toujours la même fenêtre pour ce service. **Home Assistant sera réglé pour accepter le cadre** (une ligne de configuration, à inscrire dans le document maître ; elle retire une protection contre l'affichage de Home Assistant dans une page tierce, acceptable sur un réseau fermé). À essayer sur un vrai iPhone avant de coder la vue réduite.
- **iPhone** : l'ordre entre l'anneau et la liste des pannes se choisit sur une maquette à deux versions.
- **Repris de la recommandation du président**, sans objection : l'anneau est codé dès la première étape, depuis la maquette ; déploiement tôt ; cycle de vie d'une panne (trois échecs pour l'ouvrir, trois réussites pour la clore, une notification à l'ouverture et une à la clôture, une panne par cause, « arrêt attendu » pour le PC) ; fraîcheur affichée partout ; données de l'iPhone, écran Connexion et seuils réglables à l'écran coupés du temps 1 ; preuve de vie à la mise en service.

## Questions ouvertes pour le second passage au conseil

1. **Home Assistant : lire ou recevoir ?** L'Anneau lit Home Assistant avec un jeton (simple, mais le jeton est puissant), ou Home Assistant pousse l'état vers l'Anneau (aucun jeton côté Anneau, mais des automatisations à écrire et à entretenir) ?
2. **Les seuils.** Trois volumes dépassent déjà 90 % : avec ce seuil l'Anneau serait « en panne » en permanence et l'alerte perdrait son sens. Quelle règle : seuil plus haut, alerte sur la variation, alerte « connue » qu'on met en sourdine ?
3. **Le cadre.** Trois services sur sept le refusent, et par le réseau privé en HTTPS un service en HTTP ne s'affichera pas. Faut-il garder le cadre comme mode normal, ou ouvrir un onglet par défaut et réserver le cadre aux applis maison ?
4. **La liste des services sans Portainer** au temps 1 : un fichier tenu à la main suffit-il, ou dérivera-t-il ?
5. **L'anneau comme écran d'ouverture** : sur iPhone, avec les deux rangs d'alerte en dessous, l'essentiel est-il visible sans défiler ?
6. **Le temps 3 vaut-il encore le risque**, maintenant qu'on sait que le jeton est administrateur des deux NAS et que la recréation marche ?
7. **Que manque-t-il** au temps 1 pour qu'il soit utilisable dès la première semaine ?
