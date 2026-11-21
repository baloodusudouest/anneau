"""Réglages lus dans l'environnement du conteneur. Aucune valeur personnelle dans le code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import maison

APPLI = "anneau"


@dataclass(frozen=True)
class Config:
    password: str
    data: Path
    static: Path
    secret_ha: str = ""              # secret que Home Assistant joint à ses envois ; vide : envois refusés
    attente_connexion: bool = True   # délai anti-essais ; coupé dans les tests
    veille: bool = True              # la sonde tourne toute seule ; coupée dans les tests
    periode: int = 60                # secondes entre deux tours de sonde
    atlas_depot: str = ""            # 0.11 : dépôt GitHub de la carte de la maison (« propriétaire/atlas », réduit à carte.json) ; vide : pas de carte
    github_jeton: str = ""           # jeton GitHub en lecture seule sur ce dépôt (contenu), jamais montré ni envoyé au navigateur
    sauvegarde_auto: bool = True     # 0.8 : collecte quotidienne des réglages des applis ; coupée dans les tests
    portainer_url: str = ""          # 0.17 : adresse de Portainer ; vide : pas de boutons Allumer / Éteindre / Mettre à jour
    portainer_cle: str = ""          # 0.17 : clé d'API de l'utilisateur Portainer « anneau » (X-API-Key) ; jamais montrée ni écrite
    portainer_env: str = ""          # 0.17 : numéro de l'environnement ; vide : le premier environnement Docker de /api/endpoints

    def __repr__(self) -> str:       # 0.17 : jamais un secret dans une trace
        return f"Config(data={self.data!s}, portainer_url={self.portainer_url!r}, portainer_env={self.portainer_env!r})"

    @property
    def portainer(self) -> bool:
        return bool(self.portainer_url and self.portainer_cle)


def charger() -> Config:
    mot_de_passe = maison.mot_de_passe()      # 0.8 : MAISON_PASSWORD seul (ANNEAU_PASSWORD n'est plus lu)
    if len(mot_de_passe) < 12:
        raise SystemExit("MAISON_PASSWORD est absent ou trop court (12 caractères au moins) : l'Anneau ne démarre pas.")
    return Config(
        password=mot_de_passe,
        data=Path(os.environ.get("ANNEAU_DATA", "/data")),
        static=Path(__file__).parent / "static",
        secret_ha=os.environ.get("ANNEAU_SECRET_HA", "").strip(),
        atlas_depot=os.environ.get("ANNEAU_ATLAS_DEPOT", "").strip(),
        github_jeton=os.environ.get("ANNEAU_GITHUB_JETON", "").strip(),
        portainer_url=os.environ.get("ANNEAU_PORTAINER_URL", "").strip().rstrip("/"),
        portainer_cle=os.environ.get("ANNEAU_PORTAINER_CLE", "").strip(),
        portainer_env=os.environ.get("ANNEAU_PORTAINER_ENV", "").strip(),
    )
