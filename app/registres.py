"""0.18 : l'empreinte publiée d'une image, lue dans son registre (ghcr.io, Docker Hub, lscr.io…), et la dernière version
publiée d'un dépôt GitHub (versions figées dans la stack).

Lecture seule : une demande HEAD du manifeste (« /v2/<dépôt>/manifests/<étiquette> »), avec le jeton anonyme que le
registre donne lui-même (en-tête WWW-Authenticate: Bearer realm=…,service=…,scope=…). Rien n'est téléchargé : chez
Docker Hub, une demande HEAD ne compte pas dans la limite des téléchargements anonymes. Aucun secret : l'Anneau ne lit que
des images publiques.

Une image est à jour quand l'empreinte du registre figure parmi les RepoDigests de l'image locale (Docker garde
l'empreinte de l'index multi-architecture quand l'image a été tirée par son étiquette : c'est elle que le registre rend).
"""
from __future__ import annotations

import re

import httpx

DOCKER_HUB = "registry-1.docker.io"
ALIAS_HUB = {"docker.io", "index.docker.io", "registry.hub.docker.com", DOCKER_HUB}
ACCEPTE = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])
DELAI = 15.0
GITHUB = "https://api.github.com"
DEPOT_GITHUB = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9._-]{1,100}$")
# une étiquette « figée » : un numéro de version (v2.3.1, 1.19.0, 16, 16.4-alpine…), pas latest / release / main
FIGEE = re.compile(r"^v?\d+(\.\d+){0,3}([-+_.][0-9A-Za-z.+_-]+)?$")
VERSION = re.compile(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


class ErreurRegistre(Exception):
    pass


def decouper(ref: str) -> tuple[str, str, str]:
    """« ghcr.io/a/b:1 » → (ghcr.io, a/b, 1) ; « postgres » → (registry-1.docker.io, library/postgres, latest).
    Une image épinglée par empreinte (« …@sha256: ») n'a pas d'étiquette à comparer : ErreurRegistre."""
    r = (ref or "").strip()
    if not r or "@" in r or r.startswith("sha256:"):
        raise ErreurRegistre("image épinglée par empreinte ou inconnue")
    morceaux = r.split("/")
    if len(morceaux) > 1 and ("." in morceaux[0] or ":" in morceaux[0] or morceaux[0] == "localhost"):
        hote, reste = morceaux[0].lower(), "/".join(morceaux[1:])
    else:
        hote, reste = DOCKER_HUB, r
    if hote in ALIAS_HUB:
        hote = DOCKER_HUB
    depot, _, etiquette = reste.partition(":")
    if hote == DOCKER_HUB and "/" not in depot:
        depot = "library/" + depot
    if not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", depot):
        raise ErreurRegistre(f"nom d'image inattendu (« {depot} »)")
    return hote, depot, etiquette or "latest"


def etiquette(ref: str) -> str:
    try:
        return decouper(ref)[2]
    except ErreurRegistre:
        return ""


def est_figee(ref: str) -> bool:
    """L'étiquette est un numéro de version : Watchtower ne fera jamais passer à la version suivante."""
    return bool(FIGEE.match(etiquette(ref)))


def cle_version(v: str | None) -> tuple[int, int, int] | None:
    m = VERSION.search(v or "")
    if not m:
        return None
    return tuple(int(x or 0) for x in m.groups())      # type: ignore[return-value]


def _defi(entete: str) -> dict[str, str]:
    """« Bearer realm="https://…/token",service="…",scope="…" » → ses champs."""
    if not entete.lower().startswith("bearer "):
        return {}
    return {k.lower(): v for k, v in re.findall(r'(\w+)="([^"]*)"', entete[7:])}


class Registres:
    """`transport` : faux registres dans les tests. Les jetons anonymes sont gardés le temps d'une vérification."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None, delai: float = DELAI):
        self._transport = transport
        self.delai = delai
        self._jetons: dict[tuple[str, str, str], str] = {}

    def oublier(self) -> None:
        self._jetons.clear()

    async def _jeton(self, c: httpx.AsyncClient, defi: dict[str, str]) -> str:
        cle_ = (defi.get("realm", ""), defi.get("service", ""), defi.get("scope", ""))
        if cle_ in self._jetons:
            return self._jetons[cle_]
        if not cle_[0].startswith(("https://", "http://")):
            raise ErreurRegistre("le registre demande une connexion inattendue")
        params = {k: v for k, v in (("service", cle_[1]), ("scope", cle_[2])) if v}
        r = await c.get(cle_[0], params=params)
        if r.status_code != 200:
            raise ErreurRegistre(f"le registre refuse un accès anonyme ({r.status_code}) : image privée ?")
        try:
            d = r.json()
        except ValueError as exc:
            raise ErreurRegistre("jeton du registre illisible") from exc
        jeton = str(d.get("token") or d.get("access_token") or "")
        if not jeton:
            raise ErreurRegistre("le registre n'a pas donné de jeton")
        self._jetons[cle_] = jeton
        return jeton

    async def empreinte(self, ref: str) -> str:
        """L'empreinte (sha256:…) que le registre donne aujourd'hui pour cette étiquette."""
        hote, depot, etiq = decouper(ref)
        url = f"https://{hote}/v2/{depot}/manifests/{etiq}"
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self.delai, follow_redirects=True,
                                         headers={"User-Agent": "anneau", "Accept": ACCEPTE}) as c:
                r = await c.head(url)
                for _ in range(2):                       # un registre qui redirige (lscr.io → ghcr.io) en redemande un
                    if r.status_code != 401:
                        break
                    jeton = await self._jeton(c, _defi(r.headers.get("www-authenticate", "")))
                    r = await c.head(str(r.url), headers={"Authorization": f"Bearer {jeton}"})
                if r.status_code == 200 and not r.headers.get("docker-content-digest"):
                    auth = r.request.headers.get("authorization")
                    r = await c.get(str(r.url), headers={"Authorization": auth} if auth else None)
        except httpx.TimeoutException as exc:
            raise ErreurRegistre(f"{hote} ne répond pas à temps") from exc
        except httpx.HTTPError as exc:
            raise ErreurRegistre(f"{hote} injoignable ({exc.__class__.__name__})") from exc
        if r.status_code == 404:
            raise ErreurRegistre(f"étiquette « {etiq} » introuvable dans {hote}")
        if r.status_code == 429:
            raise ErreurRegistre(f"{hote} limite les demandes (429) : réessayer plus tard")
        if r.status_code != 200:
            raise ErreurRegistre(f"{hote} a répondu {r.status_code}")
        d = r.headers.get("docker-content-digest", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", d):
            raise ErreurRegistre(f"{hote} ne donne pas l'empreinte de l'image")
        return d

    async def derniere_version(self, depot: str) -> str:
        """Étiquette de la dernière publication d'un dépôt GitHub (« immich-app/immich » → « v2.4.0 »), sans jeton."""
        if not DEPOT_GITHUB.match(depot or ""):
            raise ErreurRegistre(f"dépôt GitHub « {depot} » invalide")
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=self.delai,
                                         headers={"User-Agent": "anneau", "Accept": "application/vnd.github+json"}) as c:
                r = await c.get(f"{GITHUB}/repos/{depot}/releases/latest")
        except httpx.HTTPError as exc:
            raise ErreurRegistre(f"GitHub injoignable ({exc.__class__.__name__})") from exc
        if r.status_code == 404:
            raise ErreurRegistre(f"aucune publication dans {depot}")
        if r.status_code in (403, 429):
            raise ErreurRegistre("GitHub limite les demandes : réessayer plus tard")
        if r.status_code != 200:
            raise ErreurRegistre(f"GitHub a répondu {r.status_code}")
        try:
            v = str(r.json().get("tag_name") or "")
        except (ValueError, AttributeError) as exc:
            raise ErreurRegistre("réponse de GitHub illisible") from exc
        if not v:
            raise ErreurRegistre(f"publication sans étiquette dans {depot}")
        return v
