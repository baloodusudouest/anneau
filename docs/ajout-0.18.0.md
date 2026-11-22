# L'Anneau 0.18.0 — les applis à mettre à jour dans « À faire quand tu veux »

Demande de Julien, 22/11/2026, devant la ligne « Mise à jour du système disponible pour Synology (DSM 7.4.1-90080 Update 2) » : « il faudrait pouvoir voir quelles sont les applications qu'il faut mettre à jour aussi ».

## Choix de Julien (22/11/2026)

| Question | Choix |
|---|---|
| Lesquelles | Toutes celles de la stack homelab |
| Affichage | Une ligne groupée, qui se déplie |
| Clic | Un bouton « Mettre à jour » sur la ligne |
| Détection | Par Portainer ; s'il ne sait pas le faire en version CE, l'Anneau interroge lui-même les registres |
| Bouton pour les protégés | Oui, tous, avec double confirmation pour les protégés et les bases de données |
| Versions figées | Les dire, sans bouton |
| Conseil | Sans Conseil |

## Ce qui a été vérifié avant de coder

- Portainer CE (code public du 20/11/2026) contient le calcul « image à jour ou non » (`api/docker/images/status.go`), mais aucune route de la version gratuite ne le donne : `GET …/containers/{id}/image_status` n'existe que dans la version payante. D'où la lecture directe des registres.
- Watchtower met déjà à jour chaque nuit à 05:00 tous les conteneurs en marche de la stack (`WATCHTOWER_LABEL_ENABLE=false`). La liste montre donc surtout : ce qui est sorti depuis 05:00, les conteneurs arrêtés, les versions figées.

## Comment ça marche

1. Toutes les 6 h (et sur « Vérifier maintenant ») : liste des conteneurs de la stack chez Portainer, empreinte de leur image (`RepoDigests`), empreinte publiée (`HEAD` du manifeste, jeton anonyme du registre).
2. Empreinte différente : ligne « à mettre à jour ». Étiquette = numéro de version et ligne `figees:` dans `services.yaml` : comparaison avec la dernière publication GitHub.
3. « Mettre à jour » : identifiant de ligne → conteneur relu chez Portainer → `POST /v1/update?image=…` à Watchtower → suivi à l'état réel.
4. Conteneur protégé ou base de données : seconde confirmation ; le serveur exige `protege: true`.

## Limites

- Image sans étiquette de version et sans tuile reliée à un dépôt : « nouvelle image publiée », sans numéro.
- Conteneur arrêté : pas de bouton (Watchtower ignore les conteneurs arrêtés).
- Conteneurs du QNAP : hors de la stack homelab, pas dans la liste.
- Jamais essayé sur la vraie installation : accès réseau du conteneur aux registres, limite de Docker Hub, mise à jour de l'Anneau par lui-même.
