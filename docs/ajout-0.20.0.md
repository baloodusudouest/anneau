# L'Anneau 0.20.0 — coller le homelab, variables à coller, homelab avec ses valeurs — dossier court (26/11/2026)

Demande de Julien du 26/11/2026 (18 h 46) : « dans l'Anneau, ajoute la possibilité de coller le homelab, mets les variables à coller en dessous, et mets ensuite en dessous le homelab en remplaçant les variables par leurs valeurs définies ». Cadrage par questions à choix le même jour. Dossier court, sans Conseil (choix de Julien). **Code après le « go ».**

## 1. Besoin et choix de Julien
Dans Réglages › Stack et variables, trois blocs l'un sous l'autre :
1. **Le homelab** : en plus de « Importer homelab.yml », une zone où **coller** le texte (par exemple copié depuis la note du coffre dans SilverBullet). Le texte collé **remplace `homelab.yml` de l'Anneau**, comme l'import : vérifié par le serveur, valeurs en clair refusées.
2. **Les variables à coller** dans Portainer (`NOM=valeur`, une par ligne, dans l'ordre du homelab), tirées des **valeurs ouvertes** : export chiffré ouvert avec la clé privée, ou export de Portainer collé (comme aujourd'hui).
3. **Le homelab avec ses valeurs** : le même texte, chaque `${VAR}` remplacé par sa valeur. **Masqué** par défaut, « Afficher », « Copier », « Télécharger » ; seulement en https, seulement dans la mémoire de la page, jamais envoyé au serveur, effacé par « Oublier les valeurs ».

## 2. Contexte (lu dans le code 0.19.0)
- `POST /api/stack` (import, `stack.verifier` : refuse une valeur en clair, du balisage Markdown, un fichier sans services) ; `GET /api/stack/fichier` rend le texte ; `GET /api/stack` rend services et variables (défaut `None` = à remplir).
- `lib/environnement.js` : `comprendre` (texte `NOM=valeur`), `pourPortainer` (texte pour Portainer dans l'ordre des variables), valeurs dans la page seulement.
- Section « Variables de la stack » : bouton « Copier toutes les variables (avec valeurs) » et zone « Voir le texte ».

## 3. Technique
- **Coller** : zone de texte + « Enregistrer le homelab » → `POST /api/stack` (route existante, rien de nouveau côté serveur). Les lignes de bloc Markdown (```` ```yaml ```` et ```` ``` ````) collées depuis la note sont retirées dans la page avant l'envoi (le serveur les refuse sinon) ; le reste est vérifié par le serveur comme un fichier.
- **Variables à coller** : `pourPortainer` existant, montré en permanence dès que des valeurs sont ouvertes (aujourd'hui caché derrière « Voir le texte »), avec « Copier » et le compte des variables à remplir manquantes.
- **Homelab avec ses valeurs** : nouvelle fonction pure `resoudre(texte, valeurs)` dans `lib/environnement.js`, mêmes règles que Docker Compose :
  - `${VAR}` → valeur ; absente → laissée telle quelle et signalée « non remplie » ;
  - `${VAR:-défaut}` → valeur si non vide, sinon le défaut ; `${VAR-défaut}` → valeur si présente (même vide), sinon le défaut ;
  - `$$` reste `$$` ;
  - **les commentaires ne sont pas touchés** (ligne qui commence par `#`, ou partie après ` #` hors guillemets) : pas de secret recopié dans un commentaire.
  Texte du homelab relu par `GET /api/stack/fichier` à l'ouverture de la page. Bloc replié, valeurs masquées tant que « Afficher » n'est pas touché ; « Télécharger » produit `homelab-avec-valeurs.yml`.
- Tests : `resoudre` essayée avec Node (règles ci-dessus, commentaires intacts) ; écran : coller un homelab avec bloc Markdown → accepté, avec une valeur en clair → refusé ; les trois blocs dans l'ordre ; homelab résolu masqué puis affiché ; rien envoyé au serveur (requêtes observées) ; « Oublier » efface tout ; iPhone sans débordement.

## 4. Écrans
Stack et variables : Fichiers de la stack (importer **ou coller**) → Clé → Chiffrer → Exports chiffrés → **Variables de la stack** : valeurs ouvertes, puis « Variables à coller dans Portainer » (bloc texte + Copier), puis « Homelab avec ses valeurs » (replié, Afficher, Copier, Télécharger), puis la liste des variables.

## 5. Données
Aucune nouvelle donnée côté serveur. Rien de nouveau n'est écrit sauf `homelab.yml` (comme l'import).

## 6. Plan
1. `resoudre` + tests Node. 2. Écran (coller, deux blocs) + tests d'écran. 3. Coffre (note de version, plan de tests), dépôt, version 0.20.0.

**Jamais essayé sur la vraie installation** : le collage d'un long homelab depuis SilverBullet sur iPhone.

↑ [[L'Anneau]]
