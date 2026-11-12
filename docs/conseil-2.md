# Second avis du conseil sur L'Anneau (13/11/2026)

Second passage, sur la version 2 du dossier (après le premier avis, la maquette et les sondes). Cinq conseillers, cinq relecteurs, synthèse du président.

## Là où le conseil est d'accord

- **Le temps 1 est codable**, à condition de trancher d'abord d'où vient l'état des machines et ce qu'est une « panne » de disque.
- **L'Anneau naîtrait rouge.** Trois volumes dépassent déjà 90 % : une alerte permanente, qu'aucun geste n'éteint, n'est plus regardée au bout de trois jours. Il faut alerter sur l'aggravation et pouvoir dire « pris en compte ».
- **Home Assistant : recevoir plutôt que lire** (quatre sur cinq). L'Anneau ne détient alors aucun jeton, et l'âge du dernier envoi devient le détecteur de silence.
- **La liste des services tenue dans un fichier suffit** au temps 1, avec sa date de révision affichée.
- **Le temps 3 se décide après le mois d'usage**, et seulement pour les mises à jour.
- **Sur iPhone, rien ne prouve que la panne se voit sans défiler** sous l'anneau.
- **Il manque la fraîcheur** : sans « dernière vérification il y a X », un écran doré mais figé ment.

## Là où il se partage

- **Le cadre.** Les cinq conseillers disent « onglet par défaut, cadre pour les applis maison ». Trois relecteurs sur cinq répondent que cela ramène les trente onglets, vide de son sens la vue réduite choisie sur maquette, et que sur un iPhone où l'Anneau est installé un lien fait sortir de l'appli.
- **L'ordre du plan.** Un conseiller déploie une liste brute d'abord et l'anneau ensuite ; un relecteur objecte que le mois d'usage serait alors jugé sur un écran que l'utilisateur n'a pas choisi.
- **Élargir dès maintenant** (prédiction « plein dans N jours », « mise à jour prête » en lecture seule) : proposé par un conseiller, jugé prématuré par trois relecteurs tant que la chaîne d'alerte n'est pas fiable.

## Ce que la relecture a fait sortir

- **Un compte Home Assistant non administrateur ne protège pas** : il pilote encore toutes les entités. La voie « lire avec un compte dédié » repose sur une protection qui n'existe pas.
- **La chaîne d'alerte n'est pas écrite** : texte de la notification, où elle mène, avis de fin de panne, niveau (une panne doit-elle passer le mode silencieux ?), remplacement de la notification précédente.
- **Pannes en cascade** : un NAS tombe, vingt services passent en panne. Une seule alerte par cause.
- **Absences normales** : PC éteint, redémarrages, entretien de nuit. Sans état « arrêt attendu », les fausses pannes seront régulières.
- **Règle de retour** : trois échecs pour ouvrir une panne, rien pour la clore ; un service qui clignote notifierait en boucle.
- **États « indisponible » de Home Assistant** au redémarrage : ni panne, ni vert.
- **Le schéma des alertes** n'a ni fin ni sourdine : à refaire avant de coder.
- **Le point de vue de la sonde** : elle part du conteneur, pas du navigateur ; elle ne teste que l'adresse locale ; un service mort derrière sa page de connexion resterait en or.
- **L'Anneau écrit sur un NAS plein à 99,6 %** : garder très peu d'historique, et libérer de la place d'abord.
- **Preuve de vie** : provoquer une panne à la mise en service, puis de temps en temps, pour vérifier que l'alerte arrive.
- **La couleur seule porte l'état** : or, rouge et bleu sur un trait fin, au soleil ou pour un daltonien.
- **En mode « recevoir »**, dire comment l'Anneau reconnaît que l'envoi vient bien de Home Assistant, et contrôler qu'un envoi vide ou raté se voit.

## Recommandation du président

1. **Home Assistant pousse.** Une automatisation envoie chaque minute l'état des machines à l'Anneau, avec un secret partagé ; la réponse lui rend le nombre de pannes, qu'il notifie. L'Anneau ne détient aucun jeton aux temps 1 et 2. Un envoi vieux de plus de cinq minutes s'affiche « Home Assistant muet ». Les valeurs « indisponible » ne sont ni panne ni vert : « inconnu ».
2. **Disques : l'aggravation, pas le seuil.** L'Anneau reprend l'état que chaque NAS donne lui-même. Une panne s'ouvre quand l'état empire ou qu'un palier est franchi (90, 95, 98 %). « Pris en compte » la met en sourdine jusqu'au palier suivant. Au premier lancement, l'état actuel est enregistré comme connu : l'Anneau ne naît pas rouge.
3. **Garder le cadre choisi sur maquette, sans promettre plus qu'il ne tient.** Chaque service a un mode dans le fichier : *cadre* (applis maison et services testés), ou *fenêtre*. En mode fenêtre, « Ouvrir » réutilise toujours la même fenêtre pour un service donné, pour que les onglets ne se multiplient pas. À essayer sur un vrai iPhone avant de coder la vue réduite ; si le cadre n'y tient pas ses sessions, l'iPhone passe tout en mode fenêtre.
4. **Ordre** : squelette, fichier des services, sonde et **anneau porté depuis la maquette** ; déploiement tout de suite ; puis la poussée de Home Assistant et la notification ; puis la vue réduite. Le mois d'usage se juge sur l'écran choisi.
5. **Cycle de vie d'une panne**, à écrire avant de coder : ouverte après trois échecs, close après trois réussites ; une notification à l'ouverture, une à la clôture, remplacée et non empilée ; une panne par cause (une machine qui ne répond pas emporte ses services) ; « arrêt attendu » pour le PC de calcul.
6. **Fraîcheur partout** : heure de la dernière sonde, âge du dernier envoi de Home Assistant, date du fichier des services.
7. **Coupé du temps 1** : données de l'iPhone, écran Connexion (une ligne dans Réglages), seuils réglables à l'écran. **Reporté** : prédiction, « mise à jour prête », temps 3.
8. **État lisible sans la couleur** : le mot au centre et la liste le disent déjà ; sur l'anneau, à trancher sur maquette avec l'utilisateur.
9. **Preuve de vie** : à la mise en service, arrêter un service sans enjeu et vérifier que la notification arrive, puis qu'elle se clôt.

## La première chose à faire

Écrire le cycle de vie d'une panne et le nouveau schéma des alertes dans le dossier, puis coder l'étape 1 : squelette, fichier des services, sonde, anneau.
