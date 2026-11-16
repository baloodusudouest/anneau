"""L'Anneau : une seule porte pour les machines, les services et les applis de la maison.

Temps 1 : la vue. L'Anneau lit (une demande HTTP par service, chaque minute) et reçoit
(Home Assistant lui envoie l'état des machines). Il n'écrit nulle part hors de son dossier
(où, depuis la 0.6, il peut écrire services.yaml quand on l'importe depuis Réglages)
et ne détient aucun jeton d'un autre service — sauf, depuis la 0.5, un jeton GitHub en lecture seule pour relire Atlas.

Routes : /health (publique), /api/session, /api/connexion, /api/deconnexion, /api/etat,
/api/pannes/vue, /api/recharger, /api/services/importer (0.6), /api/ha/etat (ouverte par le secret de Home Assistant), /api/documents,
/documents/atlas.html (0.5, derrière la session), /externe/services (0.7, jeton commun),
0.8 — sauvegarde des réglages : /api/reglages, /api/restaurer, /api/sauvegardes, /api/cle-publique,
/api/variables-chiffrees (session) ; /externe/sauvegarde, /externe/sauvegardes/{appli} (jeton commun) ; puis l'interface.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
import time

from . import documents, maison, sauvegardes

from . import __version__
from .auth import COMMUN, DUREE, Sessions
from .config import APPLI, Config, charger
from .services import PRECEDENT, FichierInvalide, importer, lire
from .veille import Veille

log = logging.getLogger("anneau")
ETAT: dict = {}
PUBLIQUES = ("/api/connexion", "/api/session", "/api/ha/etat")   # la dernière a sa propre garde : le secret


def _fichier_generation(cfg: Config) -> Path:
    return cfg.data / "session_generation"


def _lire_generation(cfg: Config) -> int:
    try:
        return int(_fichier_generation(cfg).read_text().strip())
    except (OSError, ValueError):
        return 0


async def _ronde(veille: Veille, periode: int) -> None:
    while True:
        try:
            await veille.tour()
        except Exception:                          # une ronde ratée ne doit jamais arrêter la veille
            log.exception("Ronde de sonde interrompue")
        await asyncio.sleep(periode)


async def _relire_atlas(cfg: Config) -> None:
    """0.5 : Atlas est relu au démarrage puis une fois par jour (le bouton de Réglages le relit tout de suite)."""
    while True:
        try:
            if documents.a_relire(cfg.data, time.time()):
                await asyncio.to_thread(documents.telecharger_atlas, cfg.data, cfg.atlas_depot, cfg.github_jeton)
        except Exception:
            log.exception("Relecture d'Atlas interrompue")
        await asyncio.sleep(3600)


async def _sauvegarde_quotidienne(cfg: Config) -> None:
    """0.8 : chaque jour à l'heure de Réglages › Sauvegarde (rattrapée au démarrage si elle est passée)."""
    while True:
        try:
            if sauvegardes.a_lancer(cfg.data, ETAT["reglages"].get("heure_sauvegarde"), datetime.now().astimezone()):
                await _collecter(automatique=True)
        except Exception:
            log.exception("Collecte des sauvegardes interrompue")
        await asyncio.sleep(30)


@asynccontextmanager
async def cycle(app: FastAPI):
    cfg = ETAT.get("cfg") or charger()
    cfg.data.mkdir(parents=True, exist_ok=True)
    veille = ETAT.get("veille") or Veille(cfg.data, lire(cfg.data / "services.yaml"), ha_attendu=bool(cfg.secret_ha))
    reglages = ETAT.get("reglages") or maison.Reglages(cfg.data / "reglages.json", sauvegardes.DEFAUTS, {})
    sauvegardes.demarrer(cfg.data)
    ETAT.update(cfg=cfg, sessions=Sessions(APPLI, cfg.password, _lire_generation(cfg)), veille=veille,
                reglages=reglages, verrou_collecte=asyncio.Lock())
    ronde = asyncio.create_task(_ronde(veille, cfg.periode)) if cfg.veille else None
    atlas = asyncio.create_task(_relire_atlas(cfg)) if cfg.veille and cfg.atlas_depot else None
    collecte = asyncio.create_task(_sauvegarde_quotidienne(cfg)) if cfg.veille and cfg.sauvegarde_auto else None
    yield
    for t in (ronde, atlas, collecte):
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


# ================================================================ public

@app.get("/health")
def sante():
    return {"ok": True, "version": __version__}


# ================================================================ connexion

@app.get("/api/session")
def session(request: Request):
    s = ETAT["sessions"]
    return {"connecte": s.connecte(request.cookies), "version": __version__}


@app.post("/api/connexion")
async def connexion(corps: dict = Body(...)):
    s = ETAT["sessions"]
    if ETAT["cfg"].attente_connexion:
        await asyncio.sleep(s.attente())
    if not s.verifier_mot_de_passe(str(corps.get("mot_de_passe", ""))):
        raise HTTPException(401, "Mot de passe incorrect.")
    r = JSONResponse({"ok": True})
    r.set_cookie(s.cookie, s.creer(), max_age=DUREE, httponly=True, samesite="strict")
    # La connexion commune : les applis de la maison servies par la même adresse s'ouvrent sans rien demander.
    r.set_cookie(COMMUN, s.creer_commun(), max_age=DUREE, httponly=True, samesite="strict")
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


def _https(request: Request) -> bool:
    return (request.headers.get("x-forwarded-proto") or request.url.scheme) == "https"


@app.get("/api/etat")
def etat(request: Request):
    return {**ETAT["veille"].etat(prive=_prive(request), https=_https(request), hote=_hote(request)),
            "a_traiter": sauvegardes.a_traiter(ETAT["cfg"].data), "version": __version__}


@app.post("/api/pannes/vue")
def panne_vue(corps: dict = Body(...)):
    """« Pris en compte » : la panne reste affichée tant qu'elle dure, mais on sait que tu l'as vue."""
    if not ETAT["veille"].prendre_en_compte(str(corps.get("cle", ""))):
        raise HTTPException(404, "Cette panne n'est plus en cours.")
    return {"ok": True}


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
    return {"contrat": maison.CONTRAT, "services": [
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


async def _collecter(automatique: bool = False) -> dict:
    async with ETAT["verrou_collecte"]:
        return await sauvegardes.collecter(ETAT["cfg"].data, ETAT["veille"].fichier, _propre(),
                                           lire=ETAT.get("lire_sauvegarde"), automatique=automatique)


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
def changer_cle(corps: dict = Body(...)):
    try:
        cle_age = sauvegardes.valider_cle(str(corps.get("cle_publique", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
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
            "fichiers": sauvegardes.liste(data), "a_traiter": sauvegardes.a_traiter(data)}


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
    """L'export des variables, chiffré par Atlas dans le navigateur avec la clé publique. Jamais de texte clair."""
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


# ================================================================ documents (0.5 : Atlas)

@app.get("/api/documents")
def lire_documents():
    cfg = ETAT["cfg"]
    return {"atlas": {**documents.etat(cfg.data), "regle": bool(cfg.atlas_depot and cfg.github_jeton)}}


@app.post("/api/documents/atlas")
async def relire_atlas():
    """Relit Atlas tout de suite (bouton de Réglages)."""
    cfg = ETAT["cfg"]
    return {"atlas": {**await asyncio.to_thread(documents.telecharger_atlas, cfg.data, cfg.atlas_depot, cfg.github_jeton),
                      "regle": bool(cfg.atlas_depot and cfg.github_jeton)}}


@app.get("/documents/atlas.html")
def atlas(request: Request):
    """La carte de la maison : privée, donc seulement avec une session de l'Anneau (ou le cookie commun)."""
    if not ETAT["sessions"].connecte(request.cookies):
        return RedirectResponse("/", status_code=303)
    f = documents.dossier(ETAT["cfg"].data) / documents.FICHIER
    if not f.is_file():
        return JSONResponse({"detail": "Atlas n'est pas encore là : voir Réglages › Atlas."}, status_code=404)
    return FileResponse(f, media_type="text/html", headers={"Cache-Control": "no-cache"})


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
