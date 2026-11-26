"""0.19 — écarts de l'audit (https vérifié par le serveur, lecture seule), table des routes classées, réveil du PC par un
faux webhook de Home Assistant, champs de tuile « reveil » et « besoin ». Tout est inventé : aucune vraie adresse."""
import asyncio
import dataclasses

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import main, reveil, services
from app.config import Config
from app.veille import Veille

MDP = "mot-de-passe-de-test"
ORIGINE = {"Origin": "http://testserver"}
HTTPS = {"X-Forwarded-Proto": "https"}
CLE_AGE = "age1" + "q" * 58
ARMURE = "-----BEGIN AGE ENCRYPTED FILE-----\nYWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNTUxOSBhYmMK\n-----END AGE ENCRYPTED FILE-----\n"
WEBHOOK = "identifiant-secret-du-webhook-0123456789"

SERVICES = """
familles:
  - { nom: Photos, icone: image }
  - { nom: Machines, icone: serveur }
services:
  - { nom: Pc de calcul, famille: Machines, locale: "http://192.0.2.12:3003", sonde: "http://192.0.2.12:3003/ping", arret_attendu: true, cadre: false, reveil: true }
  - { nom: Millésime, famille: Photos, locale: "http://192.0.2.10:8098", sonde: "http://192.0.2.10:8098/health", besoin: Pc de calcul }
  - { nom: Galerie, famille: Photos, locale: "http://192.0.2.10:2283", besoin: Inconnu }
"""


class FauxHA:
    """Home Assistant inventé : le webhook (200 même inconnu, comme HA), /api/ (401 sans jeton)."""
    def __init__(self):
        self.appels: list[str] = []
        self.code = 200
        self.panne = False

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        if self.panne:
            raise httpx.ConnectError("injoignable")
        self.appels.append(f"{requete.method} {requete.url.path}")
        if requete.url.path == "/api/":
            return httpx.Response(401)
        return httpx.Response(self.code)


class Monde:
    def __init__(self):
        self.vivants: set[str] = set()

    async def sonder(self, adresse, *a, **k):
        return (any(v in adresse for v in self.vivants), 5)

    async def examiner(self, adresse):
        return ""


@pytest.fixture()
def monde():
    return Monde()


@pytest.fixture()
def faux():
    return FauxHA()


def _client(tmp_path, monde, faux, **cfg):
    (tmp_path / "services.yaml").write_text(SERVICES, encoding="utf-8")
    v = Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=monde.sonder, examiner=monde.examiner, versionner=monde.examiner)
    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False,
                                veille=False, ha_url="http://ha.exemple:8123", ha_webhook_reveil=WEBHOOK, **cfg),
                     veille=v, transport_ha=httpx.MockTransport(faux))
    return TestClient(main.app)


@pytest.fixture()
def client(tmp_path, monde, faux):
    with _client(tmp_path, monde, faux) as c:
        assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
        yield c
    main.ETAT.clear()


def tour():
    asyncio.run(main.un_tour(main.ETAT["veille"]))


def fiche(client, nom):
    return next(s for f in client.get("/api/etat").json()["familles"] for s in f["services"] if s["nom"] == nom)


# ---------------------------------------------------------------- écart 2 : https vérifié par le serveur

def test_ecrire_un_secret_en_http_est_refuse(client):
    r = client.put("/api/cle-publique", json={"cle_publique": CLE_AGE})
    assert r.status_code == 403 and "https" in r.json()["detail"] and "ANNEAU_GARDE_HTTPS" in r.json()["detail"]
    r = client.post("/api/variables-chiffrees", content=ARMURE.encode(), headers={"Content-Type": "text/plain"})
    assert r.status_code == 403
    assert client.get("/api/cle-publique").json() == {"cle_publique": ""}


@pytest.mark.parametrize("entetes", [HTTPS, {"Origin": "https://nas.exemple.ts.net:9094"}])
def test_ecrire_un_secret_en_https_passe(client, entetes):
    assert client.put("/api/cle-publique", json={"cle_publique": CLE_AGE}, headers=entetes).status_code == 200
    r = client.post("/api/variables-chiffrees", content=ARMURE.encode(), headers={"Content-Type": "text/plain", **entetes})
    assert r.status_code == 200


def test_sur_la_machine_meme_l_anneau_est_sur(client):
    """localhost, comme pour le navigateur (isSecureContext) : rien ne quitte la machine."""
    assert client.put("/api/cle-publique", json={"cle_publique": CLE_AGE}, headers={"Host": "127.0.0.1:8094"}).status_code == 200


def test_lire_les_exports_reste_permis_en_http(client):
    client.post("/api/variables-chiffrees", content=ARMURE.encode(), headers={"Content-Type": "text/plain", **HTTPS})
    exports = client.get("/api/variables-chiffrees").json()["exports"]
    assert exports
    nom = exports[0]["nom"] if isinstance(exports[0], dict) else exports[0]
    assert client.get(f"/api/variables-chiffrees/{nom}").status_code == 200
    assert client.get("/api/cle-publique").status_code == 200


def test_variable_de_secours_coupe_la_garde(tmp_path, monde, faux):
    with _client(tmp_path, monde, faux, garde_https=False) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        assert c.put("/api/cle-publique", json={"cle_publique": CLE_AGE}).status_code == 200
        assert c.get("/api/https").json()["garde"] is False
    main.ETAT.clear()


def test_diagnostic_dit_par_quel_signal(client):
    assert client.get("/api/https").json() | {} == {"https": False, "par": "", "garde": True, "relais": "", "lecture_seule": False}
    assert client.get("/api/https", headers=HTTPS).json()["par"] == "relais"
    assert client.get("/api/https", headers={"Origin": "https://x.exemple"}).json()["par"] == "origine"
    assert client.get("/api/https", headers={"Host": "localhost:8094"}).json()["par"] == "machine"


def test_config_lit_la_variable_de_secours(monkeypatch):
    from app import config
    monkeypatch.setenv("MAISON_PASSWORD", "un-mot-de-passe-assez-long")
    for valeur, attendu in (("", True), ("oui", True), ("non", False), ("NON", False), ("false", False)):
        monkeypatch.setenv("ANNEAU_GARDE_HTTPS", valeur)
        assert config.charger().garde_https is attendu


# ---------------------------------------------------------------- table des routes classées

# ailleurs : écrit ou ordonne chez un autre service → jamais en lecture seule ; secret : écrit un secret → https ;
# chez-soi : n'écrit que dans le dossier de l'Anneau ; lecture : rien n'est écrit ; public : avant la session.
ROUTES = {
    ("GET", "/health"): "public", ("GET", "/api/session"): "public", ("POST", "/api/connexion"): "public",
    ("POST", "/api/ha/etat"): "public", ("POST", "/api/deconnexion"): "chez-soi",
    ("GET", "/api/https"): "lecture", ("GET", "/api/etat"): "lecture",
    ("POST", "/api/reveil/{cle}"): "ailleurs",
    ("POST", "/api/conteneurs/{cle}/{geste}"): "ailleurs", ("POST", "/api/majs/{ident}/mettre-a-jour"): "ailleurs",
    ("POST", "/api/majs/verifier"): "lecture", ("GET", "/api/conteneurs/journal"): "lecture",
    ("GET", "/api/conteneurs/{cle}/stats"): "lecture", ("GET", "/api/applis/{cle}/services"): "lecture",
    ("POST", "/api/applis/{cle}/services/{service}/verifier"): "lecture",
    ("POST", "/api/pannes/vue"): "chez-soi", ("POST", "/api/sante/vu"): "chez-soi",
    ("GET", "/api/versions"): "lecture", ("GET", "/api/versions/nouveautes"): "lecture", ("POST", "/api/versions/vues"): "chez-soi",
    ("POST", "/api/recharger"): "chez-soi", ("POST", "/api/services/importer"): "chez-soi",
    ("GET", "/externe/services"): "lecture", ("GET", "/api/reglages"): "lecture", ("PUT", "/api/reglages"): "chez-soi",
    ("GET", "/api/cle-publique"): "lecture", ("PUT", "/api/cle-publique"): "secret",
    ("GET", "/externe/sauvegarde"): "lecture", ("GET", "/externe/sauvegardes/{appli}"): "lecture",
    ("GET", "/api/sauvegardes"): "lecture", ("POST", "/api/sauvegardes"): "chez-soi", ("GET", "/api/sauvegardes/{le}"): "lecture",
    ("GET", "/api/restaurer"): "lecture", ("POST", "/api/restaurer"): "chez-soi",
    ("GET", "/api/variables-chiffrees"): "lecture", ("POST", "/api/variables-chiffrees"): "secret",
    ("GET", "/api/variables-chiffrees/{nom}"): "lecture",
    ("GET", "/api/stack"): "lecture", ("POST", "/api/stack"): "chez-soi", ("GET", "/api/stack/fichier"): "lecture",
    ("GET", "/api/services/fichier"): "lecture", ("GET", "/api/carte"): "lecture", ("POST", "/api/carte/relire"): "chez-soi",
    ("GET", "/{chemin:path}"): "public",
}


def _routes():
    return {(m, r.path) for r in main.app.routes if isinstance(r, APIRoute) for m in r.methods if m != "HEAD"}


def test_chaque_route_est_classee():
    """Une route nouvelle doit être rangée ici : sinon personne n'a décidé si elle écrit ailleurs ou un secret."""
    manque = _routes() - set(ROUTES)
    assert not manque, f"Routes à classer dans ROUTES : {sorted(manque)}"
    assert not set(ROUTES) - _routes(), "ROUTES nomme une route qui n'existe plus"


def _appeler(client, methode, chemin, entetes):
    chemin = chemin.replace("{cle}", "pc-de-calcul").replace("{geste}", "allumer").replace("{ident}", "x")
    return client.request(methode, chemin, headers=entetes, json={})


def test_routes_secret_refusees_en_http(client):
    for (m, chemin), genre in ROUTES.items():
        if genre == "secret":
            assert _appeler(client, m, chemin, ORIGINE).status_code == 403, chemin


def test_routes_ailleurs_refusees_en_lecture_seule(client, monkeypatch, faux):
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "oui")
    for (m, chemin), genre in ROUTES.items():
        if genre == "ailleurs":
            r = _appeler(client, m, chemin, ORIGINE)
            assert r.status_code in (403, 404), (chemin, r.status_code)     # 404 : Portainer non réglé dans ce test
    assert not [a for a in faux.appels if "webhook" in a]


# ---------------------------------------------------------------- champs de tuile

def test_reveil_et_besoin_lus(tmp_path):
    (tmp_path / "services.yaml").write_text(SERVICES, encoding="utf-8")
    f = services.lire(tmp_path / "services.yaml")
    t = {s.nom: s for s in f.services}
    assert t["Pc de calcul"].reveil is True and t["Millésime"].reveil is False
    assert t["Millésime"].besoin == "pc-de-calcul"
    assert t["Galerie"].besoin == "" and any("Galerie : besoin" in e for e in f.erreurs)


def test_reveil_doit_etre_vrai_au_sens_strict(tmp_path):
    (tmp_path / "services.yaml").write_text(SERVICES.replace("reveil: true", 'reveil: "oui"'), encoding="utf-8")
    f = services.lire(tmp_path / "services.yaml")
    assert not any(s.reveil for s in f.services)


# ---------------------------------------------------------------- réveil

def test_reveil_appelle_le_webhook_et_suit_jusqu_a_repond(client, monde, faux):
    tour()
    v = fiche(client, "Pc de calcul")["reveil"]
    assert v["possible"] is True and v["eteint"] is True
    r = client.post("/api/reveil/pc-de-calcul", headers=ORIGINE)
    assert r.status_code == 202 and r.json()["ordre"]["etat"] == "attente"
    assert faux.appels == [f"POST /api/webhook/{WEBHOOK}"]
    assert fiche(client, "Pc de calcul")["reveil"]["possible"] is False          # pas de second clic pendant le suivi
    monde.vivants.add("192.0.2.12")
    tour()
    v = fiche(client, "Pc de calcul")["reveil"]
    assert v["ordre"]["etat"] == "fini" and v["eteint"] is False and v["raison"] == "Elle répond déjà."
    journal = client.get("/api/conteneurs/journal").json()["lignes"]
    assert [l["resultat"] for l in journal if l["quoi"] == "reveil"][:2] == ["fini", "lancé"]
    assert WEBHOOK not in str(journal) and WEBHOOK not in client.get("/api/etat").text


def test_reveil_perdu_apres_trois_minutes(client, faux):
    tour()
    t = [0.0]
    main.ETAT["reveil_pc"]._horloge = lambda: t[0]
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 202
    t[0] = reveil.DELAI + 1
    tour()
    o = fiche(client, "Pc de calcul")["reveil"]["ordre"]
    assert o["etat"] == "perdu" and "Wake-on-LAN" in o["phrase"]


def test_reveil_anti_rebond(client):
    tour()
    t = [0.0]
    main.ETAT["reveil_pc"]._horloge = lambda: t[0]
    main.ETAT["reveil_pc"].ordres["pc-de-calcul"] = {"etat": "perdu", "a": 0.0, "phrase": ""}
    t[0] = 30
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 429


def test_reveil_refuse_si_deja_allume(client, monde, faux):
    monde.vivants.add("192.0.2.12")
    tour()
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 409
    assert not faux.appels


def test_reveil_refuse_sans_origine_ou_tuile_non_marquee(client, faux):
    tour()
    assert client.post("/api/reveil/pc-de-calcul").status_code == 403
    assert client.post("/api/reveil/pc-de-calcul", headers={"Origin": "http://autre.exemple"}).status_code == 403
    assert client.post("/api/reveil/millesime", headers=ORIGINE).status_code == 403
    assert client.post("/api/reveil/inconnue", headers=ORIGINE).status_code == 404
    assert not faux.appels


def test_reveil_en_lecture_seule(client, monkeypatch, faux):
    monkeypatch.setenv("ANNEAU_LECTURE_SEULE", "oui")
    tour()
    v = fiche(client, "Pc de calcul")["reveil"]
    assert v["possible"] is False and "Lecture seule" in v["raison"]
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 403
    assert not faux.appels


def test_reveil_sans_variables(tmp_path, monde, faux):
    (tmp_path / "services.yaml").write_text(SERVICES, encoding="utf-8")
    v = Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=monde.sonder, examiner=monde.examiner, versionner=monde.examiner)
    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "s", attente_connexion=False, veille=False),
                     veille=v)
    with TestClient(main.app) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        asyncio.run(main.un_tour(v))
        r = fiche(c, "Pc de calcul")["reveil"]
        assert r["possible"] is False and "ANNEAU_HA_URL" in r["raison"]
        assert c.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 403
    main.ETAT.clear()


def test_ha_injoignable_ou_refus(client, faux):
    tour()
    faux.panne = True
    r = client.post("/api/reveil/pc-de-calcul", headers=ORIGINE)
    assert r.status_code == 502 and "ne répond pas" in r.json()["detail"]
    faux.panne, faux.code = False, 405
    main.ETAT["reveil_pc"].ordres.clear()
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 502


def test_millesime_montre_le_besoin(client, monde):
    tour()
    b = fiche(client, "Millésime")["besoin"]
    assert b["cle"] == "pc-de-calcul" and b["nom"] == "Pc de calcul" and b["reveil"]["possible"] is True
    assert fiche(client, "Galerie")["besoin"] is None
    assert fiche(client, "Millésime")["reveil"] is None


def test_verifier_ne_declenche_jamais_le_webhook(client, faux):
    r = client.post("/api/maison/services/home-assistant/verifier", headers=ORIGINE)
    assert r.status_code == 200, r.text
    assert faux.appels == ["GET /api/"]


def test_repr_sans_secret():
    r = reveil.Reveil("http://ha.exemple", WEBHOOK)
    assert WEBHOOK not in repr(r)
    c = Config(password=MDP, data=None, static=None, ha_url="http://ha.exemple", ha_webhook_reveil=WEBHOOK)
    assert WEBHOOK not in repr(c)


def test_apres_un_reveil_reussi_un_nouveau_reveil_est_permis(client, monde, faux):
    tour()
    t = [0.0]
    main.ETAT["reveil_pc"]._horloge = lambda: t[0]
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 202
    monde.vivants.add("192.0.2.12")
    tour()
    monde.vivants.clear()                      # rééteint aussitôt
    tour()
    t[0] = 10
    assert client.post("/api/reveil/pc-de-calcul", headers=ORIGINE).status_code == 202
    assert len([a for a in faux.appels if "webhook" in a]) == 2
