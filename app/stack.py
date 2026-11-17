"""0.10 : le fichier de la stack (homelab.yml), gardé dans le dossier de l'Anneau pour deux usages :
  - la liste des variables attendues (noms, défaut, services qui les lisent) de la page Variables ;
  - « Télécharger homelab.yml », prêt pour Portainer, sans le copier depuis Obsidian.

Il arrive par un import de fichier (Variables › Importer homelab.yml), jamais collé. Il ne doit contenir que des
références ${VARIABLE} : une ligne qui ressemble à une valeur de secret fait refuser tout le fichier.
Le coffre Obsidian fait foi ; ce fichier n'en est qu'une copie déposée par Julien.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

NOM = "homelab.yml"
TAILLE = 512 * 1024

RE_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:(:?-)([^}]*))?\}")
RE_SERVICE = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*(?:#.*)?$")
# Un nom qui dit mot de passe, secret, jeton ou clé, suivi d'une valeur écrite en clair (pas une référence ${…}).
RE_SENSIBLE = re.compile(r"(?i)\b([A-Z0-9_]*(?:PASSWORD|SECRET|JETON|TOKEN|API_KEY|_CLE|ENCRYPTION_KEY|HASH)[A-Z0-9_]*)"
                         r"\s*[:=]\s*[\"']?(?!\$\{)([A-Za-z0-9_+/=.-]{8,})")


class StackInvalide(ValueError):
    """Le fichier reçu n'est pas une stack utilisable : rien n'est écrit."""


def chemin(data: Path) -> Path:
    return data / NOM


def services_et_variables(texte: str) -> tuple[list[str], list[dict]]:
    """Les services de la stack et, pour chaque variable ${NOM}, son défaut (None : aucun, donc à remplir)
    et les services qui la lisent, dans l'ordre d'apparition."""
    services: list[str] = []
    variables: dict[str, dict] = {}
    dedans, courant = False, ""
    for ligne in texte.splitlines():
        if re.match(r"^services:\s*(?:#.*)?$", ligne):
            dedans = True
            continue
        if dedans and re.match(r"^[^\s#]", ligne):
            dedans, courant = False, ""
        if dedans:
            m = RE_SERVICE.match(ligne)
            if m:
                courant = m.group(1)
                services.append(courant)
        sans_commentaire = ligne.split(" #", 1)[0] if not ligne.lstrip().startswith("#") else ""
        for nom, sorte, defaut in RE_REF.findall(sans_commentaire):
            v = variables.setdefault(nom, {"nom": nom, "defaut": None, "services": []})
            if sorte and v["defaut"] is None:
                v["defaut"] = defaut
            if courant and courant not in v["services"]:
                v["services"].append(courant)
    return services, list(variables.values())


def verifier(texte: str) -> tuple[list[str], list[dict]]:
    if not isinstance(texte, str) or not texte.strip():
        raise StackInvalide("Aucun fichier reçu.")
    if len(texte.encode("utf-8")) > TAILLE:
        raise StackInvalide("Fichier trop gros pour être homelab.yml (512 Ko au plus).")
    if texte.lstrip().startswith(("---\ntype:", "# homelab.yml\n")) or "```" in texte:
        raise StackInvalide("Ce fichier contient du balisage Markdown (copié depuis la note Obsidian ?) : "
                            "exporte seulement le bloc YAML, sans les ``` ni l'en-tête de la note.")
    for n, ligne in enumerate(texte.splitlines(), 1):
        if ligne.lstrip().startswith("#"):
            continue
        m = RE_SENSIBLE.search(ligne)
        if m:
            raise StackInvalide(f"Ligne {n} : {m.group(1)} porte une valeur écrite en clair. La stack ne doit contenir "
                                "que des références ${…} : les valeurs restent dans Portainer.")
    services, variables = services_et_variables(texte)
    if not services:
        raise StackInvalide("Aucun service trouvé : ce n'est pas un fichier de stack (bloc « services: » attendu).")
    return services, variables


def importer(data: Path, texte: str) -> dict:
    """Vérifie le texte en entier, puis remplace homelab.yml (écriture à côté, puis renommage)."""
    verifier(texte)
    f = chemin(data)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(texte, encoding="utf-8")
    os.replace(tmp, f)
    return etat(data)


def etat(data: Path) -> dict:
    f = chemin(data)
    if not f.is_file():
        return {"present": False, "le": "", "services": [], "variables": []}
    texte = f.read_text(encoding="utf-8", errors="replace")
    services, variables = services_et_variables(texte)
    le = datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return {"present": True, "le": le, "services": services, "variables": variables}
