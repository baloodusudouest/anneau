"""Faux Watchtower (nickfedor/watchtower 1.19.0) pour les tests (0.17.1), écrit d'après sa documentation (« HTTP API »,
docs/advanced-features/http-api) et son code (pkg/api : api.go, update/update.go ; pkg/filters : matchImageAndTag).

Routes imitées (routage par méthode, comme Go 1.22 : une route absente rend 404 et une mauvaise méthode 405, sans
regarder le jeton ; sur une route présente, jeton absent ou faux : 401) :
  POST /v1/update[?image=a/b,c/d][&async=true]   met à jour les conteneurs EN MARCHE dont le nom d'image (avant le
                                                  premier « : ») est demandé ; un conteneur arrêté ou étiqueté
                                                  com.centurylinklabs.watchtower.enable=false est ignoré ; 200 et
                                                  {"summary": {scanned, updated, failed, restarted, skipped}, …} à la
                                                  fin ; async=true : 202 tout de suite (après le verrou)
  GET  /v1/containers                             seulement si `containers_api`
  GET  /v1/metrics                                seulement si `metrics_api`
Verrou partagé avec la mise à jour planifiée (`verrou`) : avec ?image=, la demande attend ; sans, 429 si occupé.
Il agit sur les conteneurs d'un FauxPortainer (le même « Docker »). Tout est inventé.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from tests.faux_portainer import FauxPortainer

JETON = "jeton-watchtower-de-test"
ETIQUETTE = "com.centurylinklabs.watchtower.enable"


def _maintenant() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FauxWatchtower:
    def __init__(self, docker: FauxPortainer, jeton: str = JETON, lenteur: float = 0.0, containers_api: bool = False,
                 metrics_api: bool = False, include_stopped: bool = False, revive_stopped: bool = False):
        self.docker, self.jeton, self.lenteur = docker, jeton, lenteur
        self.include_stopped, self.revive_stopped = include_stopped, revive_stopped   # 0.22 : WATCHTOWER_INCLUDE_STOPPED…
        self.containers_api, self.metrics_api = containers_api, metrics_api
        self.verrou = asyncio.Lock()
        self.echec: set[str] = set()              # conteneurs dont la mise à jour échoue (failed)
        self.saut: set[str] = set()               # 0.18.4 : image illisible (config.json mal formé, registre) : skipped
        self.appels: list[tuple[str, str, str]] = []   # (méthode, chemin, requête)
        self.jetons_vus: set[str] = set()
        self.app = self._application()

    def transport(self) -> httpx.ASGITransport:
        return httpx.ASGITransport(app=self.app)

    @staticmethod
    def injoignable() -> httpx.MockTransport:
        def refuse(requete):
            raise httpx.ConnectError("Connection refused", request=requete)
        return httpx.MockTransport(refuse)

    def mise_a_jour(self, images: list[str] | None) -> dict:
        r = {"scanned": 0, "updated": 0, "failed": 0, "restarted": 0, "skipped": 0}
        for nom, c in list(self.docker.conteneurs.items()):
            arrete = not c["State"]["Running"]
            if arrete and not self.include_stopped:
                continue                              # sans INCLUDE_STOPPED, Watchtower ne regarde que les conteneurs en marche
            if (c["Config"].get("Labels") or {}).get(ETIQUETTE, "").lower() == "false":
                continue
            nom_image = c["Config"]["Image"]
            if images is not None and nom_image.split(":")[0] not in [i.split(":")[0] for i in images]:
                continue
            if nom in self.saut:                      # « Could not check container for updates » : ni scanned ni failed
                r["skipped"] += 1
                continue
            r["scanned"] += 1
            if nom in self.echec:
                r["failed"] += 1
                continue
            derniere = self.docker.dernieres.get(nom_image)
            if derniere and derniere != c["Image"]:
                self.docker.remplacer(nom, derniere, demarrer=not arrete or self.revive_stopped)
                r["updated"] += 1
        return r

    def _application(self) -> FastAPI:
        app = FastAPI()
        moi = self

        def jeton_ok(request: Request) -> bool:
            champs = request.headers.get("authorization", "").split()
            propose = champs[1] if len(champs) >= 2 and champs[0].lower() == "bearer" else ""
            moi.jetons_vus.add(propose)
            return propose == moi.jeton

        @app.middleware("http")
        async def noter(request: Request, appel):
            moi.appels.append((request.method, request.url.path, request.url.query))
            return await appel(request)

        @app.post("/v1/update")
        async def update(request: Request):
            if not jeton_ok(request):
                return Response(status_code=401)
            images = None
            if "image" in request.query_params:
                images = [i for v in request.query_params.getlist("image") for i in v.split(",")]
            elif moi.verrou.locked():
                return JSONResponse({"error": "another update is already running", "api_version": "v1",
                                     "timestamp": _maintenant()}, status_code=429, headers={"Retry-After": "30"})
            await moi.verrou.acquire()

            async def travail():
                try:
                    if moi.lenteur:
                        await asyncio.sleep(moi.lenteur)
                    return moi.mise_a_jour(images)
                finally:
                    moi.verrou.release()

            if request.query_params.get("async") == "true":
                asyncio.get_running_loop().create_task(travail())
                return Response(status_code=202, media_type="application/json")
            debut = asyncio.get_running_loop().time()
            resume = await travail()
            duree = int((asyncio.get_running_loop().time() - debut) * 1000)
            return {"summary": resume, "timing": {"duration_ms": duree, "duration": f"{duree}ms"},
                    "timestamp": _maintenant(), "api_version": "v1"}

        if self.containers_api:
            @app.get("/v1/containers")
            def liste(request: Request):
                if not jeton_ok(request):
                    return Response(status_code=401)
                cs = [{"name": n, "image": c["Config"]["Image"], "image_id": c["Image"], "digest": ""}
                      for n, c in moi.docker.conteneurs.items()]
                return {"containers": cs, "count": len(cs), "timestamp": _maintenant(), "api_version": "v1"}

        if self.metrics_api:
            @app.get("/v1/metrics")
            def mesures(request: Request):
                if not jeton_ok(request):
                    return Response(status_code=401)
                return Response("watchtower_containers_scanned 0\n", media_type="text/plain")

        return app
