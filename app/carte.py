"""La carte de la maison (0.11, décision du 18/11/2026 : Atlas basculé dans l'Anneau).

Le coffre Obsidian fabrique carte.json à chaque envoi (action GitHub « carte » du coffre) et la pousse dans le dépôt
privé d'Atlas (ANNEAU_ATLAS_DEPOT), réduit à ce seul fichier. L'Anneau la relit toutes les heures (et sur le bouton de
Réglages) avec le jeton en lecture seule ANNEAU_GITHUB_JETON, côté serveur seulement, et garde la dernière carte valide
dans <données>/documents/carte.json : GitHub ou Internet en panne, la carte reste là, avec son âge.

L'Anneau ne détient ce jeton que pour cela : il ne lit rien d'autre sur GitHub et n'y écrit rien. Le jeton n'est
jamais montré, ni envoyé au navigateur, ni sauvegardé.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .maison import cle

log = logging.getLogger("anneau.carte")
API = "https://api.github.com"
FICHIER = "carte.json"
SCHEMA = 1                          # version du format fabriqué par le script du coffre
TAILLE_MAX = 2 * 1024 * 1024
HEURE = 3600
NATURES = {"donnees", "commande", "cookie", "acces", "maj"}


def dossier(data: Path) -> Path:
    return data / "documents"


def _fichier_etat(data: Path) -> Path:
    return dossier(data) / "carte-etat.json"


def etat(data: Path) -> dict:
    """Ce que Réglages montre : présente ou non, reçue quand, fabriquée quand et depuis quel commit, dernière erreur."""
    try:
        e = json.loads(_fichier_etat(data).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        e = {}
    return {"present": (dossier(data) / FICHIER).is_file(), **e}


def _noter(data: Path, **champs) -> dict:
    e = {k: v for k, v in etat(data).items() if k != "present"}
    e.update(champs)
    dossier(data).mkdir(parents=True, exist_ok=True)
    _fichier_etat(data).write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    return etat(data)


def a_relire(data: Path, maintenant: float) -> bool:
    e = etat(data)
    try:
        dernier = datetime.fromisoformat(e.get("essaye_le", "")).timestamp()
    except ValueError:
        return True
    return not e["present"] or maintenant - dernier >= HEURE


def valider(carte) -> str:
    """Vide si la carte est utilisable ; sinon pourquoi elle est refusée (l'ancienne est alors gardée)."""
    if not isinstance(carte, dict):
        return "le fichier n'est pas une carte"
    if carte.get("schema") != SCHEMA:
        return f"format {carte.get('schema')!r} inconnu de cette version de l'Anneau (attendu : {SCHEMA})"
    for k in ("machines", "quartiers", "services", "flux"):
        if not isinstance(carte.get(k), list):
            return f"la carte n'a pas de liste « {k} »"
    ids = set()
    for s in carte["services"]:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not s["id"]:
            return "un service sans identifiant"
        ids.add(s["id"])
    for f in carte["flux"]:
        if not isinstance(f, dict) or f.get("de") not in ids or f.get("vers") not in ids:
            return "un flux vers un service inconnu"
        if f.get("nature") not in NATURES:
            return f"une nature de flux inconnue ({f.get('nature')!r})"
    return ""


def essai(depot: str, jeton: str, transport: httpx.BaseTransport | None = None) -> tuple[bool, str]:
    """0.17.2 : « Vérifier » de la fiche GitHub. Lit les informations de carte.json dans le dépôt (lecture seule,
    rien n'est enregistré : la copie locale ne change pas). (True, phrase) si le jeton ouvre le fichier ; sinon
    (False, la raison). Le jeton ne figure jamais dans la phrase."""
    if not depot or not jeton:
        return False, "ANNEAU_ATLAS_DEPOT ou ANNEAU_GITHUB_JETON n'est pas réglé dans la stack."
    entetes = {"Authorization": f"Bearer {jeton}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "anneau",
               "Accept": "application/vnd.github+json"}
    try:
        with httpx.Client(timeout=10, transport=transport, follow_redirects=False) as c:
            r = c.get(f"{API}/repos/{depot}/contents/{FICHIER}", headers=entetes)
    except httpx.HTTPError as exc:
        return False, f"GitHub injoignable ({type(exc).__name__})."
    if r.status_code in (401, 403):
        return False, "GitHub refuse le jeton (expiré, ou sans accès en lecture au dépôt de la carte)."
    if r.status_code == 404:
        return False, f"{FICHIER} introuvable dans {depot} (ou dépôt invisible pour ce jeton)."
    if r.status_code != 200:
        return False, f"GitHub a répondu {r.status_code}."
    try:
        taille = int(r.json().get("size", 0))
    except (ValueError, AttributeError):
        taille = 0
    reste = r.headers.get("x-ratelimit-remaining")
    return True, f"Jeton accepté, {FICHIER} lisible dans {depot} ({taille} octets)" + (f", {reste} demandes restantes cette heure." if reste else ".")


def telecharger(data: Path, depot: str, jeton: str, transport: httpx.BaseTransport | None = None) -> dict:
    """Relit carte.json dans le dépôt et remplace la copie locale si elle a changé. Une erreur laisse l'ancienne
    carte en place et est notée (montrée dans Réglages)."""
    le = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not depot or not jeton:
        return _noter(data, essaye_le=le, erreur="ANNEAU_ATLAS_DEPOT ou ANNEAU_GITHUB_JETON n'est pas réglé dans la stack.")
    entetes = {"Authorization": f"Bearer {jeton}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "anneau",
               "Accept": "application/vnd.github+json"}
    try:
        with httpx.Client(timeout=30, transport=transport, follow_redirects=False) as c:
            r = c.get(f"{API}/repos/{depot}/contents/{FICHIER}", headers=entetes)
    except httpx.HTTPError as exc:
        log.warning("Carte non relue : %s", exc)
        return _noter(data, essaye_le=le, erreur=f"GitHub injoignable ({type(exc).__name__}) : la dernière carte est gardée.")
    if r.status_code in (401, 403):
        return _noter(data, essaye_le=le, erreur="GitHub refuse le jeton (expiré, ou sans accès en lecture au dépôt de la carte).")
    if r.status_code == 404:
        return _noter(data, essaye_le=le, erreur=f"{FICHIER} introuvable dans {depot} : le coffre ne l'a pas encore envoyée.")
    if r.status_code != 200:
        return _noter(data, essaye_le=le, erreur=f"GitHub a répondu {r.status_code} : la dernière carte est gardée.")
    try:
        meta = r.json()
        if meta.get("size", 0) > TAILLE_MAX or meta.get("encoding") != "base64":
            return _noter(data, essaye_le=le, erreur="Fichier trop gros ou illisible : refusé.")
        if meta.get("sha") and meta["sha"] == etat(data).get("sha") and etat(data)["present"]:
            return _noter(data, essaye_le=le, erreur="")
        contenu = base64.b64decode(meta.get("content", ""))
        carte = json.loads(contenu.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        return _noter(data, essaye_le=le, erreur=f"Carte illisible ({type(exc).__name__}) : la dernière est gardée.")
    pourquoi = valider(carte)
    if pourquoi:
        return _noter(data, essaye_le=le, erreur=f"Carte refusée : {pourquoi}. La dernière est gardée.")
    dossier(data).mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dossier(data), suffix=".tmp")
    with os.fdopen(fd, "wb") as sortie:
        sortie.write(contenu)
    os.replace(tmp, dossier(data) / FICHIER)
    return _noter(data, essaye_le=le, recu_le=le, sha=meta.get("sha", ""), genere_le=carte.get("genere_le", ""),
                  commit=carte.get("commit", ""), erreur="")


def lire(data: Path) -> dict | None:
    try:
        carte = json.loads((dossier(data) / FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return None if valider(carte) else carte


def avec_voyants(carte: dict, tuiles: list[dict]) -> dict:
    """Ajoute à chaque service de la carte le voyant de sa tuile (même nom, nom sans sa parenthèse, ou même
    identifiant ; comparés sans accents, espaces ni tirets) : ok, panne,
    eteint, inconnu ; « sans tuile » quand l'Anneau ne le suit pas. Les tuiles qui ne sont sur aucune carte
    sont rendues à part (« hors carte »)."""
    par_cle: dict[str, dict] = {}
    for t in tuiles:                       # la clé d'une tuile s'écrit « kit-d-urgence » : on compare tout aplati
        for k in (cle(t["nom"]), cle(t["cle"])):
            par_cle.setdefault(k, t)
    vues = set()
    services = []
    for s in carte["services"]:
        nom = s.get("nom", "")
        t = next((par_cle[k] for k in (cle(nom), cle(s["id"]), cle(nom.split(" (")[0])) if k in par_cle), None)
        if t:
            vues.add(t["cle"])
        services.append({**s, "voyant": t["etat"] if t else "", "tuile": t["nom"] if t else ""})
    machines = [cle(m.get("nom", "")) for m in carte.get("machines", [])]
    est_machine = lambda t: any(m.startswith(cle(t["nom"])) for m in machines if cle(t["nom"]))   # « Synology » : une machine
    hors = [{"nom": t["nom"], "etat": t["etat"], "famille": t.get("famille", "")} for t in tuiles
            if t["cle"] not in vues and not est_machine(t)]
    return {**carte, "services": services, "hors_carte": hors}
