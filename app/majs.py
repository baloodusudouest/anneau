"""0.18 : les applis de la stack homelab à mettre à jour, dans « À faire quand tu veux », avec un bouton par ligne.

Décisions de Julien du 22/11/2026 (docs/ajout-0.18.0.md) :
- toutes les applis de la stack homelab (étiquette com.docker.compose.project=homelab, lue chez Portainer), en une ligne
  repliée « N applis à mettre à jour » qui se déplie ;
- Portainer CE n'a pas d'API qui dise si une image est en retard (la route image_status est réservée à la version
  payante) : l'Anneau compare lui-même l'empreinte de l'image locale (RepoDigests) à celle du registre (registres.py),
  toutes les 6 h et sur « Vérifier maintenant » ;
- un bouton « Mettre à jour » par ligne, par Watchtower (POST /v1/update?image=…), comme celui des fiches ; les conteneurs
  protégés (ceux que la fiche ne touche jamais : l'Anneau, Immich, Watchtower, coffre-git, SilverBullet, Portainer) et
  les bases de données ont le bouton, avec une double confirmation (le serveur exige « protege: true ») ;
- une appli à version figée dans la stack (étiquette = numéro de version, ligne `figees:` de services.yaml) : ligne
  sans bouton « version X publiée, tu as Y : changer <VARIABLE> dans la stack » (dernière publication GitHub) ;
- la route reçoit l'identifiant d'une ligne de la liste lue par l'Anneau (le nom du conteneur relevé chez Portainer),
  jamais un nom libre ; le conteneur est relu chez Portainer (étiquette de la stack, en marche) avant l'ordre ;
- on ne se fie pas à la réponse de Watchtower : l'état réel est relu (nouvelle image, conteneur en marche) ;
  l'ordre est gardé sur le disque (majs.json) : il survit à un redémarrage, y compris celui de l'Anneau lui-même.
"""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable

from .conteneurs import (DELAI_MAJ, ETIQUETTE_PROJET, ETIQUETTE_WATCHTOWER, NOM_VALIDE, PROJET, ErreurPortainer,
                         ErreurWatchtower, Portainer, Refus, Watchtower, image_pour_watchtower, interdit, maintenant)
from .registres import ErreurRegistre, Registres, cle_version, est_figee, etiquette

log = logging.getLogger("anneau.majs")

FICHIER = "majs.json"
PERIODE = 6 * 3600               # s : vérification des registres
RESULTAT_VISIBLE = 1800          # s : « mis à jour » reste écrit sur la ligne 30 min
EN_PARALLELE = 6                 # demandes simultanées aux registres
ETIQUETTE_VERSION = "org.opencontainers.image.version"
BASES = re.compile(r"(^|/)(postgres|postgresql|pgvecto[-a-z]*|vectorchord|redis|valkey|mariadb|mysql|mongo|mongodb)$")
PROTEGES = "conteneur protégé : l'Anneau ne le touche jamais depuis une fiche"


def _depot_image(ref: str) -> str:
    return (ref or "").split("@")[0].rsplit(":", 1)[0] if ":" in (ref or "").split("/")[-1] else (ref or "").split("@")[0]


def protection(nom: str, ref: str) -> str:
    """Pourquoi ce conteneur demande une double confirmation (vide : une seule)."""
    if interdit(nom):
        return PROTEGES
    if BASES.search(_depot_image(ref).lower()):
        return "base de données : une nouvelle version peut demander une migration, sauvegarde conseillée"
    return ""


class MisesAJour:
    def __init__(self, data: Path, portainer: Portainer | None, watchtower: Watchtower | None = None,
                 watchtower_manque: str = "", registres: Registres | None = None,
                 horloge: Callable[[], float] = time.time, noter: Callable[..., None] | None = None):
        self.data, self.portainer, self.watchtower = data, portainer, watchtower
        self.watchtower_manque = watchtower_manque or "Watchtower n'est pas relié"
        self.registres = registres or Registres()
        self._horloge = horloge
        self._noter = noter
        self.reveil: asyncio.Event | None = None
        self._verrou = asyncio.Lock()
        self._taches: set[asyncio.Task] = set()
        m = self._lire()
        self.lignes: dict[str, dict] = m.get("lignes", {})
        self.ordres: dict[str, dict] = m.get("ordres", {})
        self.non_verifiees: list[dict] = m.get("non_verifiees", [])
        self.lu_le: str = m.get("lu_le", "")
        self.lu_t: float = float(m.get("lu_t") or 0)
        self.erreur: str = m.get("erreur", "")
        self.en_verification = False

    @property
    def actif(self) -> bool:
        return self.portainer is not None

    # ------------------------------------------------------------ disque
    def _lire(self) -> dict:
        try:
            d = json.loads((self.data / FICHIER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(d, dict):
            return {}
        for k in ("lignes", "ordres"):
            if not isinstance(d.get(k, {}), dict):
                d[k] = {}
        return d

    def _garder(self) -> None:
        try:
            self.data.mkdir(parents=True, exist_ok=True)
            neuf = self.data / (FICHIER + ".nouveau")
            neuf.write_text(json.dumps({"lignes": self.lignes, "ordres": self.ordres, "non_verifiees": self.non_verifiees,
                                        "lu_le": self.lu_le, "lu_t": self.lu_t, "erreur": self.erreur},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(neuf, self.data / FICHIER)
        except OSError as exc:
            log.warning("Liste des mises à jour non enregistrée : %s", exc)

    def noter(self, resultat: str, nom: str, **plus) -> None:
        if self._noter is not None:
            self._noter("mettre-a-jour", nom, resultat, liste="a-faire", **plus)

    # ------------------------------------------------------------ vérification
    def a_verifier(self) -> bool:
        return self.actif and self._horloge() - self.lu_t >= PERIODE

    async def verifier(self, fichier, tuiles_versions: list[dict] | None = None) -> None:
        """Relit la liste des conteneurs de la stack, puis l'empreinte publiée de chaque image. Portainer injoignable :
        l'ancienne liste reste, l'erreur est dite."""
        if not self.actif:
            return
        async with self._verrou:
            self.en_verification = True
            try:
                await self._verifier(fichier, tuiles_versions or [])
            finally:
                self.en_verification = False
                self.registres.oublier()

    async def _verifier(self, fichier, tuiles_versions: list[dict]) -> None:
        try:
            liste = await self.portainer.lister(PROJET)
        except ErreurPortainer as exc:
            self.erreur = exc.phrase
            self.lu_t, self.lu_le = self._horloge(), maintenant()
            self._garder()
            return
        par_cle = {t["cle"]: t for t in tuiles_versions}
        sem = asyncio.Semaphore(EN_PARALLELE)

        async def un(c: dict) -> tuple[dict | None, dict | None]:
            async with sem:
                return await self._examiner(c, fichier, par_cle)

        resultats = await asyncio.gather(*(un(c) for c in liste))
        lignes, non = {}, []
        for ligne, rate in resultats:
            if ligne:
                lignes[ligne["id"]] = ligne
            if rate:
                non.append(rate)
        for ident, o in self.ordres.items():             # une ligne dont la mise à jour tourne reste affichée
            if o.get("etat") == "en_cours" and ident in self.lignes and ident not in lignes:
                lignes[ident] = self.lignes[ident]
        self.lignes, self.non_verifiees = lignes, sorted(non, key=lambda x: x["nom"])
        self.erreur = ""
        self.lu_t, self.lu_le = self._horloge(), maintenant()
        self._garder()

    def _tuile(self, nom: str, fichier) -> object | None:
        for s in fichier.services:
            if nom in {s.conteneur, s.depot, s.cle}:
                return s
        return None

    async def _examiner(self, c: dict, fichier, par_cle: dict) -> tuple[dict | None, dict | None]:
        noms = [str(n).lstrip("/") for n in (c.get("Names") or []) if str(n).strip()]
        nom = noms[0] if noms else ""
        if not NOM_VALIDE.match(nom):
            return None, None
        labels = c.get("Labels") or {}
        if labels.get(ETIQUETTE_PROJET) != PROJET:
            return None, None
        ref = str(c.get("Image") or "")
        if not ref or ref.startswith("sha256:"):             # étiquette déplacée : le nom vient de l'inspection
            try:
                d = await self.portainer.inspecter(nom)
            except ErreurPortainer:
                d = None
            ref = str(((d or {}).get("Config") or {}).get("Image") or "")
        if not ref or "@" in ref:
            return None, None                                  # épinglée par empreinte : rien à comparer
        img = await self.portainer.image(str(c.get("ImageID") or "")) or {}
        version_locale = str(((img.get("Config") or {}).get("Labels") or {}).get(ETIQUETTE_VERSION) or "")
        tuile = self._tuile(nom, fichier)
        tv = par_cle.get(getattr(tuile, "cle", ""), {}) if tuile else {}
        base = {"id": nom, "conteneur": nom, "nom": getattr(tuile, "nom", "") or nom, "image": ref,
                "running": str(c.get("State") or "") == "running",
                "watchtower_non": str(labels.get(ETIQUETTE_WATCHTOWER) or "").strip().lower() == "false",
                "protege": protection(nom, ref)}
        if est_figee(ref):
            regle = next((f for f in getattr(fichier, "figees", ()) if fnmatch.fnmatchcase(nom, f["conteneur"])), None)
            if not regle:
                return None, None                              # figée sans ligne figees: : rien à dire
            try:
                publiee = await self.registres.derniere_version(regle["depot"])
            except ErreurRegistre as exc:
                return None, {"nom": base["nom"], "raison": str(exc)}
            locale = etiquette(ref)
            a, b = cle_version(locale), cle_version(publiee)
            if not a or not b or b <= a:
                return None, None
            var = regle.get("variable") or ""
            return {**base, "sorte": "figee", "version": locale, "version_neuve": publiee, "variable": var,
                    "phrase": f"version {publiee.lstrip('v')} publiée, tu as {locale.lstrip('v')}"
                              + (f" : changer {var} dans la stack" if var else " : changer la version dans la stack")}, None
        try:
            distante = await self.registres.empreinte(ref)
        except ErreurRegistre as exc:
            return None, {"nom": base["nom"], "raison": str(exc)}
        locales = {str(x).split("@")[-1] for x in (img.get("RepoDigests") or []) if "@" in str(x)}
        if not locales:
            return None, {"nom": base["nom"], "raison": "empreinte de l'image locale inconnue (image construite sur place ?)"}
        if distante in locales:
            return None, None
        version = tv.get("version") or version_locale
        neuve = tv.get("publiee") if tv.get("publiee") and tv.get("publiee") != version else ""
        phrase = f"{version} → {neuve}" if version and neuve else "nouvelle image publiée"
        return {**base, "sorte": "maj", "version": version, "version_neuve": neuve, "phrase": phrase,
                "empreinte_neuve": distante}, None

    # ------------------------------------------------------------ ordres
    def en_cours(self) -> bool:
        return any(o.get("etat") == "en_cours" for o in self.ordres.values())

    def presse(self) -> bool:
        return self.en_cours()

    def _bouton(self, ligne: dict, lecture_seule: bool) -> str:
        """Pourquoi la ligne n'a pas de bouton (vide : il est là)."""
        if ligne.get("sorte") == "figee":
            return ""                                          # la phrase dit quoi faire
        if self.watchtower is None:
            return self.watchtower_manque
        if lecture_seule:
            return "lecture seule : l'Anneau ne donne aucun ordre"
        if ligne.get("watchtower_non"):
            return f"étiquette {ETIQUETTE_WATCHTOWER}=false : Watchtower ne le met jamais à jour"
        if not ligne.get("running"):
            return "arrêté : Watchtower ne met à jour que les conteneurs allumés, l'allumer d'abord"
        _, raison = image_pour_watchtower(ligne.get("image", ""))
        return raison

    async def ordonner(self, ident: str, protege_confirme: bool, lecture_seule: bool) -> dict:
        ligne = self.lignes.get(ident)
        nom = (ligne or {}).get("nom") or ident
        try:
            if not self.actif:
                raise Refus(404, "Portainer n'est pas réglé.")
            if ligne is None or ligne.get("sorte") != "maj":
                raise Refus(404, "Cette appli n'est pas dans la liste des mises à jour : la relire.")
            if lecture_seule:
                raise Refus(403, "Lecture seule : l'Anneau ne donne aucun ordre.")
            if self.watchtower is None:
                raise Refus(409, f"« Mettre à jour » absent : {self.watchtower_manque}.")
            if (self.ordres.get(ident) or {}).get("etat") == "en_cours":
                raise Refus(409, f"La mise à jour de {nom} est déjà en cours.")
            if ligne.get("protege") and not protege_confirme:
                raise Refus(409, f"Double confirmation demandée : {ligne['protege']}.")
            try:
                d = await self.portainer.inspecter(ligne["conteneur"])
            except ErreurPortainer as exc:
                raise Refus(502, exc.phrase) from exc
            if d is None:
                raise Refus(404, f"Portainer ne connaît plus de conteneur « {ligne['conteneur']} ».")
            config = d.get("Config") or {}
            labels = config.get("Labels") or {}
            if str(d.get("Name") or "").lstrip("/") != ligne["conteneur"]:
                raise Refus(403, "Portainer rend un autre conteneur que celui de la liste.")
            if labels.get(ETIQUETTE_PROJET) != PROJET:
                raise Refus(403, f"Refusé : le conteneur n'a pas l'étiquette {ETIQUETTE_PROJET}={PROJET}.")
            if not (d.get("State") or {}).get("Running"):
                raise Refus(409, f"{nom} est arrêté : Watchtower ne met à jour que les conteneurs allumés.")
            if str(labels.get(ETIQUETTE_WATCHTOWER) or "").strip().lower() == "false":
                raise Refus(409, f"{nom} porte l'étiquette {ETIQUETTE_WATCHTOWER}=false.")
            image, raison = image_pour_watchtower(str(config.get("Image") or ""))
            if raison:
                raise Refus(409, f"« Mettre à jour » absent : {raison}.")
            protege = protection(ligne["conteneur"], str(config.get("Image") or ""))
            if protege and not protege_confirme:
                raise Refus(409, f"Double confirmation demandée : {protege}.")
        except Refus as r:
            self.noter(f"refusé : {r.phrase}", nom, conteneur=(ligne or {}).get("conteneur"))
            raise
        ordre = {"id": ident, "nom": nom, "conteneur": ligne["conteneur"], "etat": "en_cours", "debut": maintenant(),
                 "debut_t": self._horloge(), "image_avant": str(d.get("Image") or ""), "id_avant": str(d.get("Id") or ""),
                 "image_param": image, "phrase": "mise à jour en cours…", "detail": "", "wt": "attente",
                 "protege": bool(protege)}
        self.ordres[ident] = ordre
        self._garder()
        self.noter("lancé", nom, conteneur=ligne["conteneur"], protege=bool(protege))
        t = asyncio.create_task(self._par_watchtower(ident, image))
        self._taches.add(t)
        t.add_done_callback(self._taches.discard)
        if self.reveil is not None:
            self.reveil.set()
        return dict(ordre)

    async def _par_watchtower(self, ident: str, image: str) -> None:
        try:
            r = await self.watchtower.mettre_a_jour(image)
        except ErreurWatchtower as exc:
            o = self.ordres.get(ident)
            if exc.conclut:
                self._finir(ident, "echec", f"{exc.phrase} : pas de mise à jour.")
            elif o and o.get("etat") == "en_cours":
                o.update(wt="perdu", detail=f"{exc.phrase} ; l'état réel est relu.")
                self._garder()
            return
        except Exception as exc:                               # noqa: BLE001 — jamais de tâche muette
            log.exception("Mise à jour de %s", ident)
            o = self.ordres.get(ident)
            if o and o.get("etat") == "en_cours":
                o.update(wt="perdu", detail=f"erreur ({exc.__class__.__name__}) ; l'état réel est relu.")
                self._garder()
            return
        finally:
            if self.reveil is not None:
                self.reveil.set()
        o = self.ordres.get(ident)
        if o and o.get("etat") == "en_cours":
            o.update(wt="fini", wt_resume=r)
            self._garder()

    def _finir(self, ident: str, etat: str, phrase: str) -> None:
        o = self.ordres.get(ident)
        if not o or o.get("etat") != "en_cours":
            return
        o.update(etat=etat, phrase=phrase, fin=maintenant(), fin_t=self._horloge())
        if etat == "fini":
            self.lignes.pop(ident, None)                       # à jour : la ligne quitte la liste
        self._garder()
        self.noter({"fini": "fini", "echec": "échec", "delai": "délai dépassé"}[etat] + " : " + phrase, o["nom"],
                   conteneur=o.get("conteneur"))

    async def suivre(self) -> None:
        """Fin d'une mise à jour, jugée à l'état réel chez Portainer : nouvelle image et conteneur en marche."""
        if not self.actif:
            return
        for ident, o in list(self.ordres.items()):
            if o.get("etat") != "en_cours":
                continue
            if self._horloge() - o.get("debut_t", 0) > DELAI_MAJ:
                self._finir(ident, "delai", "pas de réponse, voir Watchtower et Portainer.")
                continue
            try:
                d = await self.portainer.inspecter(o["conteneur"])
            except ErreurPortainer:
                continue
            if d is None:
                continue                                       # recréation en plein milieu : on attend
            neuve = str(d.get("Image") or "") not in ("", o.get("image_avant"))
            marche = bool((d.get("State") or {}).get("Running"))
            if neuve and marche:
                self._finir(ident, "fini", "mis à jour.")
                continue
            if o.get("wt") != "fini":
                continue                                       # Watchtower travaille encore (ou attend son verrou)
            r = o.get("wt_resume") or {}
            if not marche:
                self._finir(ident, "echec", "le conteneur n'est pas en marche après le passage de Watchtower : voir Portainer.")
            elif r.get("failed"):
                self._finir(ident, "echec", "Watchtower signale un échec (voir son journal) : image inchangée.")
            elif r.get("skipped") and not r.get("scanned"):
                self._finir(ident, "echec", "Watchtower a sauté le conteneur : il n'a pas pu lire l'image (identifiants des images privées dans "
                                            "config.json, registre injoignable ?), voir le journal de Watchtower : rien n'a changé.")
            elif r and not r.get("scanned"):
                self._finir(ident, "echec", "Watchtower n'a trouvé aucun conteneur en marche de cette image : rien n'a changé.")
            elif not neuve:
                self._finir(ident, "fini", "déjà à jour (Watchtower n'a pas trouvé d'image plus récente).")

    def vider_resultats(self) -> None:
        t = self._horloge()
        for ident in [k for k, o in self.ordres.items() if o.get("fin_t") and t - o["fin_t"] > RESULTAT_VISIBLE]:
            del self.ordres[ident]

    # ------------------------------------------------------------ pour l'écran
    def vue(self, lecture_seule: bool) -> dict:
        if not self.actif:
            return {"actif": False, "lignes": [], "nombre": 0}
        self.vider_resultats()
        t = self._horloge()
        sortie = []
        idents = list(self.lignes) + [k for k, o in self.ordres.items() if k not in self.lignes and o.get("fin_t")]
        for ident in idents:
            ligne = self.lignes.get(ident) or {"id": ident, "nom": self.ordres[ident]["nom"], "sorte": "maj", "phrase": ""}
            o = self.ordres.get(ident)
            ordre = {k: o.get(k) for k in ("etat", "phrase", "detail", "debut", "fin")} if o else None
            if o and o.get("etat") != "en_cours" and t - o.get("fin_t", t) > RESULTAT_VISIBLE:
                ordre = None
            pourquoi = self._bouton(ligne, lecture_seule) if ligne.get("sorte") == "maj" and ident in self.lignes else ""
            sortie.append({"id": ident, "nom": ligne.get("nom"), "sorte": ligne.get("sorte"), "phrase": ligne.get("phrase", ""),
                           "version": ligne.get("version", ""), "version_neuve": ligne.get("version_neuve", ""),
                           # 0.18.1 : la protection ne se dit que là où il y a un bouton à confirmer
                           "protege": ligne.get("protege", "") if ligne.get("sorte") == "maj" else "", "ordre": ordre,
                           "bouton": ligne.get("sorte") == "maj" and ident in self.lignes and not pourquoi,
                           "pourquoi": pourquoi})
        sortie.sort(key=lambda x: (x["sorte"] != "maj", (x["nom"] or "").lower()))
        a_faire = [x for x in sortie if x["id"] in self.lignes]
        return {"actif": True, "lignes": sortie, "nombre": len(a_faire), "lu_le": self.lu_le, "erreur": self.erreur,
                "non_verifiees": self.non_verifiees, "en_verification": self.en_verification,
                "en_cours": self.en_cours()}
