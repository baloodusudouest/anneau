"""0.12 : santé des tâches de fond lue dans le /health des applis maison (contrat commun du socle 0.9.0),
tuile « à surveiller » (orange), « Vu », jeton commun seulement vers les applis maison, l'Anneau qui se surveille,
et le /health de l'Anneau lui-même. Noms, adresses et jetons inventés."""
import asyncio
import functools
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main, maison, sante, services, veille as veille_mod
from app.config import Config
from app.veille import Veille

MDP = "mot-de-passe-de-test"
JETON = "jeton-commun-invente-1234"

FICHIER = """
familles: [{ nom: Proches }, { nom: Médias }]
services:
  - { nom: Répertoire, famille: Proches, locale: "http://192.0.2.10:8096", sonde: "http://192.0.2.10:8096/health", sauvegarde: true }
  - { nom: Journal, famille: Proches, locale: "http://192.0.2.10:8097", sonde: "http://192.0.2.10:8097/health", sauvegarde: true }
  - { nom: Cinéma, famille: Médias, locale: "http://192.0.2.11:32400", sonde: "http://192.0.2.11:32400/health" }
  - { nom: Statistiques, famille: Médias, locale: "http://192.0.2.11:8181" }
"""


def iso(il_y_a_s: float) -> str:
    return (datetime.now().astimezone() - timedelta(seconds=il_y_a_s)).isoformat(timespec="seconds")


def tache(nom="synchro-icloud", etat="ok", type_="reguliere", periode=3600, reussite=60, essai=60, erreur=None, message=None):
    t = {"nom": nom, "type": type_, "periode_s": periode, "etat": etat,
         "derniere_reussite": iso(reussite) if reussite is not None else None,
         "dernier_essai": iso(essai) if essai is not None else None,
         "derniere_erreur": iso(erreur) if erreur is not None else None}
    if message:
        t["message"] = message
    return t


def sante_ok(**k):
    return {"ok": True, "version": "2.40.0", "version_socle": "0.9.1", "taches": [tache()],
            "copie_base": {"le": iso(3600), "ok": True, "bases": ["repertoire.db"], "taille": 4096}, **k}


class Reseau:
    """Un faux réseau : chaque adresse rend (vivant, délai, corps du /health) ; on note les jetons reçus."""
    def __init__(self):
        self.corps: dict[str, dict | None] = {}
        self.morts: set[str] = set()
        self.jetons: dict[str, str] = {}
        self.t = 1000.0

    async def sonder(self, adresse, jeton=""):
        self.jetons[adresse] = jeton
        if any(m in adresse for m in self.morts):
            return False, None, None
        return True, 5, next((c for m, c in self.corps.items() if m in adresse), None)

    async def examiner(self, adresse):
        return ""

    def horloge(self):
        return self.t


@pytest.fixture()
def reseau():
    return Reseau()


@pytest.fixture()
def veille(tmp_path, reseau):
    (tmp_path / "services.yaml").write_text(FICHIER, encoding="utf-8")
    return Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=reseau.sonder, examiner=reseau.examiner,
                  horloge=reseau.horloge, jeton=lambda: JETON)


def tour(v):
    asyncio.run(v.tour())


def tuile(v, nom):
    return next(s for f in v.etat()["familles"] for s in f["services"] if s["nom"] == nom)


# ---------------------------------------------------------------- orange

def test_tache_reguliere_en_retard_rend_la_tuile_orange_avec_sa_phrase(veille, reseau):
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=3 * 3600 + 120)])
    tour(veille)
    t = tuile(veille, "Répertoire")
    assert t["surveiller"] and t["etat"] == "ok"                       # le service répond : jamais « en panne »
    assert t["phrase"] == "synchro-icloud n'a pas réussi depuis 3 h"
    e = veille.etat()
    assert e["pannes"] == [] and e["surveiller"] == [{"cle": "repertoire", "nom": "Répertoire", "famille": "Proches",
                                                      "famille_cle": "proches", "phrase": t["phrase"]}]
    assert next(f for f in e["familles"] if f["nom"] == "Proches")["etat"] == "ok"


def test_tache_bloquee_rend_orange(veille, reseau):
    reseau.corps[":8096"] = sante_ok(taches=[tache(nom="collecte", etat="bloquee", essai=2 * 3600 + 30)])
    tour(veille)
    assert tuile(veille, "Répertoire")["phrase"] == "collecte bloquée depuis 2 h"


def test_copie_vieille_ou_ratee_rend_orange(veille, reseau):
    reseau.corps[":8096"] = sante_ok(copie_base={"le": iso(37 * 3600), "ok": True, "bases": ["a.db"], "taille": 1})
    reseau.corps[":8097"] = sante_ok(copie_base={"le": iso(3600), "ok": False, "bases": ["b.db"], "taille": None})
    tour(veille)
    assert tuile(veille, "Répertoire")["phrase"] == "dernière copie des bases il y a 37 h"
    assert tuile(veille, "Journal")["phrase"] == "copie des bases ratée"


def test_copie_recente_ou_jamais_faite_ne_rend_pas_orange(veille, reseau):
    reseau.corps[":8096"] = sante_ok(copie_base={"le": iso(35 * 3600), "ok": True, "bases": ["a.db"], "taille": 1})
    reseau.corps[":8097"] = sante_ok(copie_base={"le": None, "ok": False, "bases": [], "taille": None})
    tour(veille)
    assert not tuile(veille, "Répertoire")["surveiller"] and not tuile(veille, "Journal")["surveiller"]


def test_plusieurs_defauts_une_seule_phrase(veille, reseau):
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=5 * 3600), tache(nom="nettoyage", etat="bloquee", essai=600)],
                                     copie_base={"le": iso(3 * 86400), "ok": True, "bases": [], "taille": 0})
    tour(veille)
    assert tuile(veille, "Répertoire")["phrase"] == "synchro-icloud n'a pas réussi depuis 5 h (+2)"


def test_pas_d_orange_pour_une_tache_a_la_demande_ni_jamais_ni_ok(veille, reseau):
    reseau.corps[":8096"] = sante_ok(taches=[tache(nom="import", type_="demande", etat="erreur", erreur=60, periode=None),
                                             tache(nom="demarrage", etat="jamais", reussite=None, essai=None), tache()])
    tour(veille)
    t = tuile(veille, "Répertoire")
    assert not t["surveiller"] and t["phrase"] == "" and t["defauts"] == []
    assert t["sante"]["taches"][0]["derniere_erreur"]                  # la dernière erreur se lit dans la fiche
    assert t["sante"]["version_socle"] == "0.9.1" and t["sante"]["copie_base"]["bases"] == ["repertoire.db"]


def test_appli_sans_les_nouveaux_champs_rien_ne_change(veille, reseau):
    reseau.corps[":8096"] = {"ok": True, "version": "1.0.0"}
    tour(veille)
    t = tuile(veille, "Répertoire")
    assert t["sante"] is None and not t["surveiller"] and t["etat"] == "ok"
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=9000)])
    tour(veille)
    assert tuile(veille, "Répertoire")["surveiller"]
    reseau.corps[":8096"] = {"ok": True, "version": "1.0.0"}             # appli revenue à une version plus ancienne
    tour(veille)
    assert tuile(veille, "Répertoire")["sante"] is None


def test_une_panne_passe_devant_l_orange(veille, reseau):
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=9000)])
    tour(veille)
    reseau.morts.add(":8096")
    for _ in range(3):
        tour(veille)
    t = tuile(veille, "Répertoire")
    assert t["etat"] == "panne" and not t["surveiller"]


def test_sante_illisible_est_nettoyee():
    lue = sante.lire({"version_socle": 9, "taches": ["x", {"nom": ""}, {"nom": "a" * 300, "etat": "inventé", "type": "autre",
                                                                     "periode_s": float("inf"), "message": "m" * 999}],
                      "copie_base": {"le": 5, "ok": "oui", "bases": "pas une liste", "taille": True}})
    assert lue["version_socle"] is None and len(lue["taches"]) == 1
    t = lue["taches"][0]
    assert len(t["nom"]) == 60 and t["etat"] == "jamais" and t["type"] == "reguliere" and t["periode_s"] is None
    assert len(t["message"]) == 200
    assert lue["copie_base"] == {"le": None, "ok": False, "bases": [], "taille": None}
    assert sante.lire({"ok": True}) is None and sante.lire("texte") is None


# ---------------------------------------------------------------- « Vu »

def test_vu_puis_changement_d_etat(veille, reseau, tmp_path):
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=9000), tache(nom="nettoyage")])
    tour(veille)
    assert veille.marquer_vu("repertoire")
    t = tuile(veille, "Répertoire")
    assert not t["surveiller"] and t["vu"] and veille.etat()["surveiller"] == []
    assert (tmp_path / "vus.json").is_file()
    reseau.t += 120
    tour(veille)                                                          # même défaut, durée qui avance : reste vu
    assert tuile(veille, "Répertoire")["vu"]
    # relu après un redémarrage
    suite = Veille(tmp_path, veille.fichier, sonder=reseau.sonder, examiner=reseau.examiner, jeton=lambda: JETON)
    tour(suite)
    assert tuile(suite, "Répertoire")["vu"]
    # une autre tâche casse : orange de nouveau
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=9000), tache(nom="nettoyage", etat="bloquee", essai=4000)])
    tour(veille)
    assert tuile(veille, "Répertoire")["surveiller"]
    veille.marquer_vu("repertoire")
    # tout se répare : le « vu » est oublié ; la même tâche recasse : orange de nouveau
    reseau.corps[":8096"] = sante_ok()
    tour(veille)
    assert "repertoire" not in veille.vus.vus
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=9000), tache(nom="nettoyage", etat="bloquee", essai=4000)])
    tour(veille)
    assert tuile(veille, "Répertoire")["surveiller"]


def test_vu_refuse_sans_rien_a_surveiller(veille, reseau):
    reseau.corps[":8096"] = sante_ok()
    tour(veille)
    assert not veille.marquer_vu("repertoire") and not veille.marquer_vu("inconnue")


# ---------------------------------------------------------------- le jeton commun

def test_jeton_envoye_seulement_aux_applis_maison(veille, reseau):
    tour(veille)
    j = reseau.jetons
    assert j["http://192.0.2.10:8096/health"] == JETON and j["http://192.0.2.10:8097/health"] == JETON
    assert j["http://192.0.2.11:32400/health"] == ""                     # sonde /health sans « sauvegarde: true »
    assert j["http://192.0.2.11:8181"] == ""


def test_pas_de_jeton_vers_une_tuile_marquee_sans_sonde_health(tmp_path, reseau):
    f = services.comprendre('familles: [{nom: T}]\nservices:\n'
                            '  - {nom: Page, famille: T, locale: "http://192.0.2.12:80", sauvegarde: true}\n')
    v = Veille(tmp_path, f, sonder=reseau.sonder, examiner=reseau.examiner, jeton=lambda: JETON)
    tour(v)
    assert reseau.jetons == {"http://192.0.2.12:80": ""}


def test_sonde_reelle_joint_le_jeton_et_lit_le_json(monkeypatch):
    vus = []

    def repondre(requete):
        vus.append(requete.headers.get("authorization"))
        return httpx.Response(200, json=sante_ok())

    monkeypatch.setattr(veille_mod.httpx, "AsyncClient",
                        functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(repondre)))
    vivant, _, corps = asyncio.run(veille_mod.repond_avec_sante("http://192.0.2.10:8096/health", jeton=JETON))
    assert vivant and corps["version_socle"] == "0.9.1" and vus == [f"Bearer {JETON}"]
    vivant, _, corps = asyncio.run(veille_mod.repond_avec_sante("http://192.0.2.10:8096/health"))
    assert vivant and vus[-1] is None


def test_une_ancienne_sonde_sans_jeton_marche_encore(tmp_path):
    async def sonder(adresse):
        return True, 3

    async def examiner(adresse):
        return ""

    f = services.comprendre(FICHIER)
    v = Veille(tmp_path, f, sonder=sonder, examiner=examiner, jeton=lambda: JETON)
    tour(v)
    assert tuile(v, "Répertoire")["etat"] == "ok" and tuile(v, "Répertoire")["sante"] is None


# ---------------------------------------------------------------- l'Anneau se surveille

def test_veille_arretee_apres_dix_minutes(veille, reseau):
    tour(veille)
    assert veille.etat()["veille"]["arretee"] is False
    reseau.t += 601
    e = veille.etat()["veille"]
    assert e["arretee"] is True and e["age"] == 601 and e["derniere"]
    tour(veille)
    assert veille.etat()["veille"]["arretee"] is False


# ---------------------------------------------------------------- routes et /health de l'Anneau

@pytest.fixture()
def client(tmp_path, veille, monkeypatch):
    for nom in ("MAISON_JETON", "MAISON_JETON_ANCIEN"):
        monkeypatch.delenv(nom, raising=False)
    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, veille=False),
                     veille=veille)
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def test_route_vu_derriere_la_session(client, veille, reseau):
    reseau.corps[":8096"] = sante_ok(taches=[tache(etat="en_retard", reussite=9000)])
    tour(veille)
    assert client.post("/api/sante/vu", json={"cle": "repertoire"}).status_code == 401
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
    e = client.get("/api/etat").json()
    assert e["surveiller"][0]["phrase"].startswith("synchro-icloud") and e["veille"]["arretee"] is False
    assert client.post("/api/sante/vu", json={"cle": "repertoire"}).json() == {"ok": True}
    assert client.get("/api/etat").json()["surveiller"] == []
    assert client.post("/api/sante/vu", json={"cle": "journal"}).status_code == 404


def test_health_de_l_anneau_sans_registre(client, monkeypatch):
    monkeypatch.delattr(maison, "TACHES", raising=False)
    monkeypatch.delattr(maison, "sante", raising=False)
    r = client.get("/health").json()
    assert r["ok"] is True and r["taches"] == [] and r["copie_base"] is None and "version_socle" in r


class FauxRegistre:
    """Le registre du socle 0.9.0, tel que décrit (maison.TACHES) : declarer, tour_async, etat(avec_messages)."""
    def __init__(self):
        self.declarees, self.tours = {}, []

    def declarer(self, nom, periode_s=None, type="reguliere"):
        self.declarees[nom] = (periode_s, type)

    def tour_async(self, nom):
        @asynccontextmanager
        async def cm():
            self.tours.append(nom)
            yield
        return cm()

    def etat(self, avec_messages=False):
        t = {"nom": "veille", "type": "reguliere", "periode_s": 60, "etat": "ok", "derniere_reussite": None,
             "dernier_essai": None, "derniere_erreur": None}
        return [{**t, "message": "texte court"} if avec_messages else t]


def test_health_de_l_anneau_avec_le_registre_messages_seulement_avec_jeton(client, monkeypatch):
    monkeypatch.setattr(maison, "TACHES", FauxRegistre(), raising=False)
    monkeypatch.setattr(maison, "VERSION_SOCLE", "0.9.1", raising=False)
    monkeypatch.delattr(maison, "sante", raising=False)            # repli : maison.py d'avant le socle 0.9.0
    monkeypatch.setenv("MAISON_JETON", JETON)
    r = client.get("/health").json()
    assert r["version_socle"] == "0.9.1" and r["taches"][0]["nom"] == "veille" and "message" not in r["taches"][0]
    assert "message" not in client.get("/health", headers={"Authorization": "Bearer mauvais-jeton"}).json()["taches"][0]
    assert client.get("/health", headers={"Authorization": f"Bearer {JETON}"}).json()["taches"][0]["message"] == "texte court"
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
    assert client.get("/health").json()["taches"][0]["message"] == "texte court"     # une session de l'Anneau suffit


def test_boucles_declarees_et_suivies(tmp_path, veille, monkeypatch):
    registre = FauxRegistre()
    monkeypatch.setattr(maison, "TACHES", registre, raising=False)
    cfg = Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, periode=60,
                 atlas_depot="exemple/atlas", github_jeton="")
    main._declarer(cfg)
    assert registre.declarees == {"veille": (60, "reguliere"), "collecte-de-nuit": (86400, "reguliere"),
                                  "relecture-de-la-carte": (3600, "reguliere")}

    async def un_tour():
        t = asyncio.create_task(main._ronde(veille, 3600))
        await asyncio.sleep(0.05)
        t.cancel()

    asyncio.run(un_tour())
    assert registre.tours == ["veille"] and veille.derniere_sonde


def test_health_de_l_anneau_passe_par_maison_sante_quand_elle_existe(client, monkeypatch):
    appels = []

    def faux_sante(request=None, jeton_commun=None, session_ok=False):
        appels.append(session_ok)
        return {"version_socle": "0.9.1", "taches": [], "copie_base": None}

    monkeypatch.setattr(maison, "sante", faux_sante, raising=False)
    r = client.get("/health").json()
    assert r["ok"] is True and r["version_socle"] == "0.9.1" and r["copie_base"] is None and appels == [False]
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200
    client.get("/health")
    assert appels[-1] is True
