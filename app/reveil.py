"""0.19 — réveiller une machine (le PC de calcul) par un webhook de Home Assistant.

Choix de Julien (26/11/2026, grill puis conseil) :
- l'Anneau ne détient aucun jeton de Home Assistant : il appelle seulement un webhook (`POST <HA>/api/webhook/<id>`,
  sans corps) ; c'est Home Assistant qui envoie le paquet Wake-on-LAN (intégration wake_on_lan) ;
- seules les tuiles marquées `reveil: true` dans services.yaml (aujourd'hui « Pc de calcul ») ont le bouton, et seulement
  quand elles sont éteintes ; une appli qui en a besoin (`besoin: Pc de calcul`, Millésime) le montre aussi dans sa fiche ;
- réveiller seulement, jamais éteindre ; confirmé à l'écran ; jamais en lecture seule ;
- l'identifiant du webhook (ANNEAU_HA_WEBHOOK_REVEIL) ne sort jamais : ni à l'écran, ni au journal, ni dans une trace ;
- suivi : la sonde habituelle de la tuile ; « répond » = réveillé ; au-delà de 3 min : « pas réveillé ».
« Vérifier » (fiche Connexions) ne déclenche jamais le webhook : il regarde seulement que Home Assistant répond.
"""
from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger("anneau.reveil")

DELAI = 180            # secondes : au-delà, « pas réveillé »
REBOND = 60            # secondes : après un réveil raté, un nouvel ordre sur la même tuile attend ce temps
DELAI_APPEL = 10.0     # secondes : délai de l'appel au webhook


class Refus(Exception):
    def __init__(self, statut: int, phrase: str):
        super().__init__(phrase)
        self.statut, self.phrase = statut, phrase


class Reveil:
    """Les ordres de réveil en cours, par tuile. `transport` : un faux Home Assistant dans les tests."""

    def __init__(self, url: str, webhook: str, noter=None, horloge=time.monotonic, transport=None):
        self.url, self._webhook = url.rstrip("/"), webhook
        self._noter = noter or (lambda *a, **k: None)
        self._horloge, self._transport = horloge, transport
        self.ordres: dict[str, dict] = {}       # clé → {etat: attente|fini|perdu|refus, a, phrase}

    def __repr__(self) -> str:                  # jamais l'identifiant du webhook dans une trace
        return f"Reveil(url={self.url!r}, regle={self.actif})"

    @property
    def actif(self) -> bool:
        return bool(self.url and self._webhook)

    def _client(self, delai: float = DELAI_APPEL) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=delai, transport=self._transport, follow_redirects=False)

    def en_cours(self) -> bool:
        return any(o["etat"] == "attente" for o in self.ordres.values())

    def raison(self, t, eteint: bool, lecture_seule: bool, manque: str = "") -> str:
        """Pourquoi pas de bouton (vide : bouton permis)."""
        if not t.reveil:
            return "Cette tuile ne se réveille pas depuis l'Anneau."
        if not self.actif:
            return manque or "Le réveil n'est pas relié à Home Assistant."
        if lecture_seule:
            return "Lecture seule : l'Anneau n'envoie aucun ordre."
        if not eteint:
            return "Elle répond déjà."
        return ""

    async def ordonner(self, t, eteint: bool, lecture_seule: bool, manque: str = "") -> dict:
        raison = self.raison(t, eteint, lecture_seule, manque)
        if raison:
            self._noter("reveil", t.cle, f"refusé : {raison}")
            raise Refus(409 if raison == "Elle répond déjà." else 403, raison)
        o = self.ordres.get(t.cle)
        if o and (o["etat"] == "attente" or (o["etat"] != "fini" and self._horloge() - o["a"] < REBOND)):
            raise Refus(429, "Un réveil vient d'être demandé : attends une minute.")
        try:
            async with self._client() as c:
                r = await c.post(f"{self.url}/api/webhook/{self._webhook}")
        except httpx.HTTPError as exc:
            phrase = f"Home Assistant ne répond pas ({type(exc).__name__})."
            self.ordres[t.cle] = {"etat": "refus", "a": self._horloge(), "phrase": phrase}
            self._noter("reveil", t.cle, f"échec : {phrase}")
            raise Refus(502, phrase) from None
        if r.status_code >= 400:
            # HA rend 200 pour un webhook inconnu (il ne dit pas s'il existe) : un refus ici vient d'ailleurs (relais, 405…)
            phrase = f"Home Assistant a refusé l'appel (code {r.status_code})."
            self.ordres[t.cle] = {"etat": "refus", "a": self._horloge(), "phrase": phrase}
            self._noter("reveil", t.cle, f"échec : {phrase}")
            raise Refus(502, phrase)
        self.ordres[t.cle] = {"etat": "attente", "a": self._horloge(), "phrase": "Réveil demandé à Home Assistant…"}
        self._noter("reveil", t.cle, "lancé")
        return self.vue_ordre(t.cle)

    async def suivre(self, tuiles: dict, repond) -> None:
        """Après chaque tour de veille : la tuile répond-elle ? `repond(t)` : la sonde de la veille."""
        for cle, o in self.ordres.items():
            if o["etat"] != "attente":
                continue
            t = tuiles.get(cle)
            if t is not None and await repond(t):
                o.update(etat="fini", phrase="Réveillé : il répond.")
                self._noter("reveil", cle, "fini")
            elif self._horloge() - o["a"] > DELAI:
                o.update(etat="perdu", phrase="Pas réveillé après 3 min : vérifie le Wake-on-LAN (BIOS, carte réseau, "
                                               "démarrage rapide de Windows) et l'automatisation de Home Assistant.")
                self._noter("reveil", cle, "perdu")

    def vue_ordre(self, cle: str) -> dict | None:
        o = self.ordres.get(cle)
        if not o:
            return None
        return {"etat": o["etat"], "phrase": o["phrase"], "depuis_s": int(self._horloge() - o["a"])}

    def vue(self, t, eteint: bool, lecture_seule: bool, manque: str = "") -> dict | None:
        """Pour /api/etat : rien si la tuile n'est pas réveillable."""
        if not t.reveil:
            return None
        ordre = self.vue_ordre(t.cle)
        attente = bool(ordre and ordre["etat"] == "attente")
        return {"possible": not attente and not self.raison(t, eteint, lecture_seule, manque),
                "raison": "" if attente else self.raison(t, eteint, lecture_seule, manque),
                "eteint": eteint, "ordre": ordre}

    async def essai(self) -> tuple[bool, str]:
        """« Vérifier » : Home Assistant répond-il ? `GET /api/` sans jeton → 401 attendu. Ne déclenche jamais le webhook."""
        if not self.actif:
            return False, "Pas relié."
        try:
            async with self._client(5.0) as c:
                r = await c.get(f"{self.url}/api/")
        except httpx.HTTPError as exc:
            return False, f"Home Assistant ne répond pas à {self.url} ({type(exc).__name__})."
        if r.status_code in (200, 401):
            return True, "Home Assistant répond. Le webhook n'est pas appelé ici : seul « Réveiller le PC » l'appelle."
        return False, f"Réponse inattendue de Home Assistant (code {r.status_code})."
