"""0.8 : sauvegarde des réglages des applis maison, portes pour Restaurer, exports chiffrés des variables,
réglages de l'Anneau, nettoyage des anciens noms. Sans réseau : les applis sont de faux services."""
import asyncio
import json
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import main, maison, sauvegardes, services
from app.config import Config, charger
from app.veille import Veille

MDP = "mot-de-passe-de-test"
JETON = "jeton-commun-essai"
CLE_AGE = "age1" + "q" * 58
ARMURE = "-----BEGIN AGE ENCRYPTED FILE-----\nYWdlLWVuY3J5cHRpb24ub3JnL3YxCi0+IFgyNTUxOQ==\n-----END AGE ENCRYPTED FILE-----\n"

FICHIER = """
familles: [{ nom: Proches }, { nom: Photos }, { nom: Machines }]
services:
  - { nom: Carnet, famille: Proches, locale: "http://exemple.invalid:1", sonde: "http://exemple.invalid:1/health" }
  - { nom: Millésime, famille: Photos, locale: "http://exemple.invalid:2", sonde: "http://exemple.invalid:2/health" }
  - { nom: Muet, famille: Photos, locale: "http://exemple.invalid:3", sonde: "http://exemple.invalid:3/health" }
  - { nom: Bavard, famille: Photos, locale: "http://exemple.invalid:4", sonde: "http://exemple.invalid:4/health" }
  - { nom: Ancien, famille: Photos, locale: "http://exemple.invalid:5", sonde: "http://exemple.invalid:5/health" }
  - { nom: Immich, famille: Photos, locale: "http://exemple.invalid:6" }
  - { nom: Nginx, famille: Photos, locale: "http://exemple.invalid:7", sonde: "http://exemple.invalid:7/health", sauvegarde: false }
  - { nom: Calcul, famille: Machines, locale: "http://exemple.invalid:8", sonde: "http://exemple.invalid:8/ping" }
"""


def reponse(appli, **reglages):
    return {"contrat": 1, "appli": appli, "version": "1.0.0", "le": "2026-11-16T03:30:00+01:00", "reglages": reglages}


class FauxServices:
    """Chaque adresse de base répond comme une appli : bien, mal, pas du tout."""
    def __init__(self):
        self.demandes: list[tuple[str, str]] = []

    async def __call__(self, url, jeton):
        self.demandes.append((url, jeton))
        if jeton != JETON:
            return 401, {"detail": "Jeton refusé."}
        if ":1/" in url:
            return 200, reponse("carnet", tri="nom", par_page=50)
        if ":2/" in url:
            return 200, reponse("millesime", seuil=0.8)
        if ":3/" in url:
            raise OSError("injoignable")
        if ":4/" in url:
            return 200, reponse("bavard", mot_de_passe="ne-doit-jamais-sortir", couleur="bleu")
        if ":5/" in url:
            return 200, {**reponse("ancien"), "contrat": 0}
        return 404, None


@pytest.fixture()
def env(monkeypatch):
    for nom in ("MAISON_JETON", "MAISON_JETON_ANCIEN", "MAISON_PASSWORD", "ANNEAU_PASSWORD"):
        monkeypatch.delenv(nom, raising=False)
    return monkeypatch


@pytest.fixture()
def fichier(tmp_path):
    (tmp_path / "services.yaml").write_text(FICHIER, encoding="utf-8")
    return services.lire(tmp_path / "services.yaml")


@pytest.fixture()
def faux():
    return FauxServices()


@pytest.fixture()
def client(tmp_path, fichier, faux, env):
    async def sonder(adresse):
        return True, 1

    async def examiner(adresse):
        return ""

    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, veille=False),
                     veille=Veille(tmp_path, fichier, sonder=sonder, examiner=examiner), lire_sauvegarde=faux)
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def connecter(c):
    assert c.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200


def jour():
    return datetime.now().astimezone().date().isoformat()


# ---------------------------------------------------------------- nettoyage des anciens noms

def test_mot_de_passe_commun_seul(env, tmp_path):
    env.setenv("ANNEAU_DATA", str(tmp_path))
    env.setenv("ANNEAU_PASSWORD", "ancien-mot-de-passe-assez-long")
    with pytest.raises(SystemExit, match="MAISON_PASSWORD est absent ou trop court"):
        charger()                                                    # l'ancien nom seul ne suffit plus
    env.setenv("MAISON_PASSWORD", "nouveau-mot-de-passe-long")
    assert charger().password == "nouveau-mot-de-passe-long"


def test_portes_et_jetons(client, env):
    """Les portes des applis : MAISON_JETON seulement. Le secret de Home Assistant n'ouvre pas les portes communes,
    et MAISON_JETON n'ouvre pas celle de Home Assistant."""
    portes = ("/externe/sauvegarde", "/externe/sauvegardes/carnet", "/externe/services")
    for p in portes:
        assert client.get(p, headers={"Authorization": f"Bearer {JETON}"}).status_code == 404, p     # vide : fermé
    env.setenv("MAISON_JETON", JETON)
    env.setenv("ANNEAU_SECRET_HA", "secret-ha-essai")
    for p in portes:
        assert client.get(p).status_code == 401, p
        assert client.get(p, headers={"Authorization": "Bearer secret-ha-essai"}).status_code == 401, p
        assert client.get(p, headers={"Authorization": f"Bearer {JETON}"}).status_code == 200, p
    r = client.post("/api/ha/etat", json={}, headers={"X-Anneau-Secret": JETON})
    assert r.status_code in (401, 503)


# ---------------------------------------------------------------- réglages de l'Anneau

def test_reglages_defauts_put_et_types(client):
    assert client.get("/api/reglages").status_code == 401
    connecter(client)
    assert client.get("/api/reglages").json()["reglages"] == {"heure_sauvegarde": "03:30", "cle_publique": ""}
    r = client.put("/api/reglages", json={"reglages": {"heure_sauvegarde": "04:15"}})
    assert r.status_code == 200 and r.json()["reglages"]["heure_sauvegarde"] == "04:15"
    for faux in ({"heure_sauvegarde": "25:00"}, {"heure_sauvegarde": 4}, {"heure_sauvegarde": "4h"},
                 {"cle_publique": "pas-une-cle"}, {"cle_publique": "AGE-SECRET-KEY-1" + "Q" * 58}):
        r = client.put("/api/reglages", json={"reglages": faux})
        assert r.status_code == 400 and r.json()["detail"], faux
    assert "clé privée" in client.put("/api/reglages", json={"reglages": {"cle_publique": "AGE-SECRET-KEY-1ABC"}}).json()["detail"]
    assert client.get("/api/reglages").json()["reglages"]["heure_sauvegarde"] == "04:15"


def test_reglages_gardes_au_redemarrage(tmp_path):
    r = maison.Reglages(tmp_path / "reglages.json", sauvegardes.DEFAUTS, {})
    r.changer({"heure_sauvegarde": "02:00"})
    assert maison.Reglages(tmp_path / "reglages.json", sauvegardes.DEFAUTS, {}).get("heure_sauvegarde") == "02:00"


def test_cle_publique(client):
    assert client.get("/api/cle-publique").status_code == 401
    connecter(client)
    assert client.get("/api/cle-publique").json() == {"cle_publique": ""}
    assert client.put("/api/cle-publique", json={"cle_publique": CLE_AGE}).json() == {"cle_publique": CLE_AGE}
    assert client.get("/api/cle-publique").json() == {"cle_publique": CLE_AGE}
    r = client.put("/api/cle-publique", json={"cle_publique": "AGE-SECRET-KEY-1" + "Q" * 58})
    assert r.status_code == 400 and "clé privée" in r.json()["detail"]
    assert client.put("/api/cle-publique", json={"cle_publique": "age1court"}).status_code == 400
    assert client.get("/api/cle-publique").json() == {"cle_publique": CLE_AGE}


def test_sa_propre_sauvegarde_sans_la_cle(client, env):
    connecter(client)
    client.put("/api/cle-publique", json={"cle_publique": CLE_AGE})
    env.setenv("MAISON_JETON", JETON)
    r = client.get("/externe/sauvegarde", headers={"Authorization": f"Bearer {JETON}"}).json()
    assert r["contrat"] == 1 and r["appli"] == "anneau" and r["reglages"] == {"heure_sauvegarde": "03:30"}
    assert CLE_AGE not in json.dumps(r) and "cle_publique" not in json.dumps(r)


# ---------------------------------------------------------------- collecte

def test_adresse_de_base_et_tuiles_maison(fichier):
    assert sauvegardes.base("http://h.invalid:8096/health") == "http://h.invalid:8096"
    assert sauvegardes.base("http://h.invalid/appli/health/") == "http://h.invalid/appli"
    assert sauvegardes.base("http://h.invalid:3003/ping") == "" and sauvegardes.base("") == ""
    assert [n for n, _ in sauvegardes.applis_maison(fichier)] == ["Carnet", "Millésime", "Muet", "Bavard", "Ancien"]


def test_sauvegarder_maintenant(client, env, faux, tmp_path):
    assert client.post("/api/sauvegardes").status_code == 401
    connecter(client)
    env.setenv("MAISON_JETON", JETON)
    r = client.post("/api/sauvegardes")
    assert r.status_code == 200, r.text
    d = r.json()["derniere"]
    assert d["applis"] == ["anneau", "carnet", "millesime"]
    assert set(d["ratees"]) == {"Muet", "Bavard", "Ancien"}
    assert "secret" in d["ratees"]["Bavard"] and "contrat" in d["ratees"]["Ancien"] and "injoignable" in d["ratees"]["Muet"]
    assert all(j == JETON for _, j in faux.demandes) and len(faux.demandes) == 5
    assert {u for u, _ in faux.demandes} >= {"http://exemple.invalid:1/externe/sauvegarde"}
    f = next((tmp_path / "sauvegardes").glob("*-manuelle.json"))           # à la demande : fichier à part
    assert not (tmp_path / "sauvegardes" / f"{jour()}.json").exists()
    contenu = json.loads(f.read_text(encoding="utf-8"))
    assert contenu["contrat"] == 1 and set(contenu["applis"]) == {"anneau", "carnet", "millesime"}
    assert contenu["applis"]["carnet"]["reglages"] == {"tri": "nom", "par_page": 50}
    assert "ne-doit-jamais-sortir" not in f.read_text(encoding="utf-8")      # rien n'est écrit pour une réponse refusée
    assert not list((tmp_path / "sauvegardes").glob("*.tmp"))
    # chaque sauvegarde à la demande a son fichier ; le journal garde une ligne par collecte
    client.post("/api/sauvegardes")
    assert len(list((tmp_path / "sauvegardes").glob("*-manuelle.json"))) == 2
    l = client.get("/api/sauvegardes").json()
    assert len(l["historique"]) == 2 and "3 ratée(s)" in l["historique"][0]
    recente = l["fichiers"][0]["date"]
    assert recente.endswith("-manuelle") and l["fichiers"][0]["applis"] == ["anneau", "carnet", "millesime"]
    assert l["a_traiter"][0]["phrase"] == "Sauvegarde ratée"
    complet = client.get(f"/api/sauvegardes/{recente}").json()
    assert complet["applis"]["millesime"]["reglages"] == {"seuil": 0.8}
    assert "attachment" in client.get(f"/api/sauvegardes/{recente}?telecharger=true").headers["content-disposition"]
    assert client.get("/api/sauvegardes/2026-13-40").status_code == 400
    assert client.get("/api/sauvegardes/2026-13-40-101010-manuelle").status_code == 400
    assert client.get("/api/sauvegardes/2020-01-01").status_code == 404


def test_collecte_sans_jeton(client, faux):
    connecter(client)
    d = client.post("/api/sauvegardes").json()["derniere"]
    assert d["applis"] == ["anneau"] and len(d["ratees"]) == 5 and not faux.demandes
    assert "MAISON_JETON" in d["ratees"]["Carnet"]


def test_une_appli_trop_lente_n_arrete_pas_les_autres(tmp_path, fichier, monkeypatch):
    monkeypatch.setattr(sauvegardes, "DELAI", 0.05)

    async def lire(url, jeton):
        if ":1/" in url:
            await asyncio.sleep(5)
        return 200, reponse("app" + url.split(":")[2][0])

    d = asyncio.run(sauvegardes.collecter(tmp_path, fichier, {}, jeton=JETON, lire=lire))
    assert d["ratees"] == {"Carnet": "pas de réponse en 10 s"} and len(d["applis"]) == 4


def test_ecriture_ratee_et_a_traiter(tmp_path, fichier, monkeypatch):
    t0 = datetime(2026, 11, 16, 3, 30).astimezone()
    sauvegardes.demarrer(tmp_path, t0)
    assert sauvegardes.a_traiter(tmp_path, t0 + timedelta(hours=35)) == []
    assert "36 h" in sauvegardes.a_traiter(tmp_path, t0 + timedelta(hours=37))[0]["detail"]   # jamais de collecte réussie

    async def bien(url, jeton):
        return 200, reponse("app" + url.split(":")[2][0])
    tuiles = dataclasses_remplace(fichier, ["Carnet"])
    asyncio.run(sauvegardes.collecter(tmp_path, tuiles, {}, jeton=JETON, lire=bien, maintenant=t0))
    assert sauvegardes.a_traiter(tmp_path, t0 + timedelta(hours=1)) == []                       # tout va bien
    assert sauvegardes.a_traiter(tmp_path, t0 + timedelta(hours=37))                            # plus de 36 h sans collecte

    def refuse(*a, **k):
        raise PermissionError("lecture seule")
    monkeypatch.setattr(sauvegardes, "_ecrire_atomique", refuse)
    d = asyncio.run(sauvegardes.collecter(tmp_path, tuiles, {}, jeton=JETON, lire=bien, maintenant=t0 + timedelta(hours=2)))
    assert "lecture seule" in d["erreur"]
    monkeypatch.undo()
    assert "pas pu être écrit" in sauvegardes.a_traiter(tmp_path, t0 + timedelta(hours=3))[0]["detail"]


def dataclasses_remplace(fichier, noms):
    import dataclasses
    return dataclasses.replace(fichier, services=tuple(s for s in fichier.services if s.nom in noms))


def test_a_traiter_dans_l_etat(client, env):
    connecter(client)
    assert client.get("/api/etat").json()["a_traiter"] == []
    client.post("/api/sauvegardes")                                  # sans jeton : toutes ratées
    t = client.get("/api/etat").json()["a_traiter"]
    assert t and t[0]["phrase"] == "Sauvegarde ratée" and "5 appli(s)" in t[0]["detail"]


def test_heure_de_la_collecte_automatique(tmp_path, fichier):
    t = datetime(2026, 11, 16, 3, 29).astimezone()
    assert not sauvegardes.a_lancer(tmp_path, "03:30", t)
    assert sauvegardes.a_lancer(tmp_path, "03:30", t + timedelta(minutes=1))
    assert sauvegardes.a_lancer(tmp_path, "03:30", t + timedelta(hours=8))                    # rattrapée au démarrage
    asyncio.run(sauvegardes.collecter(tmp_path, dataclasses_remplace(fichier, []), {}, jeton=JETON,
                                      maintenant=t + timedelta(minutes=1), automatique=True))
    assert not sauvegardes.a_lancer(tmp_path, "03:30", t + timedelta(hours=8))                # déjà faite aujourd'hui
    assert sauvegardes.a_lancer(tmp_path, "03:30", t + timedelta(days=1, minutes=1))


def test_retention_manuelles_et_automatiques(tmp_path):
    d = tmp_path / "sauvegardes"
    d.mkdir()
    debut = datetime(2026, 8, 20)
    autos = [(debut + timedelta(days=i)).date().isoformat() for i in range(90)]
    for x in autos:
        (d / f"{x}.json").write_text("{}")
    manuelles = [f"2026-11-{j:02d}-100000-manuelle" for j in range(1, 9)]          # 8 à la demande
    for x in manuelles:
        (d / f"{x}.json").write_text("{}")
    sauvegardes.retention(tmp_path)
    restent = {f.stem for f in d.glob("*.json")}
    # premières de trimestre (T3 2026 : 2026-08-20 ; T4 : 2026-10-01) ; les 3 derniers trimestres seulement
    assert restent == set(autos[-30:]) | {"2026-08-20", "2026-10-01"} | set(manuelles[-5:])


def test_une_collecte_a_la_demande_ne_remplace_pas_l_automatique(tmp_path, fichier):
    t = datetime(2026, 11, 16, 3, 30).astimezone()
    asyncio.run(sauvegardes.collecter(tmp_path, dataclasses_remplace(fichier, []), {}, jeton=JETON,
                                      maintenant=t, automatique=True))
    asyncio.run(sauvegardes.collecter(tmp_path, dataclasses_remplace(fichier, []), {}, jeton=JETON,
                                      maintenant=t + timedelta(hours=2)))
    asyncio.run(sauvegardes.collecter(tmp_path, dataclasses_remplace(fichier, []), {}, jeton=JETON,
                                      maintenant=t + timedelta(hours=2)))              # même seconde : suffixe
    noms = sorted(f.stem for f in (tmp_path / "sauvegardes").glob("*.json") if f.stem != "etat")
    assert noms == ["2026-11-16", "2026-11-16-053000-2-manuelle", "2026-11-16-053000-manuelle"]
    assert sauvegardes.identifiant_valide("2026-11-16-053000-2-manuelle")
    assert not sauvegardes.identifiant_valide("2026-11-16-05300-manuelle")


def test_retention_trimestres(tmp_path):
    """Les 30 derniers jours, plus la première automatique de chacun des 3 derniers trimestres."""
    d = tmp_path / "sauvegardes"
    d.mkdir()
    debut, fin = date(2025, 6, 1), date(2026, 11, 16)
    jours = [(debut + timedelta(days=i)).isoformat() for i in range((fin - debut).days + 1)]
    for x in jours:
        (d / f"{x}.json").write_text("{}")
    sauvegardes.retention(tmp_path)
    restent = {f.stem for f in d.glob("*.json")}
    attendu = set(jours[-30:]) | {"2026-04-01", "2026-07-01", "2026-10-01"}   # T2, T3 et T4 2026 ; T1 2026 tombe
    assert restent == attendu
    assert "2026-01-01" not in restent and "2025-10-01" not in restent


def test_retention(tmp_path):
    d = tmp_path / "sauvegardes"
    d.mkdir()
    debut = datetime(2026, 8, 20)
    dates = [(debut + timedelta(days=i)).date().isoformat() for i in range(90)]
    for x in dates:
        (d / f"{x}.json").write_text("{}")
    sauvegardes.retention(tmp_path)
    restent = sorted(f.stem for f in d.glob("*.json"))
    assert restent == sorted(set(dates[-30:]) | {"2026-08-20", "2026-10-01"})          # premiers de T3 et de T4


# ---------------------------------------------------------------- portes pour Restaurer (applis)

def test_portes_restaurer(client, env):
    connecter(client)
    env.setenv("MAISON_JETON", JETON)
    client.post("/api/sauvegardes")
    h = {"Authorization": f"Bearer {JETON}"}
    dates = client.get("/externe/sauvegardes/carnet", headers=h).json()["dates"]
    assert len(dates) == 1 and dates[0].startswith(jour())
    assert client.get("/externe/sauvegardes/muet", headers=h).json() == {"dates": []}
    r = client.get(f"/externe/sauvegardes/carnet?le={dates[0]}", headers=h).json()
    assert r == {"le": dates[0], "version": "1.0.0", "reglages": {"tri": "nom", "par_page": 50}}
    assert client.get("/externe/sauvegardes/carnet?le=2020-01-01", headers=h).status_code == 404
    for faux in ("/externe/sauvegardes/..%2Fetat", "/externe/sauvegardes/Carnet", "/externe/sauvegardes/carnet?le=../etat",
                 "/externe/sauvegardes/carnet?le=2026-02-30"):
        assert client.get(faux, headers=h).status_code in (400, 404), faux
    # de bout en bout avec le module commun d'une appli
    def lire(adresse, jeton):
        chemin = adresse.split("8094", 1)[1]
        return client.get(chemin, headers={"Authorization": f"Bearer {jeton}"}).json()
    dates = maison.lire_sauvegarde("millesime", url="http://anneau:8094", lire=lire)["dates"]
    assert len(dates) == 1 and dates[0].startswith(jour())
    assert maison.lire_sauvegarde("millesime", le=dates[0], url="http://anneau:8094", lire=lire)["reglages"] == {"seuil": 0.8}


def test_restaurer_l_anneau(client):
    connecter(client)
    assert client.get("/api/restaurer").status_code == 404 and client.get("/api/restaurer").json()["detail"]
    client.post("/api/sauvegardes")                                  # l'Anneau se sauvegarde lui-même, même sans jeton
    client.put("/api/reglages", json={"reglages": {"heure_sauvegarde": "05:00"}})
    dates = client.get("/api/restaurer").json()["dates"]
    assert len(dates) == 1 and dates[0].startswith(jour())
    r = client.get(f"/api/restaurer?le={dates[0]}").json()
    assert r["differences"] == [{"cle": "heure_sauvegarde", "actuel": "05:00", "sauve": "03:30"}]
    r = client.post("/api/restaurer", json={"le": dates[0]})
    assert r.status_code == 200 and r.json()["reglages"]["heure_sauvegarde"] == "03:30"
    assert client.post("/api/restaurer", json={"le": "2020-01-01"}).status_code == 404
    assert client.post("/api/restaurer", json={}).status_code == 400


# ---------------------------------------------------------------- exports chiffrés des variables

def test_variables_chiffrees(client, tmp_path):
    assert client.post("/api/variables-chiffrees", content=ARMURE).status_code == 401
    connecter(client)
    for refuse in ("MAISON_PASSWORD=en-clair\n", "", "x" + ARMURE, ARMURE.replace("-----END AGE ENCRYPTED FILE-----", ""),
                   "-----BEGIN AGE ENCRYPTED FILE-----\n" + "A" * (1024 * 1024) + "\n-----END AGE ENCRYPTED FILE-----\n"):
        r = client.post("/api/variables-chiffrees", content=refuse.encode(), headers={"Content-Type": "text/plain"})
        assert r.status_code in (400, 413), refuse[:40]
    assert not (tmp_path / "sauvegardes" / "variables").exists() or not list((tmp_path / "sauvegardes" / "variables").iterdir())
    r = client.post("/api/variables-chiffrees", content=ARMURE.encode(), headers={"Content-Type": "text/plain"})
    assert r.status_code == 200, r.text
    nom = r.json()["nom"]
    assert sauvegardes.RE_EXPORT.match(nom)
    assert client.get("/api/variables-chiffrees").json()["exports"][0]["nom"] == nom
    t = client.get(f"/api/variables-chiffrees/{nom}")
    assert t.status_code == 200 and t.text == ARMURE and "attachment" in t.headers["content-disposition"]
    for faux in ("etat.json", "..%2Fetat.json", "2026-11-16.json"):
        assert client.get(f"/api/variables-chiffrees/{faux}").status_code == 404, faux


def test_variables_chiffrees_gardees_30(tmp_path):
    t = datetime(2026, 11, 16, 10, 0, 0)
    for i in range(33):
        sauvegardes.ranger_variables(tmp_path, ARMURE, t + timedelta(seconds=i))
    noms = [x["nom"] for x in sauvegardes.liste_variables(tmp_path)]
    assert len(noms) == 30 and noms[0] == "2026-11-16-100032.age" and noms[-1] == "2026-11-16-100003.age"
    assert sauvegardes.ranger_variables(tmp_path, ARMURE, t + timedelta(seconds=32))["nom"] == "2026-11-16-100032-2.age"
