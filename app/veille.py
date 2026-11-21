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

0.12 (santé des tâches de fond) : la réponse JSON d'une sonde /health est lue (`taches`, `copie_base`, `version_socle`,
voir sante.py) ; une tuile peut être « à surveiller » (orange), jamais comptée comme en panne. Le jeton commun part
avec la sonde des seules tuiles « sauvegarde: true » (les applis maison), jamais ailleurs. La veille note l'heure de sa
dernière boucle : au-delà de 10 min, l'écran dit qu'elle est arrêtée. Troisième petit fichier : vus.json (« Vu »).

0.13 (versions) : la version en service d'une tuile est lue dans son /health (`version`) ou, pour une tuile tierce, à son
adresse `version_url:` (sans jeton) ; un changement est ajouté au journal des versions (versions.py). La dernière
version publiée (tâche « versions-publiees ») est jointe à chaque tuile qui a un `depot:` ; jamais d'orange pour un retard.
"""
from __future__ import annotations

import asyncio
import inspect
import math
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from . import maison, sante, versions
from .sauvegardes import base as base_maison
from .services import Fichier, cle

log = logging.getLogger("anneau.veille")

ECHECS = 3          # échecs de suite avant d'ouvrir une panne
REUSSITES = 3       # réussites de suite avant de la clore
GARDEES = 30        # pannes closes gardées pour mémoire
ARRETEE = 600       # 0.12 : secondes sans boucle de veille finie avant de dire « la veille est arrêtée »
TAILLE_SANTE = 64 * 1024   # 0.12 : une réponse /health plus grosse n'est pas lue


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
    except Exception:  # noqa: BLE001 — 0.10.2 : toute erreur (adresse invalide comprise) vaut « ne répond pas »
        return False, None


async def repond_avec_sante(adresse: str, jeton: str = "") -> tuple[bool, int | None, dict | None]:
    """0.12 : la sonde de la veille. Comme `repond`, et rend en plus la réponse JSON (un /health) quand il y en a une.
    Le jeton commun n'est joint que si la veille le donne (tuiles « sauvegarde: true » seulement)."""
    debut = time.monotonic()
    entetes = {"User-Agent": "anneau"}
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    try:
        async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=False) as c:
            r = await c.get(adresse, headers=entetes)
    except Exception:  # noqa: BLE001 — toute erreur vaut « ne répond pas »
        return False, None, None
    delai = int((time.monotonic() - debut) * 1000)
    corps = None
    if r.status_code == 200 and "json" in r.headers.get("content-type", "") and len(r.content) <= TAILLE_SANTE:
        try:
            corps = r.json()
        except ValueError:
            corps = None
    return r.status_code < 500, delai, corps if isinstance(corps, dict) else None


def _accepte_jeton(sonder) -> bool:
    """La sonde sait-elle recevoir le jeton ? (les fausses sondes des tests anciens n'ont que l'adresse)"""
    try:
        params = inspect.signature(sonder).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == "jeton" or p.kind is inspect.Parameter.VAR_KEYWORD for p in params)


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
    except Exception:  # noqa: BLE001 — 0.10.2 : on n'a pas pu le savoir
        return None


class Veille:
    def __init__(self, data: Path, fichier: Fichier, ha_attendu: bool = False,
                 sonder: Callable[..., Awaitable[tuple]] = repond_avec_sante,
                 horloge: Callable[[], float] = time.monotonic,
                 examiner: Callable[[str], Awaitable[str | None]] = examiner,
                 jeton: Callable[[], str] = maison.jeton_a_envoyer,
                 instant: Callable[[], datetime] = lambda: datetime.now().astimezone(),
                 versionner: Callable[[str], Awaitable[str | None]] = versions.lire_version_url):
        self.data, self.fichier, self.ha_attendu = data, fichier, ha_attendu
        self._sonder, self._horloge, self._examiner = sonder, horloge, examiner
        self._jeton, self._instant = jeton, instant          # 0.12 : jeton commun (applis maison), heure murale
        self._sonder_jeton = _accepte_jeton(sonder)
        self.sante: dict[str, dict] = {}        # 0.12 : clé de service → santé lue dans son /health (sante.lire)
        self.vus = sante.Vus(data)              # 0.12 : les « Vu » des tuiles orange
        self._versionner = versionner           # 0.13 : lit la version_url d'une tuile tierce
        self.versions = versions.EnService(data)   # 0.13 : versions en service et journal des changements
        from . import __version__ as _moi           # 0.13 : la mise à jour de l'Anneau lui-même entre aussi au journal
        self.versions.noter("@anneau", "L'Anneau", _moi)
        self.eteints: set[str] = set()          # 0.17 : tuiles dont le conteneur est arrêté chez Portainer (exited) : « éteint »
        self.refus: dict[str, str] = {}         # adresse → raison pour laquelle le service interdit le cadre (vide : il l'accepte)
        self._tours = 0
        self.suivi: dict[str, dict] = {}        # clé de sonde → échecs, réussites, état, depuis, délai
        self.pannes: dict[str, dict] = {}       # clé de cause → panne ouverte
        self.closes: list[dict] = []
        self.a_notifier: list[dict] = []        # ouvertures et clôtures pas encore dites à Home Assistant
        self.derniere_sonde: str = ""
        self.machines: dict = {"volumes": [], "mises_a_jour": [], "recu_le": "", "recu_a": None}
        self.demarrage = horloge()
        self.boucle_a, self.boucle_le = self.demarrage, maintenant()   # 0.12 : dernière boucle de veille finie
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
    def _ouvrir(self, c: str, sorte: str, nom: str, phrase: str, famille: str = "",
                avant: str = "", etat: str = "") -> None:
        """avant → etat : le passage dit sur le téléphone (« Grimmory : répond → ne répond plus »)."""
        if c in self.pannes:
            return
        p = {"cle": c, "sorte": sorte, "nom": nom, "phrase": phrase, "famille": famille,
             "avant": avant, "etat": etat,
             "ouverte_le": maintenant(), "prise_en_compte_le": ""}
        self.pannes[c] = p
        self.a_notifier.append({"quoi": "ouverte", **p})
        self._garder()

    def _clore(self, c: str, phrase: str, etat_fin: str = "") -> None:
        p = self.pannes.pop(c, None)
        if p is None:
            return
        close = {**p, "close_le": maintenant(), "phrase_fin": phrase, "etat_fin": etat_fin}
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

    def _jeton_pour(self, s) -> str:
        """0.12 : le jeton commun ne part qu'avec la sonde /health d'une tuile « sauvegarde: true » (appli maison)."""
        if s.sauvegarde is not True or not base_maison(s.sonde):
            return ""
        return self._jeton() or ""

    def _sonde(self, adresse: str, jeton: str = ""):
        if self._sonder_jeton:
            return self._sonder(adresse, jeton=jeton)
        return self._sonder(adresse)

    async def tour(self) -> None:
        """Un tour : toutes les machines et tous les services, en même temps."""
        f = self.fichier
        cibles = [("machine:" + m.cle, m.sonde, False, "") for m in f.machines if m.sonde] \
            + [("service:" + s.cle, s.a_sonder, s.arret_attendu or s.cle in self.eteints, self._jeton_pour(s)) for s in f.services]
        resultats = await asyncio.gather(*(self._sonde(adresse, j) for _, adresse, _, j in cibles), return_exceptions=True)
        lues = {}                                                           # 0.13 : clé de tuile → version lue ce tour-ci
        for (c, _, attendu, _), r in zip(cibles, resultats):
            r = (False, None) if isinstance(r, BaseException) else tuple(r)   # 0.10.2 : une sonde en erreur ne prive pas les autres
            vivant, delai = r[0], r[1]
            self._noter(c, vivant, delai, attendu)
            if c.startswith("service:") and vivant and len(r) > 2:          # 0.12 : la santé lue dans le /health
                lue = sante.lire(r[2])
                if lue is None:
                    self.sante.pop(c[len("service:"):], None)               # appli sans ces champs : rien ne change
                else:
                    self.sante[c[len("service:"):]] = {**lue, "lu_le": maintenant()}
                lues[c[len("service:"):]] = versions.version_lue(r[2])
        await self._versions(lues)
        connues = {s.cle for s in f.services}
        for k in [k for k in self.sante if k not in connues]:
            del self.sante[k]
        self.derniere_sonde = maintenant()
        await self._cadres()
        self._pannes_de_sonde()
        self._silence_ha()
        t = self._instant()
        self.vus.menage({k: emp for k in connues if (emp := sante.empreinte(sante.defauts(self.sante.get(k), t)))})
        self.boucle_a, self.boucle_le = self._horloge(), maintenant()

    async def repond(self, s) -> bool:
        """0.17 : la tuile répond-elle maintenant ? (suivi d'un ordre donné à Portainer : /health qui répond)"""
        try:
            r = await self._sonde(s.a_sonder, self._jeton_pour(s))
        except Exception:                      # noqa: BLE001
            return False
        return bool(r and r[0])

    # ------------------------------------------------------------ versions (0.13)
    async def _versions(self, lues: dict[str, str | None]) -> None:
        """Version en service de chaque tuile vivante : sa version_url si elle en a une, sinon son /health.
        Un changement va au journal (une seule fois : la nouvelle version devient la connue)."""
        vivantes = {s.cle: s for s in self.fichier.services if self.suivi.get("service:" + s.cle, {}).get("etat") == "ok"}
        a_lire = [s for s in vivantes.values() if s.version_url]
        for s, v in zip(a_lire, await asyncio.gather(*(self._versionner(s.version_url) for s in a_lire), return_exceptions=True)):
            lues[s.cle] = None if isinstance(v, BaseException) else versions.nettoyer(v)
        for k, s in vivantes.items():
            entree = self.versions.noter(k, s.nom, lues.get(k))
            if entree:
                log.info("%s : %s → %s", s.nom, entree["de"], entree["vers"])
        self.versions.oublier_sauf({s.cle for s in self.fichier.services})

    def versions_des_tuiles(self) -> list[dict]:
        """Pour Réglages › Versions et la fiche : en service, dernière publiée, mise à jour le."""
        depots = versions.publiees(self.data)["depots"]
        sortie = []
        for s in self.fichier.services:
            en_service = self.versions.version(s.cle)
            publiee = (depots.get(s.depot) or {}).get("version") if s.depot else None
            sortie.append({"nom": s.nom, "cle": s.cle, "famille": s.famille, "depot": s.depot, "version": en_service,
                           "publiee": publiee, "a_jour": versions.a_jour(en_service, publiee),
                           "mise_a_jour_le": self.versions.mise_a_jour_le(s.cle),
                           "phrase": versions.phrase(en_service, publiee)})
        return sortie

    # ------------------------------------------------------------ « à surveiller » (0.12)
    def defauts(self, cle_service: str) -> list[dict]:
        return sante.defauts(self.sante.get(cle_service), self._instant())

    def marquer_vu(self, cle_service: str) -> bool:
        """« Vu » : la tuile n'est plus orange tant que ses défauts restent les mêmes."""
        emp = sante.empreinte(self.defauts(cle_service))
        if not emp:
            return False
        self.vus.marquer(cle_service, emp, maintenant())
        return True

    def veille_anneau(self) -> dict:
        """L'Anneau se surveille : l'heure de sa dernière boucle de veille finie, et si elle est trop vieille."""
        age = int(self._horloge() - self.boucle_a)
        return {"derniere": self.boucle_le, "age": age, "arretee": age > ARRETEE}

    async def _cadres(self) -> None:
        """Quels services interdisent d'être affichés dans une autre page ? Relu tous les dix tours,
        et tout de suite pour une adresse qu'on n'a jamais réussi à lire."""
        self._tours += 1
        adresses = {a for s in self.fichier.services if s.cadre is None for a in (s.locale, s.privee) if a}
        a_lire = sorted(adresses if self._tours % 10 == 1 else adresses - set(self.refus))
        for adresse, raison in zip(a_lire, await asyncio.gather(*(self._examiner(a) for a in a_lire), return_exceptions=True)):
            if raison is not None and not isinstance(raison, BaseException):
                self.refus[adresse] = raison

    def _pannes_de_sonde(self) -> None:
        f = self.fichier
        en_panne = {m.nom for m in f.machines if self.suivi.get("machine:" + m.cle, {}).get("etat") == "panne"}
        for m in f.machines:
            c = "machine:" + m.cle
            if m.nom in en_panne:
                self._ouvrir(c, "machine", m.nom, f"{m.nom} ne répond plus", m.famille, "répond", "ne répond plus")
            elif self.suivi.get(c, {}).get("etat") == "ok":
                self._clore(c, f"{m.nom} répond de nouveau", "répond de nouveau")
        for s in f.services:
            c = "service:" + s.cle
            etat = self.suivi.get(c, {}).get("etat")
            if etat == "panne" and s.machine not in en_panne:
                self._ouvrir(c, "service", s.nom, f"{s.nom} ne répond plus", s.famille, "répond", "ne répond plus")
            elif etat == "panne":                  # la machine est tombée : c'est sa panne, pas celle du service
                if c in self.pannes:
                    self.pannes.pop(c)
                    self._garder()
            elif etat in ("ok", "eteint"):
                self._clore(c, f"{s.nom} répond de nouveau", "répond de nouveau")
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
                pourcentage = float(v.get("pourcentage"))
                if not math.isfinite(pourcentage):       # 0.10.4 : un NaN cassait /api/etat
                    raise ValueError("pourcentage non fini")
                pourcentage = round(pourcentage, 1)
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
                pct = str(v['pourcentage']).replace('.', ',')
                self._ouvrir(c, "volume", nom, f"{nom} est plein à {pct} %", famille, "sous le seuil", f"plein à {pct} %")
            else:
                pct = str(v['pourcentage']).replace('.', ',')
                self._clore(c, f"{nom} est redescendu à {pct} %", f"{pct} %")
        self._clore("ha", "Home Assistant envoie de nouveau son état", "envoie de nouveau son état")
        return self.pour_ha()

    def _silence_ha(self) -> None:
        if not self.ha_attendu:
            return
        reference = self.machines["recu_a"] if self.machines["recu_a"] is not None else self.demarrage
        if self._horloge() - reference > self.fichier.silence_ha * 60:
            self._ouvrir("ha", "ha", "Home Assistant", "Home Assistant est muet", self.fichier.famille_ha,
                        "envoie son état", "muet")

    def pour_ha(self) -> dict:
        """Ce que Home Assistant doit dire sur le téléphone : une fois par ouverture, une fois par clôture."""
        dire, self.a_notifier = self.a_notifier, []
        # Chaque ligne dit le passage d'un état à l'autre : « Grimmory : répond → ne répond plus ».
        # Une panne ouverte puis close entre deux envois ne fait qu'une ligne, dans les closes :
        # « Grimmory : ne répond plus → répond de nouveau (coupure brève) ».
        closes_ici = {p["cle"] for p in dire if p["quoi"] == "close"}
        ouvertes, closes = [], []
        for p in dire:
            if p["quoi"] == "ouverte" and p["cle"] not in closes_ici:
                ouvertes.append(f"{p['nom']} : {p['avant']} → {p['etat']}" if p.get("etat") else p["phrase"])
            elif p["quoi"] == "close":
                ligne = f"{p['nom']} : {p['etat']} → {p['etat_fin']}" if p.get("etat") and p.get("etat_fin") else p["phrase_fin"]
                if p["sorte"] != "ha" and any(o["quoi"] == "ouverte" and o["cle"] == p["cle"] for o in dire):
                    ligne += " (coupure brève)"
                closes.append(ligne)
        return {"pannes": len(self.pannes), "ouvertes": ouvertes, "closes": closes,
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
        t = self._instant()
        en_panne = {m.nom for m in f.machines if self.suivi.get("machine:" + m.cle, {}).get("etat") == "panne"}
        vers = {v["cle"]: v for v in self.versions_des_tuiles()}      # 0.13
        familles = []
        for fam in f.familles:
            services = []
            for s in (x for x in f.services if x.famille == fam["nom"]):
                suivi = self.suivi.get("service:" + s.cle, {})
                adresse = self._adresse(s, prive, https, hote)
                d = sante.defauts(self.sante.get(s.cle), t)
                vu = self.vus.est_vu(s.cle, sante.empreinte(d))
                orange = bool(d) and not vu and suivi.get("etat") == "ok"   # le service en panne : la panne passe devant
                services.append({
                    "nom": s.nom, "cle": s.cle, "icone": s.icone, "etat": suivi.get("etat", "inconnu"),
                    "depuis": suivi.get("depuis", ""), "delai": suivi.get("delai"), "adresse": adresse,
                    "cadre": not (pourquoi := self._hors_cadre(s, adresse, https, s.privee if adresse == s.privee else s.locale)), "hors_cadre": pourquoi,
                    "machine": s.machine, "machine_en_panne": s.machine in en_panne,
                    # 0.12 : santé des tâches de fond ; « surveiller » = orange, la phrase s'écrit sur la tuile
                    "sante": self.sante.get(s.cle), "defauts": d, "surveiller": orange, "vu": bool(d) and vu,
                    "phrase": sante.phrase(d) if orange else "",
                    # 0.13 : versions (dites en mots dans la fiche, jamais en couleur)
                    "version": vers[s.cle]["version"], "version_publiee": vers[s.cle]["publiee"],
                    "a_jour": vers[s.cle]["a_jour"], "version_phrase": vers[s.cle]["phrase"]})
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
        surveiller = [{"cle": x["cle"], "nom": x["nom"], "famille": fam["nom"], "famille_cle": fam["cle"], "phrase": x["phrase"]}
                      for fam in familles for x in fam["services"] if x["surveiller"]]
        return {"familles": familles, "pannes": pannes, "a_faire": a_faire, "closes": self.closes[:5],
                "surveiller": surveiller, "veille": self.veille_anneau(),
                "volumes": self.machines["volumes"],
                "fraicheur": {"sonde": self.derniere_sonde, "ha_attendu": self.ha_attendu, "ha_recu_le": self.machines["recu_le"],
                              "ha_age": ha_age, "fichier_modifie_le": f.modifie_le, "fichier_lu_le": f.lu_le,
                              "exemple": f.exemple, "erreurs": list(f.erreurs), "seuil_disque": f.seuil_disque, "silence_ha": f.silence_ha}}
