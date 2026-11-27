"""0.21 : le QNAP comme le Synology (docs/ajout-0.21.0.md). Deux faux Portainer (le relais du Synology et celui de
l'agent du QNAP), deux faux Watchtower, faux registres. Tout est inventé : adresses, noms, empreintes, versions."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import conteneurs, main, services, versions
from app.config import Config
from app.veille import Veille
from tests.faux_portainer import CLE, FauxPortainer, attendre
from tests.faux_registre import FauxRegistres, empreinte
from tests.faux_watchtower import JETON, FauxWatchtower

MDP = "mot-de-passe-de-test"
ORIGINE = {"Origin": "http://testserver"}
URL = "http://portainer.exemple:9000"
URL_WT = "http://watchtower:8080"
URL_WT_QNAP = "http://192.0.2.33:8099"
JETON_QNAP = "jeton-watchtower-qnap-de-test"
BASE = "http://192.0.2.10"
QNAP = "http://192.0.2.33"
ENV_QNAP = "12"

FICHIER = f"""
familles: [{{ nom: Essais }}, {{ nom: Collecte }}]
machines:
  - {{ nom: Qnap, sonde: "{QNAP}:65535" }}
services:
  - {{ nom: Bac à sable, famille: Essais, locale: "{BASE}:8104", conteneur: bac-a-sable }}
  - {{ nom: Sonarr, famille: Collecte, locale: "{QNAP}:8989", machine: Qnap, conteneur: sonarr }}
  - {{ nom: Qbittorrent, famille: Collecte, locale: "{QNAP}:8080", machine: Qnap, conteneur: qbittorrent }}
"""


def _appli(p, reg, nom, ref, a_jour=True, projet="homelab", running=True, version="", hote="ghcr.io"):
    depot = ref.split("/", 1)[1].rsplit(":", 1)[0]
    etiq = ref.rsplit(":", 1)[1]
    ancienne = empreinte(f"{nom}-ancienne")
    publiee = reg.publier(hote, depot, etiq, f"{nom}-ancienne" if a_jour else f"{nom}-neuve")
    img = p.image(ref, "2026-11-20T05:00:00Z", derniere=a_jour, empreinte=ancienne, version=version)
    if not a_jour:
        p.image(ref, "2026-11-26T05:00:00Z", empreinte=publiee, version=version + "-neuve" if version else "")
    return p.ajouter(nom, img, ref, projet=projet, running=running)


@pytest.fixture()
def monde():
    syno, qnap, reg = FauxPortainer(), FauxPortainer(env=int(ENV_QNAP)), FauxRegistres()
    qnap.environnements = [{"Id": int(ENV_QNAP), "Name": "qnap", "Type": 2}]   # l'agent du QNAP (pas « Docker local »)
    _appli(syno, reg, "bac-a-sable", "ghcr.io/exemple/bac-a-sable:latest", a_jour=False)
    _appli(qnap, reg, "sonarr", "ghcr.io/exemple-ls/sonarr:latest", a_jour=False, projet="media", version="4.0.1")
    _appli(qnap, reg, "qbittorrent", "ghcr.io/exemple-ls/qbittorrent:latest", projet="media", version="5.0.0")
    _appli(qnap, reg, "intrus", "ghcr.io/exemple-ls/intrus:latest", a_jour=False, projet="autre")
    return syno, qnap, reg


def _client(tmp_path, monde, qnap_env=ENV_QNAP, qnap_wt=True):
    syno, qnap, reg = monde
    main.ETAT.clear()
    (tmp_path / "services.yaml").write_text(FICHIER, encoding="utf-8")

    async def sonder(adresse):
        return (True, 5)

    async def examiner(adresse):
        return ""

    veille = Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=sonder, examiner=examiner)
    cfg = Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, veille=False,
                 sauvegarde_auto=False, portainer_url=URL, portainer_cle=CLE, watchtower_url=URL_WT, watchtower_jeton=JETON,
                 qnap_portainer_env=qnap_env, qnap_watchtower_url=URL_WT_QNAP if qnap_wt else "",
                 qnap_watchtower_jeton=JETON_QNAP if qnap_wt else "")
    wt, wt_qnap = FauxWatchtower(syno), FauxWatchtower(qnap, jeton=JETON_QNAP)
    main.ETAT.update(cfg=cfg, veille=veille, transport_portainer=syno.transport(), transport_watchtower=wt.transport(),
                     transport_portainer_qnap=qnap.transport(), transport_watchtower_qnap=wt_qnap.transport(),
                     transport_registres=reg.transport())
    return TestClient(main.app), wt, wt_qnap


@pytest.fixture()
def tout(tmp_path, monde):
    c, wt, wt_qnap = _client(tmp_path, monde)
    with c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        yield c, wt, wt_qnap
    main.ETAT.clear()


def _tour(c):
    c.portal.call(main.un_tour, main.ETAT["veille"])


def _tuiles(c):
    return {s["cle"]: s for f in c.get("/api/etat").json()["familles"] for s in f["services"]}


def _verifier(c):
    r = c.post("/api/majs/verifier", headers=ORIGINE)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- réglages

def test_config_qnap():
    cfg = Config(password=MDP, data=None, static=None, portainer_url=URL, portainer_cle=CLE)
    assert not cfg.qnap and "ANNEAU_QNAP_PORTAINER_ENV" in cfg.qnap_manque()
    cfg = Config(password=MDP, data=None, static=None, portainer_url=URL, portainer_cle=CLE, qnap_portainer_env="12",
                 qnap_watchtower_url=URL_WT_QNAP, qnap_watchtower_jeton=JETON_QNAP)
    assert cfg.qnap and cfg.qnap_watchtower and not cfg.qnap_manque() and not cfg.qnap_watchtower_manque()
    assert JETON_QNAP not in repr(cfg)
    assert not Config(password=MDP, data=None, static=None, qnap_portainer_env="12").qnap   # sans Portainer : rien


def test_l_agent_portainer_est_interdit():
    assert conteneurs.interdit("portainer_agent")
    assert conteneurs.verifier_nom("portainer_agent")[0] == ""


# ---------------------------------------------------------------- « À faire quand tu veux »

def test_une_liste_pour_les_deux_machines(tout):
    c, _, _ = tout
    v = _verifier(c)
    par_id = {x["id"]: x for x in v["lignes"]}
    assert set(par_id) == {"bac-a-sable", "qnap:sonarr"}                 # à jour ou d'un autre projet : absents
    assert par_id["bac-a-sable"]["machine"] == "Synology"
    assert par_id["qnap:sonarr"]["machine"] == "QNAP" and par_id["qnap:sonarr"]["nom"] == "Sonarr"
    assert v["deux_machines"] is True and v["injoignables"] == [] and v["nombre"] == 2
    assert all(x["bouton"] for x in v["lignes"])


def test_qnap_injoignable_ne_bloque_pas_le_synology(tout, monde):
    c, _, _ = tout
    _verifier(c)
    main.ETAT["majs"].qnap.portainer._transport = FauxWatchtower.injoignable()
    v = _verifier(c)
    assert v["erreur"] == ""
    assert len(v["injoignables"]) == 1 and v["injoignables"][0].startswith("QNAP injoignable")
    ids = {x["id"] for x in v["lignes"]}
    assert "bac-a-sable" in ids and "qnap:sonarr" in ids                  # les anciennes lignes du QNAP restent


def test_mettre_a_jour_une_appli_du_qnap_par_son_watchtower(tout, monde):
    c, wt, wt_qnap = tout
    _, qnap, _ = monde
    _verifier(c)
    image_avant = qnap.conteneurs["sonarr"]["Image"]
    r = c.post("/api/majs/qnap:sonarr/mettre-a-jour", headers=ORIGINE, json={})
    assert r.status_code == 202, r.text
    assert attendre(lambda: any(a[1] == "/v1/update" for a in wt_qnap.appels))
    assert not any(a[1] == "/v1/update" for a in wt.appels)              # jamais le Watchtower du Synology
    assert JETON_QNAP in wt_qnap.jetons_vus and JETON not in wt_qnap.jetons_vus
    assert attendre(lambda: qnap.conteneurs["sonarr"]["Image"] != image_avant)
    m = main.ETAT["majs"]
    assert attendre(lambda: (m.ordres["qnap:sonarr"].get("wt") == "fini"))
    c.portal.call(m.suivre)
    assert m.ordres["qnap:sonarr"]["etat"] == "fini"
    journal = [json.loads(l) for l in (main.ETAT["cfg"].data / conteneurs.JOURNAL).read_text().splitlines()]
    assert any(l.get("machine") == "qnap" and l["resultat"] == "lancé" for l in journal)


def test_qnap_sans_watchtower_lignes_sans_bouton(tmp_path, monde):
    c, _, _ = _client(tmp_path, monde, qnap_wt=False)
    with c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        par_id = {x["id"]: x for x in _verifier(c)["lignes"]}
        assert par_id["bac-a-sable"]["bouton"]
        assert not par_id["qnap:sonarr"]["bouton"]
        assert "ANNEAU_QNAP_WATCHTOWER_URL" in par_id["qnap:sonarr"]["pourquoi"]
        r = c.post("/api/majs/qnap:sonarr/mettre-a-jour", headers=ORIGINE, json={})
        assert r.status_code == 409
    main.ETAT.clear()


def test_sans_qnap_comme_avant(tmp_path, monde):
    c, _, _ = _client(tmp_path, monde, qnap_env="")
    with c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        v = _verifier(c)
        assert {x["id"] for x in v["lignes"]} == {"bac-a-sable"}
        assert v["deux_machines"] is False and v["injoignables"] == []
        _tour(c)
        t = _tuiles(c)
        assert t["sonarr"]["conteneur"]["gerable"] is False
        assert "ANNEAU_QNAP_PORTAINER_ENV" in t["sonarr"]["conteneur"]["pourquoi"]
        r = c.post("/api/conteneurs/sonarr/eteindre", headers=ORIGINE)
        assert r.status_code == 409
    main.ETAT.clear()


def test_ancien_majs_json_lu_comme_synology(tmp_path, monde):
    (tmp_path / "majs.json").write_text(json.dumps({"lignes": {"bac-a-sable": {
        "id": "bac-a-sable", "conteneur": "bac-a-sable", "nom": "Bac à sable", "image": "ghcr.io/exemple/bac-a-sable:latest",
        "running": True, "watchtower_non": False, "protege": "", "sorte": "maj", "phrase": "nouvelle image publiée"}},
        "ordres": {}, "lu_t": 9e12}), encoding="utf-8")
    c, _, _ = _client(tmp_path, monde)
    with c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        lignes = c.get("/api/etat").json()["majs"]["lignes"]
        assert lignes[0]["machine"] == "Synology" and lignes[0]["bouton"]
    main.ETAT.clear()


# ---------------------------------------------------------------- fiches des tuiles du QNAP

def test_fiche_qnap_allumer_eteindre_par_l_environnement_du_qnap(tout, monde):
    c, _, _ = tout
    syno, qnap, _ = monde
    _tour(c)
    t = _tuiles(c)
    assert t["sonarr"]["conteneur"]["gerable"] and t["sonarr"]["conteneur"]["machine"] == "QNAP"
    assert t["bac-a-sable"]["conteneur"]["machine"] == "Synology"
    r = c.post("/api/conteneurs/sonarr/eteindre", headers=ORIGINE)
    assert r.status_code == 202, r.text
    assert attendre(lambda: qnap.etat("sonarr") == "exited")
    assert any(f"/api/endpoints/{ENV_QNAP}/docker/containers/sonarr/stop" == a[1] for a in qnap.appels)
    assert not any("sonarr" in a[1] for a in syno.appels)
    _tour(c)
    assert main.ETAT["conteneurs"].ordres["sonarr"]["etat"] == "fini"
    assert "sonarr" in main.ETAT["conteneurs"].eteints()


def test_fiche_qnap_mettre_a_jour_par_le_watchtower_du_qnap(tout, monde):
    c, wt, wt_qnap = tout
    _, qnap, _ = monde
    _tour(c)
    r = c.post("/api/conteneurs/sonarr/mettre-a-jour", headers=ORIGINE)
    assert r.status_code == 202, r.text
    assert attendre(lambda: any(a[1] == "/v1/update" for a in wt_qnap.appels))
    assert not any(a[1] == "/v1/update" for a in wt.appels)


def test_un_conteneur_du_mauvais_projet_est_refuse(tout, monde):
    c, _, _ = tout
    _, qnap, _ = monde
    qnap.conteneurs["sonarr"]["Config"]["Labels"]["com.docker.compose.project"] = "homelab"
    _tour(c)
    v = _tuiles(c)["sonarr"]["conteneur"]
    assert v["gerable"] is False and "project=media" in v["pourquoi"]


# ---------------------------------------------------------------- nouveautés de la nuit

def test_version_de_l_image_dans_le_journal_avec_la_machine(tout, monde):
    c, _, _ = tout
    _, qnap, _ = monde
    _tour(c)
    assert main.ETAT["veille"].versions.version("sonarr") == "4.0.1"
    neuve = qnap.image("ghcr.io/exemple-ls/sonarr:latest", "2026-11-27T05:00:00Z", version="4.0.2")
    qnap.remplacer("sonarr", neuve)                                    # le Watchtower du QNAP, la nuit
    _tour(c)
    r = c.get("/api/versions/nouveautes").json()["changements"]
    entree = next(x for x in r if x["cle"] == "sonarr")
    assert (entree["de"], entree["vers"], entree.get("machine")) == ("4.0.1", "4.0.2", "Qnap")


def test_journal_des_versions_garde_la_machine(tmp_path):
    e = versions.EnService(tmp_path)
    e.noter("sonarr", "Sonarr", "4.0.1", le="2026-11-26T05:00:00+01:00", machine="Qnap")
    e.noter("sonarr", "Sonarr", "4.0.2", le="2026-11-27T05:00:00+01:00", machine="Qnap")
    assert e.depuis(None)[0]["machine"] == "Qnap"
    e.noter("carnet", "Carnet", "2.0.0", le="2026-11-26T05:00:00+01:00")
    e.noter("carnet", "Carnet", "2.0.1", le="2026-11-27T05:00:00+01:00")
    assert "machine" not in next(x for x in e.depuis(None) if x["cle"] == "carnet")


# ---------------------------------------------------------------- fiches « Connexion »

def test_fiches_connexion_du_qnap(tout):
    c, _, _ = tout
    fiches = {f["id"]: f for f in c.get("/api/maison/services").json()["services"]}
    assert fiches["portainer-qnap"]["etat"] != "pas_relie" and fiches["watchtower-qnap"]["etat"] != "pas_relie"
    r = c.post("/api/maison/services/portainer-qnap/verifier", headers=ORIGINE)
    assert r.status_code == 200, r.text
    assert "stack media" in (r.json().get("detail") or ""), r.json()
