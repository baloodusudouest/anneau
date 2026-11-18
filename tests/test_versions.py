"""0.13 : versions publiées (étiquettes GitHub), version en service (/health ou version_url), journal des changements,
nouveautés depuis la dernière visite et « Vu », jamais d'orange pour un retard. Faux GitHub, noms et adresses inventés."""
import asyncio
import functools
import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main, maison, services, versions
from app.config import Config
from app.veille import Veille

MDP = "mot-de-passe-de-test"

FICHIER = """
familles: [{ nom: Proches }, { nom: Photos }]
services:
  - { nom: Répertoire, famille: Proches, locale: "http://192.0.2.10:8096", sonde: "http://192.0.2.10:8096/health", depot: repertoire }
  - { nom: Photothèque, famille: Photos, locale: "http://192.0.2.11:2283", version_url: "http://192.0.2.11:2283/api/server/version" }
  - { nom: Statistiques, famille: Photos, locale: "http://192.0.2.11:8181" }
"""


def faux_github(etiquettes=None, etat=200, vus=None):
    """Un faux GitHub : /repos/baloodusudouest/<dépôt>/tags rend les étiquettes données pour ce dépôt."""
    def repondre(req: httpx.Request):
        if vus is not None:
            vus.append(req)
        if etat != 200:
            return httpx.Response(etat, json={"message": "API rate limit exceeded"})
        depot = req.url.path.split("/")[3]
        if req.url.path != f"/repos/baloodusudouest/{depot}/tags" or depot not in (etiquettes or {}):
            return httpx.Response(404)
        return httpx.Response(200, json=[{"name": n, "commit": {"sha": "0" * 40}} for n in etiquettes[depot]])
    return httpx.MockTransport(repondre)


class Reseau:
    def __init__(self):
        self.corps: dict[str, dict | None] = {}
        self.morts: set[str] = set()
        self.immich = {"major": 3, "minor": 1, "patch": 4}
        self.versions_lues: list[str] = []

    async def sonder(self, adresse, jeton=""):
        if any(m in adresse for m in self.morts):
            return False, None, None
        return True, 5, next((c for m, c in self.corps.items() if m in adresse), None)

    async def examiner(self, adresse):
        return ""

    async def versionner(self, adresse):
        self.versions_lues.append(adresse)
        return versions.version_lue(self.immich)


@pytest.fixture()
def reseau():
    return Reseau()


@pytest.fixture()
def veille(tmp_path, reseau):
    (tmp_path / "services.yaml").write_text(FICHIER, encoding="utf-8")
    return Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=reseau.sonder, examiner=reseau.examiner,
                  versionner=reseau.versionner)


@pytest.fixture()
def client(tmp_path, veille):
    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, veille=False),
                     veille=veille)
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def connecter(client):
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200


def tour(v):
    asyncio.run(v.tour())


def tuile(v, nom):
    return next(s for f in v.etat()["familles"] for s in f["services"] if s["nom"] == nom)


# ---------------------------------------------------------------- étiquettes GitHub

def test_plus_haute_etiquette_semver_sans_jeton(tmp_path):
    vus = []
    t = faux_github({"repertoire": ["v2.9.0", "latest", "v2.10.0", "v3", "v4.0.0-rc1", "9.9.9", "v2.10.0-beta", "va.b.c"]}, vus=vus)
    assert versions.lire_depot("repertoire", t) == "2.10.0"           # 2.10 > 2.9 (nombres, pas texte)
    req = vus[0]
    assert str(req.url) == "https://api.github.com/repos/baloodusudouest/repertoire/tags?per_page=100"
    assert req.headers["user-agent"] == "anneau" and "authorization" not in req.headers
    assert versions.plus_haute([{"name": "latest"}, "x", {"name": None}]) is None


def test_relire_garde_l_ancienne_si_github_refuse_ou_injoignable(tmp_path):
    e = versions.relire(tmp_path, ["repertoire", "arbre"], faux_github({"repertoire": ["v1.2.0", "v1.3.0"], "arbre": ["v0.4.1"]}))
    assert e["depots"]["repertoire"]["version"] == "1.3.0" and e["depots"]["arbre"]["version"] == "0.4.1" and not e["erreur"]
    for etat in (403, 429):                                           # limite atteinte : l'ancienne reste
        e = versions.relire(tmp_path, ["repertoire", "arbre"], faux_github(etat=etat))
        assert e["depots"]["repertoire"]["version"] == "1.3.0" and str(etat) in e["erreur"]

    def coupe(req):
        raise httpx.ConnectError("hors ligne")
    e = versions.relire(tmp_path, ["repertoire"], httpx.MockTransport(coupe))
    assert "injoignable" in e["erreur"] and versions.publiees(tmp_path)["depots"]["repertoire"]["version"] == "1.3.0"
    # relu depuis le disque (redémarrage)
    assert json.loads((tmp_path / "versions.json").read_text())["depots"]["repertoire"]["version"] == "1.3.0"
    # un dépôt retiré des tuiles n'est plus gardé
    e = versions.relire(tmp_path, ["arbre"], faux_github({"arbre": ["v0.5.0"]}))
    assert set(e["depots"]) == {"arbre"} and e["depots"]["arbre"]["version"] == "0.5.0"


def test_la_tache_passe_en_erreur_sans_rien_d_autre(tmp_path, veille, monkeypatch):
    registre = maison.Taches()
    monkeypatch.setattr(maison, "TACHES", registre, raising=False)
    main.ETAT.clear()
    main.ETAT.update(veille=veille, transport_versions=faux_github(etat=403))
    cfg = Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False)
    main._declarer(cfg)

    async def un_tour():
        t = asyncio.create_task(main._versions_publiees(cfg))
        await asyncio.sleep(0.2)
        t.cancel()

    try:
        asyncio.run(un_tour())
    finally:
        main.ETAT.clear()
    t = next(x for x in registre.etat(avec_messages=True) if x["nom"] == "versions-publiees")
    assert t["derniere_erreur"] and "403" in t["message"]
    assert "403" in versions.publiees(tmp_path)["erreur"]                     # noté dans le fichier, montré nulle part


# ---------------------------------------------------------------- champs de tuile

def test_champs_depot_et_version_url():
    f = services.comprendre("""
familles: [{ nom: A }]
services:
  - { nom: Un, famille: A, locale: "http://192.0.2.1", depot: Millesime }
  - { nom: Deux, famille: A, locale: "http://192.0.2.2", depot: "../autre" }
  - { nom: Trois, famille: A, locale: "http://192.0.2.3", depot: ".." }
  - { nom: Quatre, famille: A, locale: "http://192.0.2.4", version_url: "pas une adresse" }
  - { nom: Cinq, famille: A, locale: "http://192.0.2.5", version_url: "http://192.0.2.5:2283/api/server/version" }
""")
    s = {x.nom: x for x in f.services}
    assert len(s) == 5                                               # une valeur fausse n'écarte pas la tuile
    assert s["Un"].depot == "Millesime" and s["Deux"].depot == "" and s["Trois"].depot == "" and s["Quatre"].version_url == ""
    assert s["Cinq"].version_url == "http://192.0.2.5:2283/api/server/version"
    assert sum("dépôt" in e for e in f.erreurs) == 2 and any("version_url" in e for e in f.erreurs)


# ---------------------------------------------------------------- version en service

def test_version_url_immich_et_health(veille, reseau):
    reseau.corps[":8096"] = {"ok": True, "version": "2.32.0"}
    tour(veille)
    assert tuile(veille, "Répertoire")["version"] == "2.32.0"
    assert tuile(veille, "Photothèque")["version"] == "3.1.4"
    assert reseau.versions_lues == ["http://192.0.2.11:2283/api/server/version"]   # seulement la tuile qui en a une
    assert tuile(veille, "Statistiques")["version"] is None
    assert versions.version_lue({"version": "v1.4.2"}) == "1.4.2"
    assert versions.version_lue({"major": True, "minor": 1, "patch": 2}) is None
    assert versions.version_lue("texte") is None


def test_lire_version_url_sans_jeton(monkeypatch):
    vus = []

    def repondre(req):
        vus.append(req)
        return httpx.Response(200, json={"major": 3, "minor": 0, "patch": 2})
    monkeypatch.setattr(versions.httpx, "AsyncClient", functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(repondre)))
    assert asyncio.run(versions.lire_version_url("http://192.0.2.11:2283/api/server/version")) == "3.0.2"
    assert "authorization" not in vus[0].headers

    def casse(req):
        return httpx.Response(200, text="pas du json")
    monkeypatch.setattr(versions.httpx, "AsyncClient", functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(casse)))
    assert asyncio.run(versions.lire_version_url("http://192.0.2.11:2283/api/server/version")) is None


# ---------------------------------------------------------------- journal

def test_journal_un_changement_vu_une_seule_fois(veille, reseau, tmp_path):
    reseau.corps[":8096"] = {"ok": True, "version": "2.32.0"}
    tour(veille)
    assert veille.versions.journal == []                              # première lecture : rien à dire
    reseau.corps[":8096"] = {"ok": True, "version": "2.33.0"}
    tour(veille)
    tour(veille)
    j = veille.versions.journal
    assert len(j) == 1 and j[0]["tuile"] == "Répertoire" and (j[0]["de"], j[0]["vers"]) == ("2.32.0", "2.33.0")
    assert json.loads((tmp_path / "journal-versions.json").read_text()) == j
    # une lecture sans version (appli qui ne répond pas, /health sans version) n'efface rien
    reseau.morts.add(":8096")
    tour(veille)
    reseau.morts.clear()
    reseau.corps[":8096"] = {"ok": True}
    tour(veille)
    reseau.corps[":8096"] = {"ok": True, "version": "2.33.0"}
    tour(veille)
    assert len(veille.versions.journal) == 1
    # après un redémarrage de l'Anneau (Watchtower le met à jour aussi) : un changement fait pendant ce temps est vu
    reseau.corps[":8096"] = {"ok": True, "version": "2.34.0"}
    suite = Veille(tmp_path, veille.fichier, sonder=reseau.sonder, examiner=reseau.examiner, versionner=reseau.versionner)
    tour(suite)
    assert [(x["de"], x["vers"]) for x in suite.versions.journal] == [("2.32.0", "2.33.0"), ("2.33.0", "2.34.0")]
    assert suite.versions_des_tuiles()[0]["mise_a_jour_le"] == suite.versions.journal[-1]["le"]


def test_journal_limite_a_200(tmp_path):
    e = versions.EnService(tmp_path)
    for i in range(205):
        e.noter("a", "A", f"1.0.{i}")
    assert len(e.journal) == versions.MAX_JOURNAL and e.journal[-1]["vers"] == "1.0.204"
    assert len(versions.EnService(tmp_path).journal) == versions.MAX_JOURNAL


# ---------------------------------------------------------------- nouveautés depuis la dernière visite

def il_y_a(minutes):
    return (datetime.now().astimezone() - timedelta(minutes=minutes)).isoformat(timespec="seconds")


def test_nouveautes_puis_vu(client, veille, tmp_path):
    assert client.get("/api/versions/nouveautes").status_code == 401           # derrière la session
    assert client.post("/api/versions/vues", json={}).status_code == 401
    connecter(client)
    assert client.get("/api/versions/nouveautes").json()["changements"] == []    # rien : pas de fenêtre
    e = veille.versions
    e.noter("repertoire", "Répertoire", "2.32.0", il_y_a(300))
    e.noter("repertoire", "Répertoire", "2.33.0", il_y_a(120))
    e.noter("phototheque", "Photothèque", "3.1.0", il_y_a(119))
    e.noter("phototheque", "Photothèque", "3.1.4", il_y_a(118))
    e.noter("repertoire", "Répertoire", "2.34.0", il_y_a(100))               # deux changements : une seule ligne
    r = client.get("/api/versions/nouveautes").json()
    lignes = [(c["tuile"], c["de"], c["vers"]) for c in r["changements"]]
    assert r["vu_le"] is None and lignes == [("Répertoire", "2.32.0", "2.34.0"), ("Photothèque", "3.1.0", "3.1.4")]
    # « Vu » jusqu'au plus récent montré ; un changement arrivé après sera montré la prochaine fois
    v = client.post("/api/versions/vues", json={"jusqu_a": r["changements"][0]["le"]}).json()["vu_le"]
    assert v == r["changements"][0]["le"] and client.get("/api/versions/nouveautes").json()["changements"] == []
    assert json.loads((tmp_path / "versions-vues.json").read_text())["vu_le"] == v           # gardé par l'Anneau
    e.noter("repertoire", "Répertoire", "2.35.0")
    assert [c["vers"] for c in client.get("/api/versions/nouveautes").json()["changements"]] == ["2.35.0"]
    client.post("/api/versions/vues", json={})                                # sans heure : maintenant
    assert client.get("/api/versions/nouveautes").json()["changements"] == []
    # l'heure ne recule pas
    assert versions.marquer_vu(tmp_path, il_y_a(1000)) == versions.vu_le(tmp_path) != il_y_a(1000)


def test_aller_retour_n_est_pas_une_nouveaute(tmp_path):
    e = versions.EnService(tmp_path)
    e.noter("a", "A", "1.0.0", il_y_a(10))
    e.noter("a", "A", "1.1.0", il_y_a(9))
    e.noter("a", "A", "1.0.0", il_y_a(8))
    assert e.depuis(None) == []


# ---------------------------------------------------------------- fiche, Réglages : jamais d'orange

def test_fiche_a_jour_ou_pas_encore_en_service_jamais_orange(client, veille, reseau, tmp_path):
    reseau.corps[":8096"] = {"ok": True, "version": "0.12.0"}
    tour(veille)
    versions.relire(tmp_path, ["repertoire"], faux_github({"repertoire": ["v0.12.0"]}))
    t = tuile(veille, "Répertoire")
    assert t["version_phrase"] == "Version 0.12.0 — dernière publiée 0.12.0 (à jour)" and t["a_jour"] is True
    versions.relire(tmp_path, ["repertoire"], faux_github({"repertoire": ["v0.12.0", "v0.13.0"]}))
    t = tuile(veille, "Répertoire")
    assert t["version_phrase"] == "Version 0.12.0 — dernière publiée 0.13.0 : pas encore en service"
    assert t["a_jour"] is False and not t["surveiller"] and t["phrase"] == "" and veille.etat()["surveiller"] == []
    assert t["etat"] == "ok" and veille.etat()["pannes"] == []
    connecter(client)
    r = client.get("/api/versions").json()
    lignes = {x["nom"]: x for x in r["tuiles"]}
    assert set(lignes) == {"Répertoire", "Photothèque"}                      # Statistiques : aucune version connue
    assert (lignes["Répertoire"]["version"], lignes["Répertoire"]["publiee"]) == ("0.12.0", "0.13.0")
    assert lignes["Photothèque"]["version"] == "3.1.4" and lignes["Photothèque"]["publiee"] is None
    assert r["publiees_lues_le"] and "erreur" not in r


def test_phrases():
    assert versions.phrase(None, None) == ""
    assert versions.phrase("3.1.4", None) == "Version 3.1.4"
    assert versions.phrase(None, "1.0.0") == "Version en service inconnue — dernière publiée 1.0.0"
    assert versions.phrase("0.14.0", "0.13.0").endswith("(à jour)")         # plus récente que la publiée : à jour
    assert versions.a_jour("2.10.0", "2.9.0") is True and versions.a_jour("abc", "1.0.0") is None


def test_l_anneau_note_sa_propre_mise_a_jour(tmp_path):
    """Au démarrage, une nouvelle version de l'Anneau lui-même entre au journal (aucune tuile ne le sonde)."""
    from app import versions
    e = versions.EnService(tmp_path)
    e.noter("@anneau", "L'Anneau", "0.12.0", le="2026-11-18T04:00:00+01:00")
    e2 = versions.EnService(tmp_path)
    j = e2.noter("@anneau", "L'Anneau", "0.13.0", le="2026-11-18T05:02:00+01:00")
    assert j and j["de"] == "0.12.0" and j["vers"] == "0.13.0"
    e2.oublier_sauf(set())                       # aucune tuile : « @anneau » reste
    assert versions.EnService(tmp_path).version("@anneau") == "0.13.0"
