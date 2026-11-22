"""0.18 : faux registres d'images (ghcr.io, Docker Hub, lscr.io) et fausse API GitHub (dernière publication), pour les
tests. Écrits d'après la spécification de distribution OCI (HEAD /v2/<nom>/manifests/<étiquette>, en-tête
Docker-Content-Digest) et le jeton anonyme « Bearer » (WWW-Authenticate: Bearer realm=…,service=…,scope=…).
lscr.io redirige vers ghcr.io (307), comme le vrai. Tout est inventé : dépôts, empreintes, versions."""
from __future__ import annotations

import hashlib

import httpx


def empreinte(texte: str) -> str:
    return "sha256:" + hashlib.sha256(texte.encode()).hexdigest()


class FauxRegistres:
    def __init__(self):
        self.manifestes: dict[tuple[str, str, str], str] = {}   # (hôte, dépôt, étiquette) → empreinte
        self.publications: dict[str, str] = {}                   # dépôt GitHub → étiquette de la dernière publication
        self.appels: list[tuple[str, str]] = []
        self.injoignables: set[str] = set()
        self.prives: set[str] = set()                            # dépôts dont le jeton anonyme est refusé
        self.sans_jeton_valide = 0

    def publier(self, hote: str, depot: str, etiquette: str, texte: str) -> str:
        d = empreinte(texte)
        self.manifestes[(hote, depot, etiquette)] = d
        return d

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._repondre)

    def _repondre(self, r: httpx.Request) -> httpx.Response:
        hote, chemin = r.url.host, r.url.path
        self.appels.append((r.method, f"{hote}{chemin}"))
        if hote in self.injoignables:
            raise httpx.ConnectError("refusé", request=r)
        if hote == "api.github.com":
            depot = chemin.removeprefix("/repos/").removesuffix("/releases/latest")
            if depot in self.publications:
                return httpx.Response(200, json={"tag_name": self.publications[depot]})
            return httpx.Response(404, json={"message": "Not Found"})
        if hote in ("auth.docker.io", "ghcr.io") and chemin.endswith("/token") or chemin == "/token":
            scope = r.url.params.get("scope", "")
            depot = scope.split(":")[1] if scope.count(":") >= 2 else ""
            if depot in self.prives:
                return httpx.Response(401, json={"errors": [{"code": "UNAUTHORIZED"}]})
            return httpx.Response(200, json={"token": f"jeton-{depot}"})
        if hote == "lscr.io":
            return httpx.Response(307, headers={"Location": f"https://ghcr.io{chemin}"})
        if "/manifests/" not in chemin:
            return httpx.Response(404)
        depot, _, etiquette = chemin.removeprefix("/v2/").partition("/manifests/")
        realm = "https://auth.docker.io/token" if hote == "registry-1.docker.io" else f"https://{hote}/token"
        service = "registry.docker.io" if hote == "registry-1.docker.io" else hote
        if r.headers.get("authorization") != f"Bearer jeton-{depot}":
            return httpx.Response(401, headers={"WWW-Authenticate":
                                                f'Bearer realm="{realm}",service="{service}",scope="repository:{depot}:pull"'})
        d = self.manifestes.get((hote, depot, etiquette))
        if not d:
            return httpx.Response(404, json={"errors": [{"code": "MANIFEST_UNKNOWN"}]})
        return httpx.Response(200, headers={"Docker-Content-Digest": d,
                                            "Content-Type": "application/vnd.oci.image.index.v1+json"})
