"""0.16 : fiches « Connexion » des applis dans la fiche « État » (contrat 3). Les applis sont des faux : aucun réseau.
La clé ANNEAU_CLE part vers l'appli, jamais vers le navigateur ; « Vérifier » est relayé ; aucun geste qui écrit."""
import pytest

from app import main, services
from tests.test_api import MDP, client, connecter, monde, veille  # noqa: F401 — fixtures

FICHIER = """
familles: [{ nom: Proches }, { nom: Médias }]
services:
  - { nom: carnet, famille: Proches, locale: "http://192.0.2.1:8085", sonde: "http://carnet:8085/health", sauvegarde: true }
  - { nom: Douze points, famille: Proches, locale: "http://192.0.2.1:8099", sonde: "http://douze:8099/health", sauvegarde: true }
  - { nom: L'Anneau, famille: Proches, locale: "http://192.0.2.1:8094", sonde: "http://anneau:8094/health", sauvegarde: true }
  - { nom: Cinéma, famille: Médias, locale: "http://192.0.2.1:8103" }
"""
CLE = "cle-anneau-de-test-1234567890"
FICHE = {"id": "immich", "nom": "Immich", "genre": "exterieur", "cible": None, "etat": "repond", "lit": "Les photos.",
         "ecrit": "Rien.", "reglage": None, "detail": "Refus de http://user:mdp@192.0.2.4:2283", "verifie_le": None,
         "derniere_ecriture": None, "gestes": [{"id": "synchroniser", "nom": "Synchroniser"}],
         "guide": {"allumer": ["Allumer le PC."], "inconnu": 1}, "en_trop": "x"}


@pytest.fixture()
def appel(client, tmp_path, monkeypatch):  # noqa: F811
    (tmp_path / "services.yaml").write_text(FICHIER, encoding="utf-8")
    main.ETAT["veille"].fichier = services.lire(tmp_path / "services.yaml")
    monkeypatch.setenv("ANNEAU_CLE", CLE)
    vus = []

    async def faux(methode, url, cle):
        vus.append((methode, url, cle))
        if "douze" in url:
            return 404, {"detail": "Not Found"}
        if url.endswith("/verifier"):
            return 200, {**FICHE, "etat": "ne_repond_pas"}
        return 200, {"contrat": 3, "appli": "carnet", "simule": False, "services": [FICHE, {"pas": "une fiche"}]}

    main.ETAT["lire_fiches"] = faux
    connecter(client)
    return vus


def test_etat_dit_quelles_tuiles_ont_des_fiches(client, appel):  # noqa: F811
    s = {x["nom"]: x for f in client.get("/api/etat").json()["familles"] for x in f["services"]}
    assert s["carnet"]["fiches"] and s["Douze points"]["fiches"]
    assert not s["L'Anneau"]["fiches"] and not s["Cinéma"]["fiches"]


def test_lire_les_fiches_d_une_appli(client, appel):  # noqa: F811
    r = client.get("/api/applis/carnet/services").json()
    assert r["etat"] == "ok" and len(r["services"]) == 1
    f = r["services"][0]
    assert "en_trop" not in f and "192.168" not in f["detail"] and "mdp" not in f["detail"]
    assert f["guide"]["allumer"] == ["Allumer le PC."] and "inconnu" not in f["guide"]
    assert appel == [("GET", "http://carnet:8085/api/maison/services", CLE)]
    assert CLE not in client.get("/api/applis/carnet/services").text


def test_appli_d_avant_le_contrat_3(client, appel):  # noqa: F811
    r = client.get("/api/applis/douze-points/services").json()
    assert r["etat"] == "ancien" and "pas encore les fiches communes" in r["phrase"]


def test_verifier_relaye(client, appel):  # noqa: F811
    r = client.post("/api/applis/carnet/services/immich/verifier")
    assert r.status_code == 200 and r.json()["etat"] == "ne_repond_pas"
    assert appel[-1] == ("POST", "http://carnet:8085/api/maison/services/immich/verifier", CLE)
    assert client.post("/api/applis/carnet/services/../verifier").status_code in (404, 405)
    assert client.post("/api/applis/carnet/services/A B/verifier").status_code == 404


def test_tuile_qui_n_est_pas_une_appli_maison(client, appel):  # noqa: F811
    assert client.get("/api/applis/cinema/services").status_code == 404
    assert client.get("/api/applis/l-anneau/services").status_code == 404


def test_cle_vide_et_session_exigee(client, appel, monkeypatch):  # noqa: F811
    monkeypatch.delenv("ANNEAU_CLE")
    r = client.get("/api/applis/carnet/services").json()
    assert r["etat"] == "ferme" and "ANNEAU_CLE" in r["phrase"] and appel == []
    assert client.post("/api/applis/carnet/services/immich/verifier").status_code == 409
    client.post("/api/deconnexion")
    assert client.get("/api/applis/carnet/services").status_code == 401


def test_appli_injoignable(client, appel):  # noqa: F811
    async def panne(methode, url, cle):
        raise ConnectionError("refus")
    main.ETAT["lire_fiches"] = panne
    r = client.get("/api/applis/carnet/services").json()
    assert r["etat"] == "injoignable" and "n'a pas répondu" in r["phrase"]
