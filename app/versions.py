"""0.13 : versions publiées, versions en service, journal des changements et nouveautés de la nuit (E1, 18/11/2026).

Watchtower met à jour tous les conteneurs chaque nuit à 05:00 (applis maison comprises, image `:latest`). L'Anneau dit,
pour chaque tuile :
  - la version EN SERVICE : lue par la veille dans le /health (`version`) ou, pour une tuile tierce, à l'adresse
    `version_url:` de la tuile (Immich : {"major", "minor", "patch"} ; ou {"version": "…"}), sans jeton ;
  - la DERNIÈRE PUBLIÉE : la plus haute étiquette Git `v<semver>` du dépôt `depot:` de la tuile, lue toutes les heures
    par la tâche « versions-publiees » sur l'API publique de GitHub (sans jeton). GitHub injoignable ou limite atteinte
    (403/429) : l'ancienne lecture est gardée ; seule la tâche le dit (état « erreur » dans le /health de l'Anneau).
Un retard (publiée plus récente qu'en service) n'est jamais orange : c'est dit en mots dans la fiche.

Quand la veille voit la version d'une tuile changer, elle l'ajoute au journal (200 entrées au plus). À la première
ouverture après une connexion, l'écran montre ce qui a changé depuis la dernière fois que Julien a dit « Vu » (heure
gardée ici, une pour l'Anneau, pas par navigateur).

Fichiers du dossier de données :
  versions.json             {"depots": {dépôt: {"version", "lu_le"}}, "essaye_le", "erreur"}   (dernières publiées)
  versions-en-service.json  {clé de tuile: {"version", "le"}}   (pour voir un changement même après un redémarrage)
  journal-versions.json     [{"tuile", "cle", "de", "vers", "le"}]   (le plus récent en dernier)
  versions-vues.json        {"vu_le"}

Bibliothèque standard et httpx seulement.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

import httpx

log = logging.getLogger("anneau.versions")

PROPRIETAIRE = "baloodusudouest"       # le compte GitHub des applis maison (dépôts publics, lus sans jeton)
API = "https://api.github.com"
HEURE = 3600
MAX_JOURNAL = 200
DEPOT_VALIDE = re.compile(r"^[A-Za-z0-9._-]+$")
_SEMVER = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")
FICHIER_PUBLIEES = "versions.json"
FICHIER_EN_SERVICE = "versions-en-service.json"
FICHIER_JOURNAL = "journal-versions.json"
FICHIER_VUES = "versions-vues.json"


class Injoignable(Exception):
    """GitHub n'a pas répondu, ou a refusé (limite atteinte) : l'ancienne lecture est gardée."""


def maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def instant(iso) -> datetime | None:
    if not isinstance(iso, str) or not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.astimezone()


# ---------------------------------------------------------------- fichiers (écrits à côté puis mis en place)

def _lire(chemin: Path, defaut):
    try:
        v = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut
    return v if isinstance(v, type(defaut)) else defaut


def _ecrire(chemin: Path, valeur) -> None:
    tmp = chemin.with_name(chemin.name + ".tmp")
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(valeur, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, chemin)
    except OSError as exc:                 # disque plein ou en lecture seule : l'Anneau continue, en mémoire
        tmp.unlink(missing_ok=True)
        log.warning("%s non enregistré : %s", chemin.name, exc)


# ---------------------------------------------------------------- versions : lecture et comparaison

def cle_version(v) -> tuple[int, int, int] | None:
    """« 2.33.0 », « v2.33.0 », « 3.1.4-beta » → (2, 33, 0)… ; None si ce n'est pas une version."""
    m = _VERSION.match(v.strip()) if isinstance(v, str) else None
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def nettoyer(v) -> str | None:
    """Une version lue ailleurs, rendue courte et sans « v » devant ; None si vide ou trop étrange."""
    if not isinstance(v, str) or not v.strip() or len(v.strip()) > 40:
        return None
    v = v.strip()
    return v[1:] if v[:1] in ("v", "V") and v[1:2].isdigit() else v


def version_lue(corps) -> str | None:
    """La version dans une réponse JSON : {"version": "…"} (le /health des applis maison, et d'autres) ou
    {"major", "minor", "patch"} (Immich, /api/server/version)."""
    if not isinstance(corps, dict):
        return None
    if all(isinstance(corps.get(k), int) and not isinstance(corps.get(k), bool) for k in ("major", "minor", "patch")):
        return f"{corps['major']}.{corps['minor']}.{corps['patch']}"
    return nettoyer(corps.get("version"))


async def lire_version_url(adresse: str) -> str | None:
    """La veille lit `version_url:` d'une tuile tierce, sans jeton. None si rien de lisible."""
    try:
        async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=False) as c:
            r = await c.get(adresse, headers={"User-Agent": "anneau", "Accept": "application/json"})
        if r.status_code != 200 or len(r.content) > 64 * 1024:
            return None
        return version_lue(r.json())
    except Exception:  # noqa: BLE001 — illisible ou injoignable : on ne sait pas, rien ne change
        return None


def plus_haute(etiquettes) -> str | None:
    """La plus haute étiquette `v<majeur>.<mineur>.<correctif>` (tri par nombres, pas par texte) ; les autres
    (« latest », « v2 », « v1.2.3-rc1 »…) sont ignorées. Rend la version sans « v »."""
    meilleures = []
    for e in etiquettes if isinstance(etiquettes, list) else []:
        nom = e.get("name") if isinstance(e, dict) else None
        m = _SEMVER.match(nom) if isinstance(nom, str) else None
        if m:
            meilleures.append(((int(m[1]), int(m[2]), int(m[3])), nom[1:]))
    return max(meilleures)[1] if meilleures else None


def lire_depot(depot: str, transport: httpx.BaseTransport | None = None) -> str | None:
    """La dernière version publiée d'un dépôt (étiquettes Git). Lève Injoignable si GitHub ne répond pas ou refuse."""
    url = f"{API}/repos/{PROPRIETAIRE}/{depot}/tags?per_page=100"
    entetes = {"User-Agent": "anneau", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    try:
        with httpx.Client(timeout=15, transport=transport, follow_redirects=False) as c:
            r = c.get(url, headers=entetes)
    except httpx.HTTPError as exc:
        raise Injoignable(f"GitHub injoignable ({type(exc).__name__})") from exc
    if r.status_code in (403, 429):
        raise Injoignable(f"GitHub refuse ({r.status_code}, limite atteinte ?)")
    if r.status_code != 200:
        raise Injoignable(f"GitHub a répondu {r.status_code} pour {depot}")
    try:
        return plus_haute(r.json())
    except ValueError as exc:
        raise Injoignable(f"réponse illisible pour {depot}") from exc


def publiees(data: Path) -> dict:
    e = _lire(data / FICHIER_PUBLIEES, {})
    return {"depots": e.get("depots") if isinstance(e.get("depots"), dict) else {},
            "essaye_le": e.get("essaye_le", ""), "erreur": e.get("erreur", "")}


def a_relire(data: Path, maintenant_s: float) -> bool:
    d = instant(publiees(data)["essaye_le"])
    return d is None or maintenant_s - d.timestamp() >= HEURE


def relire(data: Path, depots, transport: httpx.BaseTransport | None = None) -> dict:
    """Relit chaque dépôt. Un dépôt injoignable garde son ancienne lecture ; les erreurs sont rendues (et notées)
    pour que la tâche les compte. Rien n'est montré à l'écran au-delà de l'état de la tâche."""
    e = publiees(data)
    anciens, erreurs = e["depots"], []
    neufs = {}
    for depot in sorted(set(depots)):
        try:
            v = lire_depot(depot, transport)
        except Injoignable as exc:
            erreurs.append(str(exc))
            if depot in anciens:
                neufs[depot] = anciens[depot]
            continue
        neufs[depot] = {"version": v, "lu_le": maintenant()}          # v None : aucune étiquette v<semver>
    e = {"depots": neufs, "essaye_le": maintenant(), "erreur": " ; ".join(erreurs)[:500]}
    _ecrire(data / FICHIER_PUBLIEES, e)
    return e


# ---------------------------------------------------------------- en service et journal

class EnService:
    """Les versions en service vues par la veille, et le journal des changements."""

    def __init__(self, data: Path):
        self.data = data
        brut = _lire(data / FICHIER_EN_SERVICE, {})
        self.versions = {k: v for k, v in brut.items() if isinstance(v, dict) and isinstance(v.get("version"), str)}
        self.journal = [j for j in _lire(data / FICHIER_JOURNAL, []) if isinstance(j, dict) and instant(j.get("le"))]

    def noter(self, cle: str, nom: str, version: str | None, le: str | None = None) -> dict | None:
        """La veille a lu `version` pour la tuile. Rend l'entrée du journal si la version a changé.
        None (rien de lisible ce tour-ci) ne change rien : la dernière connue reste."""
        if not version:
            return None
        avant = self.versions.get(cle, {}).get("version")
        if avant == version:
            return None
        le = le or maintenant()
        self.versions[cle] = {"version": version, "le": le}
        _ecrire(self.data / FICHIER_EN_SERVICE, self.versions)
        if avant is None:                  # première lecture : rien à dire
            return None
        entree = {"tuile": nom, "cle": cle, "de": avant, "vers": version, "le": le}
        self.journal.append(entree)
        del self.journal[:-MAX_JOURNAL]
        _ecrire(self.data / FICHIER_JOURNAL, self.journal)
        return entree

    def oublier_sauf(self, cles: set[str]) -> None:
        """Une tuile retirée du fichier : sa version en service est oubliée (le journal garde son histoire)."""
        retirees = [k for k in self.versions if k not in cles and not k.startswith("@")]   # « @anneau » : lui-même
        for k in retirees:
            del self.versions[k]
        if retirees:
            _ecrire(self.data / FICHIER_EN_SERVICE, self.versions)

    def version(self, cle: str) -> str | None:
        return self.versions.get(cle, {}).get("version")

    def mise_a_jour_le(self, cle: str) -> str | None:
        """Quand la version de cette tuile a changé pour la dernière fois (d'après le journal)."""
        return next((j["le"] for j in reversed(self.journal) if j.get("cle") == cle), None)

    def depuis(self, iso: str | None) -> list[dict]:
        """Les changements après `iso`, un par tuile (de la première ancienne à la dernière nouvelle), du plus récent
        au plus ancien. Sans heure (jamais vu) : tout le journal. Une tuile revenue à sa version de départ n'y est pas."""
        borne = instant(iso)
        par_tuile: dict[str, dict] = {}
        for j in self.journal:
            if borne is not None and instant(j["le"]) <= borne:
                continue
            k = j.get("cle") or j.get("tuile")
            if k in par_tuile:
                par_tuile[k].update(vers=j["vers"], le=j["le"], tuile=j["tuile"])
            else:
                par_tuile[k] = dict(j)
        sortie = [j for j in par_tuile.values() if j["de"] != j["vers"]]
        return sorted(sortie, key=lambda j: instant(j["le"]), reverse=True)


def vu_le(data: Path) -> str | None:
    return _lire(data / FICHIER_VUES, {}).get("vu_le") or None


def marquer_vu(data: Path, jusqu_a: str | None = None) -> str:
    """« Vu » : jusqu'à l'heure du plus récent changement montré (un changement arrivé entre-temps sera montré la
    prochaine fois), sinon maintenant. L'heure ne recule jamais."""
    le = jusqu_a if instant(jusqu_a) is not None else maintenant()
    ancien = instant(vu_le(data))
    if ancien is not None and instant(le) < ancien:
        return vu_le(data)
    _ecrire(data / FICHIER_VUES, {"vu_le": le})
    return le


# ---------------------------------------------------------------- ce que dit la fiche

def a_jour(en_service: str | None, publiee: str | None) -> bool | None:
    a, b = cle_version(en_service), cle_version(publiee)
    return None if a is None or b is None else a >= b


def phrase(en_service: str | None, publiee: str | None) -> str:
    """« Version 0.12.0 — dernière publiée 0.12.0 (à jour) », « … dernière publiée 0.13.0 : pas encore en service ».
    Jamais une alerte : un retard se dit en mots."""
    if not en_service and not publiee:
        return ""
    debut = f"Version {en_service}" if en_service else "Version en service inconnue"
    if not publiee:
        return debut
    etat = a_jour(en_service, publiee)
    if etat is True:
        return f"{debut} — dernière publiée {publiee} (à jour)"
    if etat is False:
        return f"{debut} — dernière publiée {publiee} : pas encore en service"
    return f"{debut} — dernière publiée {publiee}"
