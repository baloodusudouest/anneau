"""0.17 : allumer, éteindre, mettre à jour un conteneur par Portainer (faux Portainer : tests/faux_portainer.py) ;
0.17.1 : la mise à jour passe par Watchtower (faux Watchtower : tests/faux_watchtower.py).
Tout est inventé : aucune vraie adresse, aucun vrai nom."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import conteneurs, main, sauvegardes, services
from app.config import Config
from app.veille import Veille
from tests.faux_portainer import CLE, FauxPortainer, attendre
from tests.faux_watchtower import JETON, FauxWatchtower

MDP = "mot-de-passe-de-test"
ORIGINE = {"Origin": "http://testserver"}
URL = "http://portainer.exemple:9000"
URL_WT = "http://watchtower:8080"
BASE = "http://192.0.2.10"
SONDES = {":8104": "bac-a-sable", ":8105": "transhumance", ":8106": "atelier"}


def fichier(leurre: str = "") -> str:
    return f"""
familles: [{{ nom: Essais }}]
services:
  - {{ nom: Bac à sable, famille: Essais, locale: "{BASE}:8104", sonde: "{BASE}:8104/health", conteneur: bac-a-sable, sauvegarde: true }}
  - {{ nom: Transhumance, famille: Essais, locale: "{BASE}:8105", conteneur: transhumance }}
  - {{ nom: Atelier, famille: Essais, locale: "{BASE}:8106", conteneur: atelier }}
  - {{ nom: Galerie, famille: Essais, locale: "{BASE}:2283", conteneur: Immich_Server }}
  - {{ nom: Libre, famille: Essais, locale: "{BASE}:8107" }}
""" + (f'  - {{ nom: Leurre, famille: Essais, locale: "{BASE}:8108", conteneur: "{leurre}" }}\n' if leurre else "")


class Horloge:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture()
def faux():
    f = FauxPortainer()
    ancienne = f.image("ghcr.io/exemple/bac-a-sable:latest", "2026-11-20T05:02:11.123456789Z", derniere=False)
    f.image("ghcr.io/exemple/bac-a-sable:latest", "2026-11-21T05:01:00Z")
    f.ajouter("bac-a-sable", ancienne, "ghcr.io/exemple/bac-a-sable:latest")
    f.ajouter("transhumance", f.image("ghcr.io/exemple/transhumance:latest", "2026-11-19T05:00:00Z"), projet="autre")
    img = f.image("ghcr.io/exemple/atelier:latest", "2026-11-18T05:00:00Z")
    f.ajouter("atelier", img, "ghcr.io/exemple/atelier:latest", redemarrage="always")
    f.immich = f.ajouter("immich_server", f.image("ghcr.io/exemple/immich:latest", "2026-11-18T05:00:00Z"))
    return f


@pytest.fixture()
def wt(faux):
    return FauxWatchtower(faux)


def _veille(tmp_path, faux, texte):
    (tmp_path / "services.yaml").write_text(texte, encoding="utf-8")

    async def sonder(adresse):
        nom = next((n for m, n in SONDES.items() if m in adresse), None)
        if nom is None:
            return (True, 5)
        c = faux.conteneurs.get(nom)
        return (bool(c and c["State"]["Running"]), 5)

    async def examiner(adresse):
        return ""

    return Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=sonder, examiner=examiner)


def _client(tmp_path, faux, avec_cle=True, texte=None, horloge=None, wt=None, wt_url=URL_WT, wt_jeton=JETON,
            wt_transport=None):
    main.ETAT.clear()
    main.CONNEXIONS._dernier.clear()                 # le registre des fiches garde le dernier essai (1 min) : on repart à zéro
    wt = wt or FauxWatchtower(faux)
    cfg = Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False, veille=False,
                 sauvegarde_auto=False, portainer_url=URL if avec_cle else "", portainer_cle=CLE if avec_cle else "",
                 watchtower_url=wt_url, watchtower_jeton=wt_jeton)
    veille = _veille(tmp_path, faux, texte or fichier())
    transport_wt = wt_transport or wt.transport()
    etat = {"cfg": cfg, "veille": veille, "transport_portainer": faux.transport(), "transport_watchtower": transport_wt}
    if horloge is not None:
        etat["conteneurs"] = conteneurs.Conteneurs(
            tmp_path, conteneurs.Portainer(URL, CLE, transport=faux.transport()), horloge=horloge,
            watchtower=conteneurs.Watchtower(URL_WT, JETON, transport=transport_wt) if cfg.watchtower else None,
            watchtower_manque=cfg.watchtower_manque())
    main.ETAT.update(etat)
    return TestClient(main.app)


@pytest.fixture()
def client(tmp_path, faux, wt):
    with _client(tmp_path, faux, wt=wt) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        yield c
    main.ETAT.clear()


def tour(c, n=1):
    for _ in range(n):
        c.portal.call(main.un_tour, main.ETAT["veille"])


def tuile(c, nom):
    return next(s for f in c.get("/api/etat").json()["familles"] for s in f["services"] if s["nom"] == nom)


def verifier(c, id_):
    main.CONNEXIONS._dernier.pop(id_, None)
    return c.post(f"/api/maison/services/{id_}/verifier")


def ordre(c, cle, geste, entetes=ORIGINE, **kw):
    return c.post(f"/api/conteneurs/{cle}/{geste}", headers=entetes, **kw)


# ---------------------------------------------------------------- le champ conteneur: de services.yaml

def test_champ_conteneur_lu_et_verifie():
    f = services.comprendre("""
familles: [{ nom: A }]
services:
  - { nom: Un, famille: A, locale: "http://192.0.2.1:1", conteneur: bac-a-sable }
  - { nom: Deux, famille: A, locale: "http://192.0.2.1:2", conteneur: "../etc" }
  - { nom: Trois, famille: A, locale: "http://192.0.2.1:3", conteneur: IMMICH_machine_learning }
  - { nom: Quatre, famille: A, locale: "http://192.0.2.1:4", conteneur: Anneau }
  - { nom: Cinq, famille: A, locale: "http://192.0.2.1:5", conteneur: silverbullet-maison }
  - { nom: Six, famille: A, locale: "http://192.0.2.1:6", conteneur: Bac-A-Sable }
  - { nom: Sept, famille: A, locale: "http://192.0.2.1:7", conteneur: coffre-git }
  - { nom: Huit, famille: A, locale: "http://192.0.2.1:8", conteneur: "a b" }
""")
    noms = {s.nom: s.conteneur for s in f.services}
    assert noms == {"Un": "bac-a-sable", "Deux": "", "Trois": "", "Quatre": "", "Cinq": "", "Six": "", "Sept": "", "Huit": ""}
    texte = " ".join(f.erreurs)
    assert "invalide" in texte and "refusé" in texte and "déjà marqué" in texte
    assert len(f.services) == 8                                   # la tuile reste, seul le champ est ignoré
    for nom in ("anneau", "IMMICH_SERVER", "immich_postgres", "Portainer", "WATCHTOWER", "coffre-git", "silverbullet"):
        assert conteneurs.interdit(nom), nom
    assert not conteneurs.interdit("bac-a-sable") and not conteneurs.interdit("anneau-essai")


# ---------------------------------------------------------------- boutons présents ou absents

def test_sans_cle_aucun_bouton(tmp_path, faux):
    with _client(tmp_path, faux, avec_cle=False) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        assert all(s["conteneur"] is None for f in c.get("/api/etat").json()["familles"] for s in f["services"])
        r = ordre(c, "bac-a-sable", "eteindre")
        assert r.status_code == 404 and "pas réglé" in r.json()["detail"]
        assert faux.etat("bac-a-sable") == "running" and not faux.appels      # rien n'est parti vers Portainer
    main.ETAT.clear()


def test_boutons_seulement_pour_les_tuiles_marquees_de_la_stack(client, faux):
    tour(client)
    bac = tuile(client, "Bac à sable")["conteneur"]
    assert bac["gerable"] and bac["statut"] == "running" and bac["maj"] and not bac["lecture_seule"]
    assert bac["image_date"].startswith("2026-11-20T05:02:11") and bac["redemarrage"] == "unless-stopped"
    trans = tuile(client, "Transhumance")["conteneur"]
    assert not trans["gerable"] and "com.docker.compose.project=homelab" in trans["pourquoi"]
    assert tuile(client, "Libre")["conteneur"] is None                   # sans marquage
    assert tuile(client, "Galerie")["conteneur"] is None                 # interdit : refusé dès la lecture du fichier
    assert tuile(client, "Atelier")["conteneur"]["redemarrage"] == "always"
    assert not any("immich" in p.lower() for _, p in faux.appels)       # jamais lu chez Portainer
    assert ("GET", "/api/endpoints") in faux.appels                     # environnement trouvé (Type 1, pas la grappe)
    assert any(p.startswith("/api/endpoints/3/docker/") for _, p in faux.appels)


# ---------------------------------------------------------------- barrières

def test_sans_session_refuse(tmp_path, faux):
    with _client(tmp_path, faux) as c:
        assert ordre(c, "bac-a-sable", "eteindre").status_code == 401
        assert c.get("/api/conteneurs/bac-a-sable/stats").status_code == 401
    main.ETAT.clear()
    assert faux.etat("bac-a-sable") == "running"


@pytest.mark.parametrize("entetes", [{}, {"Origin": "http://testserver:8096"}, {"Origin": "http://autre.exemple"},
                                     {"Origin": "null"}, {"Origin": "https://testserver"}])
def test_mauvaise_origine_refusee(client, faux, entetes):
    tour(client)
    r = ordre(client, "bac-a-sable", "eteindre", entetes=entetes)
    assert r.status_code == 403 and "Origin" in r.json()["detail"]
    assert faux.etat("bac-a-sable") == "running"
    assert client.get("/api/conteneurs/journal").json()["lignes"][0]["resultat"].startswith("refusé")


def test_origine_de_la_tuile_anneau_acceptee(tmp_path, faux):
    texte = fichier() + '  - { nom: Anneau, famille: Essais, locale: "http://192.0.2.10:8094", privee: "https://anneau.exemple.ts.net:9094" }\n'
    with _client(tmp_path, faux, texte=texte) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        assert ordre(c, "bac-a-sable", "eteindre", entetes={"Origin": "https://anneau.exemple.ts.net:9094"}).status_code == 202
        assert ordre(c, "atelier", "eteindre", entetes={"Origin": "https://anneau.exemple.ts.net:9095"}).status_code == 403
    main.ETAT.clear()


def test_la_requete_ne_choisit_jamais_le_conteneur(client, faux):
    tour(client)
    # une tuile sans marquage, avec un nom de conteneur glissé dans le corps et la requête : ignorés
    r = ordre(client, "libre", "eteindre", json={"conteneur": "bac-a-sable", "nom": "bac-a-sable"},
              params={"conteneur": "bac-a-sable"})
    assert r.status_code == 404
    assert ordre(client, "inconnue", "eteindre").status_code == 404
    assert ordre(client, "bac-a-sable", "supprimer").status_code == 404
    assert ordre(client, "galerie", "eteindre").status_code == 404           # interdit : champ ignoré dès la lecture
    r = ordre(client, "transhumance", "eteindre")                            # sans l'étiquette de la stack
    assert r.status_code == 403 and "homelab" in r.json()["detail"]
    assert faux.etat("bac-a-sable") == "running" and faux.etat("transhumance") == "running"
    assert not [p for m, p in faux.appels if m == "POST"]


def test_nom_reel_interdit_refuse(tmp_path, faux):
    """Le champ est un début d'identifiant qui désigne, chez Portainer, un conteneur interdit : refusé par le nom réel."""
    leurre = faux.immich["Id"][:12]
    with _client(tmp_path, faux, texte=fichier(leurre)) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        assert tuile(c, "Leurre")["conteneur"]["gerable"] is False
        r = ordre(c, "leurre", "eteindre")
        assert r.status_code == 403 and "ne touche jamais" in r.json()["detail"]
        assert faux.etat("immich_server") == "running"
    main.ETAT.clear()


def test_lecture_seule(client, faux, monkeypatch):
    tour(client)
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "oui")
    assert tuile(client, "Bac à sable")["conteneur"]["lecture_seule"] is True
    r = ordre(client, "bac-a-sable", "eteindre")
    assert r.status_code == 403 and "Lecture seule" in r.json()["detail"]
    monkeypatch.setenv("ANNEAU_LECTURE_SEULE", "oui")
    monkeypatch.delenv("MAISON_LECTURE_SEULE")
    assert ordre(client, "bac-a-sable", "eteindre").status_code == 403
    assert faux.etat("bac-a-sable") == "running"
    monkeypatch.setenv("MAISON_LECTURE_SEULE", "oui")
    monkeypatch.setenv("ANNEAU_LECTURE_SEULE", "non")                       # la variable de l'appli l'emporte
    assert ordre(client, "bac-a-sable", "eteindre").status_code == 202


def test_portainer_refuse_l_acces(client, faux):
    faux.caches.add("bac-a-sable")
    tour(client)
    r = ordre(client, "bac-a-sable", "eteindre")
    assert r.status_code == 502 and "403" in r.json()["detail"]
    assert "403" in tuile(client, "Bac à sable")["conteneur"]["erreur"]


def test_mauvaise_cle(tmp_path, faux):
    faux.cle = "autre-cle"
    with _client(tmp_path, faux) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        assert "401" in tuile(c, "Bac à sable")["conteneur"]["erreur"]
        assert ordre(c, "bac-a-sable", "eteindre").status_code == 502
    main.ETAT.clear()


# ---------------------------------------------------------------- ordres et suivi

def test_eteindre_puis_allumer(client, faux):
    tour(client)
    r = ordre(client, "bac-a-sable", "eteindre")
    assert r.status_code == 202 and r.json()["ordre"]["etat"] == "en_cours"
    assert ordre(client, "bac-a-sable", "eteindre").status_code == 409          # un seul ordre à la fois
    assert attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    t = tuile(client, "Bac à sable")
    assert t["etat"] == "eteint" and t["conteneur"]["statut"] == "exited" and t["conteneur"]["phrase"] == "éteint"
    assert t["conteneur"]["ordre"]["etat"] == "fini"
    tour(client, 4)                                                             # jamais « en panne »
    e = client.get("/api/etat").json()
    assert not e["pannes"] and tuile(client, "Bac à sable")["etat"] == "eteint"
    assert ordre(client, "bac-a-sable", "eteindre").status_code == 409          # déjà éteint
    r = ordre(client, "bac-a-sable", "allumer")
    assert r.status_code == 202 and r.json()["ordre"]["phrase"] == "démarrage…"
    assert attendre(lambda: faux.etat("bac-a-sable") == "running")
    tour(client)
    t = tuile(client, "Bac à sable")
    assert t["etat"] == "ok" and t["conteneur"]["ordre"]["phrase"] == "allumé."
    lignes = [json.loads(l) for l in (main.ETAT["cfg"].data / conteneurs.JOURNAL).read_text().splitlines()]
    assert [(l["quoi"], l["resultat"].split(" ")[0]) for l in lignes if l["tuile"] == "Bac à sable"] == [
        ("eteindre", "lancé"), ("eteindre", "refusé"), ("eteindre", "fini"), ("eteindre", "refusé"),
        ("allumer", "lancé"), ("allumer", "fini")]
    assert all(set(l) >= {"quand", "quoi", "tuile", "resultat"} for l in lignes)


def test_mise_a_jour_nouvelle_image_puis_deja_a_jour(client, faux, wt):
    tour(client)
    avant = faux.conteneurs["bac-a-sable"]["Id"]
    assert ordre(client, "bac-a-sable", "mettre-a-jour").status_code == 202
    assert tuile(client, "Bac à sable")["conteneur"]["phrase"] == "mise à jour en cours…"
    assert attendre(lambda: "bac-a-sable" in faux.conteneurs and faux.conteneurs["bac-a-sable"]["Id"] != avant)
    tour(client)
    c = tuile(client, "Bac à sable")["conteneur"]
    assert c["ordre"]["etat"] == "fini" and c["phrase"] == "image du 20/11 → 21/11", c
    assert ("POST", "/v1/update", "image=ghcr.io%2Fexemple%2Fbac-a-sable") in wt.appels   # image sans l'étiquette
    assert not [p for m, p in faux.appels if m == "POST"]                                # rien d'écrit chez Portainer
    avant = faux.conteneurs["bac-a-sable"]["Id"]
    assert ordre(client, "bac-a-sable", "mettre-a-jour").status_code == 202
    assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"].get("wt") == "fini")
    assert faux.conteneurs["bac-a-sable"]["Id"] == avant          # pas de nouvelle image : Watchtower n'a rien recréé
    tour(client)
    assert tuile(client, "Bac à sable")["conteneur"]["phrase"] == "déjà à jour"


def test_allumer_et_mettre_a_jour_une_tuile_eteinte(client, faux, wt):
    faux.conteneurs["bac-a-sable"]["State"] = {"Status": "exited", "Running": False}
    tour(client)
    c = tuile(client, "Bac à sable")["conteneur"]
    assert c["phrase"] == "éteint" and c["image_age"] is not None and c["image_age"] >= 1 and c["maj"]
    avant = faux.conteneurs["bac-a-sable"]["Image"]
    assert ordre(client, "bac-a-sable", "allumer-et-mettre-a-jour").status_code == 202
    assert attendre(lambda: faux.conteneurs["bac-a-sable"]["Image"] != avant)
    tour(client)
    assert tuile(client, "Bac à sable")["conteneur"]["phrase"] == "image du 20/11 → 21/11"
    # démarré par Portainer d'abord (Watchtower ignore un conteneur arrêté), puis Watchtower
    assert any(p.endswith("/bac-a-sable/start") for m, p in faux.appels if m == "POST")
    assert [a for a in wt.appels if a[1] == "/v1/update"] == [("POST", "/v1/update", "image=ghcr.io%2Fexemple%2Fbac-a-sable")]


def test_suivi_lent_puis_delai_depasse(tmp_path, faux, wt):
    horloge = Horloge()
    wt.lenteur = 0.6
    with _client(tmp_path, faux, horloge=horloge, wt=wt) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        assert ordre(c, "bac-a-sable", "mettre-a-jour").status_code == 202
        assert main.ETAT["conteneurs"].presse()                               # la ronde relit plus vite
        tour(c)                         # Watchtower travaille : même image, conteneur en marche, mais pas « déjà à jour »
        assert tuile(c, "Bac à sable")["conteneur"]["ordre"]["etat"] == "en_cours"
        horloge.t += 200
        tour(c)
        assert tuile(c, "Bac à sable")["conteneur"]["phrase"] == "mise à jour en cours…"
        assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"].get("wt") == "fini", 5)
        tour(c)
        assert tuile(c, "Bac à sable")["conteneur"]["phrase"] == "image du 20/11 → 21/11"
        horloge.t += 301
        assert not main.ETAT["conteneurs"].presse()
        # un arrêt que Portainer accepte sans que rien ne bouge : au-delà de 10 min, « pas de réponse, voir Portainer »
        faux.figes.add("atelier")
        assert ordre(c, "atelier", "eteindre").status_code == 202
        attendre(lambda: any(p.endswith("/atelier/stop") for _, p in faux.appels))
        tour(c)
        assert tuile(c, "Atelier")["conteneur"]["phrase"] == "extinction…"
        horloge.t += 601
        tour(c)
        a = tuile(c, "Atelier")["conteneur"]
        assert a["ordre"]["etat"] == "delai" and a["phrase"] == "pas de réponse, voir Portainer"
        assert faux.etat("atelier") == "running"
    main.ETAT.clear()


def test_mise_a_jour_attend_le_verrou_de_watchtower(client, faux, wt):
    """La mise à jour planifiée (05:00) tient le verrou : la demande ciblée attend ; l'Anneau ne conclut pas « déjà à
    jour » tant que Watchtower n'a pas répondu, puis suit jusqu'à la nouvelle empreinte."""
    tour(client)
    client.portal.call(wt.verrou.acquire)
    assert ordre(client, "bac-a-sable", "mettre-a-jour").status_code == 202
    attendre(lambda: any(a[1] == "/v1/update" for a in wt.appels))
    tour(client, 3)
    c = tuile(client, "Bac à sable")["conteneur"]
    assert c["ordre"]["etat"] == "en_cours" and c["phrase"] == "mise à jour en cours…"
    client.portal.call(wt.verrou.release)
    assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"].get("wt") == "fini")
    tour(client)
    assert tuile(client, "Bac à sable")["conteneur"]["phrase"] == "image du 20/11 → 21/11"


def test_sans_watchtower_pas_de_bouton_mettre_a_jour(tmp_path, faux):
    for url, jeton, variable in (("", "", "ANNEAU_WATCHTOWER_URL"), (URL_WT, "", "ANNEAU_WATCHTOWER_JETON")):
        wt = FauxWatchtower(faux)
        with _client(tmp_path, faux, wt=wt, wt_url=url, wt_jeton=jeton) as c:
            c.post("/api/connexion", json={"mot_de_passe": MDP})
            tour(c)
            b = tuile(c, "Bac à sable")["conteneur"]
            assert b["gerable"] and not b["maj"] and variable in b["maj_pourquoi"]   # Allumer / Éteindre restent
            r = ordre(c, "bac-a-sable", "mettre-a-jour")
            assert r.status_code == 409 and variable in r.json()["detail"]
            assert ordre(c, "bac-a-sable", "allumer-et-mettre-a-jour").status_code == 409
            assert not wt.appels
            w = next(f for f in c.get("/api/maison/services").json()["services"] if f["id"] == "watchtower")
            assert w["etat"] == "pas_relie" and w["reglage"] == "ANNEAU_WATCHTOWER_URL"
        main.ETAT.clear()


def test_etiquette_watchtower_false_pas_de_bouton(client, faux, wt):
    faux.conteneurs["bac-a-sable"]["Config"]["Labels"]["com.centurylinklabs.watchtower.enable"] = "False"
    tour(client)
    b = tuile(client, "Bac à sable")["conteneur"]
    assert b["gerable"] and not b["maj"] and "watchtower.enable=false" in b["maj_pourquoi"]
    r = ordre(client, "bac-a-sable", "mettre-a-jour")
    assert r.status_code == 409 and "watchtower.enable=false" in r.json()["detail"]
    assert not wt.appels
    assert ordre(client, "bac-a-sable", "eteindre").status_code == 202                   # Éteindre reste permis


def test_image_epinglee_ou_registre_a_port():
    assert conteneurs.image_pour_watchtower("ghcr.io/exemple/bac-a-sable:latest") == ("ghcr.io/exemple/bac-a-sable", "")
    assert conteneurs.image_pour_watchtower("nginx") == ("nginx", "")
    assert conteneurs.image_pour_watchtower("exemple/app@sha256:abcd")[1]
    assert conteneurs.image_pour_watchtower("sha256:abcdef0123")[1]
    assert "port" in conteneurs.image_pour_watchtower("registre.exemple:5000/app:1")[1]
    assert conteneurs.image_pour_watchtower("a,b/c")[1]                                 # pas de virgule (séparateur)


def test_jeton_refuse_par_watchtower(client, faux, wt):
    wt.jeton = "autre-jeton"
    tour(client)
    assert ordre(client, "bac-a-sable", "mettre-a-jour").status_code == 202
    assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"]["etat"] == "echec")
    c = tuile(client, "Bac à sable")["conteneur"]
    assert "jeton refusé par Watchtower" in c["ordre"]["phrase"] and c["statut"] == "running"
    assert client.get("/api/conteneurs/journal").json()["lignes"][0]["resultat"].startswith("échec : jeton refusé")
    f = verifier(client, "watchtower").json()
    assert f["etat"] == "ne_repond_pas" and "jeton refusé par Watchtower à la dernière mise à jour" in f["detail"]
    assert not [a for a in wt.appels if a[1] == "/v1/update" and a[0] != "POST"]


def test_watchtower_injoignable(tmp_path, faux):
    with _client(tmp_path, faux, wt_transport=FauxWatchtower.injoignable()) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        avant = dict(faux.conteneurs["bac-a-sable"])
        assert ordre(c, "bac-a-sable", "mettre-a-jour").status_code == 202
        assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"]["etat"] == "echec")
        b = tuile(c, "Bac à sable")["conteneur"]
        assert b["ordre"]["phrase"] == "Watchtower ne répond pas : pas de mise à jour."
        assert faux.conteneurs["bac-a-sable"] == avant and b["statut"] == "running"     # pas de changement d'état
        f = verifier(c, "watchtower").json()
        assert f["etat"] == "ne_repond_pas" and "ne répond pas" in f["detail"]
        # « Allumer et mettre à jour » : allumé par Portainer, puis Watchtower ne répond pas
        faux.conteneurs["bac-a-sable"]["State"] = {"Status": "exited", "Running": False}
        tour(c)
        assert ordre(c, "bac-a-sable", "allumer-et-mettre-a-jour").status_code == 202
        assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"]["etat"] == "echec")
        assert main.ETAT["conteneurs"].ordres["bac-a-sable"]["phrase"].startswith("allumé, mais Watchtower ne répond pas")
        assert faux.etat("bac-a-sable") == "running"
    main.ETAT.clear()


def test_watchtower_signale_un_echec(client, faux, wt):
    wt.echec.add("bac-a-sable")
    tour(client)
    assert ordre(client, "bac-a-sable", "mettre-a-jour").status_code == 202
    assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"].get("wt") == "fini")
    tour(client)
    assert "signale un échec" in tuile(client, "Bac à sable")["conteneur"]["ordre"]["phrase"]


def test_portainer_refuse_l_ordre(client, faux):
    faux.refus_ordres.add("bac-a-sable")
    tour(client)
    assert tuile(client, "Bac à sable")["conteneur"]["gerable"]                          # la lecture est permise
    assert ordre(client, "bac-a-sable", "eteindre").status_code == 202
    assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"]["etat"] == "echec")
    phrase = tuile(client, "Bac à sable")["conteneur"]["ordre"]["phrase"]
    assert phrase == "Portainer refuse : vérifier l'accès de l'équipe « anneau » à la stack."
    assert faux.etat("bac-a-sable") == "running"


def test_verifier_watchtower_sans_effet(tmp_path, faux):
    # sans /v1/containers ni /v1/metrics : seulement « adresse et jeton présents » ; jamais /v1/update
    wt = FauxWatchtower(faux)
    with _client(tmp_path, faux, wt=wt) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        w = next(f for f in c.get("/api/maison/services").json()["services"] if f["id"] == "watchtower")
        assert w["etat"] == "relie" and "/v1/update" in w["ecrit"]
        f = verifier(c, "watchtower").json()
        assert f["etat"] == "repond" and "adresse et jeton présents" in f["detail"]
        assert not [a for a in wt.appels if a[1] == "/v1/update"]
    main.ETAT.clear()
    # avec /v1/containers : le jeton est vérifié
    wt = FauxWatchtower(faux, containers_api=True)
    with _client(tmp_path, faux, wt=wt) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        f = verifier(c, "watchtower").json()
        assert f["etat"] == "repond" and "jeton accepté" in f["detail"]
        wt.jeton = "autre"
        f = verifier(c, "watchtower").json()
        assert f["etat"] == "ne_repond_pas" and "jeton refusé" in f["detail"]
        assert not [a for a in wt.appels if a[1] == "/v1/update"]
    main.ETAT.clear()


def test_etat_en_cours_survit_au_redemarrage(tmp_path, faux, wt):
    horloge = Horloge()
    with _client(tmp_path, faux, horloge=horloge, wt=wt) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        tour(c)
        wt.lenteur = 30                                     # Watchtower n'a pas fini quand l'Anneau redémarre
        faux.conteneurs["bac-a-sable"]["State"] = {"Status": "running", "Running": True}
        assert ordre(c, "bac-a-sable", "mettre-a-jour").status_code == 202
    main.ETAT.clear()
    relu = conteneurs.Conteneurs(tmp_path, conteneurs.Portainer(URL, CLE, transport=faux.transport()), horloge=horloge)
    assert relu.en_cours("bac-a-sable")
    s = services.lire(tmp_path / "services.yaml").services[0]
    assert relu.vue(s, False)["phrase"] == "mise à jour en cours…"
    import asyncio
    sonde = lambda s: asyncio.sleep(0, True)
    relu.etats["bac-a-sable"] = {**conteneurs.resume(faux.conteneurs["bac-a-sable"]), "lecture": 5}
    asyncio.run(relu.suivre(services.lire(tmp_path / "services.yaml"), sonde))
    assert relu.en_cours("bac-a-sable")                 # même image, Watchtower n'a pas répondu : jamais « déjà à jour »
    horloge.t += conteneurs.DELAI_MAJ + 1
    asyncio.run(relu.suivre(services.lire(tmp_path / "services.yaml"), sonde))
    assert relu.ordres["bac-a-sable"]["etat"] == "delai"
    assert relu.ordres["bac-a-sable"]["phrase"] == "pas de réponse, voir Watchtower et Portainer."


# ---------------------------------------------------------------- fiche : stats, connexion ; secrets

def test_stats_et_politique_de_redemarrage(client):
    tour(client)
    s = client.get("/api/conteneurs/bac-a-sable/stats").json()
    assert s["memoire"] == 260 * 1048576 and s["processeur"] == 40.0
    assert client.get("/api/conteneurs/transhumance/stats").status_code == 403
    assert client.get("/api/conteneurs/libre/stats").status_code == 404


def test_reglages_connexion_portainer(client):
    r = client.get("/api/maison/services").json()
    p = next(f for f in r["services"] if f["id"] == "portainer")
    assert p["etat"] == "relie" and "conteneur:" in p["lit"] and "Watchtower" in p["ecrit"] and "recréer" not in p["ecrit"]
    f = client.post("/api/maison/services/portainer/verifier").json()
    assert f["etat"] == "repond" and "environnement 3" in f["detail"] and "2.21.4" in f["detail"]


def test_connexion_portainer_pas_reglee(tmp_path, faux):
    with _client(tmp_path, faux, avec_cle=False) as c:
        c.post("/api/connexion", json={"mot_de_passe": MDP})
        p = next(f for f in c.get("/api/maison/services").json()["services"] if f["id"] == "portainer")
        assert p["etat"] == "pas_relie" and p["reglage"] == "ANNEAU_PORTAINER_URL"
    main.ETAT.clear()


def test_la_cle_ne_sort_jamais(client, faux, wt, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    tour(client)
    ordre(client, "bac-a-sable", "mettre-a-jour")
    assert attendre(lambda: main.ETAT["conteneurs"].ordres["bac-a-sable"].get("wt") == "fini")
    tour(client)
    verifier(client, "watchtower")
    ordre(client, "bac-a-sable", "eteindre")
    attendre(lambda: faux.etat("bac-a-sable") == "exited")
    tour(client)
    assert faux.cles_vues == {CLE}                                     # elle part bien vers Portainer…
    assert wt.jetons_vus == {JETON} and CLE not in str(wt.appels)     # le jeton vers Watchtower seulement
    data = main.ETAT["cfg"].data
    textes = [client.get("/api/etat").text, client.get("/health").text, client.get("/api/maison/services").text,
              client.get("/api/conteneurs/journal").text, json.dumps(main._propre()), repr(main.ETAT["cfg"]),
              repr(main.ETAT["conteneurs"].portainer), repr(main.ETAT["conteneurs"].watchtower), caplog.text,
              verifier(client, "watchtower").text]
    textes += [p.read_text(encoding="utf-8", errors="ignore") for p in data.rglob("*") if p.is_file()]
    assert not [t for t in textes if CLE in t or JETON in t]            # …et nulle part ailleurs


def test_sauvegarde_de_nuit_ne_compte_pas_l_eteinte(client, faux):
    import asyncio
    faux.conteneurs["bac-a-sable"]["State"] = {"Status": "exited", "Running": False}
    tour(client)
    data = main.ETAT["cfg"].data
    demandes = []

    async def lire(url, jeton):
        demandes.append(url)
        return 200, {}

    d = asyncio.run(sauvegardes.collecter(data, main.ETAT["veille"].fichier, {}, jeton="j", lire=lire, automatique=True,
                                          eteintes=main._noms_eteints()))
    assert d["ratees"] == {} and d["eteintes"] == {"Bac à sable": "éteinte, pas sauvegardée cette nuit"}
    assert not demandes and sauvegardes.a_traiter(data) == []          # pas de « Sauvegarde ratée »
    assert "éteinte(s), pas sauvegardée(s) (Bac à sable)" in sauvegardes.lire_etat(data)["historique"][0]
    # rallumée : de nouveau demandée (et ratée ici, faute de vraie appli)
    faux.conteneurs["bac-a-sable"]["State"] = {"Status": "running", "Running": True}
    tour(client)
    d = asyncio.run(sauvegardes.collecter(data, main.ETAT["veille"].fichier, {}, jeton="j", lire=lire, automatique=True,
                                          eteintes=main._noms_eteints()))
    assert d["eteintes"] == {} and demandes
