"""0.18 : les applis de la stack à mettre à jour dans « À faire quand tu veux » (faux Portainer, faux Watchtower, faux
registres et fausse API GitHub). Tout est inventé : aucune vraie adresse, aucun vrai nom, aucune vraie empreinte."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import conteneurs, main, majs, registres, services
from app.config import Config
from app.veille import Veille
from tests.faux_portainer import CLE, FauxPortainer, attendre
from tests.faux_registre import FauxRegistres, empreinte
from tests.faux_watchtower import JETON, FauxWatchtower

MDP = "mot-de-passe-de-test"
ORIGINE = {"Origin": "http://testserver"}
URL = "http://portainer.exemple:9000"
URL_WT = "http://watchtower:8080"
BASE = "http://192.0.2.10"

FICHIER = f"""
familles: [{{ nom: Essais }}]
services:
  - {{ nom: Dîme, famille: Essais, locale: "{BASE}:8105", depot: dime }}
  - {{ nom: Carnet, famille: Essais, locale: "{BASE}:8096", depot: carnet }}
figees:
  - {{ conteneur: "immich-*", depot: exemple-org/galerie, variable: GALERIE_VERSION }}
  - {{ conteneur: watchtower, depot: exemple-org/veilleur }}
"""


@pytest.fixture()
def monde():
    p, reg = FauxPortainer(), FauxRegistres()

    def appli(nom, ref, a_jour=True, running=True, projet="homelab", version="", etiquettes=None, hote="ghcr.io"):
        depot = ref.split("/", 1)[1].rsplit(":", 1)[0] if "/" in ref and "." in ref.split("/")[0] else ref.rsplit(":", 1)[0]
        etiq = ref.rsplit(":", 1)[1] if ":" in ref.split("/")[-1] else "latest"
        ancienne = empreinte(f"{nom}-ancienne")
        neuve = reg.publier(hote, depot, etiq, f"{nom}-neuve") if not a_jour else reg.publier(hote, depot, etiq, f"{nom}-ancienne")
        img = p.image(ref, "2026-11-20T05:00:00Z", derniere=a_jour, empreinte=ancienne, version=version)
        if not a_jour:
            p.image(ref, "2026-11-22T05:00:00Z", empreinte=neuve)          # la « dernière » que Watchtower tirera
        return p.ajouter(nom, img, ref, projet=projet, running=running, etiquettes=etiquettes)

    appli("dime", "ghcr.io/exemple/dime:latest", a_jour=False, version="0.9.3")
    appli("carnet", "ghcr.io/exemple/carnet:latest")
    appli("anneau", "ghcr.io/exemple/anneau:latest", a_jour=False)
    appli("cache-redis", "redis:latest", a_jour=False, hote="registry-1.docker.io")
    reg.manifestes[("registry-1.docker.io", "library/redis", "latest")] = reg.manifestes.pop(
        ("registry-1.docker.io", "redis", "latest"))
    appli("bazarr", "lscr.io/linuxserver/bazarr:latest", a_jour=False)
    reg.manifestes[("ghcr.io", "linuxserver/bazarr", "latest")] = reg.manifestes.pop(("ghcr.io", "linuxserver/bazarr", "latest"), None) \
        or reg.manifestes.pop(("lscr.io", "linuxserver/bazarr", "latest"))
    appli("dormeur", "ghcr.io/exemple/dormeur:latest", a_jour=False, running=False)
    appli("ailleurs", "ghcr.io/exemple/ailleurs:latest", a_jour=False, projet="autre")
    appli("secret", "ghcr.io/exemple/secret:latest", a_jour=False)
    reg.prives.add("exemple/secret")
    appli("immich-server", "ghcr.io/exemple/galerie-server:v2.3.0")
    appli("watchtower", "veilleur/watchtower:1.19.0", hote="registry-1.docker.io")
    reg.publications.update({"exemple-org/galerie": "v2.4.1", "exemple-org/veilleur": "v1.19.0"})
    return p, reg


def _client(tmp_path, monde, lecture_seule=False, wt_jeton=JETON):
    p, reg = monde
    main.ETAT.clear()
    (tmp_path / "services.yaml").write_text(FICHIER, encoding="utf-8")

    async def sonder(adresse):
        return (True, 5)

    async def examiner(adresse):
        return ""

    veille = Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=sonder, examiner=examiner)
    cfg = Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, veille=False,
                 sauvegarde_auto=False, portainer_url=URL, portainer_cle=CLE, watchtower_url=URL_WT, watchtower_jeton=wt_jeton)
    wt = FauxWatchtower(p)
    main.ETAT.update(cfg=cfg, veille=veille, transport_portainer=p.transport(), transport_watchtower=wt.transport(),
                     transport_registres=reg.transport())
    return TestClient(main.app)


@pytest.fixture()
def client(tmp_path, monde):
    with _client(tmp_path, monde) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        yield c
    main.ETAT.clear()


def lignes(c):
    return {x["id"]: x for x in c.get("/api/etat").json()["majs"]["lignes"]}


def verifier(c):
    r = c.post("/api/majs/verifier", headers=ORIGINE)
    assert r.status_code == 200, r.text
    return r.json()


def tour(c):
    c.portal.call(main.un_tour, main.ETAT["veille"])


# ---------------------------------------------------------------- registres

def test_decouper_les_noms_d_image():
    assert registres.decouper("ghcr.io/a/b:1.2") == ("ghcr.io", "a/b", "1.2")
    assert registres.decouper("postgres") == ("registry-1.docker.io", "library/postgres", "latest")
    assert registres.decouper("docker.io/valkey/valkey:8") == ("registry-1.docker.io", "valkey/valkey", "8")
    assert registres.decouper("lscr.io/linuxserver/bazarr") == ("lscr.io", "linuxserver/bazarr", "latest")
    for faux in ("ghcr.io/a/b@sha256:" + "0" * 64, "sha256:abc", "", "ghcr.io/A/../b"):
        with pytest.raises(registres.ErreurRegistre):
            registres.decouper(faux)
    assert registres.est_figee("ghcr.io/x/y:v2.3.0") and registres.est_figee("postgres:16.4-alpine")
    assert not registres.est_figee("ghcr.io/x/y:latest") and not registres.est_figee("ghcr.io/x/y")


def test_figees_lues_et_verifiees():
    f = services.comprendre("""
familles: [{ nom: A }]
services:
  - { nom: Un, famille: A, locale: "http://192.0.2.1:1" }
figees:
  - { conteneur: "immich-*", depot: exemple-org/galerie, variable: GALERIE_VERSION }
  - { conteneur: "../x", depot: a/b }
  - { conteneur: ok, depot: "pas un dépôt" }
  - { conteneur: ok2, depot: a/b, variable: "minuscule" }
""")
    assert f.figees == ({"conteneur": "immich-*", "depot": "exemple-org/galerie", "variable": "GALERIE_VERSION"},
                        {"conteneur": "ok2", "depot": "a/b", "variable": ""})
    assert sum("figees" in e for e in f.erreurs) == 3


# ---------------------------------------------------------------- la liste

def test_la_liste_des_applis_a_mettre_a_jour(client, monde):
    p, reg = monde
    v = verifier(client)
    par = {x["id"]: x for x in v["lignes"]}
    # à jour, d'un autre projet, ou figée sans version plus récente : absents
    assert set(par) == {"dime", "anneau", "cache-redis", "bazarr", "dormeur", "immich-server"}
    assert v["nombre"] == 6
    assert par["dime"]["nom"] == "Dîme" and par["dime"]["bouton"] and not par["dime"]["protege"]
    assert par["dime"]["phrase"] == "nouvelle image publiée"                # pas de version publiée connue ici
    assert "protégé" in par["anneau"]["protege"] and par["anneau"]["bouton"]
    assert "base de données" in par["cache-redis"]["protege"]
    assert par["bazarr"]["bouton"]                                          # lscr.io → ghcr.io suivi
    assert not par["dormeur"]["bouton"] and "allumer d'abord" in par["dormeur"]["pourquoi"]
    g = par["immich-server"]
    assert g["sorte"] == "figee" and not g["bouton"]
    assert g["phrase"] == "version 2.4.1 publiée, tu as 2.3.0 : changer GALERIE_VERSION dans la stack"
    assert [n["nom"] for n in v["non_verifiees"]] == ["secret"] and "anonyme" in v["non_verifiees"][0]["raison"]
    assert v["erreur"] == "" and v["lu_le"]
    # aucun téléchargement : seulement des HEAD de manifestes, des jetons et GitHub
    assert all(m in ("HEAD", "GET") for m, _ in reg.appels)
    assert not any("/blobs/" in u for _, u in reg.appels)
    assert all(m == "HEAD" for m, u in reg.appels if "/manifests/" in u)
    # gardée sur le disque
    d = json.loads((main.ETAT["cfg"].data / majs.FICHIER).read_text(encoding="utf-8"))
    assert set(d["lignes"]) == set(par)


def test_mettre_a_jour_depuis_la_liste(client, monde):
    p, _ = monde
    verifier(client)
    avant = p.conteneurs["dime"]["Image"]
    r = client.post("/api/majs/dime/mettre-a-jour", headers=ORIGINE, json={})
    assert r.status_code == 202, r.text
    assert attendre(lambda: p.conteneurs["dime"]["Image"] != avant)
    assert attendre(lambda: main.ETAT["majs"].ordres["dime"].get("wt") == "fini")
    tour(client)
    x = lignes(client)["dime"]
    assert x["ordre"]["etat"] == "fini" and x["ordre"]["phrase"] == "mis à jour." and not x["bouton"]
    assert client.get("/api/etat").json()["majs"]["nombre"] == 5
    journal = client.get("/api/conteneurs/journal").json()["lignes"]
    assert journal[0]["resultat"] == "fini : mis à jour." and journal[0]["liste"] == "a-faire"
    # vérifiée de nouveau : à jour, elle n'y est plus du tout une fois le résultat effacé
    verifier(client)
    assert "dime" not in main.ETAT["majs"].lignes


def test_double_confirmation_pour_les_proteges(client, monde):
    p, _ = monde
    verifier(client)
    r = client.post("/api/majs/anneau/mettre-a-jour", headers=ORIGINE, json={})
    assert r.status_code == 409 and "Double confirmation" in r.json()["detail"]
    r = client.post("/api/majs/cache-redis/mettre-a-jour", headers=ORIGINE, json={"protege": "oui"})
    assert r.status_code == 409                                         # seul « true » vaut confirmation
    r = client.post("/api/majs/cache-redis/mettre-a-jour", headers=ORIGINE, json={"protege": True})
    assert r.status_code == 202
    assert attendre(lambda: main.ETAT["majs"].ordres["cache-redis"].get("wt") == "fini")
    tour(client)
    assert lignes(client)["cache-redis"]["ordre"]["etat"] == "fini"


def test_refus(client, monde, monkeypatch):
    p, _ = monde
    verifier(client)
    assert client.post("/api/majs/dime/mettre-a-jour", json={}).status_code == 403          # pas d'Origin
    assert client.post("/api/majs/ailleurs/mettre-a-jour", headers=ORIGINE).status_code == 404   # hors de la liste
    assert client.post("/api/majs/inconnu/mettre-a-jour", headers=ORIGINE).status_code == 404
    assert client.post("/api/majs/immich-server/mettre-a-jour", headers=ORIGINE).status_code == 404   # figée : pas de bouton
    r = client.post("/api/majs/dormeur/mettre-a-jour", headers=ORIGINE)
    assert r.status_code == 409 and "arrêté" in r.json()["detail"]
    # le conteneur a quitté la stack entre la liste et le clic : refusé
    p.conteneurs["bazarr"]["Config"]["Labels"]["com.docker.compose.project"] = "autre"
    r = client.post("/api/majs/bazarr/mettre-a-jour", headers=ORIGINE)
    assert r.status_code == 403
    monkeypatch.setenv("ANNEAU_LECTURE_SEULE", "1")
    r = client.post("/api/majs/dime/mettre-a-jour", headers=ORIGINE)
    assert r.status_code == 403 and "Lecture seule" in r.json()["detail"]
    assert "lecture seule" in lignes(client)["dime"]["pourquoi"]
    journal = client.get("/api/conteneurs/journal").json()["lignes"]
    assert all(l["resultat"].startswith("refusé") for l in journal)


def test_echec_de_watchtower(tmp_path, monde):
    with _client(tmp_path, monde, wt_jeton="faux-jeton") as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        verifier(c)
        assert c.post("/api/majs/dime/mettre-a-jour", headers=ORIGINE).status_code == 202
        assert attendre(lambda: main.ETAT["majs"].ordres["dime"]["etat"] == "echec")
        x = lignes(c)["dime"]
        assert "jeton refusé" in x["ordre"]["phrase"] and x["bouton"]
    main.ETAT.clear()


def test_l_ordre_survit_a_un_redemarrage(tmp_path, monde):
    """Mettre à jour l'Anneau lui-même : le processus s'arrête en route ; au retour, l'ordre gardé sur le disque est
    conclu à l'état réel (nouvelle image, conteneur en marche)."""
    p, reg = monde
    portainer = conteneurs.Portainer(URL, CLE, transport=p.transport())
    m = majs.MisesAJour(tmp_path, portainer, watchtower=None, registres=registres.Registres(reg.transport()))
    fichier = services.comprendre(FICHIER)
    import asyncio
    asyncio.run(m.verifier(fichier, []))
    m.ordres["anneau"] = {"id": "anneau", "nom": "anneau", "conteneur": "anneau", "etat": "en_cours", "debut": "x",
                          "debut_t": m._horloge(), "image_avant": p.conteneurs["anneau"]["Image"], "wt": "attente",
                          "phrase": "mise à jour en cours…"}
    m._garder()
    p.remplacer("anneau", p.dernieres["ghcr.io/exemple/anneau:latest"])     # Watchtower a fini pendant l'arrêt
    neuf = majs.MisesAJour(tmp_path, portainer, watchtower=None, registres=registres.Registres(reg.transport()))
    assert neuf.en_cours() and "anneau" in neuf.lignes
    asyncio.run(neuf.suivre())
    assert neuf.ordres["anneau"]["etat"] == "fini" and "anneau" not in neuf.lignes


def test_sans_portainer_rien(tmp_path, monde):
    p, reg = monde
    m = majs.MisesAJour(tmp_path, None)
    assert m.vue(False) == {"actif": False, "lignes": [], "nombre": 0} and not m.a_verifier()


def test_registre_injoignable_garde_l_application_debout(client, monde):
    _, reg = monde
    reg.injoignables.add("ghcr.io")
    v = verifier(client)
    assert v["erreur"] == ""
    assert {"dime", "anneau"} <= {n["nom"] if n["nom"] != "Dîme" else "dime" for n in v["non_verifiees"]}
    assert all("injoignable" in n["raison"] for n in v["non_verifiees"])
    assert "cache-redis" in {x["id"] for x in v["lignes"]}               # Docker Hub, lui, répond


def test_protection():
    assert majs.protection("anneau", "ghcr.io/x/anneau:latest")
    assert majs.protection("Immich_machine_learning", "ghcr.io/x/ml:latest")
    assert "base" in majs.protection("galerie-db", "ghcr.io/immich-app/postgres:14-vectorchord0.4.3")
    assert "base" in majs.protection("cache", "docker.io/valkey/valkey:8-bookworm")
    assert majs.protection("dime", "ghcr.io/baloodusudouest/dime:latest") == ""
