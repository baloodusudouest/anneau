"""L'Anneau : une seule porte pour les machines, les services et les applis de la maison.

Temps 1 : la vue. L'Anneau lit (une demande HTTP par service, chaque minute) et reçoit
(Home Assistant lui envoie l'état des machines). Il n'écrit nulle part hors de son dossier
(où, depuis la 0.6, il peut écrire services.yaml quand on l'importe depuis Réglages)
et ne détient aucun jeton d'un autre service — sauf, depuis la 0.5, un jeton GitHub en lecture seule pour relire Atlas.

Routes : /health (publique), /api/session, /api/connexion, /api/deconnexion, /api/etat,
/api/pannes/vue, /api/recharger, /api/services/importer (0.6), /api/ha/etat (ouverte par le secret de Home Assistant), /api/carte,
/api/carte (0.11 : la carte de la maison, ex-Atlas, derrière la session), /externe/services (0.7, jeton commun),
0.8 — sauvegarde des réglages : /api/reglages, /api/restaurer, /api/sauvegardes, /api/cle-publique,
/api/variables-chiffrees (session) ; /externe/sauvegarde, /externe/sauvegardes/{appli} (jeton commun) ;
0.10 — la sauvegarde regroupée dans l'Anneau : /api/stack, /api/stack/fichier, /api/services/fichier (session) ;
0.12 — santé des tâches de fond : /health rend aussi version_socle, taches (veille, collecte de nuit, relecture de la
carte ; messages seulement avec le jeton commun ou une session) et copie_base (null : l'Anneau n'a pas de base) ;
/api/sante/vu (session) ;
0.13 — versions et nouveautés de la nuit : tâche « versions-publiees » (étiquettes GitHub, chaque heure) ; /api/versions,
/api/versions/nouveautes, /api/versions/vues (session) ;
0.16 — fiches « Connexion » des applis (contrat 3) : /api/applis/{cle}/services et
/api/applis/{cle}/services/{service}/verifier (session) ; l'Anneau les lit chez l'appli avec ANNEAU_CLE, côté serveur ;
0.17 — allumer, éteindre, mettre à jour un conteneur marqué « conteneur: » (Portainer, ANNEAU_PORTAINER_*) :
POST /api/conteneurs/{cle}/{geste} (session + en-tête Origin exactement celui de l'Anneau ; jamais en lecture seule),
GET /api/conteneurs/{cle}/stats, GET /api/conteneurs/journal ; fiches « Connexion » de l'Anneau lui-même
(/api/maison/services : Portainer, GitHub) ; journal des écritures (journal-ecritures.jsonl) ;
0.17.1 — « Mettre à jour » par l'API HTTP de Watchtower (ANNEAU_WATCHTOWER_*), fiche « Connexion » Watchtower ;
0.19 — GET /api/https (ce que voit le serveur) ; la clé publique et le rangement d'un export exigent une page sûre (403,
ANNEAU_GARDE_HTTPS=non pour le dépannage) ; POST /api/reveil/{cle} (réveil du PC par le webhook de Home Assistant,
ANNEAU_HA_URL, ANNEAU_HA_WEBHOOK_REVEIL), fiche « Connexion » Home Assistant ;
0.22 — applis en veille : liste « veille » des réglages (sauvegardée, restaurée), GET /api/veille, POST /api/veille/{cle}
({"veille": vrai|faux}), POST /api/veille/{cle}/laisser ; Éteindre et Allumer d'une fiche mettent et sortent de la veille ;
une appli en veille qui tourne sans ordre donne une tuile « À traiter » (jamais d'arrêt seul) ;
puis l'interface. Le chiffrement et le déchiffrement de l'export des variables se font dans la page (HTTPS seulement) :
le serveur ne reçoit jamais que la clé publique et du texte déjà chiffré.
"""
from __future__ import annotations

import asyncio
import dataclasses
import hmac
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
import time

from . import carte, conteneurs, fiches, maison, majs, registres, reveil as reveils, sauvegardes, stack, versions

from . import __version__
from .auth import COMMUN, DUREE, Sessions, en_https
from .config import APPLI, Config, charger
from .services import PRECEDENT, FichierInvalide, adresse_https, importer, lire
from .veille import Veille

log = logging.getLogger("anneau")
ETAT: dict = {}
PUBLIQUES = ("/api/connexion", "/api/session", "/api/ha/etat")   # la dernière a sa propre garde : le secret


def _fichier_generation(cfg: Config) -> Path:
    return cfg.data / "session_generation"


def _generation_commune() -> int | None:
    """0.10.5 : génération du cookie commun = génération des sessions de l'Anneau (None avant le démarrage)."""
    s = ETAT.get("sessions")
    return s.generation if s is not None else None


def _lire_generation(cfg: Config) -> int:
    try:
        return int(_fichier_generation(cfg).read_text().strip())
    except (OSError, ValueError):
        return 0


# ---------------------------------------------------------------- 0.12 : les tâches de fond de l'Anneau lui-même
# Registre commun du socle 0.9.0 (maison.TACHES). Écrit contre son API ; tant que le maison.py diffusé est plus ancien,
# l'Anneau tourne comme avant et son /health n'a pas de tâches.
TACHE_VEILLE, TACHE_COLLECTE, TACHE_CARTE = "veille", "collecte-de-nuit", "relecture-de-la-carte"
TACHE_VERSIONS = "versions-publiees"          # 0.13
TACHE_MAJS = "mises-a-jour-des-applis"       # 0.18


def _registre():
    return getattr(maison, "TACHES", None)


@asynccontextmanager
async def _rien():
    yield


def _tour(nom: str):
    """`async with _tour(nom):` marque début, réussite ou erreur dans le registre commun (s'il existe)."""
    r = _registre()
    return r.tour_async(nom) if r is not None else _rien()


def _declarer(cfg: Config) -> None:
    r = _registre()
    if r is None:
        return
    if cfg.veille:
        r.declarer(TACHE_VEILLE, periode_s=max(int(cfg.periode), 1), type="reguliere")
        if cfg.sauvegarde_auto:
            r.declarer(TACHE_COLLECTE, periode_s=86400, type="reguliere")
        if cfg.atlas_depot:
            r.declarer(TACHE_CARTE, periode_s=3600, type="reguliere")
        r.declarer(TACHE_VERSIONS, periode_s=versions.HEURE, type="reguliere")
        if cfg.portainer:
            r.declarer(TACHE_MAJS, periode_s=majs.PERIODE, type="reguliere")


PERIODE_PRESSEE = 5                            # 0.17 : secondes entre deux tours pendant les 5 min qui suivent un ordre


async def un_tour(veille: Veille) -> None:
    """Un tour de veille. 0.17 : l'état des conteneurs marqués est relu chez Portainer avant la sonde (un conteneur
    arrêté est « éteint », jamais « en panne »), puis les ordres en cours sont suivis (état réel, /health)."""
    c = ETAT.get("conteneurs")
    if c is not None and c.actif:
        try:
            await c.relire(veille.fichier)
        except Exception:                          # noqa: BLE001 — Portainer en panne n'arrête pas la veille
            log.exception("Lecture des conteneurs interrompue")
        veille.eteints = c.eteints() | (_en_veille() - set(c.revenues(_en_veille())))   # 0.22 : en veille = arrêt attendu
        veille.versions_conteneurs = c.versions()   # 0.21 : version des applis tierces (étiquette de leur image)
    else:
        veille.eteints = _en_veille()
    await veille.tour()
    if c is not None and c.actif:
        await c.suivre(veille.fichier, veille.repond)
    r = ETAT.get("reveil_pc")                      # 0.19 : un réveil demandé : la tuile répond-elle ?
    if r is not None and r.en_cours():
        await r.suivre({t.cle: t for t in veille.fichier.services}, veille.repond)
    m = ETAT.get("majs")                           # 0.18 : une mise à jour lancée depuis « À faire » est-elle finie ?
    if m is not None and m.en_cours():
        try:
            await m.suivre()
        except Exception:                          # noqa: BLE001
            log.exception("Suivi des mises à jour interrompu")


async def _ronde(veille: Veille, periode: int) -> None:
    reveil = ETAT.get("reveil")
    while True:
        try:
            async with _tour(TACHE_VEILLE):
                await un_tour(veille)
        except Exception:                          # une ronde ratée ne doit jamais arrêter la veille
            log.exception("Ronde de sonde interrompue")
        c = ETAT.get("conteneurs")
        m = ETAT.get("majs")
        rp = ETAT.get("reveil_pc")                  # 0.19 : un réveil en cours presse aussi la ronde
        presse = (c is not None and c.presse()) or (m is not None and m.presse()) or (rp is not None and rp.en_cours())
        attente = min(periode, PERIODE_PRESSEE) if presse else periode
        if reveil is None:
            await asyncio.sleep(attente)
            continue
        reveil.clear()
        with suppress(asyncio.TimeoutError):       # 0.17 : un ordre réveille la ronde (relecture tout de suite)
            await asyncio.wait_for(reveil.wait(), timeout=attente)


async def _relire_carte(cfg: Config) -> None:
    """0.11 : la carte de la maison est relue au démarrage puis toutes les heures (le bouton de Réglages la relit
    tout de suite)."""
    while True:
        try:
            if carte.a_relire(cfg.data, time.time()):
                async with _tour(TACHE_CARTE):
                    e = await asyncio.to_thread(carte.telecharger, cfg.data, cfg.atlas_depot, cfg.github_jeton)
                    if e.get("erreur"):            # 0.12 : une relecture ratée compte comme une erreur de la tâche
                        raise RuntimeError(e["erreur"])
        except Exception:
            log.exception("Relecture de la carte interrompue")
        await asyncio.sleep(300)


async def _versions_publiees(cfg: Config) -> None:
    """0.13 : la dernière version publiée de chaque tuile qui a un `depot:`, relue toutes les heures (étiquettes Git,
    API publique de GitHub, sans jeton). GitHub injoignable ou limite atteinte : l'ancienne lecture reste et seule la
    tâche passe en erreur (rien d'autre à l'écran)."""
    while True:
        try:
            if versions.a_relire(cfg.data, time.time()):
                async with _tour(TACHE_VERSIONS):
                    depots = [s.depot for s in ETAT["veille"].fichier.services if s.depot]
                    e = await asyncio.to_thread(versions.relire, cfg.data, depots, ETAT.get("transport_versions"))
                    if e.get("erreur"):
                        raise RuntimeError(e["erreur"])
        except Exception:
            log.exception("Lecture des versions publiées interrompue")
        await asyncio.sleep(300)


async def _verifier_majs() -> None:
    """0.18 : les images de la stack comparées à leur registre toutes les 6 h (rattrapé au démarrage, après 1 min)."""
    await asyncio.sleep(60)
    while True:
        try:
            m = ETAT.get("majs")
            if m is not None and m.a_verifier():
                async with _tour(TACHE_MAJS):
                    await m.verifier(ETAT["veille"].fichier, ETAT["veille"].versions_des_tuiles())
                    if m.erreur:
                        raise RuntimeError(m.erreur)
        except Exception:
            log.exception("Vérification des mises à jour interrompue")
        await asyncio.sleep(300)


async def _sauvegarde_quotidienne(cfg: Config) -> None:
    """0.8 : chaque jour à l'heure de Réglages › Sauvegarde (rattrapée au démarrage si elle est passée)."""
    while True:
        try:
            if sauvegardes.a_lancer(cfg.data, ETAT["reglages"].get("heure_sauvegarde"), datetime.now().astimezone()):
                async with _tour(TACHE_COLLECTE):
                    d = await _collecter(automatique=True)
                    if d.get("erreur"):            # 0.12 : fichier non écrit = tâche en erreur (une appli ratée, non)
                        raise RuntimeError(d["erreur"])
        except Exception:
            log.exception("Collecte des sauvegardes interrompue")
        await asyncio.sleep(30)


def _lire_au_demarrage(data: Path):
    """0.10.2 : un services.yaml illisible n'empêche plus l'Anneau de démarrer ; l'exemple sert, l'erreur s'affiche."""
    try:
        return lire(data / "services.yaml")
    except FichierInvalide as exc:
        log.error("services.yaml illisible : %s", exc)
        f = lire(data / "services.absent.yaml")
        return dataclasses.replace(f, erreurs=(f"services.yaml illisible, exemple affiché à la place : {exc}",) + tuple(f.erreurs))


@asynccontextmanager
async def cycle(app: FastAPI):
    cfg = ETAT.get("cfg") or charger()
    cfg.data.mkdir(parents=True, exist_ok=True)
    veille = ETAT.get("veille") or Veille(cfg.data, _lire_au_demarrage(cfg.data), ha_attendu=bool(cfg.secret_ha))
    reglages = ETAT.get("reglages") or maison.Reglages(cfg.data / "reglages.json", sauvegardes.DEFAUTS, {})
    sauvegardes.demarrer(cfg.data)
    portainer = conteneurs.Portainer(cfg.portainer_url, cfg.portainer_cle, cfg.portainer_env,
                                     transport=ETAT.get("transport_portainer")) if cfg.portainer else None
    watchtower = conteneurs.Watchtower(cfg.watchtower_url, cfg.watchtower_jeton,
                                       transport=ETAT.get("transport_watchtower")) if cfg.watchtower else None
    qnap = None                                      # 0.21 : le QNAP, par le même Portainer (environnement écrit)
    if cfg.qnap:
        qnap = conteneurs.Machine(
            "qnap", "QNAP",
            conteneurs.Portainer(cfg.portainer_url, cfg.portainer_cle, cfg.qnap_portainer_env,
                                 transport=ETAT.get("transport_portainer_qnap") or ETAT.get("transport_portainer")),
            conteneurs.PROJET_QNAP,
            conteneurs.Watchtower(cfg.qnap_watchtower_url, cfg.qnap_watchtower_jeton,
                                  transport=ETAT.get("transport_watchtower_qnap")) if cfg.qnap_watchtower else None,
            cfg.qnap_watchtower_manque(), cfg.qnap_machine)
    gestion = ETAT.get("conteneurs") or conteneurs.Conteneurs(cfg.data, portainer, watchtower=watchtower,
                                                              watchtower_manque=cfg.watchtower_manque(), qnap=qnap,
                                                              qnap_tuiles=cfg.qnap_machine, qnap_manque=cfg.qnap_manque())
    mises = ETAT.get("majs") or majs.MisesAJour(cfg.data, portainer, watchtower=watchtower,
                                                watchtower_manque=cfg.watchtower_manque(), qnap=qnap,
                                                registres=registres.Registres(ETAT.get("transport_registres"),
                                                                              identifiants={"ghcr.io": (cfg.ghcr_utilisateur, cfg.ghcr_jeton)}),
                                                noter=gestion.noter)
    reveil_pc = ETAT.get("reveil_pc") or reveils.Reveil(cfg.ha_url, cfg.ha_webhook_reveil, noter=gestion.noter,
                                                       transport=ETAT.get("transport_ha"))
    reveil = asyncio.Event()
    gestion.reveil = reveil
    mises.reveil = reveil
    ETAT.update(cfg=cfg, sessions=Sessions(APPLI, cfg.password, _lire_generation(cfg)), veille=veille,
                reglages=reglages, verrou_collecte=asyncio.Lock(), conteneurs=gestion, reveil=reveil, majs=mises,
                reveil_pc=reveil_pc)
    # 0.10.5 : la génération des sessions de l'Anneau sert aussi au cookie commun ; « Se déconnecter » l'augmente
    # et les autres applis la lisent dans /externe/services : les cookies communs d'avant ne valent plus nulle part
    maison.definir_generation_commune(_generation_commune)
    _declarer(cfg)
    ronde = asyncio.create_task(_ronde(veille, cfg.periode)) if cfg.veille else None
    atlas = asyncio.create_task(_relire_carte(cfg)) if cfg.veille and cfg.atlas_depot else None
    collecte = asyncio.create_task(_sauvegarde_quotidienne(cfg)) if cfg.veille and cfg.sauvegarde_auto else None
    publiees = asyncio.create_task(_versions_publiees(cfg)) if cfg.veille else None
    verif = asyncio.create_task(_verifier_majs()) if cfg.veille and mises.actif else None
    yield
    for t in (ronde, atlas, collecte, publiees, verif):
        if t:
            t.cancel()
            with suppress(asyncio.CancelledError):
                await t


app = FastAPI(title=APPLI, version=__version__, lifespan=cycle, docs_url=None, redoc_url=None)


# ================================================================ sécurité

@app.middleware("http")
async def garde(request: Request, appel):
    chemin = request.url.path
    if chemin.startswith("/api/"):
        if chemin not in PUBLIQUES and not ETAT["sessions"].connecte(request.cookies):
            return JSONResponse({"detail": "Connexion nécessaire."}, status_code=401)
    reponse = await appel(request)
    if chemin.startswith("/api/"):
        reponse.headers["Cache-Control"] = "no-store"
    return reponse


# 0.17 : fiches « Connexion » de l'Anneau lui-même (contrat 3) : Réglages › Connexion. Montées après la garde (le dernier
# middleware ajouté passe en premier) ; accès : session de l'Anneau, ou ANNEAU_CLE.
CONNEXIONS = maison.Services(APPLI)


def _cfg_ou_vide():
    return ETAT.get("cfg")


async def _essai_portainer():
    c = ETAT.get("conteneurs")
    if c is None:
        return False, "Pas réglé."
    try:
        return await c.essai()
    except conteneurs.ErreurPortainer as exc:
        return False, exc.phrase


CONNEXIONS.ajouter(
    "portainer", "Portainer",
    lit="L'état, l'image, la mémoire et le processeur des seuls conteneurs marqués « conteneur: » dans le fichier "
        "des services (relus à chaque tour de veille).",
    ecrit="Sur ordre depuis la fiche d'une tuile marquée : arrêter ou démarrer ce seul conteneur (jamais la stack). La "
          "mise à jour passe par Watchtower. Chaque ordre est noté au journal des écritures.",
    regle=lambda: bool(_cfg_ou_vide() and _cfg_ou_vide().portainer), reglage="ANNEAU_PORTAINER_URL",
    essai=_essai_portainer,
    derniere_ecriture=lambda: ETAT["conteneurs"].derniere_ecriture(("allumer", "eteindre", "allumer-et-mettre-a-jour"))
    if ETAT.get("conteneurs") else None)


async def _essai_watchtower():
    """0.17.1 : sans effet (GET /v1/containers, /v1/metrics) ; JAMAIS /v1/update depuis « Vérifier »."""
    c = ETAT.get("conteneurs")
    if c is None or c.watchtower is None:
        return False, "Pas réglé."
    try:
        return await c.watchtower.essai()
    except conteneurs.ErreurWatchtower as exc:
        return False, exc.phrase + "."


CONNEXIONS.ajouter(
    "watchtower", "Watchtower",
    lit="Rien ; « Vérifier » regarde seulement s'il répond (sans rien mettre à jour).",
    ecrit="Sur ordre « Mettre à jour » depuis la fiche d'une tuile marquée : demande à Watchtower de mettre à jour les "
          "conteneurs en marche de son image (POST /v1/update?image=…). Chaque ordre est noté au journal des écritures.",
    regle=lambda: bool(_cfg_ou_vide() and _cfg_ou_vide().watchtower), reglage="ANNEAU_WATCHTOWER_URL",
    essai=_essai_watchtower,
    derniere_ecriture=lambda: ETAT["conteneurs"].derniere_ecriture(conteneurs.MAJ) if ETAT.get("conteneurs") else None)
async def _essai_portainer_qnap():
    c = ETAT.get("conteneurs")
    if c is None or c.qnap is None:
        return False, "Pas réglé."
    try:
        return await c.essai_qnap()
    except conteneurs.ErreurPortainer as exc:
        return False, exc.phrase


CONNEXIONS.ajouter(
    "portainer-qnap", "Portainer (QNAP)",
    lit="La stack media du QNAP (environnement ANNEAU_QNAP_PORTAINER_ENV, par le même Portainer) : état et image des "
        "conteneurs marqués, et liste des applis à mettre à jour.",
    ecrit="Sur ordre depuis la fiche d'une tuile du QNAP marquée : arrêter ou démarrer ce seul conteneur. Chaque ordre est "
          "noté au journal des écritures.",
    regle=lambda: bool(_cfg_ou_vide() and _cfg_ou_vide().qnap), reglage="ANNEAU_QNAP_PORTAINER_ENV",
    essai=_essai_portainer_qnap)


async def _essai_watchtower_qnap():
    c = ETAT.get("conteneurs")
    if c is None or c.qnap is None or c.qnap.watchtower is None:
        return False, "Pas réglé."
    try:
        return await c.qnap.watchtower.essai()
    except conteneurs.ErreurWatchtower as exc:
        return False, exc.phrase + "."


CONNEXIONS.ajouter(
    "watchtower-qnap", "Watchtower (QNAP)",
    lit="Rien ; « Vérifier » regarde seulement s'il répond (sans rien mettre à jour).",
    ecrit="Sur ordre « Mettre à jour » d'un conteneur du QNAP (fiche ou « À faire quand tu veux ») : POST /v1/update?image=… "
          "au Watchtower du QNAP. Chaque ordre est noté au journal des écritures.",
    regle=lambda: bool(_cfg_ou_vide() and _cfg_ou_vide().qnap_watchtower), reglage="ANNEAU_QNAP_WATCHTOWER_URL",
    essai=_essai_watchtower_qnap)


async def _essai_ha():
    """0.19 : Home Assistant répond-il ? JAMAIS le webhook depuis « Vérifier »."""
    r = ETAT.get("reveil_pc")
    if r is None or not r.actif:
        return False, (_cfg_ou_vide().reveil_manque() if _cfg_ou_vide() else "Pas réglé.")
    return await r.essai()


CONNEXIONS.ajouter(
    "home-assistant", "Home Assistant",
    lit="Rien : Home Assistant envoie lui-même l'état des machines à l'Anneau (secret ANNEAU_SECRET_HA). « Vérifier » "
        "regarde seulement s'il répond.",
    ecrit="Sur ordre « Réveiller le PC » depuis la fiche d'une tuile marquée « reveil: true » : appelle le webhook de "
          "réveil de Home Assistant, qui envoie le signal Wake-on-LAN. Chaque ordre est noté au journal des écritures.",
    regle=lambda: bool(_cfg_ou_vide() and _cfg_ou_vide().reveil), reglage="ANNEAU_HA_URL",
    essai=_essai_ha,
    derniere_ecriture=lambda: ETAT["conteneurs"].derniere_ecriture(("reveil",)) if ETAT.get("conteneurs") else None)


def _essai_github():
    """0.17.2 : lit les informations de carte.json avec le jeton (lecture seule, rien n'est enregistré)."""
    cfg = _cfg_ou_vide()
    if cfg is None:
        return False, "Pas réglé."
    return carte.essai(cfg.atlas_depot, cfg.github_jeton, ETAT.get("transport_github"))


CONNEXIONS.ajouter(
    "github", "GitHub",
    lit="La carte de la maison (carte.json du dépôt d'Atlas, chaque heure, jeton en lecture seule) et les étiquettes "
        "publiques des dépôts des tuiles (versions publiées).",
    ecrit="Rien.",
    regle=lambda: bool(_cfg_ou_vide() and _cfg_ou_vide().atlas_depot and _cfg_ou_vide().github_jeton),
    reglage="ANNEAU_ATLAS_DEPOT", essai=_essai_github)
maison.monter_services(app, CONNEXIONS, lambda request: ETAT["sessions"].connecte(request.cookies))


# ================================================================ public

@app.get("/health")
def sante(request: Request):
    """Publique. 0.12 : avec la santé des tâches de fond (contrat commun du socle 0.9.0) ; les messages d'erreur
    seulement si la demande porte le jeton commun ou une session de l'Anneau."""
    return {"ok": True, "version": __version__, **_ma_sante(request)}


def _autorise(request: Request) -> bool:
    if maison.jeton_valide(maison.jeton_propose(request.headers), maison.jetons()):   # temps constant
        return True
    s = ETAT.get("sessions")
    return bool(s and s.connecte(request.cookies))


def _ma_sante(request: Request) -> dict:
    s = ETAT.get("sessions")
    commun = getattr(maison, "sante", None)          # socle 0.9.0 : maison.sante(request, jeton_commun, session_ok)
    if commun is not None:
        return commun(request, session_ok=bool(s and s.connecte(request.cookies)))
    r = _registre()                                  # maison.py plus ancien : même contrat, fait ici
    version_socle = getattr(maison, "VERSION_SOCLE", None) or getattr(maison, "VERSION", None)
    taches = r.etat(avec_messages=_autorise(request)) if r is not None else []
    return {"version_socle": version_socle, "taches": taches, "copie_base": None}   # l'Anneau n'a pas de base SQLite


# ================================================================ connexion

@app.get("/api/session")
def session(request: Request):
    s = ETAT["sessions"]
    return {"connecte": s.connecte(request.cookies), "version": __version__}


@app.post("/api/connexion")
async def connexion(request: Request, corps: dict = Body(...)):
    s = ETAT["sessions"]
    if ETAT["cfg"].attente_connexion:
        await asyncio.sleep(s.attente())
    if not s.verifier_mot_de_passe(str(corps.get("mot_de_passe", ""))):
        raise HTTPException(401, "Mot de passe incorrect.")
    r = JSONResponse({"ok": True})
    r.set_cookie(s.cookie, s.creer(), max_age=DUREE, httponly=True, samesite="strict", secure=en_https(request))
    # La connexion commune : les applis de la maison servies par la même adresse s'ouvrent sans rien demander.
    r.set_cookie(COMMUN, s.creer_commun(), max_age=DUREE, httponly=True, samesite="strict", secure=en_https(request))
    return r


@app.post("/api/deconnexion")
def deconnexion():
    s = ETAT["sessions"]
    s.generation += 1
    try:
        _fichier_generation(ETAT["cfg"]).write_text(str(s.generation))
    except OSError:
        pass  # volume en lecture seule : la déconnexion vaut jusqu'au prochain redémarrage
    r = JSONResponse({"ok": True})
    r.delete_cookie(s.cookie)
    r.delete_cookie(COMMUN)      # « Se déconnecter » ferme aussi la connexion commune
    return r


# ================================================================ l'état

def _hote(request: Request) -> str:
    return (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(":")[0].lower()


def _prive(request: Request) -> bool:
    """L'Anneau est-il ouvert par son adresse du réseau privé ? Alors tous les liens le sont aussi."""
    hote = _hote(request)
    return any(hote == h or hote.endswith("." + h) for h in ETAT["veille"].fichier.hotes_prives)


def _port(request: Request) -> int | None:
    """Le port par lequel le navigateur a ouvert l'Anneau (en-tête Host), ou None."""
    hote = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    morceau = hote.rsplit(":", 1)[1] if ":" in hote and not hote.endswith("]") else ""
    return int(morceau) if morceau.isdigit() else None


def _https(request: Request) -> bool:
    return (request.headers.get("x-forwarded-proto") or request.url.scheme) == "https"


LOCAUX = ("localhost", "127.0.0.1", "::1", "[::1]")


def _https_par(request: Request) -> str:
    """0.19 : d'où l'Anneau tient que la page est sûre : « direct » (servie en https), « relais » (X-Forwarded-Proto de
    Tailscale Serve), « origine » (en-tête Origin du navigateur, envoyé à chaque écriture), « machine » (localhost : rien
    ne quitte la machine, comme pour le navigateur), ou « » (http sur le réseau). La garde protège Julien d'une page
    ouverte par erreur en http : un client qui forge ces en-têtes a déjà la session, il n'apprend rien de plus."""
    if request.url.scheme == "https":
        return "direct"
    if request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower() == "https":
        return "relais"
    if request.headers.get("origin", "").strip().lower().startswith("https://"):
        return "origine"
    return "machine" if _hote_brut(request) in LOCAUX else ""


def _hote_brut(request: Request) -> str:
    """L'hôte de l'en-tête Host, sans le port ([::1] garde ses crochets)."""
    h = (request.headers.get("host") or "").strip().lower()
    if h.startswith("["):
        return h.split("]")[0] + "]"
    return h.rsplit(":", 1)[0] if ":" in h else h


HTTPS_REQUIS = "Les secrets ne s'écrivent qu'en https : ouvre l'Anneau par son adresse https (Tailscale). Tailscale en panne : " \
               "ANNEAU_GARDE_HTTPS=non dans la stack, le temps du dépannage."


def _exiger_https(request: Request) -> None:
    """0.19 (écart de l'audit) : écrire la clé publique ou ranger un export chiffré exige une page sûre, vérifié ici et
    plus seulement dans le navigateur. La lecture et le téléchargement des exports (du texte chiffré) restent permis."""
    if ETAT["cfg"].garde_https and not _https_par(request):
        raise HTTPException(403, HTTPS_REQUIS)


def _exiger_ecriture() -> None:
    """0.19 (écart de l'audit) : en lecture seule, l'Anneau n'envoie aucun ordre à un autre service (Portainer, Watchtower,
    Home Assistant). Ce qu'il écrit dans son propre dossier reste permis, comme dans le socle."""
    if _lecture_seule():
        raise HTTPException(403, "Lecture seule (MAISON_LECTURE_SEULE ou ANNEAU_LECTURE_SEULE) : aucun ordre n'est envoyé.")


@app.get("/api/https")
def diagnostic_https(request: Request):
    """0.19 : ce que voit le serveur (étape zéro du conseil) : page sûre ou non, et par quel signal. Aucun secret."""
    return {"https": bool(_https_par(request)), "par": _https_par(request), "garde": ETAT["cfg"].garde_https,
            "relais": request.headers.get("x-forwarded-proto", ""), "lecture_seule": _lecture_seule()}


def _a_traiter() -> list[dict]:
    return _tuiles_revenues() + sauvegardes.a_traiter(ETAT["cfg"].data, cle_publique=ETAT["reglages"].get("cle_publique"))


# ================================================================ applis en veille (0.22)

def _en_veille() -> set[str]:
    """Clés des tuiles en veille (réglage « veille »), limitées aux tuiles marquées conteneur:."""
    r, v = ETAT.get("reglages"), ETAT.get("veille")
    if r is None or v is None:
        return set()
    marquees = {t.cle for t in v.fichier.services if t.conteneur}
    return set(sauvegardes.lire_veille(r.get("veille") or "")) & marquees


def _poser_veille(cles: set[str]) -> None:
    ETAT["reglages"].changer({"veille": sauvegardes.joindre_veille(cles)})


def _revenues() -> list[str]:
    c = ETAT.get("conteneurs")
    return c.revenues(_en_veille()) if c is not None and c.actif else []


def _tuiles_revenues() -> list[dict]:
    noms = {t.cle: t.nom for t in ETAT["veille"].fichier.services} if ETAT.get("veille") else {}
    return [{"cle": f"veille-revenue-{k}", "sorte": "veille-revenue", "tuile": k, "nom": noms.get(k, k),
             "phrase": f"Revenue de veille : {noms.get(k, k)}",
             "detail": "Elle tourne sans ordre de l'Anneau (redéploiement de la stack ou démarrage dans Portainer)."}
            for k in _revenues()]


def _partages(t) -> set[str]:
    """Conteneurs de t (compagnons) encore utilisés par une autre tuile hors veille : jamais arrêtés avec t."""
    veille = _en_veille()
    utilises = set()
    for x in ETAT["veille"].fichier.services:
        if x.cle != t.cle and x.cle not in veille and x.conteneur:
            utilises |= {x.conteneur.lower(), *(c.lower() for c in x.compagnons)}
    return {c for c in t.compagnons if c.lower() in utilises}


async def _changer_veille(t, en_veille: bool) -> dict:
    """Met en veille (ajoute à la liste, puis arrête) ou sort de veille (retire, puis démarre). Un ordre refusé remet la
    liste comme avant ; « déjà éteint » / « déjà allumé » ne sont pas des refus ici."""
    gestion = ETAT["conteneurs"]
    avant = _en_veille()
    apres = (avant | {t.cle}) if en_veille else (avant - {t.cle})
    if not t.conteneur:
        raise HTTPException(404, "Cette tuile n'a pas de conteneur à gérer (champ conteneur: absent).")
    _poser_veille(apres)
    ordre = None
    try:
        ordre = await gestion.ordonner(t, "eteindre" if en_veille else "allumer", _lecture_seule(),
                                       partages=_partages(t) if en_veille else frozenset())
    except conteneurs.Refus as r:
        e = gestion.etats.get(t.cle) or {}
        deja = r.statut == 409 and not gestion.en_cours(t.cle) and e and not e.get("absent") \
            and bool(e.get("running")) != en_veille and "déjà" in r.phrase
        if not deja:
            _poser_veille(avant)
            raise HTTPException(r.statut, r.phrase) from None
    gestion.noter("veille" if en_veille else "sortie de veille", t.nom, "liste changée", conteneur=t.conteneur)
    if ETAT.get("reveil") is not None:
        ETAT["reveil"].set()
    return {"veille": sorted(apres), "ordre": ordre}


def _vue_veille(seule: bool) -> dict:
    gestion = ETAT.get("conteneurs")
    veille, revenues = _en_veille(), set(_revenues())
    lignes = []
    for t in ETAT["veille"].fichier.services:
        if not t.conteneur:
            continue
        v = gestion.vue(t, seule, en_veille=t.cle in veille) if gestion is not None else None
        pourquoi = "Portainer n'est pas réglé (ANNEAU_PORTAINER_URL, ANNEAU_PORTAINER_CLE)" if v is None else v["pourquoi"]
        if not pourquoi and v and v.get("ordre") and v["ordre"].get("etat") == "en_cours":
            pourquoi = "un ordre est déjà en cours"
        if not pourquoi and seule:
            pourquoi = "lecture seule"
        lignes.append({"cle": t.cle, "nom": t.nom, "famille": t.famille, "machine": (v or {}).get("machine", ""),
                       "en_veille": t.cle in veille, "revenue": t.cle in revenues,
                       "statut": (v or {}).get("statut", "inconnu"), "phrase": (v or {}).get("phrase", ""),
                       "compagnons": list(t.compagnons), "possible": not pourquoi, "pourquoi": pourquoi})
    return {"tuiles": lignes, "erreur": (gestion.erreur if gestion is not None else "")}


@app.get("/api/veille")
def lire_veille():
    return _vue_veille(_lecture_seule())


@app.post("/api/veille/{cle}")
async def changer_veille(cle: str, request: Request, corps: dict = Body(...)):
    """Cocher / décocher une appli en veille (Réglages) ou « Démarrer » depuis une tuile grise. Session, Origin, jamais
    en lecture seule. Le nom du conteneur vient de services.yaml, jamais de la requête."""
    _verifier_origine(request)
    _exiger_ecriture()
    if not isinstance(corps, dict) or not isinstance(corps.get("veille"), bool):
        raise HTTPException(400, "Corps attendu : {\"veille\": true} ou {\"veille\": false}.")
    return await _changer_veille(_tuile(cle), corps["veille"])


@app.post("/api/veille/{cle}/laisser")
def laisser_allumee(cle: str, request: Request):
    """Une appli revenue de veille : « La laisser allumée » la retire de la liste, sans ordre (rien n'est envoyé)."""
    _verifier_origine(request)
    t = _tuile(cle)
    _poser_veille(_en_veille() - {t.cle})
    ETAT["conteneurs"].noter("laissée allumée", t.nom, "retirée de la veille", conteneur=t.conteneur)
    return {"veille": sorted(_en_veille())}


@app.get("/api/etat")
def etat(request: Request):
    e = ETAT["veille"].etat(prive=_prive(request), https=_https(request), hote=_hote(request))
    maisons = fiches.cibles(ETAT["veille"].fichier, APPLI)       # 0.16 : tuiles qui ont des fiches « Connexion »
    tuiles = {t.cle: t for t in ETAT["veille"].fichier.services}
    gestion, seule = ETAT.get("conteneurs"), _lecture_seule()
    en_veille = _en_veille()                                     # 0.22
    for fam in e.get("familles", []):
        for s in fam.get("services", []):
            s["fiches"] = s.get("cle") in maisons
            t = tuiles.get(s.get("cle"))                         # 0.17 : conteneur gérable depuis la fiche
            s["conteneur"] = gestion.vue(t, seule, en_veille=t.cle in en_veille) \
                if gestion is not None and t is not None else None
            s["reveil"] = _vue_reveil(t, seule) if t is not None else None            # 0.19
            b = tuiles.get(t.besoin) if t is not None and t.besoin else None          # 0.19 : « besoin: Pc de calcul »
            s["besoin"] = {"cle": b.cle, "nom": b.nom, "reveil": _vue_reveil(b, seule)} if b is not None else None
    m = ETAT.get("majs")                                         # 0.18 : applis de la stack à mettre à jour
    return {**e, "a_traiter": _a_traiter(), "version": __version__, "majs": m.vue(seule) if m is not None else None}


# ================================================================ réveil du PC (0.19 : webhook de Home Assistant)

def _eteint(t) -> bool:
    """La tuile ne répond pas d'après la veille (arrêt attendu, panne ou pas encore sondée)."""
    return ETAT["veille"].suivi.get("service:" + t.cle, {}).get("etat") != "ok"


def _vue_reveil(t, seule: bool) -> dict | None:
    r = ETAT.get("reveil_pc")
    return r.vue(t, _eteint(t), seule, ETAT["cfg"].reveil_manque()) if r is not None else None


@app.post("/api/reveil/{cle}")
async def reveiller(cle: str, request: Request):
    """Réveiller la machine d'une tuile marquée « reveil: true » : session, en-tête Origin de l'Anneau, jamais en lecture
    seule, seulement si elle est éteinte. Le corps est ignoré ; l'identifiant du webhook reste côté serveur."""
    r = ETAT["reveil_pc"]
    try:
        _verifier_origine(request)
    except HTTPException as exc:
        ETAT["conteneurs"].noter("reveil", cle, f"refusé : {exc.detail}")
        raise
    t = _tuile(cle)
    try:
        ordre = await r.ordonner(t, _eteint(t), _lecture_seule(), ETAT["cfg"].reveil_manque())
    except reveils.Refus as x:
        raise HTTPException(x.statut, x.phrase) from None
    ETAT["reveil"].set()                           # la ronde se presse pour suivre le réveil
    return JSONResponse({"ordre": ordre}, status_code=202)


# ================================================================ conteneurs (0.17 : Portainer)

def _lecture_seule() -> bool:
    return maison.lecture_seule("ANNEAU_LECTURE_SEULE")


def _origine_de_la_requete(request: Request) -> str:
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").split(",")[0].strip().lower()
    hote = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip().lower()
    return f"{proto}://{hote}" if hote else ""


def _origine(adresse: str) -> str:
    try:
        u = urlsplit(adresse)
        port = u.port
    except ValueError:
        return ""
    if not u.scheme or not u.hostname:
        return ""
    defaut = {"http": 80, "https": 443}.get(u.scheme.lower())
    return f"{u.scheme.lower()}://{u.hostname.lower()}" + (f":{port}" if port and port != defaut else "")


def origines_de_l_anneau(request: Request) -> set[str]:
    """Les adresses de l'Anneau : celle par laquelle la page est ouverte (hôte de la requête), et la locale et la privée
    d'une tuile « anneau » s'il y en a une. Le cookie de connexion est commun à toutes les applis de la maison : « même
    site » ne suffit pas, l'Origin doit être exactement l'une de celles-ci."""
    sortie = {_origine_de_la_requete(request)}
    for t in ETAT["veille"].fichier.services:
        if t.cle == APPLI:
            sortie |= {_origine(t.locale), _origine(t.privee)}
    return {o for o in sortie if o}


def _verifier_origine(request: Request) -> None:
    origine = (request.headers.get("origin") or "").strip().lower()
    if not origine or origine not in origines_de_l_anneau(request):
        raise HTTPException(403, "Ordre refusé : il ne vient pas d'une page de l'Anneau (en-tête Origin).")


def _tuile(cle: str):
    t = next((x for x in ETAT["veille"].fichier.services if x.cle == cle), None)
    if t is None:
        raise HTTPException(404, "Tuile inconnue.")
    return t


@app.post("/api/conteneurs/{cle}/{geste}")
async def ordre_conteneur(cle: str, geste: str, request: Request):
    """Allumer, éteindre, mettre à jour le conteneur d'une tuile. Le nom du conteneur vient de services.yaml (champ
    conteneur:), jamais de la requête : son corps est ignoré."""
    gestion = ETAT["conteneurs"]
    try:
        _verifier_origine(request)
    except HTTPException as exc:
        gestion.noter(geste, cle, f"refusé : {exc.detail}")
        raise
    if geste not in conteneurs.GESTES:
        raise HTTPException(404, "Geste inconnu.")
    t = _tuile(cle)
    if geste in ("eteindre", "allumer"):                       # 0.22 : un seul état éteint, celui de la veille
        _exiger_ecriture()
        r = await _changer_veille(t, geste == "eteindre")
        return JSONResponse({"ordre": r["ordre"], "veille": r["veille"]}, status_code=202)
    try:
        ordre = await gestion.ordonner(t, geste, _lecture_seule())
    except conteneurs.Refus as r:
        raise HTTPException(r.statut, r.phrase) from None
    return JSONResponse({"ordre": ordre}, status_code=202)


# ================================================================ applis à mettre à jour (0.18)

@app.post("/api/majs/verifier")
async def verifier_majs(request: Request):
    """« Vérifier maintenant » : relit la stack chez Portainer et les registres (lecture seule)."""
    _verifier_origine(request)
    m = ETAT["majs"]
    if not m.actif:
        raise HTTPException(404, "Portainer n'est pas réglé (ANNEAU_PORTAINER_URL, ANNEAU_PORTAINER_CLE).")
    async with _tour(TACHE_MAJS):
        await m.verifier(ETAT["veille"].fichier, ETAT["veille"].versions_des_tuiles())
    return m.vue(_lecture_seule())


@app.post("/api/majs/{ident}/mettre-a-jour")
async def mettre_a_jour_appli(ident: str, request: Request, corps: dict = Body(default={})):
    """Mettre à jour une appli de la liste. `ident` : une ligne de la liste lue par l'Anneau, jamais un nom libre ;
    `protege: true` = la double confirmation d'un conteneur protégé ou d'une base de données."""
    m = ETAT["majs"]
    try:
        _verifier_origine(request)
    except HTTPException as exc:
        m.noter(f"refusé : {exc.detail}", ident)
        raise
    try:
        ordre = await m.ordonner(ident, bool((corps or {}).get("protege") is True), _lecture_seule())
    except conteneurs.Refus as r:
        raise HTTPException(r.statut, r.phrase) from None
    return JSONResponse({"ordre": ordre}, status_code=202)


@app.get("/api/conteneurs/journal")
def journal_conteneurs():
    """Les derniers ordres donnés à Portainer (journal des écritures), du plus récent au plus ancien."""
    return {"lignes": ETAT["conteneurs"].journal(50)}


@app.get("/api/conteneurs/{cle}/stats")
async def stats_conteneur(cle: str):
    """Mémoire et processeur du conteneur (un GET stats?stream=false), lus à l'ouverture de la fiche."""
    try:
        return await ETAT["conteneurs"].stats(_tuile(cle))
    except conteneurs.Refus as r:
        raise HTTPException(r.statut, r.phrase) from None


# ================================================================ fiches « Connexion » des applis (0.16, contrat 3)

def _appli_maison(cle: str) -> tuple[str, str]:
    trouve = fiches.cibles(ETAT["veille"].fichier, APPLI).get(cle)
    if not trouve:
        raise HTTPException(404, "Cette tuile n'est pas une appli maison.")
    return trouve


@app.get("/api/applis/{cle}/services")
async def fiches_appli(cle: str):
    """Lues à l'ouverture de la fiche « État », jamais en boucle. La clé ANNEAU_CLE reste côté serveur."""
    nom, b = _appli_maison(cle)
    return await fiches.services(nom, b, maison.cle_anneau(), lire=ETAT.get("lire_fiches"))


@app.post("/api/applis/{cle}/services/{service}/verifier")
async def fiches_verifier(cle: str, service: str):
    nom, b = _appli_maison(cle)
    statut, corps = await fiches.verifier(nom, b, maison.cle_anneau(), service, lire=ETAT.get("lire_fiches"))
    if statut != 200:
        raise HTTPException(statut, corps.get("detail", "Erreur."))
    return corps


@app.post("/api/pannes/vue")
def panne_vue(corps: dict = Body(...)):
    """« Pris en compte » : la panne reste affichée tant qu'elle dure, mais on sait que tu l'as vue."""
    if not ETAT["veille"].prendre_en_compte(str(corps.get("cle", ""))):
        raise HTTPException(404, "Cette panne n'est plus en cours.")
    return {"ok": True}


@app.post("/api/sante/vu")
def sante_vue(corps: dict = Body(...)):
    """0.12 : « Vu » sur la fiche d'une tuile orange : elle redevient normale jusqu'au prochain changement."""
    if not ETAT["veille"].marquer_vu(str(corps.get("cle", ""))):
        raise HTTPException(404, "Cette tuile n'a rien à surveiller.")
    return {"ok": True}


# ================================================================ versions (0.13)

@app.get("/api/versions")
def lire_versions():
    """Réglages › Versions : les tuiles dont on connaît une version (en service ou publiée)."""
    tuiles = [t for t in ETAT["veille"].versions_des_tuiles() if t["version"] or t["depot"]]
    return {"tuiles": tuiles, "publiees_lues_le": versions.publiees(ETAT["cfg"].data)["essaye_le"]}


@app.get("/api/versions/nouveautes")
def nouveautes():
    """Ce qui a changé de version depuis le dernier « Vu » (une heure pour l'Anneau, pas par navigateur)."""
    vu = versions.vu_le(ETAT["cfg"].data)
    return {"vu_le": vu, "changements": ETAT["veille"].versions.depuis(vu)}


@app.post("/api/versions/vues")
def nouveautes_vues(corps: dict = Body(default={})):
    """« Vu » sur la fenêtre des nouveautés : jusqu'au plus récent changement montré (`jusqu_a`), sinon maintenant."""
    jusqu_a = corps.get("jusqu_a") if isinstance(corps, dict) else None
    return {"vu_le": versions.marquer_vu(ETAT["cfg"].data, jusqu_a if isinstance(jusqu_a, str) else None)}


async def _adopter(veille: Veille, fichier) -> dict:
    """Le fichier relu ou importé devient celui de la veille, qui refait un tour tout de suite."""
    veille.fichier = fichier
    veille.refus.clear()                       # les services sont relus : ce qu'ils disent du cadre aussi
    veille._tours = 0
    await veille.tour()
    return {"ok": True, "services": len(fichier.services), "erreurs": list(fichier.erreurs)}


@app.post("/api/recharger")
async def recharger():
    """Relit le fichier des services (après une modification à la main), puis refait un tour."""
    try:
        fichier = lire(ETAT["cfg"].data / "services.yaml")
    except FichierInvalide as exc:
        raise HTTPException(422, str(exc)) from exc
    return await _adopter(ETAT["veille"], fichier)


@app.post("/api/services/importer")
async def importer_services(corps: dict = Body(...)):
    """0.6 : le fichier choisi dans Réglages remplace services.yaml (l'ancien est gardé en secours).
    Refusé en entier s'il est illisible ou ne porte aucun service valable."""
    texte = corps.get("texte")
    if not isinstance(texte, str) or not texte.strip():
        raise HTTPException(422, "Aucun fichier reçu.")
    data = ETAT["cfg"].data
    avant = (data / "services.yaml").is_file()
    try:
        fichier = await asyncio.to_thread(importer, data, texte)
    except FichierInvalide as exc:
        raise HTTPException(422, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, str(exc)) from exc
    log.info("Fichier des services importé depuis Réglages : %d service(s)", len(fichier.services))
    return {**await _adopter(ETAT["veille"], fichier), "precedent": PRECEDENT if avant else ""}


# ================================================================ Home Assistant

@app.post("/api/ha/etat")
def recevoir_ha(request: Request, corps: dict = Body(...)):
    """Home Assistant envoie l'état des machines, avec le secret partagé. La réponse lui dit quoi notifier.
    L'Anneau ne détient aucun jeton de Home Assistant : il reçoit, il ne va rien chercher."""
    secret = ETAT["cfg"].secret_ha
    if not secret:
        raise HTTPException(503, "Aucun secret n'est défini pour Home Assistant (ANNEAU_SECRET_HA).")
    if not hmac.compare_digest(request.headers.get("x-anneau-secret", "").encode(), secret.encode()):
        raise HTTPException(401, "Secret incorrect.")
    return ETAT["veille"].recevoir(corps)


# ================================================================ annuaire (0.7 : module commun maison)

@app.get("/externe/services")
def annuaire(request: Request):
    """Adresses des services (nom, famille, adresse locale, adresse privée) pour les autres applis maison,
    qui y lisent les liens à montrer au lieu d'une IP et d'un port codés chez elles. Jeton commun MAISON_JETON ;
    vide : adresse fermée. Rien d'autre (ni sonde, ni état, ni secret)."""
    _jeton_commun(request)
    return {"contrat": maison.CONTRAT, "generation_commune": ETAT["sessions"].generation, "services": [
        {"nom": s.nom, "cle": s.cle, "famille": s.famille, "locale": s.locale, "privee": s.privee}
        for s in ETAT["veille"].fichier.services]}


# ================================================================ sauvegarde des réglages (0.8 : contrat de sauvegarde 1)

def _jeton_commun(request: Request) -> None:
    """Portes des applis maison : jeton commun seulement ; vide = porte fermée (404)."""
    acceptes = maison.jetons()
    if not acceptes:
        raise HTTPException(404, "Adresse fermée : MAISON_JETON est vide.")
    if not maison.jeton_valide(maison.jeton_propose(request.headers), acceptes):
        raise HTTPException(401, "Jeton refusé.")


def _propre() -> dict:
    return maison.sauvegarde(APPLI, __version__, ETAT["reglages"].tout(), exclus=sauvegardes.EXCLUS)


def _noms_eteints() -> set[str]:
    """0.17 : noms des tuiles dont le conteneur est arrêté chez Portainer (pas demandées à la collecte)."""
    c = ETAT.get("conteneurs")
    cles = (c.eteints() if c is not None else set()) | (_en_veille() - set(_revenues()))   # 0.22 : en veille aussi
    return {s.nom for s in ETAT["veille"].fichier.services if s.cle in cles}


async def _collecter(automatique: bool = False) -> dict:
    async with ETAT["verrou_collecte"]:
        return await sauvegardes.collecter(ETAT["cfg"].data, ETAT["veille"].fichier, _propre(),
                                           lire=ETAT.get("lire_sauvegarde"), automatique=automatique,
                                           eteintes=_noms_eteints())


@app.get("/api/reglages")
def lire_reglages():
    return {"reglages": ETAT["reglages"].tout()}


@app.put("/api/reglages")
def changer_reglages(corps: dict = Body(...)):
    try:
        propres = sauvegardes.valider(corps.get("reglages", corps) if isinstance(corps, dict) else corps)
        return {"reglages": ETAT["reglages"].changer(propres)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/cle-publique")
def lire_cle():
    """La clé publique age où Atlas chiffre l'export des variables (ce n'est pas un secret)."""
    return {"cle_publique": ETAT["reglages"].get("cle_publique")}


@app.put("/api/cle-publique")
def changer_cle(request: Request, corps: dict = Body(...)):
    """0.19 : https exigé (_exiger_https). 0.11.2 (audit M7) : remplacer ou retirer une clé déjà posée exige la clé actuelle (« actuelle ») ; sinon les
    exports déjà rangés ne seraient plus lisibles qu'avec une clé que personne n'a vérifiée."""
    _exiger_https(request)
    try:
        cle_age = sauvegardes.valider_cle(str(corps.get("cle_publique", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    actuelle = ETAT["reglages"].get("cle_publique")
    if actuelle and cle_age != actuelle and str(corps.get("actuelle", "")).strip() != actuelle:
        raise HTTPException(409, "Une clé publique est déjà posée : pour la remplacer, confirme la clé actuelle.")
    return {"cle_publique": ETAT["reglages"].changer({"cle_publique": cle_age})["cle_publique"]}


@app.get("/externe/sauvegarde")
def ma_sauvegarde(request: Request):
    """La sauvegarde de l'Anneau lui-même (la clé publique en est exclue)."""
    _jeton_commun(request)
    return _propre()


@app.get("/externe/sauvegardes/{appli}")
def sauvegardes_d_une_appli(appli: str, request: Request, le: str = ""):
    """Pour « Restaurer » dans chaque appli : ses dates, ou ses réglages d'un jour."""
    _jeton_commun(request)
    if not sauvegardes.RE_APPLI.match(appli):
        raise HTTPException(400, "Nom d'appli invalide.")
    data = ETAT["cfg"].data
    if not le:
        return {"dates": sauvegardes.dates_de(data, appli)}
    if not sauvegardes.identifiant_valide(le):
        raise HTTPException(400, "Sauvegarde invalide (AAAA-MM-JJ ou AAAA-MM-JJ-HHMMSS-manuelle).")
    r = sauvegardes.reglages_de(data, appli, le)
    if r is None:
        raise HTTPException(404, f"Aucune sauvegarde de {appli} le {le}.")
    return r


@app.get("/api/sauvegardes")
def liste_sauvegardes():
    data = ETAT["cfg"].data
    e = sauvegardes.lire_etat(data)
    return {"heure": ETAT["reglages"].get("heure_sauvegarde"), "derniere": e.get("derniere"),
            "derniere_reussie": e.get("derniere_reussie", ""), "historique": (e.get("historique") or [])[:10],
            "fichiers": sauvegardes.liste(data), "a_traiter": _a_traiter()}


@app.post("/api/sauvegardes")
async def sauvegarder_maintenant():
    return {"derniere": await _collecter()}


@app.get("/api/sauvegardes/{le}")
def une_sauvegarde(le: str, telecharger: bool = False):
    if not sauvegardes.identifiant_valide(le):
        raise HTTPException(400, "Sauvegarde invalide (AAAA-MM-JJ ou AAAA-MM-JJ-HHMMSS-manuelle).")
    d = sauvegardes.fichier_du_jour(ETAT["cfg"].data, le)
    if d is None:
        raise HTTPException(404, f"Aucune sauvegarde le {le}.")
    entetes = {"Content-Disposition": f'attachment; filename="sauvegarde-{le}.json"'} if telecharger else {}
    return JSONResponse(d, headers=entetes)


@app.get("/api/restaurer")
def restaurer_voir(le: str = ""):
    """Les réglages de l'Anneau lui-même, lus dans ses propres fichiers (pas de réseau)."""
    data = ETAT["cfg"].data
    if not le:
        dates = sauvegardes.dates_de(data, APPLI)
        if not dates:
            raise HTTPException(404, "Aucune sauvegarde à restaurer pour l'instant.")
        return {"dates": dates}
    if not sauvegardes.identifiant_valide(le):
        raise HTTPException(400, "Sauvegarde invalide (AAAA-MM-JJ ou AAAA-MM-JJ-HHMMSS-manuelle).")
    r = sauvegardes.reglages_de(data, APPLI, le)
    if r is None:
        raise HTTPException(404, f"Aucune sauvegarde de l'Anneau le {le}.")
    return {"le": le, "version": r["version"],
            "differences": maison.differences(ETAT["reglages"].tout(), r["reglages"], sauvegardes.EXCLUS)}


@app.post("/api/restaurer")
def restaurer(corps: dict = Body(...)):
    le = str(corps.get("le", ""))
    vu = restaurer_voir(le) if le else None
    if not vu:
        raise HTTPException(400, "Date à restaurer manquante.")
    valeurs = {d["cle"]: d["sauve"] for d in vu["differences"]}
    try:
        reglages = ETAT["reglages"].changer(sauvegardes.valider(valeurs))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    log.info("Réglages de l'Anneau restaurés depuis la sauvegarde du %s : %s", le, ", ".join(valeurs) or "rien à changer")
    return {"reglages": reglages, "restaures": sorted(valeurs)}


@app.get("/api/variables-chiffrees")
def liste_variables():
    return {"exports": sauvegardes.liste_variables(ETAT["cfg"].data)}


@app.post("/api/variables-chiffrees")
async def ranger_variables(request: Request):
    """L'export des variables, chiffré dans le navigateur avec la clé publique. Jamais de texte clair. 0.19 : https exigé."""
    _exiger_https(request)
    try:
        if int(request.headers.get("content-length") or 0) > sauvegardes.TAILLE_VARIABLES:
            raise HTTPException(413, "Fichier trop gros (1 Mo au plus).")
    except ValueError:
        raise HTTPException(400, "Longueur illisible.") from None
    brut = b""
    async for morceau in request.stream():
        brut += morceau
        if len(brut) > sauvegardes.TAILLE_VARIABLES:
            raise HTTPException(413, "Fichier trop gros (1 Mo au plus).")
    try:
        texte = brut.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "Seul un fichier chiffré par age, en texte, est accepté.") from None
    try:
        return sauvegardes.ranger_variables(ETAT["cfg"].data, texte)
    except sauvegardes.Refus as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"Le dossier de l'Anneau n'accepte pas l'écriture : {exc}") from exc


@app.get("/api/variables-chiffrees/{nom}")
def telecharger_variables(nom: str):
    f = sauvegardes.chemin_variables(ETAT["cfg"].data, nom)
    if f is None:
        raise HTTPException(404, "Export introuvable.")
    return FileResponse(f, media_type="application/octet-stream", filename=nom)


# ================================================================ la stack et le fichier des services (0.10)

@app.get("/api/stack")
def lire_stack(request: Request):
    """homelab.yml déposé dans l'Anneau : ses services et ses variables (noms, défaut, services qui les lisent).
    0.10.1 : avec l'adresse https de l'Anneau tirée des tuiles, pour le lien de l'avertissement « ouvert en http »."""
    return {**stack.etat(ETAT["cfg"].data), "coffre": ETAT["reglages"].get("coffre_obsidian"),
            "adresse_https": adresse_https(ETAT["veille"].fichier, _port(request))}


@app.post("/api/stack")
async def importer_stack(corps: dict = Body(...)):
    """Importer homelab.yml (fichier choisi dans la page Variables). Refusé en entier s'il porte une valeur en clair."""
    try:
        e = await asyncio.to_thread(stack.importer, ETAT["cfg"].data, corps.get("texte"))
    except stack.StackInvalide as exc:
        raise HTTPException(422, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"Le dossier de l'Anneau n'accepte pas l'écriture : {exc}") from exc
    log.info("homelab.yml importé : %d service(s), %d variable(s)", len(e["services"]), len(e["variables"]))
    return {**e, "coffre": ETAT["reglages"].get("coffre_obsidian")}


@app.get("/api/stack/fichier")
def telecharger_stack():
    f = stack.chemin(ETAT["cfg"].data)
    if not f.is_file():
        raise HTTPException(404, "homelab.yml n'a pas encore été importé dans l'Anneau.")
    return FileResponse(f, media_type="text/yaml; charset=utf-8", filename=stack.NOM)


@app.get("/api/services/fichier")
def telecharger_services():
    f = ETAT["cfg"].data / "services.yaml"
    if not f.is_file():
        raise HTTPException(404, "Aucun fichier des services : l'Anneau montre l'exemple inventé.")
    return FileResponse(f, media_type="text/yaml; charset=utf-8", filename="services.yaml")


# ================================================================ la carte de la maison (0.11 : Atlas basculé dans l'Anneau)

def _tuiles() -> list[dict]:
    return [{"nom": s["nom"], "cle": s["cle"], "etat": s["etat"], "famille": f["nom"]}
            for f in ETAT["veille"].etat()["familles"] for s in f["services"]]


def _vue_carte() -> dict:
    cfg = ETAT["cfg"]
    c = carte.lire(cfg.data)
    return {"etat": {**carte.etat(cfg.data), "regle": bool(cfg.atlas_depot and cfg.github_jeton)},
            "carte": carte.avec_voyants(c, _tuiles()) if c else None}


@app.get("/api/carte")
def lire_carte():
    """La carte (machines, quartiers, services, flux) avec le voyant de chaque tuile ; derrière la session."""
    return _vue_carte()


@app.post("/api/carte/relire")
async def relire_carte():
    """Relit la carte tout de suite (bouton de Réglages)."""
    cfg = ETAT["cfg"]
    await asyncio.to_thread(carte.telecharger, cfg.data, cfg.atlas_depot, cfg.github_jeton)
    return _vue_carte()


# ================================================================ interface

@app.get("/{chemin:path}")
def interface(chemin: str):
    if chemin.startswith("api/"):
        raise HTTPException(404, "Adresse inconnue.")
    statique = ETAT["cfg"].static
    fichier = (statique / chemin).resolve() if chemin else None
    if fichier and fichier.is_file() and statique.resolve() in fichier.parents:
        return FileResponse(fichier)
    index = statique / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"detail": "Interface non compilée."}, status_code=404)
