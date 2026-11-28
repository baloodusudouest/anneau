"""Faux Portainer CE pour les tests (0.17), écrit d'après la documentation de son API et de l'API Docker qu'il relaie.

Routes imitées (toutes exigent l'en-tête X-API-Key ; mauvaise clé : 401) :
  GET  /api/status                                              {"Version": "2.21.4"} (publique)
  GET  /api/endpoints                                           environnements visibles (Type 1 = Docker local)
  GET  /api/endpoints/{env}/docker/containers/{nom}/json        inspection (nom ou début d'identifiant ; 404 inconnu)
  POST /api/endpoints/{env}/docker/containers/{nom}/stop        204, ou 304 déjà arrêté
  POST /api/endpoints/{env}/docker/containers/{nom}/start       204, ou 304 déjà démarré
  GET  /api/endpoints/{env}/docker/containers/{nom}/stats       ?stream=false : un relevé
  GET  /api/endpoints/{env}/docker/images/{id}/json             date de création de l'image (0.18 : RepoDigests, étiquette version)
  GET  /api/endpoints/{env}/docker/containers/json?all=1&filters={"label":[…]}   0.18 : liste filtrée par étiquette
0.17.1 : plus de route recreate (l'Anneau ne s'en sert plus : la mise à jour passe par Watchtower, tests/faux_watchtower.py,
qui agit sur les mêmes conteneurs par `remplacer`).
Accès : un conteneur listé dans `caches` rend 403 (l'utilisateur standard n'y a pas accès) ; un conteneur de
`refus_ordres` se lit mais refuse stop et start (403) ; un conteneur de `figes` accepte stop et start (204) sans changer
d'état (ordre qui ne mène à rien).
Aucune adresse, aucun nom réel : tout est inventé.
"""
from __future__ import annotations

import itertools
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

CLE = "cle-portainer-de-test"
_compteur = itertools.count(1)


def _ident() -> str:
    return f"{next(_compteur):04d}" + "c0ffee" * 10


class FauxPortainer:
    def __init__(self, cle: str = CLE, version: str = "2.21.4", env: int = 3, lenteur: float = 0.0):
        self.cle, self.version, self.env, self.lenteur = cle, version, env, lenteur
        self.environnements = [{"Id": 9, "Name": "grappe", "Type": 5}, {"Id": env, "Name": "local", "Type": 1},
                               {"Id": 7, "Name": "agent", "Type": 2}]
        self.conteneurs: dict[str, dict] = {}
        self.images: dict[str, str] = {}          # identifiant d'image → date de création
        self.dernieres: dict[str, str] = {}       # nom d'image (dépôt:étiquette) → identifiant de la dernière image
        self.empreintes: dict[str, str] = {}      # 0.18 : identifiant d'image → empreinte du registre (RepoDigests)
        self.versions: dict[str, str] = {}        # 0.18 : identifiant d'image → étiquette org.opencontainers.image.version
        self.caches: set[str] = set()
        self.refus_ordres: set[str] = set()       # lecture permise, stop/start refusés (403)
        self.figes: set[str] = set()              # conteneurs qui acceptent stop/start (204) sans jamais changer d'état
        self.appels: list[tuple[str, str]] = []
        self.cles_vues: set[str] = set()
        self.app = self._application()

    # ------------------------------------------------------------ fabrication
    def image(self, nom_image: str, date: str, derniere: bool = True, empreinte: str = "", version: str = "") -> str:
        ident = "sha256:" + _ident()
        self.images[ident] = date
        if empreinte:
            self.empreintes[ident] = empreinte
        if version:
            self.versions[ident] = version
        if derniere:
            self.dernieres[nom_image] = ident
        return ident

    def ajouter(self, nom: str, image: str, nom_image: str = "", projet: str | None = "homelab",
                running: bool = True, redemarrage: str = "unless-stopped", etiquettes: dict | None = None) -> dict:
        labels = {"com.docker.compose.project": projet} if projet else {}
        labels.update(etiquettes or {})
        c = {"Id": _ident(), "Name": "/" + nom, "Image": image,
             "State": {"Status": "running" if running else "exited", "Running": running},
             "Config": {"Image": nom_image or f"ghcr.io/exemple/{nom}:latest", "Labels": labels},
             "HostConfig": {"RestartPolicy": {"Name": redemarrage}}}
        self.conteneurs[nom] = c
        return c

    def trouver(self, ref: str) -> dict | None:
        if ref in self.conteneurs:
            return self.conteneurs[ref]
        for c in self.conteneurs.values():
            if len(ref) >= 4 and c["Id"].startswith(ref):
                return c
        return None

    def remplacer(self, nom: str, image: str, demarrer: bool = True) -> dict:
        """Ce que fait Watchtower : arrête l'ancien, crée un nouveau conteneur du même nom (nouvel identifiant, nouvelle
        image), le démarre (0.22 : sauf un conteneur arrêté sans WATCHTOWER_REVIVE_STOPPED)."""
        ancien = self.conteneurs[nom]
        etat = {"Status": "running", "Running": True} if demarrer else {"Status": "exited", "Running": False}
        neuf = {**ancien, "Id": _ident(), "Image": image, "State": etat}
        self.conteneurs[nom] = neuf
        return neuf

    def transport(self) -> httpx.ASGITransport:
        return httpx.ASGITransport(app=self.app)

    def etat(self, nom: str) -> str:
        return self.conteneurs[nom]["State"]["Status"]

    # ------------------------------------------------------------ l'application
    def _application(self) -> FastAPI:
        app = FastAPI()
        moi = self

        @app.middleware("http")
        async def cle(request: Request, appel):
            moi.appels.append((request.method, request.url.path))
            if request.url.path != "/api/status":
                propose = request.headers.get("x-api-key", "")
                moi.cles_vues.add(propose)
                if propose != moi.cle:
                    return JSONResponse({"message": "Invalid API key"}, status_code=401)
            return await appel(request)

        def env_ok(env: str):
            return str(env) in {str(e["Id"]) for e in moi.environnements}

        def acces(c):
            if c is None:
                return JSONResponse({"message": "No such container"}, status_code=404)
            if c["Name"].lstrip("/") in moi.caches:
                return JSONResponse({"message": "Access denied to resource"}, status_code=403)
            return None

        @app.get("/api/status")
        def statut():
            return {"Version": moi.version, "InstanceID": "essai"}

        @app.get("/api/endpoints")
        def environnements():
            return moi.environnements

        @app.get("/api/endpoints/{env}/docker/containers/json")
        def lister(env: str, request: Request):
            if not env_ok(env):
                return JSONResponse({"message": "Unable to find an environment"}, status_code=404)
            import json as _json
            filtres = _json.loads(request.query_params.get("filters") or "{}")
            voulues = [x.split("=", 1) for x in filtres.get("label", [])]
            tous = request.query_params.get("all") in ("1", "true")
            sortie = []
            for nom, c in moi.conteneurs.items():
                if nom in moi.caches:
                    continue
                labels = c["Config"].get("Labels") or {}
                if any(labels.get(k) != v for k, v in voulues):
                    continue
                if not tous and not c["State"]["Running"]:
                    continue
                sortie.append({"Id": c["Id"], "Names": ["/" + nom], "Image": c["Config"]["Image"], "ImageID": c["Image"],
                               "State": c["State"]["Status"], "Labels": labels})
            return sortie

        @app.get("/api/endpoints/{env}/docker/containers/{ref}/json")
        def inspecter(env: str, ref: str):
            if not env_ok(env):
                return JSONResponse({"message": "Unable to find an environment"}, status_code=404)
            c = moi.trouver(ref)
            return acces(c) or c

        @app.post("/api/endpoints/{env}/docker/containers/{ref}/{action}")
        def ordre(env: str, ref: str, action: str):
            c = moi.trouver(ref)
            refus = acces(c)
            if refus:
                return refus
            if c["Name"].lstrip("/") in moi.refus_ordres:
                return JSONResponse({"message": "Access denied to resource"}, status_code=403)
            if c["Name"].lstrip("/") in moi.figes and action in ("stop", "start"):
                return Response(status_code=204)
            if action == "stop":
                if not c["State"]["Running"]:
                    return Response(status_code=304)
                c["State"] = {"Status": "exited", "Running": False}
                return Response(status_code=204)
            if action == "start":
                if c["State"]["Running"]:
                    return Response(status_code=304)
                c["State"] = {"Status": "running", "Running": True}
                return Response(status_code=204)
            return JSONResponse({"message": "page not found"}, status_code=404)

        @app.get("/api/endpoints/{env}/docker/containers/{ref}/stats")
        def stats(env: str, ref: str, stream: str = "true"):
            c = moi.trouver(ref)
            refus = acces(c)
            if refus:
                return refus
            marche = c["State"]["Running"]
            return {"memory_stats": {"usage": 300 * 1048576 if marche else 0, "limit": 8 * 1073741824,
                                     "stats": {"inactive_file": 40 * 1048576 if marche else 0}},
                    "cpu_stats": {"cpu_usage": {"total_usage": 2_000_000_000}, "system_cpu_usage": 100_000_000_000,
                                  "online_cpus": 4},
                    "precpu_stats": {"cpu_usage": {"total_usage": 1_900_000_000}, "system_cpu_usage": 99_000_000_000}}

        @app.get("/api/endpoints/{env}/docker/images/{ident}/json")
        def image(env: str, ident: str):
            if ident not in moi.images:
                return JSONResponse({"message": "No such image"}, status_code=404)
            d = {"Id": ident, "Created": moi.images[ident]}
            depot = next((c["Config"]["Image"].rsplit(":", 1)[0] for c in moi.conteneurs.values() if c["Image"] == ident), "")
            if ident in moi.empreintes:
                d["RepoDigests"] = [f"{depot or 'exemple/inconnu'}@{moi.empreintes[ident]}"]
            if ident in moi.versions:
                d["Config"] = {"Labels": {"org.opencontainers.image.version": moi.versions[ident]}}
            return d

        return app


def attendre(predicat, delai: float = 5.0, pas: float = 0.02) -> bool:
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        if predicat():
            return True
        time.sleep(pas)
    return predicat()
