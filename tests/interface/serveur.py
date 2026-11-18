"""Anneau de démonstration pour les tests d'écran : un faux réseau, des services inventés.

    python -m tests.interface.serveur <dossier> <port>     (mot de passe : « essai-essai-essai »)

Le fichier <dossier>/morts.txt liste, une par ligne, les adresses qui ne répondent plus.
La ronde tourne toutes les demi-secondes pour que les tests n'attendent pas.
0.8 : MAISON_JETON n'est pas posé ici, donc « Sauvegarder maintenant » note ratées les deux applis maison (tuiles avec une sonde /health) (tuile « Sauvegarde ratée »),
l'Anneau ne sauvegardant que lui-même.
0.12 : <dossier>/sante.json ({morceau d'adresse: corps du /health}) donne la santé des tâches de fond des tuiles ;
<dossier>/arret.txt fait échouer chaque tour de veille et <dossier>/avance.txt avance l'horloge de la veille
(en secondes) : ensemble, ils simulent une veille arrêtée depuis plus de 10 min."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import uvicorn

from app import main, services
from app.config import Config
from app.veille import Veille

MDP, SECRET = "essai-essai-essai", "secret-de-demonstration"


def fichier(base: str) -> str:
    return f"""
reglages: {{ seuil_disque: 99.8, famille_ha: Maison }}
familles:
  - {{ nom: Proches, icone: personnes }}
  - {{ nom: Photos, icone: image }}
  - {{ nom: Médias, icone: lecture }}
  - {{ nom: Maison, icone: maison }}
  - {{ nom: Collecte, icone: descente }}
  - {{ nom: Machines, icone: serveur }}
machines:
  - {{ nom: Grand NAS, sonde: "{base}/health?machine=grand", famille: Machines }}
services:
  - {{ nom: Répertoire, famille: Proches, locale: "{base}/health?s=repertoire", sonde: "{base}/health?s=repertoire", icone: carnet, machine: Grand NAS }}
  - {{ nom: Arbre, famille: Proches, locale: "{base}/health?s=arbre", sonde: "{base}/health?s=arbre", icone: arbre, machine: Grand NAS }}
  - {{ nom: Photothèque, famille: Photos, locale: "{base}/health?s=phototheque", icone: soleil, machine: Grand NAS }}
  - {{ nom: Numérisation, famille: Photos, locale: "{base}/health?s=numerisation", icone: numerisation, machine: Grand NAS }}
  - {{ nom: Cinéma, famille: Médias, locale: "{base}/health?s=cinema", icone: disque }}
  - {{ nom: Statistiques, famille: Médias, locale: "{base}/health?s=statistiques", icone: courbes, machine: Grand NAS }}
  - {{ nom: Livres lus, famille: Médias, locale: "{base}/health?s=livres", icone: casque, machine: Grand NAS }}
  - {{ nom: Domotique, famille: Maison, locale: "{base}/health?s=domotique", icone: maison }}
  - {{ nom: Séries, famille: Collecte, locale: "{base}/health?s=series", icone: ecran }}
  - {{ nom: Films, famille: Collecte, locale: "{base}/health?s=films", icone: pellicule }}
  - {{ nom: Musique, famille: Collecte, locale: "{base}/health?s=musique", icone: musique }}
  - {{ nom: Ordinateur de calcul, famille: Machines, locale: "{base}/health?s=calcul", icone: processeur, arret_attendu: true }}
"""


def carte_demo(data: Path) -> None:
    """0.11 : une carte de la maison inventée, comme si le coffre l'avait envoyée (les noms suivent les tuiles)."""
    import json
    s = lambda i, nom, q, fam="maison", **k: {"id": i, "nom": nom, "famille": fam, "machine": "grand", "quartier": q, "stack": True,
                                             "role": f"Rôle de {nom}.", "couleur": "#b7c0cc", **k}
    carte = {"schema": 1, "genere_le": "2026-11-18T08:00:00+00:00", "commit": "demo1234",
             "machines": [{"id": "grand", "nom": "Grand NAS", "detail": ""}, {"id": "dehors", "nom": "En ligne", "detail": ""}],
             "quartiers": [{"id": "proches", "nom": "Proches"}, {"id": "photos", "nom": "Photos"}],
             "familles": {"maison": {"nom": "Applis maison", "detail": ""}, "stockage": {"nom": "Bases", "detail": ""},
                          "tiers": {"nom": "Services tiers", "detail": ""}},
             "services": [s("repertoire", "Répertoire", "proches", port="8096"), s("arbre", "Arbre", "proches", fam="tiers"),
                          s("base-arbre", "Base de l'arbre", "proches", fam="stockage"), s("phototheque", "Photothèque", "photos", fam="tiers"),
                          s("numerisation", "Numérisation", "photos"), {**s("nuage", "Nuage", "photos", fam="tiers"), "machine": "dehors"}],
             "flux": [{"de": "arbre", "vers": "repertoire", "nature": "donnees", "infos": ["familles"], "retour": ["noms"], "echange": True},
                      {"de": "arbre", "vers": "base-arbre", "nature": "donnees", "infos": ["arbre"]},
                      {"de": "numerisation", "vers": "phototheque", "nature": "donnees", "infos": ["scans datés"]},
                      {"de": "phototheque", "vers": "nuage", "nature": "maj", "infos": ["copie"]}]}
    (data / "documents").mkdir(parents=True, exist_ok=True)
    (data / "documents" / "carte.json").write_text(json.dumps(carte, ensure_ascii=False), encoding="utf-8")


def main_() -> None:
    racine, port = Path(sys.argv[1]), int(sys.argv[2])
    data = racine / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "services.yaml").write_text(fichier(f"http://127.0.0.1:{port}"), encoding="utf-8")
    carte_demo(data)
    morts = racine / "morts.txt"
    morts.write_text("s=calcul\n")                      # le PC de calcul est éteint, comme souvent

    sante = racine / "sante.json"
    arret, avance = racine / "arret.txt", racine / "avance.txt"

    async def sonder(adresse: str, jeton: str = ""):
        try:
            corps = json.loads(sante.read_text(encoding="utf-8")) if sante.is_file() else {}
        except ValueError:
            corps = {}
        return (not any(m and m in adresse for m in morts.read_text().split()), 14,
                next((c for m, c in corps.items() if m in adresse), None))

    def horloge() -> float:
        try:
            return time.monotonic() + float(avance.read_text() or 0)
        except (OSError, ValueError):
            return time.monotonic()

    class VeilleDemo(Veille):
        async def tour(self):
            if arret.exists():
                raise RuntimeError("arrêt simulé de la veille")
            await super().tour()

    async def examiner(adresse: str):
        return "X-Frame-Options : SAMEORIGIN" if "s=numerisation" in adresse else ""

    cfg = Config(password=MDP, data=data, static=Path(__file__).resolve().parents[2] / "app" / "static", secret_ha=SECRET,
                 attente_connexion=False, periode=0.5, sauvegarde_auto=False)   # la collecte se lance par le bouton
    main.ETAT.update(cfg=cfg, veille=VeilleDemo(data, services.lire(data / "services.yaml"), ha_attendu=False, sonder=sonder,
                                                examiner=examiner, horloge=horloge))
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main_()
