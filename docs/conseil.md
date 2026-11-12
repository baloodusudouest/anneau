# Avis du conseil sur le dossier de L'Anneau (12/11/2026, premier passage)

Cinq conseillers ont lu `dossier.md` séparément, cinq relecteurs ont jugé leurs réponses sans savoir qui les avait écrites. Synthèse du président. L'Anneau est une grosse appli : un second passage est prévu, sur le dossier révisé et les résultats de la sonde.

## Là où le conseil est d'accord

- **L'appli sur mesure est justifiée** (cinq sur cinq), pour une raison précise : aucun portail tout fait ne lit l'état des applis maison ni ne les met à jour. Pour de simples liens, un portail suffirait.
- **La place disque doit être surveillée** (cinq sur cinq). « Dire ce qui ne va pas » sans la seule panne réelle de la semaine (un NAS plein à 99,6 %) contredit le but. Home Assistant connaît déjà la valeur : c'est une ligne d'alerte.
- **L'Anneau ne se met jamais à jour lui-même, et ne redéploie jamais la stack** (quatre sur cinq) : redéployer relance tout, lui compris.
- **Dépendre de Home Assistant est une simplification**, à condition d'afficher « Home Assistant ne répond pas » plutôt que des voyants faux.
- **Le périmètre est trop large** pour une première version (quatre sur cinq). L'étape 2 — la liste et les voyants — ferme déjà les onglets.
- **L'inscription avec trente noms** : quatre sur cinq la jugent illisible telle quelle, surtout sur iPhone, et proposent l'anneau par familles.

## Là où il se partage

- **Les jetons Portainer.** Trois les jugent acceptables sous conditions, un les refuse, un demande de les supprimer : l'Anneau serait une vue, et les mises à jour passeraient par un déclencheur à portée unique par appli. Deux relecteurs doutent que ce déclencheur existe dans l'édition gratuite pour un conteneur seul : à sonder.
- **Par quoi commencer après la liste** : l'état commun des applis (la « file de travail de la maison »), ou les mises à jour (la douleur citée au besoin).

## Ce que la relecture a fait sortir

- **La sécurité prévue ne tient pas** (réponse jugée la plus forte par trois relecteurs sur cinq). Sans droits fins, un compte Portainer « dédié » qui peut redémarrer un conteneur peut aussi en créer un : il peut tout sur le NAS. La seule barrière, la liste des conteneurs autorisés, serait modifiable depuis Réglages, derrière un mot de passe partagé avec sept applis.
- **Le jeton Home Assistant** n'a pas de portée limitée non plus : il donne toute la maison. Personne ne l'avait vu.
- **Suivre `latest`** fait tourner, à côté des jetons, tout ce que publierait un compte de registre compromis ; et il n'y a pas de retour arrière. Il faut des versions numérotées et un geste « revenir ».
- **Revenir à l'image précédente ne défait pas une base modifiée** : sauvegarde des données de l'appli avant sa mise à jour.
- **Requêtes forgées** : des gestes derrière un simple cookie demandent une protection ; une adresse de sonde modifiable permet de faire interroger n'importe quelle adresse interne.
- **Fausses alertes** : une sonde HTTP sans seuil (redirection vers la connexion, lenteur passagère) alertera dès le premier jour. Il faut « N échecs de suite » et les réponses tenues pour saines.
- **« Ce qui cloche » mélange panne et à-faire** : une mise à jour prête n'est pas une panne ; la liste ne serait jamais vide.
- **Les onglets reviendront-ils ?** Chaque « Ouvrir » crée un onglet, chaque service garde sa connexion, et sur iPhone l'appli installée ouvre les liens hors d'elle. Aucun critère de réussite n'est écrit.
- **L'inscription est jugée sans avoir été vue**, alors que l'utilisateur y tient : une maquette avec les vrais noms, sur PC et iPhone, avant de trancher.
- **Double inventaire** : le fichier des services recopie ce que Portainer sait déjà ; il dérivera. Le préremplir depuis les conteneurs.
- **Adresses** : locales à la maison, autres hors de la maison ; dire lesquelles l'Anneau ouvre.

## Recommandation du président

1. **Livrer en trois temps.**
   - *Temps 1, la vue* : sonde des API, liste des services et voyants, écran d'ouverture, alerte de place disque, lecture de Home Assistant. Aucun jeton qui écrit. C'est ce qui ferme les onglets.
   - *Temps 2, la file de travail* : l'état commun des applis maison, d'abord les deux qui l'ont déjà, les autres au fil de leurs versions.
   - *Temps 3, les mises à jour* des applis maison, seulement si la sonde montre un moyen sûr. Redémarrer, synchroniser et allumer le PC viennent après, ou jamais si le temps 1 suffit.
2. **Sécurité des gestes**, quand ils arrivent : la liste des conteneurs touchables est dans les variables de la stack, pas dans l'interface ; l'Anneau a son propre mot de passe pour les gestes ; lecture seule par défaut ; versions numérotées et « revenir » ; protection contre les requêtes forgées ; jamais lui-même, jamais la stack.
3. **Écran d'ouverture en deux rangs** : « en panne » (service qui ne répond pas, disque presque plein, Home Assistant muet) et « à faire quand tu veux » (mise à jour prête, choses à traiter). « Tout va bien » ne dépend que du premier.
4. **L'inscription** : la garder, mais la juger sur maquette, avec les vrais noms. Proposition : l'anneau porte les familles en or sur iPhone, tous les noms sur PC ; la liste reste l'outil.
5. **Sondes** : trois échecs de suite avant d'alerter ; une réponse « demande de connexion » compte comme vivante.
6. **Fichier des services** prérempli depuis la liste des conteneurs, corrigé à la main ; pas d'éditeur dans l'interface au début.
7. **Critère de réussite** : après un mois, l'Anneau est le seul onglet épinglé, et il a signalé au moins une vraie panne avant que l'utilisateur la voie.

## La première chose à faire

La sonde, en lecture seule : ce qu'un compte Portainer non administrateur peut voir et faire ; s'il existe un moyen de recréer un seul conteneur ; quelles entités Home Assistant existent pour les deux NAS (mise à jour, place), l'iPhone et le PC.
