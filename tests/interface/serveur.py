"""Anneau de démonstration pour les tests d'écran : un faux réseau, des services inventés.

    python -m tests.interface.serveur <dossier> <port>     (mot de passe : « essai-essai-essai »)

Le fichier <dossier>/morts.txt liste, une par ligne, les adresses qui ne répondent plus.
La ronde tourne toutes les demi-secondes pour que les tests n'attendent pas.
0.8 : MAISON_JETON n'est pas posé ici, donc « Sauvegarder maintenant » note ratées les deux applis maison (tuiles avec une sonde /health) (tuile « Sauvegarde ratée »),
l'Anneau ne sauvegardant que lui-même.
0.12 : <dossier>/sante.json ({morceau d'adresse: corps du /health}) donne la santé des tâches de fond des tuiles ;
<dossier>/arret.txt fait échouer chaque tour de veille et <dossier>/avance.txt avance l'horloge de la veille
(en secondes) : ensemble, ils simulent une veille arrêtée depuis plus de 10 min.
0.13 : Répertoire et Arbre ont un `depot:` ; un faux GitHub (jamais le vrai) rend leurs étiquettes. La version en service
se donne par le champ `version` de leur corps dans sante.json.
0.17 : un faux Portainer (tests/faux_portainer.py, dans le même processus) ; Séries et Films sont marqués `conteneur:`
(ils ne répondent que si leur conteneur tourne ; recréation lente : 1,5 s ; une image plus récente attend), Musique est
marquée mais son conteneur n'a pas l'étiquette de la stack (pas de boutons).
0.17.1 : la mise à jour passe par un faux Watchtower (tests/faux_watchtower.py, lent : 1,5 s) qui agit sur les conteneurs
du faux Portainer.
0.18 : de faux registres (tests/faux_registre.py) : Séries, Films, « lecteur » (sans tuile) et « base-lecteur » (une base de
données, double confirmation) ont une image plus récente publiée ; « galerie-server » est figée en v1.2.0 (v1.3.0
publiée). La liste se vérifie par POST /api/majs/verifier (le test le demande)."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
import uvicorn

from app import main, services
from app.config import Config
from app.veille import Veille
from tests.faux_portainer import CLE as CLE_PORTAINER, FauxPortainer
from tests.faux_registre import FauxRegistres, empreinte
from tests.faux_watchtower import JETON as JETON_WATCHTOWER, FauxWatchtower

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
figees:
  - {{ conteneur: "galerie-*", depot: exemple-org/galerie, variable: GALERIE_VERSION }}
machines:
  - {{ nom: Grand NAS, sonde: "{base}/health?machine=grand", famille: Machines }}
services:
  - {{ nom: Répertoire, famille: Proches, locale: "{base}/health?s=repertoire", sonde: "{base}/health?s=repertoire", icone: carnet, machine: Grand NAS, depot: repertoire }}
  - {{ nom: Arbre, famille: Proches, locale: "{base}/health?s=arbre", sonde: "{base}/health?s=arbre", icone: arbre, machine: Grand NAS, depot: arbre }}
  - {{ nom: Photothèque, famille: Photos, locale: "{base}/health?s=phototheque", icone: soleil, machine: Grand NAS }}
  - {{ nom: Numérisation, famille: Photos, locale: "{base}/health?s=numerisation", icone: numerisation, machine: Grand NAS }}
  - {{ nom: Cinéma, famille: Médias, locale: "{base}/health?s=cinema", icone: disque }}
  - {{ nom: Statistiques, famille: Médias, locale: "{base}/health?s=statistiques", icone: courbes, machine: Grand NAS }}
  - {{ nom: Livres lus, famille: Médias, locale: "{base}/health?s=livres", icone: casque, machine: Grand NAS }}
  - {{ nom: Domotique, famille: Maison, locale: "{base}/health?s=domotique", icone: maison }}
  - {{ nom: Séries, famille: Collecte, locale: "{base}/health?s=series", icone: ecran, conteneur: series }}
  - {{ nom: Films, famille: Collecte, locale: "{base}/health?s=films", icone: pellicule, conteneur: films }}
  - {{ nom: Musique, famille: Collecte, locale: "{base}/health?s=musique", icone: musique, conteneur: musique }}
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


ETIQUETTES = {"repertoire": ["v2.39.0", "v2.40.0", "latest"], "arbre": ["v3.0.0", "v9.0.0", "v9.0.0-rc1", "essai"]}


def faux_github(req: httpx.Request) -> httpx.Response:
    """0.13 : les étiquettes des dépôts inventés ; rien ne part vers le vrai GitHub."""
    depot = req.url.path.split("/")[3]
    return httpx.Response(200, json=[{"name": n} for n in ETIQUETTES[depot]]) if depot in ETIQUETTES else httpx.Response(404)


CONTENEURS = {"s=series": "series", "s=films": "films", "s=musique": "musique"}


def faux_portainer(reg: FauxRegistres | None = None) -> FauxPortainer:
    """0.17 : Séries (redémarrage « always ») et Films tournent sur une image du 10/11 ; celle du 20/11 attend.
    0.18 : la même image du 20/11 est publiée dans le faux registre ; « lecteur » et « base-lecteur » aussi en retard."""
    f = FauxPortainer()
    reg = reg or FauxRegistres()
    for nom, redemarrage in (("series", "always"), ("films", "unless-stopped"), ("lecteur", "unless-stopped"),
                             ("base-lecteur", "unless-stopped")):
        image = f"ghcr.io/exemple/{nom}:latest" if nom != "base-lecteur" else "ghcr.io/exemple/redis:latest"
        depot = image.split("/", 1)[1].rsplit(":", 1)[0]
        neuve = reg.publier("ghcr.io", depot, "latest", f"{nom}-20-11")
        ancienne = f.image(image, "2026-11-10T05:00:00Z", derniere=False, empreinte=empreinte(f"{nom}-10-11"))
        f.image(image, "2026-11-20T05:00:00Z", empreinte=neuve)
        f.ajouter(nom, ancienne, image, redemarrage=redemarrage)
    galerie = "ghcr.io/exemple/galerie-server:v1.2.0"
    f.ajouter("galerie-server", f.image(galerie, "2026-11-01T05:00:00Z", empreinte=empreinte("galerie")), galerie)
    reg.publications["exemple-org/galerie"] = "v1.3.0"
    f.ajouter("musique", f.image("ghcr.io/exemple/musique:latest", "2026-11-15T05:00:00Z"), projet="autre")
    return f


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

    registres_ = FauxRegistres()
    portainer = faux_portainer(registres_)
    watchtower = FauxWatchtower(portainer, lenteur=1.5)

    async def sonder(adresse: str, jeton: str = ""):
        try:
            corps = json.loads(sante.read_text(encoding="utf-8")) if sante.is_file() else {}
        except ValueError:
            corps = {}
        nom = next((n for m, n in CONTENEURS.items() if m in adresse), None)
        if nom is not None:                                # 0.17 : répond si son conteneur tourne
            c = portainer.conteneurs.get(nom)
            return (bool(c and c["State"]["Running"]), 14, None)
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

    # 0.16 : fiches « Connexion » des applis maison (contrat 3), sans réseau : quatre services (tuiles), un guide
    os.environ.setdefault("ANNEAU_CLE", "cle-anneau-de-demonstration")
    FICHE = lambda id_, nom, etat, **kw: {"id": id_, "nom": nom, "genre": "exterieur", "cible": None, "etat": etat,
                                         "lit": "Les fiches et leurs photos.", "ecrit": "Rien.", "reglage": None,
                                         "detail": None, "verifie_le": None, "derniere_ecriture": None, "gestes": [],
                                         "guide": None, **kw}
    fiches_demo = [
        FICHE("immich", "Immich", "repond", detail="Version 2.1.0."),
        FICHE("pc-calcul", "Calculateur du PC", "ne_repond_pas", detail="Pas de réponse en 8 s.",
              gestes=[{"id": "calculer", "nom": "Calculer"}],
              guide={"reglages": [{"nom": "Adresse appelée", "valeur": "http://192.0.2.12:8000"}],
                     "allumer": ["Allumer le PC.", "Ouvrir Docker Desktop."],
                     "pannes": [{"signe": "« PC injoignable »", "faire": ["Le PC est-il allumé ?"], "commandes": ["ipconfig"]}],
                     "terminal": "Les commandes se tapent dans PowerShell sur le PC."}),
        FICHE("carnet", "carnet", "relie"),
        FICHE("home-assistant", "Home Assistant", "pas_relie", reglage="HA_URL"),
    ]

    async def lire_fiches(methode, url, cle):
        if url.endswith("/verifier"):
            id_ = url.rsplit("/", 2)[-2]
            f = next(x for x in fiches_demo if x["id"] == id_)
            return 200, {**f, "verifie_le": "2026-11-20T08:00:00+01:00"}
        return 200, {"contrat": 3, "appli": "repertoire", "simule": False, "services": fiches_demo}

    cfg = Config(password=MDP, data=data, static=Path(__file__).resolve().parents[2] / "app" / "static", secret_ha=SECRET,
                 attente_connexion=False, periode=0.5, sauvegarde_auto=False,   # la collecte se lance par le bouton
                 portainer_url="http://portainer.exemple:9000", portainer_cle=CLE_PORTAINER,
                 watchtower_url="http://watchtower:8080", watchtower_jeton=JETON_WATCHTOWER)
    main.ETAT.update(cfg=cfg, veille=VeilleDemo(data, services.lire(data / "services.yaml"), ha_attendu=False, sonder=sonder,
                                                examiner=examiner, horloge=horloge),
                     transport_versions=httpx.MockTransport(faux_github), lire_fiches=lire_fiches,
                     transport_portainer=portainer.transport(), transport_watchtower=watchtower.transport(),
                     transport_registres=registres_.transport())
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main_()
