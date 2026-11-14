"""Documents gardés par l'Anneau (1.0 : Atlas). Ils viennent d'une publication GitHub privée, avec un jeton
en lecture seule, et sont rangés dans le dossier de données (documents/). Servis derrière la session.

L'Anneau ne détient ce jeton que pour cela : il ne lit rien d'autre sur GitHub et n'y écrit rien.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

log = logging.getLogger("anneau.documents")
API = "https://api.github.com"
PUBLICATION = "derniere"          # la publication que la CI d'Atlas tient à jour
FICHIER = "atlas.html"
TAILLE_MAX = 20 * 1024 * 1024
JOUR = 24 * 3600


def dossier(data: Path) -> Path:
    return data / "documents"


def etat(data: Path) -> dict:
    """Ce que Réglages montre : présent ou non, quand, quelle version, la dernière erreur."""
    try:
        e = json.loads((dossier(data) / "atlas.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        e = {}
    f = dossier(data) / FICHIER
    return {"present": f.is_file(), "taille": f.stat().st_size if f.is_file() else 0, **e}


def _noter(data: Path, **champs) -> dict:
    e = {k: v for k, v in etat(data).items() if k not in ("present", "taille")}
    e.update(champs)
    dossier(data).mkdir(parents=True, exist_ok=True)
    (dossier(data) / "atlas.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    return etat(data)


def a_relire(data: Path, maintenant: float) -> bool:
    e = etat(data)
    try:
        dernier = datetime.fromisoformat(e.get("essaye_le", "")).timestamp()
    except ValueError:
        return True
    return not e["present"] or maintenant - dernier >= JOUR


def telecharger_atlas(data: Path, depot: str, jeton: str, transport: httpx.BaseTransport | None = None) -> dict:
    """Relit la publication « derniere » du dépôt d'Atlas et remplace le fichier s'il a changé.
    Une erreur laisse l'ancien fichier en place et est notée (montrée dans Réglages)."""
    le = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not depot or not jeton:
        return _noter(data, essaye_le=le, erreur="ANNEAU_ATLAS_DEPOT ou ANNEAU_GITHUB_JETON n'est pas réglé dans la stack.")
    entetes = {"Authorization": f"Bearer {jeton}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "anneau"}
    try:
        with httpx.Client(timeout=30, transport=transport, follow_redirects=True) as c:
            r = c.get(f"{API}/repos/{depot}/releases/tags/{PUBLICATION}", headers={**entetes, "Accept": "application/vnd.github+json"})
            if r.status_code in (401, 403):
                return _noter(data, essaye_le=le, erreur="GitHub refuse le jeton (expiré, ou sans accès en lecture au dépôt d'Atlas).")
            if r.status_code == 404:
                return _noter(data, essaye_le=le, erreur=f"Publication « {PUBLICATION} » introuvable dans {depot}.")
            r.raise_for_status()
            pub = r.json()
            piece = next((a for a in pub.get("assets", []) if a.get("name") == FICHIER), None)
            if not piece:
                return _noter(data, essaye_le=le, erreur=f"La publication n'a pas de fichier {FICHIER}.")
            if piece.get("size", 0) > TAILLE_MAX:
                return _noter(data, essaye_le=le, erreur="Fichier trop gros, refusé.")
            if piece.get("updated_at") == etat(data).get("publie_le") and etat(data)["present"]:
                return _noter(data, essaye_le=le, erreur="")
            # httpx retire l'en-tête Authorization quand GitHub redirige vers son stockage (autre hôte).
            f = c.get(piece["url"], headers={**entetes, "Accept": "application/octet-stream"})
            f.raise_for_status()
            contenu = f.content
    except (httpx.HTTPError, OSError, ValueError) as exc:
        log.warning("Atlas non relu : %s", exc)
        return _noter(data, essaye_le=le, erreur=f"GitHub injoignable ou réponse illisible ({type(exc).__name__}).")
    if b"<html" not in contenu[:2000].lower() or len(contenu) > TAILLE_MAX:
        return _noter(data, essaye_le=le, erreur="Le fichier reçu n'est pas une page HTML : l'ancien est gardé.")
    dossier(data).mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dossier(data), suffix=".tmp")
    with os.fdopen(fd, "wb") as sortie:
        sortie.write(contenu)
    os.replace(tmp, dossier(data) / FICHIER)
    return _noter(data, essaye_le=le, recu_le=le, publie_le=piece.get("updated_at", ""), note=pub.get("body", "")[:200], erreur="")
