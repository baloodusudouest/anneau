"""Fiches « Connexion » des applis maison, montrées dans la fiche « État » de l'Anneau (0.16, contrat 3, socle 0.10.0).

L'Anneau lit, à l'ouverture de la fiche seulement (jamais en boucle), GET <appli>/api/maison/services avec sa clé de
lecture ANNEAU_CLE, et relaie « Vérifier » (POST <appli>/api/maison/services/<id>/verifier). Les deux appels partent
du serveur de l'Anneau : la clé ne va jamais au navigateur. Aucun geste qui écrit (Synchroniser, Livrer…) : ils
restent dans l'appli, l'Anneau n'écrit chez personne.

Les applis visées sont les tuiles d'applis maison (même règle que la collecte des sauvegardes : « sauvegarde: true »,
ou une sonde en /health). La réponse est relue champ par champ et le détail nettoyé une seconde fois.
Bibliothèque standard et httpx seulement.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

import httpx

from . import maison
from .sauvegardes import base

DELAI = 4.0                     # secondes : au-delà, « n'a pas répondu »
CHEMIN = "/api/maison/services"
CHAMPS_TEXTE = ("id", "nom", "genre", "cible", "etat", "lit", "ecrit", "reglage", "detail", "verifie_le",
                "derniere_ecriture")

Lecteur = Callable[[str, str, str], Awaitable[tuple[int, object]]]


async def lire_http(methode: str, url: str, cle: str) -> tuple[int, object]:
    """GET ou POST avec ANNEAU_CLE ; rend (statut, JSON ou None). Délai DELAI, sans suivre de redirection."""
    async with httpx.AsyncClient(timeout=DELAI, verify=False, follow_redirects=False) as c:
        r = await c.request(methode, url, headers={"Authorization": f"Bearer {cle}", "User-Agent": "anneau",
                                                    "Accept": "application/json"})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


def cibles(fichier, propre: str = "anneau") -> dict[str, tuple[str, str]]:
    """{clé de tuile: (nom, adresse de base)} des tuiles qui sont des applis maison (l'Anneau lui-même exclu)."""
    sortie: dict[str, tuple[str, str]] = {}
    choisies = any(getattr(s, "sauvegarde", None) is True for s in fichier.services)
    for s in fichier.services:
        drapeau = getattr(s, "sauvegarde", None)
        if drapeau is False or (choisies and drapeau is not True):
            continue
        b = base(s.sonde)
        if b and propre not in s.cle:
            sortie[s.cle] = (s.nom, b)
    return sortie


def _fiche(brute) -> dict | None:
    """Une fiche relue : champs connus seulement, textes bornés, détail nettoyé, au plus un geste (nom affiché seul)."""
    if not isinstance(brute, dict) or not isinstance(brute.get("id"), str) or not isinstance(brute.get("nom"), str):
        return None
    f = {k: (str(brute[k])[:600] if isinstance(brute.get(k), str) else None) for k in CHAMPS_TEXTE}
    if f["etat"] not in maison.ETATS_SERVICE:
        f["etat"] = "relie"
    f["detail"] = maison.nettoyer_detail(f["detail"])
    gestes = brute.get("gestes") if isinstance(brute.get("gestes"), list) else []
    f["gestes"] = [{"id": str(g.get("id", ""))[:40], "nom": str(g.get("nom", ""))[:40]}
                   for g in gestes[:1] if isinstance(g, dict)]
    f["guide"] = maison.nettoyer_guide(brute.get("guide"))       # socle 0.11.0 : guide facultatif, relu ici aussi
    return f


def _phrase_statut(nom: str, statut: int) -> str:
    if statut == 401:
        return f"{nom} refuse la clé de l'Anneau : ANNEAU_CLE n'est pas la même des deux côtés."
    if statut == 404:
        return f"{nom} n'a pas encore les fiches communes (version d'avant le contrat 3)."
    return f"{nom} a répondu {statut}."


async def services(nom: str, b: str, cle: str, lire: Lecteur | None = None) -> dict:
    """Fiches d'une appli : {"etat": ok | ancien | injoignable | refus | ferme, "phrase", "simule", "services"}."""
    if not cle:
        return {"etat": "ferme", "phrase": "ANNEAU_CLE est vide dans la stack : l'Anneau ne lit pas les fiches.",
                "simule": False, "services": []}
    try:
        statut, corps = await asyncio.wait_for((lire or lire_http)("GET", b + CHEMIN, cle), timeout=DELAI + 1)
    except asyncio.TimeoutError:
        return {"etat": "injoignable", "phrase": f"{nom} n'a pas répondu en {int(DELAI)} s.", "simule": False,
                "services": []}
    except Exception as exc:                                    # noqa: BLE001 — réseau, nom inconnu…
        return {"etat": "injoignable", "phrase": f"{nom} n'a pas répondu ({exc.__class__.__name__}).",
                "simule": False, "services": []}
    if statut != 200:
        return {"etat": "ancien" if statut == 404 else "refus", "phrase": _phrase_statut(nom, statut),
                "simule": False, "services": []}
    if not isinstance(corps, dict) or corps.get("contrat") != maison.CONTRAT or not isinstance(corps.get("services"), list):
        contrat = corps.get("contrat") if isinstance(corps, dict) else None
        return {"etat": "ancien", "phrase": f"{nom} parle le contrat {contrat!r} des fiches, pas le {maison.CONTRAT}.",
                "simule": False, "services": []}
    fiches = [f for f in (_fiche(x) for x in corps["services"][:40]) if f]
    return {"etat": "ok", "phrase": "", "simule": corps.get("simule") is True, "services": fiches}


async def verifier(nom: str, b: str, cle: str, service: str, lire: Lecteur | None = None) -> tuple[int, dict]:
    """Relaie « Vérifier » ; rend (statut HTTP pour l'interface, fiche ou {"detail"})."""
    if not cle:
        return 409, {"detail": "ANNEAU_CLE est vide dans la stack : l'Anneau ne lit pas les fiches."}
    if not maison._ID_SERVICE.match(service or ""):
        return 404, {"detail": "Service inconnu."}
    try:
        statut, corps = await asyncio.wait_for(
            (lire or lire_http)("POST", f"{b}{CHEMIN}/{service}/verifier", cle), timeout=maison.DUREE_ESSAI_S + 2)
    except asyncio.TimeoutError:
        return 504, {"detail": f"{nom} n'a pas répondu à temps."}
    except Exception as exc:                                    # noqa: BLE001
        return 502, {"detail": f"{nom} n'a pas répondu ({exc.__class__.__name__})."}
    if statut != 200:
        return (404 if statut == 404 else 502), {"detail": _phrase_statut(nom, statut) if statut != 404 else "Service inconnu."}
    f = _fiche(corps)
    return (200, f) if f else (502, {"detail": f"Réponse de {nom} illisible."})
