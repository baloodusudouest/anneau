# L'Anneau

Une seule porte pour les machines, les services et les applis de la maison : un anneau porte les familles de services, dit ce qui est en panne et ce qui est à faire, et ouvre n'importe quel service d'un geste.

Version 0.1 : **la vue**. L'Anneau lit (une demande par service, chaque minute) et reçoit (Home Assistant lui envoie l'état des machines). Il n'écrit nulle part hors de son dossier et ne détient aucun jeton d'un autre service.

## Mise en place

1. Ajouter le service de [`docker-compose.yml`](docker-compose.yml) à la stack, avec les variables de [`.env.example`](.env.example).
2. Écrire `services.yaml` dans le dossier de données, sur le modèle de [`app/services.exemple.yaml`](app/services.exemple.yaml) : familles, machines, services (adresse locale, adresse du réseau privé, icône, cadre ou non). Sans ce fichier, l'Anneau montre l'exemple.
3. Ouvrir `http://<NAS>:8094`, se connecter avec le mot de passe commun. Après une modification du fichier : Réglages › « Recharger le fichier ».

## Home Assistant (facultatif)

Avec `ANNEAU_SECRET_HA`, Home Assistant peut envoyer chaque minute l'état des machines :

```
POST /api/ha/etat        en-tête X-Anneau-Secret: <le secret>
{"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": 97.1, "etat": "attention"}],
 "mises_a_jour": [{"machine": "Grand NAS", "disponible": true, "version": "8.1"}]}
```

La réponse dit quoi notifier : `{"pannes": 1, "ouvertes": ["…"], "closes": ["…"], "liste": ["…"]}`. Chaque ouverture et chaque clôture n'est donnée qu'une fois.

## Développement

```
pip install -r requirements-dev.txt && python -m pytest -q tests --ignore=tests/interface
cd frontend && npm ci && npx vite build
python -m tests.interface.serveur /tmp/anneau 8094      # Anneau de démonstration, mot de passe « essai-essai-essai »
```

À lire avant de toucher au code : [`REPRISE.md`](REPRISE.md), puis [`docs/dossier.md`](docs/dossier.md).
