"""0.17 : allumer, éteindre et mettre à jour un conteneur depuis la fiche de sa tuile (Portainer CE, et Watchtower
pour la mise à jour depuis la 0.17.1).

Décisions de Julien du 21/11/2026 (dossier et avis du conseil, docs/ajout-0.17.0.md et docs/conseil-0.17.0.md) :
- seules les tuiles marquées `conteneur: <container_name>` dans services.yaml ont ces boutons (liste blanche, format vérifié
  à la lecture) ; le nom du conteneur n'est JAMAIS pris dans la requête : la route reçoit la clé de la tuile ;
- liste d'interdits, insensible à la casse, appliquée au champ ET au nom réel renvoyé par Portainer ;
- étiquette `com.docker.compose.project=homelab` exigée sur le conteneur ;
- 0.17.1 (21/11/2026) : « Mettre à jour » passe par l'API HTTP de Watchtower (POST /v1/update?image=<dépôt/image>,
  en-tête Authorization: Bearer <jeton>) : dans Portainer CE, dès qu'un réglage « Hide … for non-administrators » est
  actif (obligatoire pour la sécurité de la clé « anneau »), la recréation est interdite aux non-admins. Allumer et
  Éteindre restent par Portainer. L'image (Config.Image, sans l'étiquette) et son empreinte avant sont lues par
  Portainer ; Watchtower met à jour les conteneurs EN MARCHE de cette image (un conteneur arrêté est ignoré) ; un
  conteneur qui porte com.centurylinklabs.watchtower.enable=false n'a pas le bouton. La recréation par Portainer
  (route recreate) n'est plus utilisée ;
- on ne se fie jamais à la réponse d'un ordre (leçon du 13/11/2026 : une mise à jour qui dépasse le délai « échoue » en
  réussissant) : l'état réel est relu (conteneur running + /health qui répond, ou exited) ; au-delà de 10 min :
  « pas de réponse, voir Portainer » ;
- l'ordre en cours est gardé sur le disque (conteneurs.json) : il survit à un redémarrage de l'Anneau ;
- chaque ordre (refusé, lancé, fini) est noté dans le journal des écritures (journal-ecritures.jsonl, JSON lignes :
  quand, quoi, tuile, résultat) ; jamais de secret.

La clé d'API (ANNEAU_PORTAINER_CLE, en-tête X-API-Key) ne sort que vers Portainer, et le jeton de Watchtower
(ANNEAU_WATCHTOWER_JETON, en-tête Authorization) que vers Watchtower : jamais dans un journal, une page, une réponse,
ni la sauvegarde.

Watchtower (fork nickfedor/watchtower 1.19.0, d'après sa documentation et son code, pkg/api) :
- /v1/update n'accepte que POST (GET : 405) ; 200 avec un résumé JSON {"summary": {"scanned", "updated", "failed",
  "restarted", "skipped"}, …} quand la mise à jour est FINIE ; 401 jeton absent ou faux ; 429 trop de demandes (60/min
  par adresse) ; 503 demande abandonnée en attendant le verrou ; 500 erreur ;
- avec ?image=, la demande ATTEND le verrou (partagé avec la mise à jour planifiée de 05:00) au lieu de rendre 429 ; le
  serveur coupe une réponse au-delà de 10 min (la mise à jour continue) ;
- /v1/containers et /v1/metrics (GET, jeton) n'existent que si WATCHTOWER_HTTP_API_CONTAINERS / _METRICS sont actifs ;
  une route absente rend 404 sans regarder le jeton.
"""
from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import httpx

log = logging.getLogger("anneau.conteneurs")

# Conteneurs qu'on ne touche jamais, même marqués (motifs insensibles à la casse)
INTERDITS = ("anneau", "immich*", "portainer", "watchtower", "coffre-git", "silverbullet*")
# Nom de conteneur Docker : lettre ou chiffre, puis lettres, chiffres, « _ », « . », « - » (128 au plus)
NOM_VALIDE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ETIQUETTE_PROJET = "com.docker.compose.project"
PROJET = "homelab"

GESTES = {"allumer": "Allumer", "eteindre": "Éteindre", "mettre-a-jour": "Mettre à jour",
          "allumer-et-mettre-a-jour": "Allumer et mettre à jour"}
EN_COURS = {"allumer": "démarrage…", "eteindre": "extinction…", "mettre-a-jour": "mise à jour en cours…",
            "allumer-et-mettre-a-jour": "mise à jour en cours…"}
DELAI_MAX = 600              # s : au-delà, « pas de réponse, voir Portainer »
PRESSE = 300                 # s : après un ordre, la ronde relit plus vite pendant 5 min
RESULTAT_VISIBLE = 1800      # s : le résultat (« déjà à jour »…) reste écrit sur la tuile 30 min
DELAI_APPEL = 15.0           # s : délai d'un appel ordinaire à Portainer
DELAI_MAJ = 900              # s : une mise à jour par Watchtower peut attendre son verrou (05:00) : 15 min avant « pas de réponse »
DELAI_WATCHTOWER = 660.0     # s : Watchtower coupe lui-même une réponse au-delà de 10 min (la mise à jour continue)
DELAI_ESSAI = 8.0            # s : « Vérifier » de la fiche Watchtower
DELAI_DEMARRAGE = 60.0       # s : « Allumer et mettre à jour » attend que le conteneur tourne avant d'appeler Watchtower
ETIQUETTE_WATCHTOWER = "com.centurylinklabs.watchtower.enable"
MAJ = ("mettre-a-jour", "allumer-et-mettre-a-jour")
# Paramètre image de Watchtower : dépôt sans étiquette (ex. ghcr.io/exemple/bac-a-sable) ; pas de virgule (séparateur)
IMAGE_VALIDE = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,254}$")
JOURNAL = "journal-ecritures.jsonl"
ETAT = "conteneurs.json"
JOURNAL_MAX = 2000           # lignes ; au-delà, les 1000 dernières sont gardées


def interdit(nom: str) -> bool:
    n = (nom or "").strip().lower()
    return any(fnmatch.fnmatchcase(n, motif) for motif in INTERDITS)


def verifier_nom(valeur) -> tuple[str, str]:
    """Champ `conteneur:` d'une tuile → (nom, erreur). Nom vide si absent ou refusé."""
    v = str(valeur or "").strip()
    if not v:
        return "", ""
    if not NOM_VALIDE.match(v):
        return "", f"conteneur « {v} » invalide (lettres, chiffres, « _ », « . », « - »), ignoré."
    if interdit(v):
        return "", f"conteneur « {v} » refusé (l'Anneau ne touche jamais à ce conteneur), ignoré."
    return v, ""


def maintenant() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _date_docker(texte) -> str | None:
    """« 2026-11-20T05:02:11.123456789Z » → ISO à la seconde, ou None."""
    if not isinstance(texte, str) or not texte:
        return None
    t = re.sub(r"\.\d+", "", texte.strip()).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return None
    if d.year < 2000:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat(timespec="seconds")


def image_pour_watchtower(nom: str) -> tuple[str, str]:
    """Config.Image → (paramètre image de Watchtower, raison du refus). Watchtower compare le nom avant le premier « : »
    (pkg/filters, matchImageAndTag) : on lui donne exactement ce nom, sans l'étiquette."""
    n = (nom or "").strip()
    if not n:
        return "", "image du conteneur inconnue"
    if "@" in n or re.fullmatch(r"sha256:[0-9a-fA-F]+", n):
        return "", "image épinglée par empreinte (…@sha256) : Watchtower ne la met pas à jour"
    if "/" in n and ":" in n.split("/")[0]:
        return "", "image d'un registre avec numéro de port : non prise en charge"
    base = n.split(":")[0]
    if not IMAGE_VALIDE.match(base):
        return "", f"nom d'image inattendu (« {base} »)"
    return base, ""


def jour_mois(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m")
    except ValueError:
        return ""


# ================================================================ Portainer (client)

class ErreurPortainer(Exception):
    def __init__(self, phrase: str, statut: int | None = None):
        super().__init__(phrase)
        self.phrase, self.statut = phrase, statut


PHRASES_STATUT = {401: "Portainer refuse la clé d'API (401)",
                  403: "Portainer refuse l'accès à l'utilisateur de la clé (403) : voir l'équipe « anneau » et l'accès à la stack"}
PHRASE_ORDRE_403 = "Portainer refuse : vérifier l'accès de l'équipe « anneau » à la stack"


class Portainer:
    """Appels à l'API de Portainer (relais Docker). `transport` : un faux Portainer dans les tests."""

    def __init__(self, url: str, cle: str, env: str = "", transport: httpx.AsyncBaseTransport | None = None,
                 delai: float = DELAI_APPEL):
        self.url = url.rstrip("/")
        self._cle = cle
        self._env_regle = (env or "").strip()
        self._env: str | None = self._env_regle or None
        self._transport = transport
        self.delai = delai

    def __repr__(self) -> str:                       # jamais la clé, même dans une trace
        return f"Portainer({self.url!r}, env={self._env!r})"

    async def _demande(self, methode: str, chemin: str, corps=None, delai: float | None = None,
                       params: dict | None = None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(base_url=self.url, transport=self._transport, timeout=delai or self.delai,
                                         verify=False, follow_redirects=False) as c:
                return await c.request(methode, chemin, json=corps, params=params,
                                       headers={"X-API-Key": self._cle, "User-Agent": "anneau", "Accept": "application/json"})
        except httpx.TimeoutException as exc:
            raise ErreurPortainer("Portainer ne répond pas à temps") from exc
        except httpx.HTTPError as exc:
            raise ErreurPortainer(f"Portainer injoignable ({exc.__class__.__name__})") from exc

    @staticmethod
    def _refus(r: httpx.Response) -> None:
        if r.status_code in PHRASES_STATUT:
            raise ErreurPortainer(PHRASES_STATUT[r.status_code], r.status_code)

    async def statut(self) -> str | None:
        """Version de Portainer (GET /api/status), ou None si illisible."""
        try:
            r = await self._demande("GET", "/api/status")
            v = r.json().get("Version") if r.status_code == 200 else None
            return v if isinstance(v, str) else None
        except (ErreurPortainer, ValueError, AttributeError):
            return None

    async def environnement(self) -> str:
        """ANNEAU_PORTAINER_ENV, sinon le premier environnement Docker local (Type 1) de GET /api/endpoints."""
        if self._env:
            return self._env
        r = await self._demande("GET", "/api/endpoints")
        self._refus(r)
        if r.status_code != 200:
            raise ErreurPortainer(f"Portainer a répondu {r.status_code} à la liste des environnements", r.status_code)
        try:
            liste = r.json()
        except ValueError as exc:
            raise ErreurPortainer("liste des environnements illisible") from exc
        for e in liste if isinstance(liste, list) else []:
            if isinstance(e, dict) and e.get("Type") == 1 and str(e.get("Id", "")).isdigit():
                self._env = str(e["Id"])
                return self._env
        raise ErreurPortainer("aucun environnement Docker visible par la clé : régler ANNEAU_PORTAINER_ENV")

    def _docker(self, env: str, reste: str) -> str:
        return f"/api/endpoints/{env}/docker/{reste}"

    async def inspecter(self, nom: str) -> dict | None:
        env = await self.environnement()
        r = await self._demande("GET", self._docker(env, f"containers/{nom}/json"))
        self._refus(r)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise ErreurPortainer(f"Portainer a répondu {r.status_code}", r.status_code)
        try:
            d = r.json()
        except ValueError as exc:
            raise ErreurPortainer("réponse de Portainer illisible") from exc
        return d if isinstance(d, dict) else None

    async def lister(self, projet: str = PROJET) -> list[dict]:
        """0.18 : les conteneurs (allumés ou non) qui portent l'étiquette com.docker.compose.project=<projet>."""
        env = await self.environnement()
        r = await self._demande("GET", self._docker(env, "containers/json"),
                                params={"all": "1", "filters": json.dumps({"label": [f"{ETIQUETTE_PROJET}={projet}"]})})
        self._refus(r)
        if r.status_code != 200:
            raise ErreurPortainer(f"Portainer a répondu {r.status_code} à la liste des conteneurs", r.status_code)
        try:
            liste = r.json()
        except ValueError as exc:
            raise ErreurPortainer("liste des conteneurs illisible") from exc
        return [x for x in liste if isinstance(x, dict)] if isinstance(liste, list) else []

    async def image(self, ident: str) -> dict | None:
        env = await self.environnement()
        try:
            r = await self._demande("GET", self._docker(env, f"images/{ident}/json"))
            return r.json() if r.status_code == 200 else None
        except (ErreurPortainer, ValueError):
            return None

    async def stats(self, nom: str) -> dict | None:
        env = await self.environnement()
        r = await self._demande("GET", self._docker(env, f"containers/{nom}/stats"), params={"stream": "false"})
        self._refus(r)
        if r.status_code != 200:
            return None
        try:
            return r.json()
        except ValueError:
            return None

    async def ordre(self, nom: str, action: str) -> int:
        """stop ou start : rend le code HTTP (204 fait, 304 déjà dans cet état). 0.17.1 : un 403 ici (lecture permise,
        ordre refusé) dit d'aller voir l'accès de l'équipe « anneau » à la stack."""
        env = await self.environnement()
        r = await self._demande("POST", self._docker(env, f"containers/{nom}/{action}"), delai=60)
        if r.status_code == 403:
            raise ErreurPortainer(PHRASE_ORDRE_403, 403)
        self._refus(r)
        return r.status_code


# ================================================================ Watchtower (client, 0.17.1)

class ErreurWatchtower(Exception):
    """`conclut` : la demande n'a pas pu partir ou a été refusée net (rien n'a changé) ; sinon on relit l'état réel."""

    def __init__(self, phrase: str, statut: int | None = None, conclut: bool = True):
        super().__init__(phrase)
        self.phrase, self.statut, self.conclut = phrase, statut, conclut


PHRASE_JETON = "jeton refusé par Watchtower"
PHRASE_INJOIGNABLE = "Watchtower ne répond pas"


class Watchtower:
    """API HTTP de Watchtower (nickfedor/watchtower). `transport` : un faux Watchtower dans les tests."""

    def __init__(self, url: str, jeton: str, transport: httpx.AsyncBaseTransport | None = None,
                 delai: float = DELAI_WATCHTOWER, delai_essai: float = DELAI_ESSAI):
        self.url = url.rstrip("/")
        self._jeton = jeton
        self._transport = transport
        self.delai, self.delai_essai = delai, delai_essai
        self.dernier_refus = ""                      # heure du dernier 401/403 sur /v1/update (« Vérifier » le redit)

    def __repr__(self) -> str:                       # jamais le jeton, même dans une trace
        return f"Watchtower({self.url!r})"

    async def _demande(self, methode: str, chemin: str, params: dict | None = None,
                       delai: float | None = None) -> httpx.Response:
        try:
            async with httpx.AsyncClient(base_url=self.url, transport=self._transport, timeout=delai or self.delai_essai,
                                         follow_redirects=False) as c:
                return await c.request(methode, chemin, params=params,
                                       headers={"Authorization": f"Bearer {self._jeton}", "User-Agent": "anneau",
                                                "Accept": "application/json"})
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ErreurWatchtower(PHRASE_INJOIGNABLE) from exc
        except httpx.TimeoutException as exc:          # la demande est partie : Watchtower travaille peut-être encore
            raise ErreurWatchtower("Watchtower n'a pas répondu à temps", conclut=False) from exc
        except httpx.HTTPError as exc:
            raise ErreurWatchtower(f"liaison avec Watchtower coupée ({exc.__class__.__name__})", conclut=False) from exc

    async def mettre_a_jour(self, image: str) -> dict:
        """POST /v1/update?image=<image> : rend le résumé quand Watchtower a FINI (la demande peut attendre son verrou)."""
        r = await self._demande("POST", "/v1/update", params={"image": image}, delai=self.delai)
        if r.status_code == 200:
            self.dernier_refus = ""
            try:
                d = r.json()
            except ValueError:
                d = {}
            resume_ = (d.get("summary") if isinstance(d, dict) else None) or {}
            return {k: int(resume_.get(k) or 0) for k in ("scanned", "updated", "failed", "restarted", "skipped")
                    if isinstance(resume_.get(k, 0), (int, float))}
        if r.status_code in (401, 403):
            self.dernier_refus = maintenant()
            raise ErreurWatchtower(f"{PHRASE_JETON} ({r.status_code})", r.status_code)
        if r.status_code == 429:
            raise ErreurWatchtower("Watchtower refuse : trop de demandes (429), réessayer dans une minute", 429)
        if r.status_code in (404, 405):
            raise ErreurWatchtower(f"Watchtower n'a pas l'API de mise à jour ({r.status_code}) : WATCHTOWER_HTTP_API_UPDATE"
                                   f"=true et nickfedor/watchtower 1.19 ou plus récent", r.status_code)
        raise ErreurWatchtower(f"Watchtower a répondu {r.status_code}", r.status_code, conclut=False)

    async def essai(self) -> tuple[bool, str]:
        """Sans effet : GET /v1/containers puis /v1/metrics (lecture, s'ils sont activés). JAMAIS /v1/update."""
        for chemin, quoi in (("/v1/containers", "WATCHTOWER_HTTP_API_CONTAINERS"), ("/v1/metrics", "WATCHTOWER_HTTP_API_METRICS")):
            r = await self._demande("GET", chemin)
            if r.status_code == 200:
                n = ""
                if chemin == "/v1/containers":
                    try:
                        n = f" ({int(r.json().get('count'))} conteneurs surveillés)"
                    except (ValueError, TypeError, AttributeError):
                        n = ""
                return True, f"Watchtower répond, jeton accepté{n}."
            if r.status_code in (401, 403):
                return False, PHRASE_JETON + "."
            if r.status_code == 429:
                return False, "Watchtower refuse : trop de demandes (429)."
        if self.dernier_refus:
            quand = datetime.fromisoformat(self.dernier_refus).strftime("%d/%m à %H:%M")
            return False, f"Watchtower répond, mais {PHRASE_JETON} à la dernière mise à jour (le {quand})."
        # 160 caractères au plus (fiche « Connexion ») : le jeton sera vérifié à la première mise à jour
        return True, ("Watchtower répond ; adresse et jeton présents. Jeton vérifié à la première mise à jour, ou ici "
                      "si WATCHTOWER_HTTP_API_CONTAINERS est activé.")


def lire_stats(s: dict | None) -> dict | None:
    """Mémoire (octets, sans le cache) et processeur (% d'un cœur × nombre de cœurs) d'un GET stats?stream=false."""
    if not isinstance(s, dict):
        return None
    try:
        m = s.get("memory_stats") or {}
        detail = m.get("stats") or {}
        memoire = int(m.get("usage") or 0) - int(detail.get("inactive_file", detail.get("cache", 0)) or 0)
        c, p = s.get("cpu_stats") or {}, s.get("precpu_stats") or {}
        dc = (c.get("cpu_usage") or {}).get("total_usage", 0) - (p.get("cpu_usage") or {}).get("total_usage", 0)
        ds = (c.get("system_cpu_usage") or 0) - (p.get("system_cpu_usage") or 0)
        coeurs = c.get("online_cpus") or len((c.get("cpu_usage") or {}).get("percpu_usage") or []) or 1
        cpu = round(dc / ds * coeurs * 100, 1) if ds > 0 and dc >= 0 else 0.0
        return {"memoire": max(memoire, 0), "limite": int(m.get("limit") or 0) or None, "processeur": cpu}
    except (TypeError, ValueError, AttributeError):
        return None


def resume(d: dict) -> dict:
    """Ce que l'Anneau garde d'un GET …/containers/{nom}/json."""
    etat = d.get("State") or {}
    config = d.get("Config") or {}
    return {"id": str(d.get("Id") or ""), "nom_reel": str(d.get("Name") or "").lstrip("/"),
            "statut": str(etat.get("Status") or ("running" if etat.get("Running") else "inconnu")),
            "running": bool(etat.get("Running")), "image": str(d.get("Image") or ""),
            "image_nom": str(config.get("Image") or ""),
            "projet": str((config.get("Labels") or {}).get(ETIQUETTE_PROJET) or ""),
            "watchtower": str((config.get("Labels") or {}).get(ETIQUETTE_WATCHTOWER) or ""),
            "redemarrage": str(((d.get("HostConfig") or {}).get("RestartPolicy") or {}).get("Name") or "")}


# ================================================================ les conteneurs des tuiles

class Refus(Exception):
    def __init__(self, statut: int, phrase: str):
        super().__init__(phrase)
        self.statut, self.phrase = statut, phrase


class Conteneurs:
    def __init__(self, data: Path, portainer: Portainer | None, horloge: Callable[[], float] = time.time,
                 watchtower: Watchtower | None = None, watchtower_manque: str = "",
                 delai_demarrage: float = DELAI_DEMARRAGE):
        self.data, self.portainer, self._horloge = data, portainer, horloge
        self.watchtower = watchtower                 # 0.17.1 : « Mettre à jour » ; None : pas de bouton
        self.watchtower_manque = watchtower_manque or ("Watchtower n'est pas relié (ANNEAU_WATCHTOWER_URL, "
                                                       "ANNEAU_WATCHTOWER_JETON)")
        self.delai_demarrage = delai_demarrage
        self._lectures = 0                           # numéro de la relecture : un état lu APRÈS la réponse de Watchtower
        self.etats: dict[str, dict] = {}        # clé de tuile → resume() + image_date + lu_le, ou {"erreur"}
        self._dates: dict[str, str | None] = {}  # identifiant d'image → date de création
        self.erreur = ""                         # dernière erreur de lecture (Portainer injoignable…)
        self.lu_le = ""
        self.version: str | None = None          # version de Portainer (GET /api/status)
        self._taches: set[asyncio.Task] = set()
        self.reveil: asyncio.Event | None = None  # posé par main : réveille la ronde après un ordre
        m = self._lire_memoire()
        self.ordres: dict[str, dict] = m.get("ordres", {})
        for o in self.ordres.values():               # après un redémarrage, toute relecture est postérieure
            if isinstance(o, dict) and "wt_lecture" in o:
                o["wt_lecture"] = -1

    @property
    def actif(self) -> bool:
        return self.portainer is not None

    # ------------------------------------------------------------ mémoire et journal
    def _lire_memoire(self) -> dict:
        try:
            d = json.loads((self.data / ETAT).read_text(encoding="utf-8"))
            return d if isinstance(d, dict) and isinstance(d.get("ordres", {}), dict) else {}
        except (OSError, ValueError):
            return {}

    def _garder(self) -> None:
        try:
            self.data.mkdir(parents=True, exist_ok=True)
            neuf = self.data / (ETAT + ".nouveau")
            neuf.write_text(json.dumps({"ordres": self.ordres}, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(neuf, self.data / ETAT)
        except OSError as exc:
            log.warning("État des conteneurs non enregistré : %s", exc)

    def noter(self, quoi: str, tuile: str, resultat: str, **plus) -> None:
        """Une ligne au journal des écritures (JSON lignes). Jamais de secret : quoi, tuile, résultat, et le conteneur."""
        ligne = {"quand": maintenant(), "quoi": quoi, "tuile": tuile, "resultat": resultat}
        ligne.update({k: v for k, v in plus.items() if isinstance(v, (str, int, float, bool)) or v is None})
        try:
            chemin = self.data / JOURNAL
            with chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            if chemin.stat().st_size > JOURNAL_MAX * 300:
                lignes = chemin.read_text(encoding="utf-8").splitlines()
                if len(lignes) > JOURNAL_MAX:
                    chemin.write_text("\n".join(lignes[-JOURNAL_MAX // 2:]) + "\n", encoding="utf-8")
        except OSError as exc:
            log.warning("Journal des écritures non écrit : %s", exc)
        log.info("Écriture : %s %s → %s", quoi, tuile, resultat)

    def journal(self, n: int = 50) -> list[dict]:
        try:
            lignes = (self.data / JOURNAL).read_text(encoding="utf-8").splitlines()[-n:]
        except OSError:
            return []
        sortie = []
        for l in reversed(lignes):
            try:
                sortie.append(json.loads(l))
            except ValueError:
                continue
        return sortie

    # ------------------------------------------------------------ lecture de l'état
    async def relire(self, fichier) -> None:
        """Un GET …/json par tuile marquée (plus la date de l'image quand elle change). Portainer injoignable : les
        derniers états connus restent (une tuile éteinte ne devient pas « en panne » pour autant)."""
        if not self.actif:
            return
        marquees = [s for s in fichier.services if s.conteneur]
        self._lectures += 1
        if self.version is None:
            self.version = await self.portainer.statut() or ""
        erreurs = []
        for s in marquees:
            try:
                d = await self.portainer.inspecter(s.conteneur)
            except ErreurPortainer as exc:
                erreurs.append(exc.phrase)
                continue
            if d is None:
                self.etats[s.cle] = {"absent": True, "lu_le": maintenant()}
                continue
            r = resume(d)
            if r["image"] and r["image"] not in self._dates:
                img = await self.portainer.image(r["image"])
                self._dates[r["image"]] = _date_docker((img or {}).get("Created"))
            self.etats[s.cle] = {**r, "image_date": self._dates.get(r["image"]), "lu_le": maintenant(),
                                 "lecture": self._lectures}
        for k in [k for k in self.etats if k not in {s.cle for s in marquees}]:
            del self.etats[k]
        self.erreur = erreurs[0] if erreurs else ""
        self.lu_le = maintenant()

    def eteints(self) -> set[str]:
        """Tuiles dont le conteneur est arrêté (exited chez Portainer) : ni « en panne », ni sauvegardées la nuit."""
        return {k for k, e in self.etats.items() if e.get("statut") == "exited"}

    # ------------------------------------------------------------ barrières
    def barriere(self, s, e: dict | None) -> str:
        """Pourquoi les boutons sont absents pour cette tuile (vide : ils sont là)."""
        if not self.actif or not s or not s.conteneur:
            return "pas de conteneur à gérer"
        if interdit(s.conteneur):
            return "l'Anneau ne touche jamais à ce conteneur"
        if e is None:
            return "état pas encore lu chez Portainer"
        if e.get("absent"):
            return f"Portainer ne connaît pas de conteneur « {s.conteneur} »"
        if interdit(e.get("nom_reel", "")):
            return "l'Anneau ne touche jamais à ce conteneur"
        if e.get("nom_reel") != s.conteneur:
            return f"Portainer rend un autre conteneur (« {e.get('nom_reel')} ») que celui de la tuile"
        if e.get("projet") != PROJET:
            return f"le conteneur n'a pas l'étiquette {ETIQUETTE_PROJET}={PROJET} (il n'est pas de la stack)"
        return ""

    def raison_maj(self, e: dict | None) -> str:
        """0.17.1 : pourquoi « Mettre à jour » est absent pour ce conteneur (vide : le bouton est là)."""
        if self.watchtower is None:
            return f"« Mettre à jour » absent : {self.watchtower_manque}."
        if not e or e.get("absent"):
            return ""
        if str(e.get("watchtower") or "").strip().lower() == "false":
            return (f"« Mettre à jour » absent : le conteneur porte l'étiquette {ETIQUETTE_WATCHTOWER}=false "
                    f"(Watchtower ne le met jamais à jour).")
        _, raison = image_pour_watchtower(e.get("image_nom", ""))
        return f"« Mettre à jour » absent : {raison}." if raison else ""

    def en_cours(self, cle: str) -> bool:
        return (self.ordres.get(cle) or {}).get("etat") == "en_cours"

    def presse(self) -> bool:
        """Un ordre lancé il y a moins de 5 min est encore en cours : la ronde relit plus vite."""
        t = self._horloge()
        return any(o.get("etat") == "en_cours" and t - o.get("debut_t", 0) < PRESSE for o in self.ordres.values())

    # ------------------------------------------------------------ ordres
    async def ordonner(self, s, geste: str, lecture_seule: bool) -> dict:
        """Vérifie toutes les barrières (nom relu chez Portainer), lance l'ordre, rend l'ordre en cours. Refus : Refus."""
        nom_tuile = s.nom if s else "?"
        try:
            if geste not in GESTES:
                raise Refus(404, "Geste inconnu.")
            if not self.actif:
                raise Refus(404, "Portainer n'est pas réglé (ANNEAU_PORTAINER_URL, ANNEAU_PORTAINER_CLE).")
            if not s.conteneur:
                raise Refus(404, "Cette tuile n'a pas de conteneur à gérer (champ conteneur: absent).")
            if interdit(s.conteneur):
                raise Refus(403, "L'Anneau ne touche jamais à ce conteneur.")
            if lecture_seule:
                raise Refus(403, "Lecture seule : l'Anneau ne donne aucun ordre à Portainer.")
            if self.en_cours(s.cle):
                raise Refus(409, f"Un ordre est déjà en cours pour {s.nom}.")
            if geste in MAJ and self.watchtower is None:
                raise Refus(409, f"« Mettre à jour » absent : {self.watchtower_manque}.")
            try:
                d = await self.portainer.inspecter(s.conteneur)
            except ErreurPortainer as exc:
                raise Refus(502, exc.phrase) from exc
            if d is None:
                raise Refus(404, f"Portainer ne connaît pas de conteneur « {s.conteneur} ».")
            e = resume(d)
            if e["image"] and e["image"] not in self._dates:
                img = await self.portainer.image(e["image"])
                self._dates[e["image"]] = _date_docker((img or {}).get("Created"))
            e["image_date"] = self._dates.get(e["image"])
            self.etats[s.cle] = {**e, "lu_le": maintenant(), "lecture": self._lectures}
            raison = self.barriere(s, e)
            if raison:
                raise Refus(403, f"Refusé : {raison}.")
            image = ""
            if geste in MAJ:
                raison = self.raison_maj(e)
                if raison:
                    raise Refus(409, raison)
                image, _ = image_pour_watchtower(e["image_nom"])
            if geste == "allumer" and e["running"]:
                raise Refus(409, f"{s.nom} est déjà allumé.")
            if geste == "eteindre" and not e["running"]:
                raise Refus(409, f"{s.nom} est déjà éteint.")
        except Refus as r:
            self.noter(geste, nom_tuile, f"refusé : {r.phrase}", conteneur=getattr(s, "conteneur", "") or None)
            raise
        t = self._horloge()
        ordre = {"geste": geste, "tuile": s.nom, "conteneur": s.conteneur, "etat": "en_cours", "debut": maintenant(),
                 "debut_t": t, "id_avant": e["id"], "image_avant": e["image"], "date_avant": e.get("image_date"),
                 "phrase": EN_COURS[geste], "detail": "", "demarre": False, "image_param": image}
        self.ordres[s.cle] = ordre
        self._garder()
        self.noter(geste, s.nom, "lancé", conteneur=s.conteneur)
        tache = asyncio.create_task(self._executer(s.cle, s.nom, s.conteneur, geste, image))
        self._taches.add(tache)
        tache.add_done_callback(self._taches.discard)
        if self.reveil is not None:
            self.reveil.set()
        return dict(ordre)

    async def _executer(self, cle: str, nom: str, conteneur: str, geste: str, image: str) -> None:
        """L'appel lui-même. Sa réponse ne dit pas le résultat (sauf un refus net) : c'est le suivi qui conclut."""
        try:
            if geste == "eteindre":
                statut = await self.portainer.ordre(conteneur, "stop")
            elif geste == "allumer":
                statut = await self.portainer.ordre(conteneur, "start")
            else:
                if geste == "allumer-et-mettre-a-jour":
                    await self.portainer.ordre(conteneur, "start")
                    if not await self._attendre_marche(cle, conteneur):
                        self._finir(cle, "echec", "le conteneur n'a pas démarré : pas de mise à jour, voir Portainer.")
                        return
                await self._par_watchtower(cle, geste, image)
                return
            if statut >= 400 and statut not in (404,):
                o = self.ordres.get(cle)
                if o and o.get("etat") == "en_cours":
                    o["detail"] = f"Portainer a répondu {statut} ; l'état réel est relu."
                    self._garder()
        except ErreurPortainer as exc:
            if exc.statut in (401, 403):
                self._finir(cle, "echec", exc.phrase + ".")
                return
            o = self.ordres.get(cle)                       # délai, coupure : on ne conclut pas, on relit l'état
            if o and o.get("etat") == "en_cours":
                o["detail"] = f"{exc.phrase} ; l'état réel est relu."
                self._garder()
        except Exception as exc:                            # noqa: BLE001 — ne jamais laisser une tâche muette
            log.exception("Ordre %s sur %s", geste, nom)
            o = self.ordres.get(cle)
            if o and o.get("etat") == "en_cours":
                o["detail"] = f"erreur ({exc.__class__.__name__}) ; l'état réel est relu."
                self._garder()
        finally:
            if self.reveil is not None:
                self.reveil.set()

    async def _attendre_marche(self, cle: str, conteneur: str) -> bool:
        """« Allumer et mettre à jour » : Watchtower ignore un conteneur arrêté, on attend donc qu'il tourne."""
        fin = time.monotonic() + self.delai_demarrage
        while True:
            d = await self.portainer.inspecter(conteneur)
            if d and (d.get("State") or {}).get("Running"):
                o = self.ordres.get(cle)
                if o:
                    o["demarre"] = True
                    self._garder()
                return True
            if time.monotonic() >= fin:
                return False
            await asyncio.sleep(min(1.0, max(self.delai_demarrage / 20, 0.01)))

    async def _par_watchtower(self, cle: str, geste: str, image: str) -> None:
        """POST /v1/update?image=… ; la réponse arrive quand Watchtower a fini (ou jamais : coupure, redémarrage)."""
        o = self.ordres.get(cle)
        if not o:
            return
        o["wt"] = "attente"
        self._garder()
        avant = "allumé, mais " if geste == "allumer-et-mettre-a-jour" else ""
        try:
            r = await self.watchtower.mettre_a_jour(image)
        except ErreurWatchtower as exc:
            o = self.ordres.get(cle)
            if exc.conclut:
                if o:
                    o["wt"] = "refus"
                self._finir(cle, "echec", f"{avant}{exc.phrase} : pas de mise à jour.")
                return
            if o and o.get("etat") == "en_cours":
                o.update(wt="perdu", detail=f"{exc.phrase} ; l'état réel est relu.")
                self._garder()
            return
        o = self.ordres.get(cle)
        if o and o.get("etat") == "en_cours":
            o.update(wt="fini", wt_resume=r, wt_lecture=self._lectures)
            self._garder()

    def _finir(self, cle: str, etat: str, phrase: str) -> None:
        o = self.ordres.get(cle)
        if not o or o.get("etat") != "en_cours":
            return
        o.update(etat=etat, phrase=phrase, fin=maintenant(), fin_t=self._horloge())
        self._garder()
        self.noter(o["geste"], o["tuile"], {"fini": "fini", "echec": "échec", "delai": "délai dépassé"}[etat] + " : " + phrase,
                   conteneur=o.get("conteneur"))

    async def suivre(self, fichier, repond: Callable[[object], Awaitable[bool]]) -> None:
        """Après la relecture : un ordre en cours est-il fini ? (état réel chez Portainer, /health de la tuile)."""
        if not self.actif:
            return
        tuiles = {s.cle: s for s in fichier.services}
        for cle, o in list(self.ordres.items()):
            if o.get("etat") != "en_cours":
                continue
            s = tuiles.get(cle)
            if s is None or s.conteneur != o.get("conteneur"):
                self._finir(cle, "echec", "la tuile a changé dans le fichier des services.")
                continue
            maj = o["geste"] in MAJ
            if self._horloge() - o.get("debut_t", 0) > (DELAI_MAJ if maj else DELAI_MAX):
                self._finir(cle, "delai", "pas de réponse, voir Watchtower et Portainer." if maj
                            else "pas de réponse, voir Portainer.")
                continue
            e = self.etats.get(cle)
            if not e or e.get("absent"):
                continue                                    # recréation en plein milieu : on attend
            if o["geste"] == "eteindre":
                if e.get("statut") == "exited":
                    self._finir(cle, "fini", "éteint.")
                continue
            if maj:
                await self._suivre_maj(cle, o, e, s, repond)
                continue
            if not e.get("running"):
                continue
            if await self._vivant(s, repond):
                self._finir(cle, "fini", "allumé.")

    @staticmethod
    async def _vivant(s, repond) -> bool:
        try:
            return bool(await repond(s))
        except Exception:                                   # noqa: BLE001
            return False

    async def _suivre_maj(self, cle: str, o: dict, e: dict, s, repond) -> bool:
        """0.17.1 : fin d'une mise à jour par Watchtower, jugée à l'état réel. Nouvelle empreinte d'image + conteneur en
        marche + /health : « image du JJ/MM → JJ/MM ». Même empreinte : « déjà à jour » seulement quand Watchtower a
        répondu ET que l'état a été relu après sa réponse (sinon il travaille peut-être encore, ou attend son verrou)."""
        wt = o.get("wt", "")
        neuve = bool(e.get("image")) and e.get("image") != o.get("image_avant")
        repondu = wt == "fini" and e.get("lecture", 0) > o.get("wt_lecture", 10 ** 12)
        if not e.get("running"):
            if repondu:
                self._finir(cle, "echec", "le conteneur n'est pas en marche après le passage de Watchtower : voir Portainer.")
            return False
        if not neuve:
            if not repondu:
                return False
            r = o.get("wt_resume") or {}
            if r.get("failed"):
                self._finir(cle, "echec", "Watchtower signale un échec (voir son journal) : image inchangée.")
                return False
            if r.get("skipped") and not r.get("scanned"):
                self._finir(cle, "echec", "Watchtower a sauté le conteneur : il n'a pas pu lire l'image (identifiants des images privées dans "
                                          "config.json, registre injoignable ?), voir le journal de Watchtower : rien n'a changé.")
                return False
            if r and not r.get("scanned"):
                self._finir(cle, "echec", "Watchtower n'a trouvé aucun conteneur en marche de cette image (étiquette, "
                                          "portée ?) : rien n'a changé.")
                return False
        if not await self._vivant(s, repond):
            return False
        if neuve:
            avant, apres = jour_mois(o.get("date_avant")), jour_mois(e.get("image_date"))
            self._finir(cle, "fini", f"image du {avant} → {apres}." if avant and apres else "nouvelle image.")
        else:
            self._finir(cle, "fini", "déjà à jour.")
        return True

    # ------------------------------------------------------------ pour l'écran
    def vue(self, s, lecture_seule: bool) -> dict | None:
        """Ce que /api/etat rend pour une tuile marquée (None : pas de conteneur, ou Portainer pas réglé)."""
        if not self.actif or not s.conteneur:
            return None
        e = self.etats.get(s.cle)
        raison = self.barriere(s, e)
        o = self.ordres.get(s.cle)
        t = self._horloge()
        ordre = None
        if o:
            ordre = {k: o.get(k) for k in ("geste", "etat", "phrase", "detail", "debut", "fin")}
        statut = (e or {}).get("statut", "inconnu") if e and not e.get("absent") else "inconnu"
        phrase = ""
        if o and o.get("etat") == "en_cours":
            phrase = o["phrase"]
        elif o and o.get("fin_t") and t - o["fin_t"] < RESULTAT_VISIBLE and not (o["geste"] == "eteindre" and o["etat"] == "fini"):
            phrase = o["phrase"].rstrip(".")
        elif statut == "exited":
            phrase = "éteint"
        date = (e or {}).get("image_date")
        age = None
        if date:
            try:
                age = max(0, int((datetime.now().astimezone() - datetime.fromisoformat(date)).total_seconds() // 86400))
            except ValueError:
                age = None
        return {"gerable": not raison, "pourquoi": raison, "statut": statut, "phrase": phrase, "ordre": ordre,
                "image_date": date, "image_age": age, "redemarrage": (e or {}).get("redemarrage", ""),
                "maj": not raison and not self.raison_maj(e), "maj_pourquoi": self.raison_maj(e),
                "lecture_seule": lecture_seule, "erreur": self.erreur}

    async def stats(self, s) -> dict:
        if not self.actif or not s or not s.conteneur:
            raise Refus(404, "Pas de conteneur à lire.")
        raison = self.barriere(s, self.etats.get(s.cle))
        if raison:
            raise Refus(403, f"Refusé : {raison}.")
        try:
            return lire_stats(await self.portainer.stats(s.conteneur)) or {}
        except ErreurPortainer as exc:
            raise Refus(502, exc.phrase) from exc

    async def essai(self) -> tuple[bool, str]:
        """Essai léger pour la fiche « Connexion » : la liste des environnements (rien d'écrit)."""
        if not self.actif:
            return False, "Pas réglé."
        env = await self.portainer.environnement()
        self.version = await self.portainer.statut() or self.version
        v = f"Portainer {self.version}, " if self.version else ""
        return True, f"{v}environnement {env}."

    def derniere_ecriture(self, gestes: tuple[str, ...] | None = None) -> str | None:
        for l in self.journal(200):
            if gestes is not None and l.get("quoi") not in gestes:
                continue
            if l.get("resultat", "").startswith(("fini", "lancé")):
                return l.get("quand")
        return None
