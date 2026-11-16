"""Sauvegarde des réglages des applis maison (0.8 ; contrat de sauvegarde 1 du module commun).

Chaque jour à l'heure réglée (Réglages › Sauvegarde, défaut 03:30), et sur le bouton « Sauvegarder maintenant »,
l'Anneau demande à chaque appli maison de services.yaml ses réglages d'usage :

    GET <adresse de base>/externe/sauvegarde     Authorization: Bearer <MAISON_JETON>     10 s au plus

L'adresse de base est la sonde de la tuile sans son « /health » : seules les tuiles dont la sonde finit par
« /health » sont des applis maison (une tuile peut s'en retirer par « sauvegarde: false »). Une appli qui ne répond
pas, ou dont la réponse n'a pas « contrat == 1 », ou qui porte une clé qui ressemble à un secret, est notée ratée ;
rien n'est écrit pour elle et les autres continuent.

Fichiers, dans <données>/sauvegardes/ :
  AAAA-MM-JJ.json            {"contrat": 1, "le", "applis": {<id>: <réponse>}, "ratees": {<tuile>: <raison>}}
                             (un par jour, remplacé le même jour ; 30 derniers jours + le premier de chaque mois)
  etat.json                  dernière collecte, dernière réussie, journal court des collectes
  variables/AAAA-MM-JJ-HHMMSS.age   exports chiffrés des variables, fabriqués par Atlas dans le navigateur
                             (l'Anneau ne voit jamais le texte clair ; 30 derniers gardés)

Ces fichiers partent avec le dossier de l'Anneau dans Hyper Backup. Bibliothèque standard et httpx seulement.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from . import maison

log = logging.getLogger("anneau.sauvegardes")

DOSSIER = "sauvegardes"
GARDES_JOURS = 30            # derniers fichiers quotidiens gardés (plus le premier de chaque mois)
GARDES_VARIABLES = 30        # derniers exports chiffrés gardés
DELAI = 10                   # secondes au plus par appli
SILENCE = 36 * 3600          # sans collecte réussie depuis 36 h : « Sauvegarde ratée »
HISTORIQUE = 60              # lignes du journal des collectes gardées
TAILLE_VARIABLES = 1024 * 1024
DEBUT_AGE = "-----BEGIN AGE ENCRYPTED FILE-----"
FIN_AGE = "-----END AGE ENCRYPTED FILE-----"

# Réglages d'usage de l'Anneau (maison.Reglages dans <données>/reglages.json). Aucune ancienne variable à reprendre.
DEFAUTS = {"heure_sauvegarde": "03:30", "cle_publique": ""}
EXCLUS = ("cle_publique",)   # jamais dans la sauvegarde de l'Anneau (est_secret l'écarte déjà : « cle »)

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_APPLI = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
RE_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
RE_CLE_AGE = re.compile(r"^age1[02-9ac-hj-np-z]{58}$")       # clé publique age : bech32, 62 caractères
RE_EXPORT = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}(-\d{1,3})?\.age$")


class Refus(ValueError):
    """Une valeur reçue n'est pas acceptable ; le message se montre tel quel."""


# ---------------------------------------------------------------- réglages de l'Anneau

def valider(valeurs: dict) -> dict:
    """Vérifie les réglages reçus de l'écran (PUT /api/reglages) avant de les ranger."""
    if not isinstance(valeurs, dict):
        raise Refus("Réglages attendus sous forme d'un objet.")
    propres = {}
    for k, v in valeurs.items():
        if k not in DEFAUTS:
            continue
        if not isinstance(v, str):
            raise Refus(f"{k} : texte attendu.")
        v = v.strip()
        if k == "heure_sauvegarde" and not RE_HEURE.match(v):
            raise Refus("heure_sauvegarde : une heure « HH:MM » est attendue (par exemple 03:30).")
        if k == "cle_publique":
            v = valider_cle(v)
        propres[k] = v
    return propres


def valider_cle(v: str) -> str:
    v = (v or "").strip()
    if v.upper().startswith("AGE-SECRET-KEY-"):
        raise Refus("C'est une clé privée : elle ne doit jamais être donnée à l'Anneau. Seule la clé publique « age1… » se pose ici.")
    if v and not RE_CLE_AGE.match(v):
        raise Refus("cle_publique : une clé publique age est attendue (« age1… », 62 caractères).")
    return v


# ---------------------------------------------------------------- chemins

def dossier(data: Path) -> Path:
    return data / DOSSIER


def dossier_variables(data: Path) -> Path:
    return dossier(data) / "variables"


def date_valide(le: str) -> bool:
    if not isinstance(le, str) or not RE_DATE.match(le):
        return False
    try:
        date.fromisoformat(le)
        return True
    except ValueError:
        return False


def _ecrire_atomique(chemin: Path, contenu: str | bytes) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    tmp = chemin.with_name(chemin.name + ".tmp")
    try:
        if isinstance(contenu, bytes):
            tmp.write_bytes(contenu)
        else:
            tmp.write_text(contenu, encoding="utf-8")
        os.replace(tmp, chemin)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------- état et journal des collectes

_EN_MEMOIRE: dict[str, dict] = {}     # état qui n'a pas pu être écrit (disque plein, dossier fermé) : gardé en mémoire


def lire_etat(data: Path) -> dict:
    if str(data) in _EN_MEMOIRE:
        return json.loads(json.dumps(_EN_MEMOIRE[str(data)]))
    try:
        e = json.loads((dossier(data) / "etat.json").read_text(encoding="utf-8"))
        if isinstance(e, dict):
            return e
    except (OSError, ValueError):
        pass
    return {}


def _garder_etat(data: Path, e: dict) -> None:
    try:
        _ecrire_atomique(dossier(data) / "etat.json", json.dumps(e, ensure_ascii=False, indent=1))
        _EN_MEMOIRE.pop(str(data), None)
    except OSError as exc:
        _EN_MEMOIRE[str(data)] = e        # la tuile « Sauvegarde ratée » s'affiche quand même jusqu'au redémarrage
        log.warning("État des sauvegardes non enregistré : %s", exc)


def demarrer(data: Path, maintenant: datetime | None = None) -> dict:
    """Au démarrage : note depuis quand l'Anneau attend une première collecte (pour la règle des 36 h)."""
    e = lire_etat(data)
    if not e.get("depuis"):
        e["depuis"] = (maintenant or datetime.now().astimezone()).isoformat(timespec="seconds")
        _garder_etat(data, e)
    return e


def a_traiter(data: Path, maintenant: datetime | None = None) -> list[dict]:
    """La tuile « Sauvegarde ratée » de l'écran : dernière collecte avec des ratées, écriture ratée,
    ou aucune collecte réussie depuis 36 h. Rien n'est envoyé à Home Assistant."""
    t = maintenant or datetime.now().astimezone()
    e = lire_etat(data)
    d = e.get("derniere") or {}
    raisons = []
    if d.get("erreur"):
        raisons.append(f"le fichier n'a pas pu être écrit ({d['erreur']})")
    elif d.get("ratees"):
        noms = sorted(d["ratees"])
        raisons.append(f"{len(noms)} appli(s) non lue(s) : " + ", ".join(noms[:4]) + (" …" if len(noms) > 4 else ""))
    reference = e.get("derniere_reussie") or e.get("depuis")
    try:
        ecoule = (t - datetime.fromisoformat(reference)).total_seconds() if reference else 0
    except (TypeError, ValueError):
        ecoule = 0
    if ecoule > SILENCE:
        raisons.append("aucune collecte réussie depuis plus de 36 h")
    if not raisons:
        return []
    return [{"cle": "sauvegarde", "sorte": "sauvegarde", "phrase": "Sauvegarde ratée",
             "detail": " ; ".join(raisons), "le": d.get("le", "")}]


# ---------------------------------------------------------------- collecte

Lecteur = Callable[[str, str], Awaitable[tuple[int, object]]]


async def lire_http(url: str, jeton: str) -> tuple[int, object]:
    """GET avec le jeton commun ; rend (statut, JSON ou None)."""
    async with httpx.AsyncClient(timeout=DELAI, verify=False, follow_redirects=False) as c:
        r = await c.get(url, headers={"Authorization": f"Bearer {jeton}", "User-Agent": "anneau"})
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


def base(sonde: str) -> str:
    """Adresse de base d'une appli maison : sa sonde sans « /health » (vide si la sonde n'est pas un /health)."""
    try:
        m = urlsplit(sonde or "")
    except ValueError:
        return ""
    chemin = m.path.rstrip("/")
    if m.scheme not in ("http", "https") or not m.netloc or not chemin.endswith("/health"):
        return ""
    return urlunsplit((m.scheme, m.netloc, chemin[: -len("/health")], "", "")).rstrip("/")


def applis_maison(fichier) -> list[tuple[str, str]]:
    """(nom de tuile, adresse de base) des tuiles qui sont des applis maison."""
    sortie = []
    for s in fichier.services:
        if getattr(s, "sauvegarde", True) is False:
            continue
        b = base(s.sonde)
        if b:
            sortie.append((s.nom, b))
    return sortie


def _cles_secretes(v, chemin: str = "") -> list[str]:
    trouvees = []
    if isinstance(v, dict):
        for k, x in v.items():
            if maison.est_secret(str(k)):
                trouvees.append(chemin + str(k))
            trouvees += _cles_secretes(x, chemin + str(k) + ".")
    elif isinstance(v, list):
        for x in v:
            trouvees += _cles_secretes(x, chemin)
    return trouvees


def examiner_reponse(reponse) -> str:
    """Raison du refus d'une réponse ; vide si elle est acceptable."""
    if not isinstance(reponse, dict):
        return "réponse illisible"
    if reponse.get("contrat") != maison.CONTRAT_SAUVEGARDE:
        return f"contrat {reponse.get('contrat')!r} au lieu de {maison.CONTRAT_SAUVEGARDE}"
    if not isinstance(reponse.get("appli"), str) or not RE_APPLI.match(reponse["appli"]):
        return "nom d'appli manquant ou invalide"
    if not isinstance(reponse.get("reglages"), dict):
        return "réglages manquants"
    secretes = _cles_secretes(reponse)
    if secretes:
        return "clé qui ressemble à un secret : " + ", ".join(secretes[:3])
    return ""


async def _une(nom: str, b: str, jeton: str, lire: Lecteur) -> tuple[str, dict | None, str]:
    try:
        statut, corps = await asyncio.wait_for(lire(b + "/externe/sauvegarde", jeton), timeout=DELAI + 1)
    except asyncio.TimeoutError:
        return nom, None, "pas de réponse en 10 s"
    except Exception as exc:                                    # noqa: BLE001 — une appli ratée n'arrête pas les autres
        return nom, None, f"injoignable ({exc.__class__.__name__})"
    if statut != 200:
        return nom, None, {401: "jeton refusé (401)", 404: "pas de sauvegarde ou porte fermée (404)"}.get(statut, f"réponse {statut}")
    raison = examiner_reponse(corps)
    return (nom, None, raison) if raison else (nom, corps, "")


def retention(data: Path) -> list[str]:
    """Garde les 30 derniers fichiers quotidiens et le premier de chaque mois ; rend les dates retirées."""
    dates = sorted(f.stem for f in dossier(data).glob("*.json") if date_valide(f.stem))
    garder = set(dates[-GARDES_JOURS:])
    premiers: dict[str, str] = {}
    for d in dates:
        premiers.setdefault(d[:7], d)
    garder |= set(premiers.values())
    retirees = [d for d in dates if d not in garder]
    for d in retirees:
        (dossier(data) / f"{d}.json").unlink(missing_ok=True)
    return retirees


async def collecter(data: Path, fichier, propre: dict, jeton: str | None = None, lire: Lecteur | None = None,
                    maintenant: datetime | None = None, automatique: bool = False) -> dict:
    """Une collecte : toutes les applis maison en même temps, puis le fichier du jour (remplacé s'il existe).
    `propre` est la sauvegarde de l'Anneau lui-même (sans passer par le réseau)."""
    t = maintenant or datetime.now().astimezone()
    jeton = maison.jeton_a_envoyer() if jeton is None else jeton
    lire = lire or lire_http
    cibles = applis_maison(fichier)
    applis: dict[str, dict] = {}
    ratees: dict[str, str] = {}
    if propre:
        applis[propre["appli"]] = propre
    if not jeton:
        ratees = {nom: "MAISON_JETON est vide : rien n'a été demandé" for nom, _ in cibles}
    else:
        for nom, corps, raison in await asyncio.gather(*(_une(nom, b, jeton, lire) for nom, b in cibles)):
            if corps is None:
                ratees[nom] = raison
            elif corps["appli"] != (propre or {}).get("appli"):     # la tuile d'Atlas peut renvoyer l'Anneau lui-même
                applis[corps["appli"]] = corps
    jour = t.date().isoformat()
    contenu = {"contrat": maison.CONTRAT_SAUVEGARDE, "le": t.isoformat(timespec="seconds"),
               "applis": applis, "ratees": ratees}
    erreur = ""
    try:
        _ecrire_atomique(dossier(data) / f"{jour}.json", json.dumps(contenu, ensure_ascii=False, indent=1))
        retention(data)
    except OSError as exc:
        erreur = str(exc) or exc.__class__.__name__
    e = lire_etat(data)
    derniere = {"le": contenu["le"], "fichier": f"{jour}.json", "applis": sorted(applis), "ratees": ratees,
                "erreur": erreur, "automatique": automatique}
    e["derniere"] = derniere
    if automatique:
        e["auto_le"] = jour
    if not erreur:
        e["derniere_reussie"] = contenu["le"]
    ligne = (f"{contenu['le']} — " + ("collecte automatique" if automatique else "collecte à la demande")
             + f" : {len(applis)} appli(s) lue(s)" + (f", {len(ratees)} ratée(s) ({', '.join(sorted(ratees))})" if ratees else "")
             + (f", fichier non écrit : {erreur}" if erreur else ""))
    e["historique"] = ([ligne] + list(e.get("historique") or []))[:HISTORIQUE]
    _garder_etat(data, e)
    (log.warning if (ratees or erreur) else log.info)("Sauvegarde : %s", ligne)
    return derniere


def a_lancer(data: Path, heure: str, maintenant: datetime) -> bool:
    """Vrai si la collecte automatique du jour est due (heure passée, pas encore faite aujourd'hui)."""
    if not RE_HEURE.match(heure or ""):
        heure = DEFAUTS["heure_sauvegarde"]
    return maintenant.strftime("%H:%M") >= heure and lire_etat(data).get("auto_le") != maintenant.date().isoformat()


# ---------------------------------------------------------------- lecture des fichiers

def _lire_jour(data: Path, le: str) -> dict | None:
    if not date_valide(le):
        return None
    try:
        d = json.loads((dossier(data) / f"{le}.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def liste(data: Path) -> list[dict]:
    """Pour Atlas et Réglages : chaque fichier, la plus récente d'abord."""
    sortie = []
    for f in sorted(dossier(data).glob("*.json"), reverse=True):
        if not date_valide(f.stem):
            continue
        d = _lire_jour(data, f.stem) or {}
        sortie.append({"date": f.stem, "le": d.get("le", ""), "applis": sorted((d.get("applis") or {})),
                       "ratees": d.get("ratees") or {}, "taille": f.stat().st_size})
    return sortie


def fichier_du_jour(data: Path, le: str) -> dict | None:
    return _lire_jour(data, le)


def dates_de(data: Path, appli: str) -> list[str]:
    return [x["date"] for x in liste(data) if appli in x["applis"]]


def reglages_de(data: Path, appli: str, le: str) -> dict | None:
    d = _lire_jour(data, le)
    a = ((d or {}).get("applis") or {}).get(appli)
    if not isinstance(a, dict):
        return None
    return {"le": le, "version": a.get("version", ""), "reglages": a.get("reglages") or {}}


# ---------------------------------------------------------------- exports chiffrés des variables (Atlas)

def ranger_variables(data: Path, texte: str, maintenant: datetime | None = None) -> dict:
    """Range un export chiffré par age (armure texte). Tout autre contenu est refusé : jamais de texte clair."""
    if len(texte.encode("utf-8")) > TAILLE_VARIABLES:
        raise Refus("Fichier trop gros (1 Mo au plus).")
    if not texte.startswith(DEBUT_AGE) or not texte.rstrip().endswith(FIN_AGE):
        raise Refus("Seul un fichier chiffré par age (« -----BEGIN AGE ENCRYPTED FILE----- ») est accepté : rien n'a été rangé.")
    t = maintenant or datetime.now().astimezone()
    base_nom = t.strftime("%Y-%m-%d-%H%M%S")
    nom, n = f"{base_nom}.age", 1
    while (dossier_variables(data) / nom).exists():
        n += 1
        nom = f"{base_nom}-{n}.age"
    _ecrire_atomique(dossier_variables(data) / nom, texte)
    exports = sorted(dossier_variables(data).glob("*.age"))
    for f in exports[:-GARDES_VARIABLES]:
        f.unlink(missing_ok=True)
    return {"nom": nom, "taille": len(texte.encode("utf-8"))}


def liste_variables(data: Path) -> list[dict]:
    return [{"nom": f.name, "taille": f.stat().st_size,
             "le": datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(timespec="seconds")}
            for f in sorted(dossier_variables(data).glob("*.age"), reverse=True) if RE_EXPORT.match(f.name)]


def chemin_variables(data: Path, nom: str) -> Path | None:
    if not isinstance(nom, str) or not RE_EXPORT.match(nom):
        return None
    f = dossier_variables(data) / nom
    return f if f.is_file() else None

