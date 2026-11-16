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
    atlas_depot: str = ""            # 0.5 : dépôt GitHub d'Atlas (« propriétaire/atlas ») ; vide : pas d'Atlas
    github_jeton: str = ""           # 0.5 : jeton GitHub en lecture seule sur ce dépôt (contenu), jamais montré
    sauvegarde_auto: bool = True     # 0.8 : collecte quotidienne des réglages des applis ; coupée dans les tests


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
    )
