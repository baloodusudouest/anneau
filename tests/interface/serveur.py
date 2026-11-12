"""Anneau de démonstration pour les tests d'écran : un faux réseau, des services inventés.

    python -m tests.interface.serveur <dossier> <port>     (mot de passe : « essai-essai-essai »)

Le fichier <dossier>/morts.txt liste, une par ligne, les adresses qui ne répondent plus.
La ronde tourne toutes les demi-secondes pour que les tests n'attendent pas."""
from __future__ import annotations

import sys
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
  - {{ nom: Répertoire, famille: Proches, locale: "{base}/health?s=repertoire", icone: carnet, cadre: true, machine: Grand NAS }}
  - {{ nom: Arbre, famille: Proches, locale: "{base}/health?s=arbre", icone: arbre, machine: Grand NAS }}
  - {{ nom: Photothèque, famille: Photos, locale: "{base}/health?s=phototheque", icone: soleil, cadre: true, machine: Grand NAS }}
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


def main_() -> None:
    racine, port = Path(sys.argv[1]), int(sys.argv[2])
    data = racine / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "services.yaml").write_text(fichier(f"http://127.0.0.1:{port}"), encoding="utf-8")
    morts = racine / "morts.txt"
    morts.write_text("s=calcul\n")                      # le PC de calcul est éteint, comme souvent

    async def sonder(adresse: str):
        return (not any(m and m in adresse for m in morts.read_text().split()), 14)

    cfg = Config(password=MDP, data=data, static=Path(__file__).resolve().parents[2] / "app" / "static", secret_ha=SECRET,
                 attente_connexion=False, periode=0.5)
    main.ETAT.update(cfg=cfg, veille=Veille(data, services.lire(data / "services.yaml"), ha_attendu=False, sonder=sonder))
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main_()
