"""0.22 : les applis en veille (liste « veille » des réglages, compagnons, retour sans ordre, mise à jour d'une appli
arrêtée par Watchtower). Faux Portainer et faux Watchtower ; tout est inventé : aucune vraie adresse, aucun vrai nom."""
from __future__ import annotations

import pytest

from app import main, sauvegardes, services
from tests.faux_portainer import FauxPortainer, attendre
from tests.faux_watchtower import FauxWatchtower
from tests.test_conteneurs import BASE, MDP, ORIGINE, _client, tour, tuile

SONDES_022 = {":8104": "bac-a-sable", ":8110": "arbre-web", ":8111": "papiers", ":8112": "gazette-essai"}


def fichier() -> str:
    return f"""
familles: [{{ nom: Essais }}]
services:
  - {{ nom: Bac à sable, famille: Essais, locale: "{BASE}:8104", sonde: "{BASE}:8104/health", conteneur: bac-a-sable }}
  - {{ nom: Arbre, famille: Essais, locale: "{BASE}:8110", conteneur: arbre-web, compagnons: [arbre-api, arbre-db] }}
  - {{ nom: Papiers, famille: Essais, locale: "{BASE}:8111", conteneur: papiers, compagnons: [arbre-db] }}
  - {{ nom: Gazette essai, famille: Essais, locale: "{BASE}:8112", conteneur: gazette-essai, compagnons: [fantome, immich_redis] }}
  - {{ nom: Libre, famille: Essais, locale: "{BASE}:8107" }}
"""


@pytest.fixture()
def faux():
    f = FauxPortainer()
    for nom in ("bac-a-sable", "arbre-web", "arbre-api", "arbre-db", "papiers", "gazette-essai"):
        f.ajouter(nom, f.image(f"ghcr.io/exemple/{nom}:latest", "2026-11-20T05:00:00Z"), f"ghcr.io/exemple/{nom}:latest")
    return f


@pytest.fixture()
def wt(faux):
    return FauxWatchtower(faux, include_stopped=True)


@pytest.fixture()
def client(tmp_path, faux, wt, monkeypatch):
    import tests.test_conteneurs as tc
    monkeypatch.setattr(tc, "SONDES", SONDES_022)
    with _client(tmp_path, faux, wt=wt, texte=fichier()) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        yield c
    main.ETAT.clear()


def veille(c, cle, valeur, entetes=ORIGINE):
    return c.post(f"/api/veille/{cle}", json={"veille": valeur}, headers=entetes)


def ligne(c, cle):
    return next(x for x in c.get("/api/veille").json()["tuiles"] if x["cle"] == cle)


# ---------------------------------------------------------------- champ compagnons

def test_compagnons_lus_et_verifies(tmp_path):
    (tmp_path / "s.yaml").write_text(f"""
familles: [{{ nom: Essais }}]
services:
  - {{ nom: Un, famille: Essais, locale: "{BASE}:1", conteneur: un, compagnons: [un-db, "mauvais nom", portainer, un] }}
  - {{ nom: Deux, famille: Essais, locale: "{BASE}:2", compagnons: [deux-db] }}
""", encoding="utf-8")
    f = services.lire(tmp_path / "s.yaml")
    un, deux = f.services
    assert un.compagnons == ("un-db",) and deux.compagnons == ()
    assert any("compagnons sans conteneur" in e for e in f.erreurs)
    assert any("refusé" in e for e in f.erreurs) and any("invalide" in e for e in f.erreurs)


def test_reglage_veille_valide():
    assert sauvegardes.valider({"veille": " gazette, comptoir ,gazette"}) == {"veille": "comptoir,gazette"}
    with pytest.raises(sauvegardes.Refus):
        sauvegardes.valider({"veille": "Gazette!"})


# ---------------------------------------------------------------- critère 1 : en veille = gris, jamais rouge

def test_mettre_en_veille_arrete_et_reste_gris(client, faux):
    r = veille(client, "bac-a-sable", True)
    assert r.status_code == 200 and r.json()["veille"] == ["bac-a-sable"] and r.json()["ordre"]["geste"] == "eteindre"
    assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    t = tuile(client, "Bac à sable")
    assert t["etat"] == "eteint" and t["conteneur"]["phrase"] == "en veille" and t["conteneur"]["en_veille"]
    main.ETAT["conteneurs"].portainer._transport = None          # Portainer injoignable désormais (critère 6)
    main.ETAT["conteneurs"].portainer.url = "http://192.0.2.250:1"
    main.ETAT["conteneurs"].portainer.delai = 0.2
    tour(client, 5)
    e = client.get("/api/etat").json()
    assert not e["pannes"] and tuile(client, "Bac à sable")["etat"] == "eteint"
    assert main.ETAT["reglages"].get("veille") == "bac-a-sable"


# ---------------------------------------------------------------- critère 2 : retour sans ordre → À traiter

def test_revenue_sans_ordre_previent_sans_arreter(client, faux):
    veille(client, "bac-a-sable", True)
    assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    faux.conteneurs["bac-a-sable"]["State"] = {"Status": "running", "Running": True}     # redéploiement de la stack
    tour(client, 3)
    assert faux.etat("bac-a-sable") == "running"                                         # jamais arrêtée seule
    a = [x for x in client.get("/api/etat").json()["a_traiter"] if x["sorte"] == "veille-revenue"]
    assert [x["tuile"] for x in a] == ["bac-a-sable"] and "Bac à sable" in a[0]["phrase"]
    assert ligne(client, "bac-a-sable")["revenue"]
    # « Remettre en veille »
    assert veille(client, "bac-a-sable", True).status_code == 200
    assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    assert not [x for x in client.get("/api/etat").json()["a_traiter"] if x["sorte"] == "veille-revenue"]
    # nouveau retour, puis « La laisser allumée »
    faux.conteneurs["bac-a-sable"]["State"] = {"Status": "running", "Running": True}
    tour(client)
    r = client.post("/api/veille/bac-a-sable/laisser", headers=ORIGINE)
    assert r.status_code == 200 and r.json()["veille"] == []
    tour(client)
    assert faux.etat("bac-a-sable") == "running" and tuile(client, "Bac à sable")["etat"] == "ok"
    assert not client.get("/api/etat").json()["a_traiter"]


# ---------------------------------------------------------------- critère 3 : Démarrer depuis la tuile grise

def test_demarrer_sort_de_la_veille(client, faux):
    veille(client, "bac-a-sable", True)
    assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    r = veille(client, "bac-a-sable", False)
    assert r.status_code == 200 and r.json()["veille"] == [] and r.json()["ordre"]["geste"] == "allumer"
    assert attendre(lambda: faux.etat("bac-a-sable") == "running")
    tour(client)
    assert tuile(client, "Bac à sable")["etat"] == "ok" and not ligne(client, "bac-a-sable")["en_veille"]


# ---------------------------------------------------------------- critère 4 : compagnons et ordre

def test_compagnons_arretes_apres_demarres_avant(client, faux):
    veille(client, "papiers", True)                     # arrête papiers ; arbre-db reste (Arbre est hors veille)
    assert attendre(lambda: faux.etat("papiers") == "exited")
    assert faux.etat("arbre-db") == "running"
    tour(client)
    faux.appels.clear()
    veille(client, "arbre", True)                       # Papiers en veille : arbre-db n'est plus partagé
    assert attendre(lambda: faux.etat("arbre-db") == "exited")
    stops = [a for a in faux.appels if a[0] == "POST" and a[1].endswith("/stop")]
    assert [a[1].split("/")[-2] for a in stops] == ["arbre-web", "arbre-api", "arbre-db"]
    tour(client)
    faux.appels.clear()
    veille(client, "arbre", False)
    assert attendre(lambda: faux.etat("arbre-web") == "running")
    starts = [a[1].split("/")[-2] for a in faux.appels if a[0] == "POST" and a[1].endswith("/start")]
    assert starts == ["arbre-api", "arbre-db", "arbre-web"]


def test_compagnon_partage_jamais_arrete(client, faux):
    veille(client, "arbre", True)
    assert attendre(lambda: faux.etat("arbre-web") == "exited")
    assert attendre(lambda: faux.etat("arbre-api") == "exited")
    assert faux.etat("arbre-db") == "running"           # Papiers (hors veille) en a besoin


# ---------------------------------------------------------------- critère 5 : impossibles

def test_cases_impossibles_et_refus(client, faux):
    l = ligne(client, "gazette-essai")
    assert l["compagnons"] == ["fantome"]                                  # interdit (immich_redis) écarté à la lecture
    assert any("immich_redis" in e for e in main.ETAT["veille"].fichier.erreurs)
    assert not l["possible"] and "fantome" in l["pourquoi"]                # compagnon inconnu de Portainer
    assert veille(client, "gazette-essai", True).status_code == 403
    assert main.ETAT["reglages"].get("veille") == ""                       # liste remise comme avant
    assert veille(client, "libre", True).status_code == 404               # tuile sans conteneur
    assert "libre" not in {x["cle"] for x in client.get("/api/veille").json()["tuiles"]}
    assert veille(client, "bac-a-sable", True, entetes={}).status_code == 403          # sans Origin
    assert client.post("/api/veille/bac-a-sable", json={"veille": "oui"}, headers=ORIGINE).status_code == 400


def test_compagnon_hors_stack_refuse(client, faux):
    faux.conteneurs["arbre-api"]["Config"]["Labels"] = {"com.docker.compose.project": "autre"}
    tour(client)
    l = ligne(client, "arbre")
    assert not l["possible"] and "arbre-api" in l["pourquoi"]
    assert veille(client, "arbre", True).status_code == 403
    assert faux.etat("arbre-web") == "running"


def test_ordre_en_cours_case_grisee(client, faux):
    faux.figes.add("bac-a-sable")                        # accepte stop sans jamais s'arrêter : l'ordre reste en cours
    veille(client, "bac-a-sable", True)
    l = ligne(client, "bac-a-sable")
    assert not l["possible"] and "en cours" in l["pourquoi"]
    assert veille(client, "bac-a-sable", False).status_code == 409
    assert main.ETAT["reglages"].get("veille") == "bac-a-sable"


# ---------------------------------------------------------------- critère 2 bis : mise à jour d'une appli en veille

def test_mise_a_jour_d_une_appli_en_veille(client, faux):
    veille(client, "bac-a-sable", True)
    assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    avant = faux.conteneurs["bac-a-sable"]["Image"]
    faux.image("ghcr.io/exemple/bac-a-sable:latest", "2026-11-28T05:00:00Z")
    r = client.post("/api/conteneurs/bac-a-sable/mettre-a-jour", headers=ORIGINE)
    assert r.status_code == 202
    assert attendre(lambda: faux.conteneurs["bac-a-sable"]["Image"] != avant)
    for _ in range(5):
        tour(client)
        if tuile(client, "Bac à sable")["conteneur"]["ordre"]["etat"] != "en_cours":
            break
    t = tuile(client, "Bac à sable")
    assert t["conteneur"]["ordre"]["etat"] == "fini" and "toujours arrêté" in t["conteneur"]["ordre"]["phrase"]
    assert faux.etat("bac-a-sable") == "exited" and t["etat"] == "eteint"


def test_mise_a_jour_arretee_sans_include_stopped(tmp_path, faux, monkeypatch):
    import tests.test_conteneurs as tc
    monkeypatch.setattr(tc, "SONDES", SONDES_022)
    wt = FauxWatchtower(faux)                                             # sans WATCHTOWER_INCLUDE_STOPPED
    with _client(tmp_path, faux, wt=wt, texte=fichier()) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        veille(c, "bac-a-sable", True)
        assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
        tour(c)
        assert c.post("/api/conteneurs/bac-a-sable/mettre-a-jour", headers=ORIGINE).status_code == 202
        for _ in range(10):
            tour(c)
            o = tuile(c, "Bac à sable")["conteneur"]["ordre"]
            if o["etat"] != "en_cours":
                break
        assert o["etat"] == "echec" and "INCLUDE_STOPPED" in o["phrase"]
    main.ETAT.clear()


# ---------------------------------------------------------------- critère 7 : sauvegarde et restauration

def test_veille_dans_la_sauvegarde(client, faux):
    veille(client, "bac-a-sable", True)
    assert main._propre()["reglages"]["veille"] == "bac-a-sable"
    assert "Bac à sable" in main._noms_eteints()                          # pas demandée à la collecte de nuit
