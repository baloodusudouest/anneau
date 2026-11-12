"""Réglages lus dans l'environnement du conteneur. Aucune valeur personnelle dans le code."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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


def charger() -> Config:
    mot_de_passe = os.environ.get("ANNEAU_PASSWORD", "")
    if len(mot_de_passe) < 12:
        raise SystemExit("ANNEAU_PASSWORD est absent ou trop court (12 caractères au moins) : l'Anneau ne démarre pas.")
    return Config(
        password=mot_de_passe,
        data=Path(os.environ.get("ANNEAU_DATA", "/data")),
        static=Path(__file__).parent / "static",
        secret_ha=os.environ.get("ANNEAU_SECRET_HA", "").strip(),
    )
