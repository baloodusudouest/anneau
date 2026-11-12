# Dossier de L'Anneau — une seule porte pour les machines, les services et les applis de la maison

Écrit le 12/11/2026 à partir du grill (six tours). Rien n'est codé, aucune API n'a encore été sondée.

## 1. Besoin

Aujourd'hui : une trentaine d'onglets ouverts en permanence, rangés en trois groupes (le NAS principal, Home Assistant, le second NAS), et un passage par Portainer à chaque nouvelle version d'une appli maison. Le but : une seule page, sur iPhone et sur PC, qui dit ce qui ne va pas, ouvre n'importe quel service d'un geste, et fait les quelques gestes d'entretien courants.

Décidé au grill :

- **Nom : L'Anneau.** Une appli maison au format commun, pour un seul utilisateur, derrière le mot de passe commun. Elle remplace le portail tout fait envisagé auparavant.
- **Périmètre : surveiller et faire des gestes simples.** Pas d'administration complète, pas de SSH.
- **Écran d'ouverture : ce qui cloche en haut**, puis tous les services, par machine, à ouvrir d'un geste.
- **Gestes, toujours avec confirmation** :
  - mettre à jour une appli maison (retélécharger son image et la relancer), **une par une**, version en place et nouvelle version annoncées avec le journal des changements, jamais pendant un traitement en cours ;
  - redémarrer un conteneur (sur les deux NAS) ;
  - lancer les synchros des applis maison ;
  - allumer le PC de calcul.
- **Surveillance : l'Anneau sonde lui-même**, sans brique de supervision en plus.
- **Second NAS : un voyant « répond ou non » et un lien par service** ; redémarrage possible, pas de mise à jour.
- **NAS : seulement les mises à jour du système disponibles.** La place, la santé des disques, les sauvegardes, la charge n'ont pas été retenues (elles se regardent dans l'interface des NAS).
- **Alertes : dans l'Anneau, et sur l'iPhone par Home Assistant.** Home Assistant veille aussi que l'Anneau répond.
- **iOS : les deux** — l'Anneau s'installe sur l'écran d'accueil et ouvre les applis de l'iPhone par des liens ; il affiche des données du téléphone remontées par Home Assistant.
- **Où il tourne : sur le NAS principal, dans la stack.**
- **Thème : un clin d'œil.** Un anneau autour duquel les noms et les icônes des services sont écrits en or, comme une inscription gravée. Dessin original : ni images, ni écriture, ni noms repris des films.
- **L'Anneau passe avant le projet d'ajout de nouveaux services** (gestion de documents, recettes, flux) : la liste des services est un fichier de réglages, les nouveaux s'y ajoutent.

**L'inventaire** (une trentaine de services) n'est pas dans le dépôt : il est dans le fichier de réglages de l'installation. Par familles : sept applis maison ; photos et généalogie (trois) ; médias et lecture sur le NAS principal (six) ; Home Assistant ; sur le second NAS, une douzaine de services de gestion et de récupération de médias ; les machines (deux NAS, leurs deux Portainer, le réseau privé, le PC de calcul).

## 2. Technique

**Pile.** Celle du socle : FastAPI, SQLite, Svelte 5, Tailwind 4. Un conteneur, mot de passe commun obligatoire, mise à jour automatique coupée (l'Anneau agit sur les autres conteneurs).

**Le fichier des services** (`/data/services.yaml`, hors dépôt) : les machines ; pour chaque service son nom, son icône, sa famille, son adresse à ouvrir, sa sonde, et le conteneur qui le porte. Modifiable depuis Réglages. Un fichier d'exemple inventé est dans le dépôt.

**Les sondes**, toutes les minutes, en lecture seule, avec un délai court :

- *répond ou non* : une demande HTTP sur l'adresse du service (tous les services) ;
- *appli maison* : `/health` (version) et une adresse d'état commune, ouverte par un jeton, qui donne les compteurs « à traiter », la dernière synchro et « un traitement est en cours ». Deux applis l'ont déjà sous une forme voisine ; il faut l'écrire une fois dans le socle et l'ajouter aux autres ;
- *conteneurs* : l'API de Portainer de chaque NAS (liste, état, image) ;
- *mises à jour des NAS, données de l'iPhone, PC de calcul* : lues dans **Home Assistant** (API REST, jeton), qui connaît déjà ces machines par ses intégrations. L'Anneau ne parle pas directement aux API des NAS.

**Nouvelle version d'une appli maison.** Comparer l'empreinte de l'image en service (Portainer) à celle de `latest` dans le registre ; lire le journal des changements dans le dépôt de l'appli.

**Les gestes.**

- *Redémarrer* : API de Portainer, sur une liste de conteneurs autorisés écrite dans le fichier des services.
- *Mettre à jour une appli* : par Portainer, retélécharger l'image et recréer le conteneur (à sonder : l'adresse « recréer avec retéléchargement » de Portainer, ou à défaut le redéploiement de la stack). Refusé si l'appli dit « traitement en cours ». Après : attendre `/health`, afficher la nouvelle version, sinon dire que l'appli ne redémarre pas.
- *Synchroniser* : l'adresse à jeton de chaque appli.
- *Allumer le PC* : par Home Assistant (le conteneur ne peut pas envoyer lui-même le signal de réveil sur le réseau).

**Home Assistant dans l'autre sens** : une adresse d'état de l'Anneau, à jeton, que Home Assistant lit toutes les minutes (nombre d'alertes, liste courte). Home Assistant notifie, et s'alarme si l'Anneau ne répond plus.

**Sécurité — le point dur.** L'Anneau détient les jetons de deux Portainer (qui peuvent tout sur les deux NAS), un jeton Home Assistant et les jetons des applis. Mesures prévues :

- aucun accès direct au moteur Docker ; tout passe par Portainer, avec un compte dédié ;
- l'Anneau n'expose que des gestes nommés, sur des conteneurs listés : pas d'adresse générique « fais ceci dans Portainer » ;
- mode lecture seule par variable (refus à l'adresse appelée et au plus près de l'appel) ;
- chaque geste est journalisé ; un test fige ce que chaque geste demande à Portainer ;
- les jetons restent dans les variables de la stack, jamais dans le fichier des services ni dans le navigateur ;
- réseau local et réseau privé seulement.

## 3. Parcours des clics et des écrans

Cinq entrées : **Anneau**, **Services**, **Mises à jour**, **Connexion**, **Réglages**. Rail sur PC, pilule sur iPhone.

**Anneau** (ouverture) — en haut, « Tout va bien » ou la liste de ce qui cloche : service qui ne répond pas, mise à jour prête, choses à traiter dans une appli maison (avec leur nombre), système d'un NAS à mettre à jour, PC éteint alors qu'un calcul attend. Chaque ligne a son geste (ouvrir, redémarrer, mettre à jour). Dessous, l'anneau : les services écrits en or sur le cercle, un voyant par service ; toucher un nom ouvre le service. Sur iPhone, l'anneau montre les familles, et toucher une famille déploie ses services en liste.

**Services** — la liste complète, par machine puis par famille : icône, nom, voyant, version quand elle est connue, « Ouvrir », et « Redémarrer » pour les conteneurs autorisés. Recherche. Les liens vers les applis de l'iPhone sont une famille de plus.

**Mises à jour** — une ligne par appli maison : version en place, version disponible, ce qui change (journal), et « Mettre à jour » avec sa confirmation. Les applis dont un traitement est en cours sont grisées, avec la raison. Les mises à jour des systèmes des NAS sont annoncées ici, avec un lien vers leur interface.

**Connexion** — les deux Portainer, Home Assistant, le registre des images : état, dernière lecture, droits constatés, « Vérifier ». L'iPhone et le PC de calcul (ce que Home Assistant en dit, « Allumer »).

**Réglages** — le fichier des services (ajouter, retirer, ranger), les conteneurs autorisés au redémarrage, le journal des gestes, la version, la déconnexion.

## 4. Design

Format commun (neutres chauds, sombre par défaut, Inter). **Couleur : or** (à fixer à l'écran ; trois applis de la famille ont déjà une teinte jaune ou ocre, il faudra un or plus froid ou plus pâle pour s'en distinguer).

**Signature : l'inscription.** Un cercle fin ; les noms des services courent le long du cercle en lettres d'or (texte sur un tracé, capitales espacées d'un caractère à empattements), séparés par leurs icônes. Un service qui ne répond pas s'éteint (gris), un service en alerte passe en couleur d'alerte. Au centre : « Tout va bien » ou le nombre de choses à voir. L'anneau tourne lentement au chargement puis s'immobilise ; aucune autre animation.

**Icône** : un anneau d'or fin sur fond sombre, avec quelques traits gravés.

## 5. Schéma de données

```
services.yaml   machines, familles, services (nom, icône, adresse, sonde, conteneur, autorisé au redémarrage, lien iPhone)
sondes          service, le, répond, délai, version, détail — gardées quelques jours
alertes         sorte, service, depuis, vue
versions        appli, en service, disponible, lue_le
journal         le, geste, service, résultat — sans secret
```

## 6. Plan d'implémentation

1. **Sonde des API**, en lecture seule : Portainer (liste des conteneurs, droits d'un compte dédié, adresse de recréation), Home Assistant (entités des NAS, de l'iPhone, du PC), registre des images.
2. **Squelette** depuis le socle, fichier des services, sonde « répond ou non », écran Services : dès cette étape, l'Anneau remplace les onglets.
3. **L'écran Anneau** : ce qui cloche, et l'inscription.
4. **L'état commun des applis maison** : écrit dans le socle, ajouté à chaque appli ; compteurs « à traiter » dans l'Anneau.
5. **Home Assistant** : lecture (NAS, iPhone, PC), adresse d'état de l'Anneau, notification et veille. Mise à jour du document maître de Home Assistant.
6. **Gestes** : redémarrer, synchroniser, allumer le PC.
7. **Mises à jour** des applis maison.
8. Liens iPhone, installation sur l'écran d'accueil, un mois d'usage.

Tests : faux Portainer, faux Home Assistant, faux services ; un test par geste fige ce qui est demandé à Portainer ; un test prouve qu'un conteneur non listé ne peut pas être touché ; tests d'écran sur PC et iPhone.

## Décisions prises après le conseil (12/11/2026, premier passage)

Avis complet : `conseil.md`. Ce qui change par rapport au texte ci-dessus :

- **Trois temps.** 1) *La vue* : sonde des API, liste des services et voyants, écran d'ouverture, alerte de place, lecture de Home Assistant ; aucun pouvoir d'écrire. 2) *La file de travail* : l'état commun des applis maison, d'abord celles qui l'ont déjà. 3) *Les mises à jour* des applis maison, si la sonde montre un moyen sûr ; redémarrer, synchroniser, allumer le PC ensuite.
- **Alerte de place libre** sur les deux NAS (au-delà de 90 %), lue dans Home Assistant : ajoutée, contre le choix du grill.
- **Sécurité des gestes** : un second mot de passe, propre à l'Anneau, pour tout geste ; la liste des conteneurs touchables est dans les variables de la stack, jamais modifiable depuis l'appli ; lecture seule par défaut ; versions numérotées et « revenir » ; protection contre les requêtes forgées ; jamais lui-même, jamais la stack.
- **Écran d'ouverture en deux rangs** : « en panne » et « à faire quand tu veux ». « Tout va bien » ne dépend que du premier.
- **L'inscription** se juge sur une maquette avec les vrais noms, sur PC et iPhone, avant de coder.
- **Sondes** : trois échecs de suite avant d'alerter ; une réponse qui demande une connexion compte comme vivante. « Home Assistant ne répond pas » est affiché tel quel.
- **Fichier des services** prérempli depuis la liste des conteneurs, corrigé à la main ; pas d'éditeur dans l'interface au début.
- **Critère de réussite** : après un mois, l'Anneau est le seul onglet épinglé, et il a signalé au moins une vraie panne avant que l'utilisateur la voie.
- **Second passage au conseil** après la sonde et la maquette.

## Design arrêté sur maquette (12/11/2026)

Maquette cliquable : `maquette/anneau-maquette-2.html`. Choix de l'utilisateur, « pour le moment » :

- **L'anneau porte les familles, en texte seul**, écrites à la plume fine (police calligraphique en lettres latines ; ni l'écriture ni le dessin de l'inscription des films ne sont repris). La moitié basse est retournée pour se lire à l'endroit.
- **Toucher une famille la déplie** : ses services montent de l'anneau et se rangent au-dessus du mot, en un ou plusieurs arcs, en texte seul. Sur iPhone, ils se déplient sous l'anneau, en pastilles.
- **Toucher un service** : l'anneau file en haut à gauche et devient le bouton de retour ; dessous, **une colonne d'icônes, une par secteur** (sans les noms) ; en haut, les services du secteur en pastilles, avec leur icône et leur nom ; au centre, le service ouvert dans un cadre (ou son état et « Ouvrir » s'il refuse d'être affiché dans une autre page — à sonder).
- **États, portés par le texte** : or quand tout répond ; **rouge lave**, avec un halo qui couve, pour une panne ; **bleu spectral** pour une action à faire. Une famille prend l'état de son service le plus mal en point. Au centre : le nombre de pannes, puis les actions à faire.
- **Noms des services** : première lettre en majuscule, jamais tout en majuscules.
- **Icônes** : les applis maison gardent la leur ; pour les autres, celle que le service fournit lui-même, sinon un pictogramme générique.
- **Six familles** : Proches (contacts, arbre généalogique, kit d'urgence), Photos (photothèque, numérisation, et les quatre applis maison de photos), Médias, Maison, Collecte, Machines. Le squelette des applis n'est pas dans l'Anneau. La répartition exacte est dans le fichier des services, hors dépôt.

## Ajouts du 13/11/2026

- **Adresses** : si l'Anneau est ouvert par son adresse du réseau privé, tous les services s'ouvrent par leur adresse du réseau privé ; sinon par leur adresse locale. Chaque service a donc deux adresses dans le fichier des services, et l'Anneau choisit d'après l'adresse par laquelle il est lui-même appelé.
- **Icône de la vue réduite** : un anneau d'or lisse et brillant, sans aucune inscription.
- **Première sonde de Portainer** (lecture seule, par le navigateur) — ce qu'elle change au dossier :
  - **Un seul Portainer** (édition gratuite, 2.45) pilote les deux NAS : le second par un agent. Un seul jeton suffira, pas deux.
  - **Un seul compte, administrateur.** Aucun compte restreint n'existe ; l'édition gratuite n'a pas de droits fins. Le « compte dédié » du dossier ne protège donc de rien : la protection reste la liste figée et le second mot de passe.
  - **Aucun déclencheur** (webhook) n'est défini.
  - Sur le NAS principal, tout est dans une seule stack ; sur le second, une stack connue de Portainer et un ensemble de conteneurs lancés hors de Portainer (il peut les voir et les redémarrer, pas les redéployer).
  - Deux services de la liste ne sont pas des conteneurs (le serveur de médias, Home Assistant) : pour eux, seulement « répond ou non ».
  - **Affichage dans un cadre** (cinq services testés) : deux l'acceptent, deux le refusent (« même origine seulement »), un reste à tester. Le cadre « état + Ouvrir » sera donc courant, pas une exception ; les applis maison, elles, pourront l'autoriser.
  - **Reste à sonder** : l'appel « recréer un conteneur » (non essayé, il écrit), Home Assistant, et le cas du réseau privé en HTTPS, où un service en HTTP ne peut pas être affiché dans un cadre.

- **Sonde de Home Assistant** (lecture seule, 13/11/2026) :
  - Le NAS principal y est connu : une entité « mise à jour du système », et pour chaque volume son état et son pourcentage utilisé. L'alerte de place et la mise à jour du système se lisent donc sans rien ajouter.
  - **Le second NAS n'y est pas** : aucune entité. Il faudra y ajouter son intégration, ou renoncer pour lui à la place et aux mises à jour.
  - L'iPhone y est (batterie, stockage, réseau), et un bouton de réveil du PC existe.
  - L'adresse HTTPS de Home Assistant présente une erreur de certificat depuis ce navigateur ; la sonde est passée par l'adresse locale. À régler avant de compter sur les adresses du réseau privé.
- **Essai de l'appel « recréer un conteneur »** (13/11/2026, sur le conteneur du squelette, avec l'accord de l'utilisateur) : accepté par Portainer en 29 secondes, avec retéléchargement de l'image. Le conteneur revient sous un nouvel identifiant, toujours rattaché à sa stack, avec son port. Le temps 3 (mises à jour une par une) est donc faisable sans redéployer la stack. Non vérifié : le cas où une image plus récente existe réellement, et le retour à « sain » du conteneur (encore « en démarrage » 48 secondes après).

## Questions ouvertes pour le conseil

1. **Une appli sur mesure est-elle justifiée**, quand des portails tout faits existent, pour un seul utilisateur ?
2. **Les jetons Portainer** : le risque d'une appli web qui peut redémarrer et recréer des conteneurs sur deux NAS est-il acceptable, et que manque-t-il aux mesures prévues ?
3. **Mettre à jour une appli depuis l'Anneau** : par recréation du conteneur, par redéploiement de la stack, ou faut-il y renoncer ? Et l'Anneau peut-il se mettre à jour lui-même ?
4. **Dépendre de Home Assistant** pour l'état des NAS, l'iPhone, le PC et les alertes : simplification ou fragilité ?
5. **L'inscription en anneau** avec une trentaine de services : lisible, surtout sur iPhone ? Signature ou gadget ?
6. **Ne pas surveiller la place ni les sauvegardes** (choix de l'utilisateur, alors qu'un NAS était plein à 99,6 % cette semaine) : faut-il insister ?
7. **Le périmètre** est-il trop large pour une première version ? Qu'enlever ?
