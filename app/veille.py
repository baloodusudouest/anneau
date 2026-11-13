"""La veille : qui répond, qui ne répond plus, et ce qu'on appelle une panne.

Règles (dossier, décisions du 13/11/2026) :
- un service est interrogé chaque minute ; toute réponse HTTP en dessous de 500 compte comme vivante
  (une page de connexion aussi) ;
- TROIS échecs de suite ouvrent une panne, TROIS réussites de suite la closent ;
- un service marqué « arrêt attendu » n'est jamais en panne : il est « éteint » ;
- si une machine ne répond plus, la panne est la sienne : ses services ne comptent pas en plus ;
- un volume plus plein que le seuil du fichier est une panne, tant qu'il le reste ;
- Home Assistant envoie l'état des machines ; sans envoi depuis cinq minutes, c'est lui la panne.

L'Anneau n'écrit que deux petits fichiers dans son dossier (pannes en cours, dernières pannes closes) :
le NAS qui l'héberge est presque plein, il ne garde aucun historique de sondes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from .services import Fichier, cle

log = logging.getLogger("anneau.veille")

ECHECS = 3          # échecs de suite avant d'ouvrir une panne
REUSSITES = 3       # réussites de suite avant de la clore
SILENCE_HA = 300    # secondes sans envoi de Home Assistant avant de le dire muet
GARDEES = 30        # pannes closes gardées pour mémoire


def maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def repond(adresse: str) -> tuple[bool, int | None]:
    """Vrai si le service répond (même par une demande de connexion). Rend aussi le délai en millisecondes."""
    debut = time.monotonic()
    try:
        # verify=False : les services de la maison ont souvent un certificat fait maison
        async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=False) as c:
            r = await c.get(adresse, headers={"User-Agent": "anneau"})
        return r.status_code < 500, int((time.monotonic() - debut) * 1000)
    except (httpx.HTTPError, OSError, ValueError):
        return False, None


def interdit_le_cadre(entetes) -> str:
    """Ce que le service dit de son affichage dans une autre page. Vide : il ne l'interdit pas."""
    for regle in (entetes.get("content-security-policy") or "").split(";"):
        mots = regle.strip().split()
        if mots and mots[0].lower() == "frame-ancestors":
            if not any(m in ("*", "http:", "https:") for m in mots[1:]):
                return "Content-Security-Policy : frame-ancestors"
    if (entetes.get("x-frame-options") or "").strip():
        return "X-Frame-Options : " + entetes["x-frame-options"].strip().upper()
    return ""


async def examiner(adresse: str) -> str | None:
    """Lit la page d'accueil du service (en suivant ses renvois) pour savoir s'il interdit le cadre.
    Rend la raison, vide s'il ne l'interdit pas, None si on n'a pas pu le savoir."""
    try:
        async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=True, max_redirects=5) as c:
            r = await c.get(adresse, headers={"User-Agent": "anneau", "Accept": "text/html"})
        return interdit_le_cadre(r.headers)
    except (httpx.HTTPError, OSError, ValueError):
        return None


class Veille:
    def __init__(self, data: Path, fichier: Fichier, ha_attendu: bool = False,
                 sonder: Callable[[str], Awaitable[tuple[bool, int | None]]] = repond,
                 horloge: Callable[[], float] = time.monotonic,
                 examiner: Callable[[str], Awaitable[str | None]] = examiner):
        self.data, self.fichier, self.ha_attendu = data, fichier, ha_attendu
        self._sonder, self._horloge, self._examiner = sonder, horloge, examiner
        self.refus: dict[str, str] = {}         # adresse → raison pour laquelle le service interdit le cadre (vide : il l'accepte)
        self._tours = 0
        self.suivi: dict[str, dict] = {}        # clé de sonde → échecs, réussites, état, depuis, délai
        self.pannes: dict[str, dict] = {}       # clé de cause → panne ouverte
        self.closes: list[dict] = []
        self.a_notifier: list[dict] = []        # ouvertures et clôtures pas encore dites à Home Assistant
        self.derniere_sonde: str = ""
        self.machines: dict = {"volumes": [], "mises_a_jour": [], "recu_le": "", "recu_a": None}
        self.demarrage = horloge()
        self._relire()

    # ------------------------------------------------------------ mémoire sur disque
    def _relire(self) -> None:
        try:
            memoire = json.loads((self.data / "pannes.json").read_text(encoding="utf-8"))
            self.pannes = {p["cle"]: p for p in memoire.get("ouvertes", [])}
            self.closes = memoire.get("closes", [])[:GARDEES]
        except (OSError, ValueError, KeyError, TypeError):
            self.pannes, self.closes = {}, []
        for c, p in self.pannes.items():        # une panne ouverte avant le redémarrage reste une panne
            if p["sorte"] in ("service", "machine"):
                self.suivi[c] = {"echecs": ECHECS, "reussites": 0, "etat": "panne", "depuis": p["ouverte_le"], "delai": None}

    def _garder(self) -> None:
        try:
            self.data.mkdir(parents=True, exist_ok=True)
            (self.data / "pannes.json").write_text(json.dumps({"ouvertes": list(self.pannes.values()), "closes": self.closes[:GARDEES]},
                                                               ensure_ascii=False), encoding="utf-8")
        except OSError as exc:                  # disque plein : la veille continue, en mémoire
            log.warning("Pannes non enregistrées sur disque : %s", exc)

    # ------------------------------------------------------------ ouvrir, clore
    def _ouvrir(self, c: str, sorte: str, nom: str, phrase: str, famille: str = "") -> None:
        if c in self.pannes:
            return
        p = {"cle": c, "sorte": sorte, "nom": nom, "phrase": phrase, "famille": famille,
             "ouverte_le": maintenant(), "prise_en_compte_le": ""}
        self.pannes[c] = p
        self.a_notifier.append({"quoi": "ouverte", **p})
        self._garder()

    def _clore(self, c: str, phrase: str) -> None:
        p = self.pannes.pop(c, None)
        if p is None:
            return
        close = {**p, "close_le": maintenant(), "phrase_fin": phrase}
        self.closes.insert(0, close)
        del self.closes[GARDEES:]
        self.a_notifier.append({"quoi": "close", **close})
        self._garder()

    def prendre_en_compte(self, c: str) -> bool:
        if c not in self.pannes:
            return False
        self.pannes[c]["prise_en_compte_le"] = maintenant()
        self._garder()
        return True

    # ------------------------------------------------------------ la sonde
    def _noter(self, c: str, vivant: bool, delai: int | None, attendu: bool = False) -> str:
        s = self.suivi.setdefault(c, {"echecs": 0, "reussites": 0, "etat": "inconnu", "depuis": maintenant(), "delai": None})
        avant = s["etat"]
        s["delai"] = delai
        if vivant:
            s["reussites"], s["echecs"] = s["reussites"] + 1, 0
            if avant != "panne" or s["reussites"] >= REUSSITES:
                s["etat"] = "ok"
        else:
            s["echecs"], s["reussites"] = s["echecs"] + 1, 0
            if attendu:
                s["etat"] = "eteint"
            elif s["echecs"] >= ECHECS:
                s["etat"] = "panne"
        if s["etat"] != avant:
            s["depuis"] = maintenant()
        return s["etat"]

    async def tour(self) -> None:
        """Un tour : toutes les machines et tous les services, en même temps."""
        f = self.fichier
        cibles = [("machine:" + m.cle, m.sonde, False) for m in f.machines if m.sonde] \
            + [("service:" + s.cle, s.a_sonder, s.arret_attendu) for s in f.services]
        resultats = await asyncio.gather(*(self._sonder(adresse) for _, adresse, _ in cibles))
        for (c, _, attendu), (vivant, delai) in zip(cibles, resultats):
            self._noter(c, vivant, delai, attendu)
        self.derniere_sonde = maintenant()
        await self._cadres()
        self._pannes_de_sonde()
        self._silence_ha()

    async def _cadres(self) -> None:
        """Quels services interdisent d'être affichés dans une autre page ? Relu tous les dix tours,
        et tout de suite pour une adresse qu'on n'a jamais réussi à lire."""
        self._tours += 1
        adresses = {a for s in self.fichier.services if s.cadre is None for a in (s.locale, s.privee) if a}
        a_lire = sorted(adresses if self._tours % 10 == 1 else adresses - set(self.refus))
        for adresse, raison in zip(a_lire, await asyncio.gather(*(self._examiner(a) for a in a_lire))):
            if raison is not None:
                self.refus[adresse] = raison

    def _pannes_de_sonde(self) -> None:
        f = self.fichier
        en_panne = {m.nom for m in f.machines if self.suivi.get("machine:" + m.cle, {}).get("etat") == "panne"}
        for m in f.machines:
            c = "machine:" + m.cle
            if m.nom in en_panne:
                self._ouvrir(c, "machine", m.nom, f"{m.nom} ne répond plus", m.famille)
            elif self.suivi.get(c, {}).get("etat") == "ok":
                self._clore(c, f"{m.nom} répond de nouveau")
        for s in f.services:
            c = "service:" + s.cle
            etat = self.suivi.get(c, {}).get("etat")
            if etat == "panne" and s.machine not in en_panne:
                self._ouvrir(c, "service", s.nom, f"{s.nom} ne répond plus", s.famille)
            elif etat == "panne":                  # la machine est tombée : c'est sa panne, pas celle du service
                if c in self.pannes:
                    self.pannes.pop(c)
                    self._garder()
            elif etat in ("ok", "eteint"):
                self._clore(c, f"{s.nom} répond de nouveau")
        connus = {"machine:" + m.cle for m in f.machines} | {"service:" + s.cle for s in f.services}
        for c in [c for c, p in self.pannes.items() if p["sorte"] in ("service", "machine") and c not in connus]:
            self.pannes.pop(c)                     # service retiré du fichier : sa panne n'a plus d'objet
            self._garder()

    # ------------------------------------------------------------ Home Assistant
    def recevoir(self, envoi: dict) -> dict:
        """L'état des machines, envoyé par Home Assistant. Rend ce qu'il doit notifier."""
        volumes = []
        for v in envoi.get("volumes") or []:
            if not isinstance(v, dict) or not str(v.get("nom", "")).strip():
                continue
            try:
                pourcentage = round(float(v.get("pourcentage")), 1)
            except (TypeError, ValueError):
                pourcentage = None                 # « indisponible » : ni panne, ni vert
            volumes.append({"machine": str(v.get("machine", "")).strip(), "nom": str(v["nom"]).strip(),
                            "pourcentage": pourcentage, "etat": str(v.get("etat", "")).strip()})
        mises = [{"machine": str(m.get("machine", "")).strip(), "version": str(m.get("version", "")).strip()}
                 for m in (envoi.get("mises_a_jour") or []) if isinstance(m, dict) and m.get("disponible") in (True, "on", "true", "True")]
        self.machines = {"volumes": volumes, "mises_a_jour": mises, "recu_le": maintenant(), "recu_a": self._horloge()}
        vus = set()
        for v in volumes:
            c = "volume:" + cle(v["machine"] + " " + v["nom"])
            vus.add(c)
            nom = f"{v['nom']} de {v['machine']}" if v["machine"] else v["nom"]
            if v["pourcentage"] is None:
                continue                           # on ne sait pas : on ne change rien
            if v["pourcentage"] >= self.fichier.seuil_disque:
                famille = next((m.famille for m in self.fichier.machines if m.nom == v["machine"]), "")
                self._ouvrir(c, "volume", nom, f"{nom} est plein à {str(v['pourcentage']).replace('.', ',')} %", famille)
            else:
                self._clore(c, f"{nom} est redescendu à {str(v['pourcentage']).replace('.', ',')} %")
        self._clore("ha", "Home Assistant envoie de nouveau son état")
        return self.pour_ha()

    def _silence_ha(self) -> None:
        if not self.ha_attendu:
            return
        reference = self.machines["recu_a"] if self.machines["recu_a"] is not None else self.demarrage
        if self._horloge() - reference > SILENCE_HA:
            self._ouvrir("ha", "ha", "Home Assistant", "Home Assistant est muet", self.fichier.famille_ha)

    def pour_ha(self) -> dict:
        """Ce que Home Assistant doit dire sur le téléphone : une fois par ouverture, une fois par clôture."""
        dire, self.a_notifier = self.a_notifier, []
        return {"pannes": len(self.pannes),
                "ouvertes": [p["phrase"] for p in dire if p["quoi"] == "ouverte"],
                "closes": [p["phrase_fin"] for p in dire if p["quoi"] == "close"],
                "liste": [p["phrase"] for p in self.pannes.values()][:10]}

    # ------------------------------------------------------------ ce que l'écran affiche
    def _hors_cadre(self, s, adresse: str, https: bool, examinee: str) -> str:
        """Pourquoi ce service ne s'affiche pas dans l'Anneau ; vide : il s'y affiche."""
        if https and adresse.startswith("http://"):
            return "son adresse est en http et l'Anneau est ouvert en https"
        if s.cadre is False:
            return "le fichier des services le veut ainsi (cadre: false)"
        if s.cadre is None and self.refus.get(examinee):
            return f"il interdit d'être affiché dans une autre page ({self.refus[examinee]})"
        return ""

    def _adresse(self, s, prive: bool, https: bool, hote: str) -> str:
        """L'adresse à donner au navigateur. L'adresse du réseau privé si l'Anneau est ouvert par là ; sinon la locale,
        où l'hôte de la maison est remplacé par celui qui a servi à ouvrir l'Anneau : le service reste ainsi « du même
        site » que l'Anneau, sans quoi le navigateur refuse son cookie de connexion dans le cadre."""
        if prive and s.privee:
            return s.privee
        local = self.fichier.hote_local
        if local and hote and hote != local and not https:
            morceaux = urlsplit(s.locale)
            if morceaux.hostname == local:
                return urlunsplit(morceaux._replace(netloc=hote + (f":{morceaux.port}" if morceaux.port else "")))
        return s.locale

    def etat(self, prive: bool = False, https: bool = False, hote: str = "") -> dict:
        f = self.fichier
        en_panne = {m.nom for m in f.machines if self.suivi.get("machine:" + m.cle, {}).get("etat") == "panne"}
        familles = []
        for fam in f.familles:
            services = []
            for s in (x for x in f.services if x.famille == fam["nom"]):
                suivi = self.suivi.get("service:" + s.cle, {})
                adresse = self._adresse(s, prive, https, hote)
                services.append({
                    "nom": s.nom, "cle": s.cle, "icone": s.icone, "etat": suivi.get("etat", "inconnu"),
                    "depuis": suivi.get("depuis", ""), "delai": suivi.get("delai"), "adresse": adresse,
                    "cadre": not (pourquoi := self._hors_cadre(s, adresse, https, s.privee if adresse == s.privee else s.locale)), "hors_cadre": pourquoi,
                    "machine": s.machine, "machine_en_panne": s.machine in en_panne})
            etats = {x["etat"] for x in services}
            familles.append({**fam, "services": services,
                             "etat": "panne" if "panne" in etats else "ok" if etats & {"ok", "eteint"} else "inconnu"})
        a_faire = [{"cle": "maj:" + cle(m["machine"]), "sorte": "systeme", "famille": "",
                    "phrase": f"Mise à jour du système disponible pour {m['machine']}" + (f" ({m['version']})" if m["version"] else "")}
                   for m in self.machines["mises_a_jour"]]
        pannes = sorted(self.pannes.values(), key=lambda p: p["ouverte_le"])
        touchees = {p["famille"] for p in pannes if p["famille"]}
        for fam in familles:                       # une machine, un volume ou Home Assistant en panne colore sa famille
            if fam["nom"] in touchees:
                fam["etat"] = "panne"
        ha_age = None if self.machines["recu_a"] is None else int(self._horloge() - self.machines["recu_a"])
        return {"familles": familles, "pannes": pannes, "a_faire": a_faire, "closes": self.closes[:5],
                "volumes": self.machines["volumes"],
                "fraicheur": {"sonde": self.derniere_sonde, "ha_attendu": self.ha_attendu, "ha_recu_le": self.machines["recu_le"],
                              "ha_age": ha_age, "fichier_modifie_le": f.modifie_le, "fichier_lu_le": f.lu_le,
                              "exemple": f.exemple, "erreurs": list(f.erreurs), "seuil_disque": f.seuil_disque}}
