"""Tests de l'Anneau (temps 1) : la garde, le fichier des services, les règles d'une panne,
les envois de Home Assistant, le choix des adresses. Tout est inventé : aucune vraie adresse."""
import asyncio
import dataclasses
import json

import pytest
from fastapi.testclient import TestClient

from app import main, services
from app.config import Config
from app.veille import Veille

MDP = "mot-de-passe-de-test"
SECRET = "secret-de-home-assistant"


class Monde:
    """Un faux réseau : on dit quelles adresses répondent, et quelle heure il est."""
    def __init__(self):
        self.morts: set[str] = set()
        self.t = 1000.0
        self.demandes: list[str] = []
        self.refusent: dict[str, str] = {}      # morceau d'adresse → ce que le service dit du cadre
        self.examens: list[str] = []

    async def sonder(self, adresse):
        self.demandes.append(adresse)
        return (not any(m in adresse for m in self.morts), 12)

    async def examiner(self, adresse):
        self.examens.append(adresse)
        if any(m in adresse for m in self.morts):
            return None
        return next((r for m, r in self.refusent.items() if m in adresse), "")

    def horloge(self):
        return self.t


@pytest.fixture()
def monde():
    return Monde()


@pytest.fixture()
def veille(tmp_path, monde):
    return Veille(tmp_path, services.lire(tmp_path / "services.yaml"), ha_attendu=True, sonder=monde.sonder, horloge=monde.horloge, examiner=monde.examiner)


def tours(v, n=1):
    for _ in range(n):
        asyncio.run(v.tour())


def etat_de(v, nom, **kw):
    return next(s for f in v.etat(**kw)["familles"] for s in f["services"] if s["nom"] == nom)


@pytest.fixture()
def client(tmp_path, veille):
    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "static", secret_ha=SECRET,
                                attente_connexion=False, veille=False), veille=veille)
    with TestClient(main.app) as c:
        yield c
    main.ETAT.clear()


def connecter(client):
    assert client.post("/api/connexion", json={"mot_de_passe": MDP}).status_code == 200


# ---------------------------------------------------------------- la garde

def test_tout_est_ferme_sans_session(client):
    assert client.get("/health").json()["ok"] is True
    for chemin in ("/api/etat", "/api/inconnue"):
        assert client.get(chemin).status_code == 401, chemin
    for chemin in ("/api/pannes/vue", "/api/recharger"):
        assert client.post(chemin, json={}).status_code == 401, chemin
    assert client.post("/api/connexion", json={"mot_de_passe": "faux"}).status_code == 401
    connecter(client)
    assert client.get("/api/etat").status_code == 200 and client.get("/api/inconnue").status_code == 404
    assert client.get("/api/etat").headers["cache-control"] == "no-store"


def test_deconnexion_invalide_les_anciens_cookies(client, tmp_path):
    connecter(client)
    ancien = client.cookies.get("anneau_session")
    assert client.post("/api/deconnexion").status_code == 200
    client.cookies.set("anneau_session", ancien)
    assert client.get("/api/etat").status_code == 401
    assert (tmp_path / "session_generation").read_text() == "1"


# ---------------------------------------------------------------- le fichier des services

def test_sans_fichier_l_exemple_sert_et_c_est_dit(tmp_path):
    f = services.lire(tmp_path / "services.yaml")
    assert f.exemple and len(f.services) == 7 and [x["nom"] for x in f.familles][:2] == ["Proches", "Photos"]
    assert f.seuil_disque == 99.8 and f.famille_ha == "Maison" and not f.erreurs
    assert all("192.0.2." in s.locale for s in f.services)              # adresses réservées à la documentation


def test_une_ligne_fausse_est_ecartee_et_signalee(tmp_path):
    (tmp_path / "services.yaml").write_text("""
reglages: { seuil_disque: beaucoup }
familles: [{ nom: Photos }]
machines: [{ nom: Grand NAS, sonde: "pas une adresse" }]
services:
  - { nom: Bon, famille: Photos, locale: "http://192.0.2.1:80/" }
  - { nom: Bon, famille: Photos, locale: "http://192.0.2.1:81" }
  - { nom: Sans famille, famille: Ailleurs, locale: "http://192.0.2.1:82" }
  - { nom: Sans adresse, famille: Photos }
  - { nom: Machine fantôme, famille: Photos, locale: "http://192.0.2.1:83", machine: Inconnue }
""", encoding="utf-8")
    f = services.lire(tmp_path / "services.yaml")
    assert [s.nom for s in f.services] == ["Bon", "Machine fantôme"] and f.services[0].locale == "http://192.0.2.1:80"
    assert f.seuil_disque == 99.8 and not f.exemple and f.modifie_le
    assert len(f.erreurs) == 6
    (tmp_path / "services.yaml").write_text("- ceci\n- n'est pas\n- un fichier de services")
    with pytest.raises(services.FichierInvalide):
        services.lire(tmp_path / "services.yaml")


# ---------------------------------------------------------------- les règles d'une panne

def test_trois_echecs_ouvrent_trois_reussites_closent(veille, monde):
    tours(veille)
    assert etat_de(veille, "Cinéma")["etat"] == "ok" and veille.pannes == {} and veille.derniere_sonde
    monde.morts.add(":8103")
    tours(veille, 2)
    assert etat_de(veille, "Cinéma")["etat"] == "ok" and veille.pannes == {}        # deux échecs : rien encore
    tours(veille)
    assert etat_de(veille, "Cinéma")["etat"] == "panne"
    p = veille.pannes["service:cinema"]
    assert p["phrase"] == "Cinéma ne répond plus" and p["famille"] == "Médias"
    assert next(f for f in veille.etat()["familles"] if f["nom"] == "Médias")["etat"] == "panne"
    monde.morts.clear()
    tours(veille, 2)
    assert "service:cinema" in veille.pannes                                        # deux réussites : pas encore close
    tours(veille)
    assert veille.pannes == {} and veille.closes[0]["phrase_fin"] == "Cinéma répond de nouveau"
    # 0.4.2 : ouverte puis close entre deux envois de HA, une seule ligne, avec le passage
    r = veille.pour_ha()
    assert r["ouvertes"] == [] and r["closes"] == ["Cinéma : ne répond plus → répond de nouveau (coupure brève)"]
    monde.morts.add(":8103")
    tours(veille, 3)
    assert veille.pour_ha()["ouvertes"] == ["Cinéma : répond → ne répond plus"]
    monde.morts.clear()
    tours(veille, 3)
    assert veille.pour_ha()["closes"] == ["Cinéma : ne répond plus → répond de nouveau"]
    assert etat_de(veille, "Cinéma")["etat"] == "ok"


def test_un_arret_attendu_n_est_jamais_une_panne(veille, monde):
    monde.morts.add(":3003")
    tours(veille, 5)
    assert etat_de(veille, "Ordinateur de calcul")["etat"] == "eteint" and veille.pannes == {}
    assert next(f for f in veille.etat()["familles"] if f["nom"] == "Machines")["etat"] == "ok"


def test_une_machine_qui_tombe_fait_une_seule_panne(veille, monde):
    monde.morts.add("192.0.2.10")                      # le grand NAS et ses quatre services
    tours(veille, 3)
    assert list(veille.pannes) == ["machine:grand-nas"]
    assert veille.pannes["machine:grand-nas"]["phrase"] == "Grand NAS ne répond plus"
    e = etat_de(veille, "Cinéma")
    assert e["etat"] == "panne" and e["machine_en_panne"]
    assert next(f for f in veille.etat()["familles"] if f["nom"] == "Machines")["etat"] == "panne"   # la famille de la machine
    monde.morts.clear()
    tours(veille, 3)
    assert veille.pannes == {}


def test_une_panne_survit_au_redemarrage_et_se_prend_en_compte(veille, monde, tmp_path):
    monde.morts.add(":8104")
    tours(veille, 3)
    assert veille.prendre_en_compte("service:statistiques") and not veille.prendre_en_compte("service:inconnu")
    suite = Veille(tmp_path, veille.fichier, sonder=monde.sonder, horloge=monde.horloge, examiner=monde.examiner)
    assert suite.pannes["service:statistiques"]["prise_en_compte_le"]
    assert etat_de(suite, "Statistiques")["etat"] == "panne"
    monde.morts.clear()
    tours(suite, 3)
    assert suite.pannes == {} and json.loads((tmp_path / "pannes.json").read_text())["ouvertes"] == []


def test_un_service_retire_du_fichier_emporte_sa_panne(veille, monde):
    monde.morts.add(":8104")
    tours(veille, 3)
    veille.fichier = dataclasses.replace(veille.fichier, services=tuple(s for s in veille.fichier.services if s.nom != "Statistiques"))
    tours(veille)
    assert veille.pannes == {}


# ---------------------------------------------------------------- Home Assistant

ENVOI = {"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": 99.6, "etat": "attention"},
                     {"machine": "Grand NAS", "nom": "Volume 2", "pourcentage": "unavailable", "etat": "unavailable"}],
         "mises_a_jour": [{"machine": "Grand NAS", "disponible": False}, {"machine": "Petit NAS", "disponible": True, "version": "9.9"}]}


def test_le_seuil_des_disques_est_fixe(veille):
    r = veille.recevoir(ENVOI)
    assert r["pannes"] == 0 and veille.pannes == {}                                  # 99,6 % : sous le seuil, pas une panne
    assert veille.etat()["volumes"][1]["pourcentage"] is None                        # « indisponible » : ni panne ni vert
    assert veille.etat()["a_faire"] == [{"cle": "maj:petit-nas", "sorte": "systeme", "famille": "",
                                         "phrase": "Mise à jour du système disponible pour Petit NAS (9.9)"}]
    plein = {"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": 99.8}]}
    r = veille.recevoir(plein)
    assert r == {"pannes": 1, "ouvertes": ["Volume 1 de Grand NAS : sous le seuil → plein à 99,8 %"], "closes": [],
                 "liste": ["Volume 1 de Grand NAS est plein à 99,8 %"]}
    assert veille.pannes["volume:grand-nas-volume-1"]["famille"] == "Machines"
    assert veille.recevoir(plein)["ouvertes"] == []                                  # dit une fois, pas à chaque envoi
    veille.recevoir({"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": "unknown"}]})
    assert "volume:grand-nas-volume-1" in veille.pannes                              # on ne sait pas : on ne clôt pas
    r = veille.recevoir({"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": 97}]})
    assert r["pannes"] == 0 and r["closes"] == ["Volume 1 de Grand NAS : plein à 99,8 % → 97,0 %"]


def test_home_assistant_muet_apres_son_silence(veille, monde):
    """0.4.1 : Home Assistant envoie chaque heure ; il est muet après `silence_ha` minutes (90 par défaut)."""
    assert veille.fichier.silence_ha == 90
    tours(veille)
    monde.t += 89 * 60
    tours(veille)
    assert veille.pannes == {}                                                       # une heure sans envoi : normal
    monde.t += 2 * 60
    tours(veille)
    assert veille.pannes["ha"]["phrase"] == "Home Assistant est muet" and veille.pannes["ha"]["famille"] == "Maison"
    assert veille.recevoir({})["closes"] == ["Home Assistant : muet → envoie de nouveau son état"] and veille.pannes == {}
    assert veille.etat()["fraicheur"]["ha_age"] == 0
    sans = Veille(veille.data, veille.fichier, ha_attendu=False, sonder=monde.sonder, horloge=monde.horloge, examiner=monde.examiner)
    monde.t += 10 * 3600
    tours(sans)
    assert "ha" not in sans.pannes                                                   # sans secret, on n'attend personne


def test_silence_ha_reglable(tmp_path):
    from app.services import lire
    f = tmp_path / "services.yaml"
    base = "familles: [{nom: Maison}]\nservices: [{nom: X, famille: Maison, locale: 'http://192.0.2.1'}]\n"
    f.write_text(base + "reglages: {silence_ha: 10}\n", encoding="utf-8")
    assert lire(f).silence_ha == 10
    for faux in ("0", "abc", "-5"):
        f.write_text(base + f"reglages: {{silence_ha: {faux}}}\n", encoding="utf-8")
        r = lire(f)
        assert r.silence_ha == 90 and any("silence_ha" in e for e in r.erreurs)


def test_l_envoi_de_home_assistant_demande_le_secret(client):
    assert client.post("/api/ha/etat", json=ENVOI).status_code == 401
    assert client.post("/api/ha/etat", json=ENVOI, headers={"X-Anneau-Secret": "faux"}).status_code == 401
    r = client.post("/api/ha/etat", json=ENVOI, headers={"X-Anneau-Secret": SECRET})
    assert r.status_code == 200 and r.json()["pannes"] == 0
    main.ETAT["cfg"] = dataclasses.replace(main.ETAT["cfg"], secret_ha="")
    assert client.post("/api/ha/etat", json=ENVOI, headers={"X-Anneau-Secret": ""}).status_code == 503


# ---------------------------------------------------------------- les adresses, par l'API

def test_adresse_locale_ou_du_reseau_prive_selon_l_appel(client, veille):
    connecter(client)
    tours(veille)
    def service(nom, **entetes):
        return next(s for f in client.get("/api/etat", headers=entetes).json()["familles"] for s in f["services"] if s["nom"] == nom)
    maison = {"host": "192.0.2.10:8094"}
    assert service("Photothèque", **maison)["adresse"] == "http://192.0.2.10:8102" and service("Photothèque", **maison)["cadre"] is True
    prive = {"host": "anneau.reseau-prive.exemple", "x-forwarded-proto": "https"}
    assert service("Photothèque", **prive)["adresse"] == "https://photos.reseau-prive.exemple"
    assert service("Photothèque", **prive)["cadre"] is True
    assert service("Domotique", **prive)["adresse"] == "http://192.0.2.30:8123"       # pas d'adresse privée : la locale
    assert service("Domotique", **prive)["cadre"] is False                           # du http dans une page https : pas de cadre
    assert service("Répertoire", host="faux-reseau-prive.exemple.invalide")["adresse"].startswith("http://")      # pas l'adresse privée


def test_le_service_suit_l_hote_par_lequel_l_anneau_est_ouvert(client, veille):
    """Ouvert par un autre nom que celui de la maison, l'Anneau donne ses services sous ce nom :
    sinon le navigateur refuse leur cookie de connexion dans le cadre."""
    connecter(client)
    tours(veille)
    def adresse(nom, **entetes):
        return next(s for f in client.get("/api/etat", headers=entetes).json()["familles"] for s in f["services"] if s["nom"] == nom)["adresse"]
    assert adresse("Photothèque", host="192.0.2.10:8094") == "http://192.0.2.10:8102"         # ouvert par l'hôte de la maison : rien ne change
    assert adresse("Photothèque", host="grand-nas:8094") == "http://grand-nas:8102"           # par un nom : le service suit, port gardé
    assert adresse("Photothèque", host="100.64.0.7:8094") == "http://100.64.0.7:8102"         # par une autre adresse : pareil
    assert adresse("Domotique", host="grand-nas:8094") == "http://192.0.2.30:8123"            # une autre machine garde son adresse
    assert adresse("Photothèque", host="grand-nas", **{"x-forwarded-proto": "https"}) == "http://192.0.2.10:8102"   # en https : on ne devine pas
    assert adresse("Photothèque", host="anneau.reseau-prive.exemple") == "https://photos.reseau-prive.exemple"     # l'adresse privée passe devant


def test_tout_s_ouvre_dans_l_anneau_sauf_refus(veille, monde):
    """Sans rien dire dans le fichier, l'Anneau essaie le cadre ; il y renonce si le service l'interdit."""
    def service(nom):
        return next(s for f in veille.etat()["familles"] for s in f["services"] if s["nom"] == nom)
    assert service("Cinéma")["cadre"] is True                                        # avant tout examen : on essaie
    monde.refusent = {":8103": "X-Frame-Options : SAMEORIGIN"}
    monde.morts = {":8105"}
    tours(veille)
    assert service("Cinéma")["cadre"] is False and "X-Frame-Options : SAMEORIGIN" in service("Cinéma")["hors_cadre"]
    assert service("Photothèque")["cadre"] is True and service("Photothèque")["hors_cadre"] == ""
    assert service("Statistiques")["cadre"] is False and "cadre: false" in service("Statistiques")["hors_cadre"]
    assert not any(":8104" in a for a in monde.examens)                              # un choix du fichier ne se discute pas
    assert service("Téléchargements")["cadre"] is True                               # muet : on ne sait pas, on essaie
    monde.examens.clear()
    tours(veille)
    assert monde.examens == ["http://192.0.2.20:8105"]                               # seul l'inconnu est relu au tour suivant
    monde.refusent = {}
    tours(veille, 9)                                                                 # au onzième tour, tout est relu
    assert service("Cinéma")["cadre"] is True


def test_ce_que_dit_un_service_du_cadre():
    from app.veille import interdit_le_cadre
    assert interdit_le_cadre({}) == ""
    assert interdit_le_cadre({"x-frame-options": "sameorigin"}) == "X-Frame-Options : SAMEORIGIN"
    assert interdit_le_cadre({"content-security-policy": "default-src 'self'; frame-ancestors 'self'"}) == "Content-Security-Policy : frame-ancestors"
    assert interdit_le_cadre({"content-security-policy": "frame-ancestors 'none'"}) != ""
    assert interdit_le_cadre({"content-security-policy": "frame-ancestors *"}) == ""
    assert interdit_le_cadre({"content-security-policy": "default-src 'self'"}) == ""


def test_pris_en_compte_et_recharger_par_l_api(client, veille, monde, tmp_path):
    connecter(client)
    monde.morts.add(":8104")
    tours(veille, 3)
    assert client.post("/api/pannes/vue", json={"cle": "service:statistiques"}).status_code == 200
    assert client.get("/api/etat").json()["pannes"][0]["prise_en_compte_le"]
    assert client.post("/api/pannes/vue", json={"cle": "service:rien"}).status_code == 404
    (tmp_path / "services.yaml").write_text('familles: [{nom: Photos}]\nservices: [{nom: Seul, famille: Photos, locale: "http://192.0.2.9"}]')
    r = client.post("/api/recharger").json()
    assert r["services"] == 1 and client.get("/api/etat").json()["fraicheur"]["exemple"] is False
    assert client.get("/api/etat").json()["pannes"] == []
    (tmp_path / "services.yaml").write_text("[")
    assert client.post("/api/recharger").status_code == 422


def test_l_anneau_ne_fait_que_des_lectures(veille, monde):
    """Temps 1 : aucune écriture hors de chez lui. La sonde ne connaît qu'un geste, lire une adresse du fichier."""
    tours(veille, 2)
    attendues = {s.a_sonder for s in veille.fichier.services} | {m.sonde for m in veille.fichier.machines}
    assert set(monde.demandes) == attendues
    import inspect
    from app import veille as module
    source = inspect.getsource(module)
    assert ".post(" not in source and ".put(" not in source and ".delete(" not in source and ".patch(" not in source


# ---------------------------------------------------------------- 0.5 : Atlas

import httpx  # noqa: E402

from app import documents  # noqa: E402

PAGE = b"<!doctype html><html><head><title>Atlas</title></head><body>carte</body></html>"


def faux_github(etat_publication=200, piece=True, contenu=PAGE, vus=None, publie="2026-11-14T09:00:00Z"):
    def repondre(req: httpx.Request):
        if vus is not None:
            vus.append((str(req.url), req.headers.get("authorization", "")))
        if req.url.path.endswith("/releases/tags/derniere"):
            if etat_publication != 200:
                return httpx.Response(etat_publication)
            assets = [{"name": "atlas.html", "size": len(contenu), "updated_at": publie,
                       "url": "https://api.github.com/repos/moi/atlas/releases/assets/7"}] if piece else []
            return httpx.Response(200, json={"body": "Atlas 1.1.0", "assets": assets})
        if req.url.path.endswith("/releases/assets/7"):
            return httpx.Response(302, headers={"location": "https://stockage.exemple/atlas.html"})
        if req.url.host == "stockage.exemple":
            return httpx.Response(200, content=contenu)
        return httpx.Response(404)
    return httpx.MockTransport(repondre)


def test_atlas_telecharge_puis_garde_l_ancien_en_cas_d_echec(tmp_path):
    vus = []
    e = documents.telecharger_atlas(tmp_path, "moi/atlas", "jeton-essai", faux_github(vus=vus))
    assert e["present"] and not e["erreur"] and e["note"] == "Atlas 1.1.0"
    assert (tmp_path / "documents" / "atlas.html").read_bytes() == PAGE
    # le jeton ne part jamais vers le stockage où GitHub redirige
    assert all(auth == "" for url, auth in vus if "stockage.exemple" in url)
    assert any(auth == "Bearer jeton-essai" for url, auth in vus if "api.github.com" in url)
    vus.clear()
    e = documents.telecharger_atlas(tmp_path, "moi/atlas", "jeton-essai", faux_github(vus=vus))   # déjà à jour : rien de retéléchargé
    assert not e["erreur"] and not any("stockage" in u for u, _ in vus)
    e = documents.telecharger_atlas(tmp_path, "moi/atlas", "mauvais", faux_github(etat_publication=401))
    assert "refuse le jeton" in e["erreur"] and e["present"]
    e = documents.telecharger_atlas(tmp_path, "moi/atlas", "jeton-essai", faux_github(contenu=b"pas une page", publie="2026-11-15T09:00:00Z"))
    assert "pas une page HTML" in e["erreur"]
    assert (tmp_path / "documents" / "atlas.html").read_bytes() == PAGE


def test_atlas_sans_reglage(tmp_path):
    e = documents.telecharger_atlas(tmp_path, "", "", None)
    assert not e["present"] and "ANNEAU_ATLAS_DEPOT" in e["erreur"]


def test_atlas_servi_seulement_avec_une_session(client, tmp_path):
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "atlas.html").write_bytes(PAGE)
    r = client.get("/documents/atlas.html", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert client.get("/api/documents").status_code == 401
    connecter(client)
    r = client.get("/documents/atlas.html")
    assert r.status_code == 200 and b"carte" in r.content
    assert client.get("/api/documents").json()["atlas"]["present"] is True
