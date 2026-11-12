# Reprise — L'Anneau

Fichier à lire en premier dans une nouvelle session, et à mettre à jour à chaque fin de session, dans le même commit que le code.

## État (12/11/2026)

- Grill fini, **dossier écrit** (`docs/dossier.md`), **premier passage au conseil** (`docs/conseil.md`), décisions d'après conseil et design arrêté sur maquette en fin de dossier.
- **Rien n'est codé.** La maquette cliquable porte la vraie liste des services : elle n'est pas dans ce dépôt (voir `.gitignore`).
- L'inventaire réel des services n'est pas dans ce dépôt non plus : il ira dans le fichier des services de l'installation.

## Sonde de Portainer (13/11/2026)

Faite en lecture seule ; résultats et conséquences en fin de `docs/dossier.md` (« Ajouts du 13/11/2026 »). Un seul Portainer gratuit pour les deux NAS, un seul compte administrateur, aucun déclencheur. La sonde s'est arrêtée sur un onglet figé pendant le test d'affichage en cadre : trois services restent à tester.

## Prochaine étape

1. **Sonde en lecture seule de Home Assistant** (Portainer est fait, sauf l'appel de recréation) (entités des deux NAS, de l'iPhone, du PC). Par le navigateur, sans rien écrire. Rapport sans secret.
2. Vérifier quels services acceptent d'être affichés dans un cadre.
3. **Second passage au conseil**, sur le dossier révisé et la sonde.
4. Temps 1 : la vue (liste, voyants, écran d'ouverture, alerte de place), depuis le socle.

## Décisions à ne pas rouvrir sans raison

- Trois temps : la vue sans pouvoir d'écrire, puis la file de travail des applis maison, puis les mises à jour.
- Gestes : second mot de passe propre à l'Anneau ; liste des conteneurs touchables dans les variables de la stack ; jamais lui-même, jamais la stack.
- État des NAS, de l'iPhone et du PC lu dans Home Assistant ; alerte de place au-delà de 90 %.
- Design : familles en texte seul sur l'anneau, plume fine, rouge lave pour une panne, bleu spectral pour une action ; colonne d'icônes en vue réduite.
