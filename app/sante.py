"""0.12 : la santé des tâches de fond des applis maison, lue dans leur /health (socle 0.9.0).

Chaque appli maison à jour ajoute à son /health (contrat commun du 18/11/2026) :
  version_socle   « 0.9.0 »
  taches          [{nom, type: reguliere|demande, periode_s, etat: ok|en_retard|bloquee|jamais|erreur,
                    derniere_reussite, dernier_essai, derniere_erreur, message?}]
                  (message seulement si la demande porte le jeton commun : l'Anneau l'envoie aux seules tuiles
                  « sauvegarde: true »)
  copie_base      {le, ok, bases, taille} ou null (appli sans base)

Une appli qui n'a pas ces champs : rien ne change pour sa tuile.

Règle de la tuile « à surveiller » (orange, jamais « en panne » : le service répond) :
  - une tâche RÉGULIÈRE « en_retard » ou « bloquee » (l'appli calcule l'état elle-même) ;
  - une copie des bases « ok: false », ou faite il y a plus de 36 h.
  Une tâche À LA DEMANDE ne rend jamais orange : sa dernière erreur se lit dans la fiche.
  Une copie jamais faite (« le » vide) ne rend pas orange : la tâche « copie-des-bases » le dira (« jamais » une période,
  puis « en_retard »).

« Vu » (bouton de la fiche) : l'empreinte des défauts actuels d'une tuile (noms des tâches en défaut, « copie ») est
gardée dans <données>/vus.json ; tant qu'elle ne change pas, la tuile n'est pas orange. Dès que la tuile n'a plus de
défaut, ou que ses défauts changent, le « vu » est oublié (la veille fait ce ménage à chaque tour).

Bibliothèque standard seulement.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("anneau.sante")

COPIE_VIEILLE = 36 * 3600          # secondes : au-delà, la copie des bases est « vieille »
FICHIER_VUS = "vus.json"
ETATS = {"ok", "en_retard", "bloquee", "jamais", "erreur"}
TYPES = {"reguliere", "demande"}
MAX_TACHES = 30


def _texte(v, longueur: int) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return None
    return v.strip()[:longueur]


def _entier(v) -> int | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        return int(v)
    except (OverflowError, ValueError):     # inf, nan
        return None


def lire(corps) -> dict | None:
    """Extrait du /health d'une appli ses champs de santé, nettoyés (types, longueurs). None si elle n'en a aucun."""
    if not isinstance(corps, dict) or not any(k in corps for k in ("taches", "copie_base", "version_socle")):
        return None
    taches = []
    for t in (corps.get("taches") if isinstance(corps.get("taches"), list) else [])[:MAX_TACHES]:
        if not isinstance(t, dict) or not _texte(t.get("nom"), 60):
            continue
        tache = {"nom": _texte(t["nom"], 60),
                 "type": t.get("type") if t.get("type") in TYPES else "reguliere",
                 "periode_s": _entier(t.get("periode_s")),
                 "etat": t.get("etat") if t.get("etat") in ETATS else "jamais",
                 "derniere_reussite": _texte(t.get("derniere_reussite"), 40),
                 "dernier_essai": _texte(t.get("dernier_essai"), 40),
                 "derniere_erreur": _texte(t.get("derniere_erreur"), 40)}
        if _texte(t.get("message"), 200):
            tache["message"] = _texte(t["message"], 200)
        taches.append(tache)
    copie = None
    c = corps.get("copie_base")
    if isinstance(c, dict):
        copie = {"le": _texte(c.get("le"), 40), "ok": c.get("ok") is True,
                 "bases": [b[:80] for b in (c.get("bases") if isinstance(c.get("bases"), list) else []) if isinstance(b, str)][:10],
                 "taille": _entier(c.get("taille"))}
    return {"version_socle": _texte(corps.get("version_socle"), 20), "taches": taches, "copie_base": copie}


def _instant(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:                          # sans fuseau : l'heure du conteneur
        d = d.astimezone()
    return d


def duree(secondes: float) -> str:
    """« 12 min », « 3 h », « 2 j » : une durée écrite court, arrondie vers le bas."""
    s = max(0, int(secondes))
    if s < 3600:
        return f"{max(1, s // 60)} min"
    if s < 48 * 3600:
        return f"{s // 3600} h"
    return f"{s // 86400} j"


def _depuis(iso: str | None, t: datetime) -> str:
    d = _instant(iso)
    return duree((t - d).total_seconds()) if d else ""


def defauts(s: dict | None, t: datetime) -> list[dict]:
    """Ce qui rend la tuile orange, dans l'ordre : [{cle, phrase}]. Vide : rien à surveiller."""
    if not s:
        return []
    t = t if t.tzinfo else t.astimezone()
    sortie = []
    for x in s.get("taches") or []:
        if x["type"] != "reguliere":
            continue                               # une tâche à la demande ne rend jamais orange
        if x["etat"] == "en_retard":
            d = _depuis(x["derniere_reussite"], t)
            sortie.append({"cle": "tache:" + x["nom"],
                           "phrase": f"{x['nom']} n'a pas réussi depuis {d}" if d else f"{x['nom']} n'a pas réussi depuis le démarrage"})
        elif x["etat"] == "bloquee":
            d = _depuis(x["dernier_essai"], t)
            sortie.append({"cle": "tache:" + x["nom"], "phrase": f"{x['nom']} bloquée depuis {d}" if d else f"{x['nom']} bloquée"})
    c = s.get("copie_base")
    if isinstance(c, dict) and c.get("le"):        # « le » vide : jamais copiée, la tâche copie-des-bases le dira
        fait = _instant(c["le"])
        if not c.get("ok"):
            sortie.append({"cle": "copie", "phrase": "copie des bases ratée"})
        elif fait is not None and (t - fait).total_seconds() > COPIE_VIEILLE:
            sortie.append({"cle": "copie", "phrase": f"dernière copie des bases il y a {duree((t - fait).total_seconds())}"})
    return sortie


def empreinte(d: list[dict]) -> list[str]:
    """L'empreinte d'un état orange : ce qui est en défaut, sans les durées (qui avancent toutes seules)."""
    return sorted({x["cle"] for x in d})


def phrase(d: list[dict]) -> str:
    """La phrase écrite sur la tuile : le premier défaut, et combien d'autres."""
    if not d:
        return ""
    return d[0]["phrase"] + (f" (+{len(d) - 1})" if len(d) > 1 else "")


class Vus:
    """Les « Vu » des tuiles orange : {clé de tuile: {empreinte, le}} dans <données>/vus.json.
    Disque refusé : gardé en mémoire jusqu'au redémarrage."""

    def __init__(self, data: Path):
        self.chemin = data / FICHIER_VUS
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8"))
            self.vus = {k: v for k, v in brut.items() if isinstance(v, dict) and isinstance(v.get("empreinte"), list)} \
                if isinstance(brut, dict) else {}
        except (OSError, ValueError):
            self.vus = {}

    def _garder(self) -> None:
        tmp = self.chemin.with_name(self.chemin.name + ".tmp")
        try:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.vus, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.chemin)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            log.warning("« Vu » non enregistré sur disque : %s", exc)

    def est_vu(self, cle: str, emp: list[str]) -> bool:
        return bool(emp) and self.vus.get(cle, {}).get("empreinte") == emp

    def marquer(self, cle: str, emp: list[str], le: str) -> None:
        self.vus[cle] = {"empreinte": emp, "le": le}
        self._garder()

    def menage(self, actuelles: dict[str, list[str]]) -> None:
        """Oublie le « vu » d'une tuile qui n'a plus de défaut, dont les défauts ont changé, ou qui n'existe plus."""
        perimes = [c for c, v in self.vus.items() if actuelles.get(c) != v.get("empreinte")]
        for c in perimes:
            del self.vus[c]
        if perimes:
            self._garder()
