"""Le fichier des services : familles, machines, services, réglages.

Il vit dans /data/services.yaml, hors du dépôt : c'est lui qui porte les vraies adresses.
S'il est absent, l'Anneau démarre sur l'exemple inventé et le dit.
Depuis la 0.6, il se pose à la main dans le dossier ou s'importe depuis Réglages (`importer`).
"""
from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

import yaml

EXEMPLE = Path(__file__).parent / "services.exemple.yaml"
NOM = "services.yaml"
PRECEDENT = "services.precedent.yaml"     # 0.6 : le fichier d'avant le dernier import, gardé en secours
TAILLE_MAX = 512 * 1024                   # un fichier de services fait quelques kilo-octets


class FichierInvalide(Exception):
    pass


def cle(nom: str) -> str:
    """Un nom lisible devient une clé stable : « Kit d'urgence » → « kit-d-urgence »."""
    brut = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", brut).strip("-")


@dataclass(frozen=True)
class Service:
    nom: str
    cle: str
    famille: str
    locale: str                 # adresse à la maison
    privee: str = ""            # adresse par le réseau privé ; vide : la locale sert partout
    sonde: str = ""             # adresse interrogée ; vide : la locale
    icone: str = ""             # nom d'un pictogramme, ou adresse d'une image
    cadre: bool | None = None   # affiché dans l'Anneau : oui, non, ou vide = essayer (sauf si le service l'interdit)
    machine: str = ""           # si cette machine ne répond pas, la panne est la sienne
    arret_attendu: bool = False  # un service qu'on éteint exprès (PC de calcul) n'est jamais « en panne »
    sauvegarde: bool = True     # 0.8 : « sauvegarde: false » retire de la collecte une tuile dont la sonde finit par /health sans être une appli maison

    @property
    def a_sonder(self) -> str:
        return self.sonde or self.locale


@dataclass(frozen=True)
class Machine:
    nom: str
    cle: str
    sonde: str = ""
    famille: str = ""           # la famille que sa panne (ou celle d'un de ses volumes) colore sur l'anneau


@dataclass(frozen=True)
class Fichier:
    familles: tuple[dict, ...] = ()
    machines: tuple[Machine, ...] = ()
    services: tuple[Service, ...] = ()
    seuil_disque: float = 99.8
    hotes_prives: tuple[str, ...] = ()
    hote_local: str = ""        # l'hôte de la maison (ex. l'adresse du NAS) : remplacé par celui par lequel l'Anneau est ouvert
    famille_ha: str = ""        # la famille que colore « Home Assistant est muet »
    silence_ha: int = 90        # 0.4.1 : minutes sans envoi de Home Assistant avant de le dire muet
    lu_le: str = ""
    modifie_le: str = ""
    exemple: bool = False
    erreurs: tuple[str, ...] = field(default=())


def adresse_https(f: Fichier, port: int | None) -> str:
    """0.10.1 : l'adresse https de l'Anneau, tirée des tuiles. Les applis du NAS dont la tuile ouvre en https et
    sonde en http sur l'hôte de la maison donnent le nom https (Tailscale) et l'écart de port (Tailscale Serve :
    +1000). Appliqués au port par lequel l'Anneau est ouvert : http://192.0.2.90:8094 → https://….ts.net:9094.
    Vide si aucune tuile ne le permet ou si le port est inconnu."""
    if not port:
        return ""
    vus: Counter = Counter()
    for s in f.services:
        try:
            l, so = urlsplit(s.locale), urlsplit(s.sonde)
            lp, sp = l.port, so.port
        except ValueError:
            continue
        if l.scheme == "https" and so.scheme == "http" and l.hostname and lp and sp and lp > sp \
                and (not f.hote_local or so.hostname == f.hote_local):
            vus[(l.hostname, lp - sp)] += 1
    if not vus:
        return ""
    (hote, ecart), _ = vus.most_common(1)[0]
    return f"https://{hote}:{port + ecart}"


def _adresse(valeur, quoi: str, erreurs: list[str]) -> str:
    v = str(valeur or "").strip()
    if v and not re.match(r"^https?://[^\s/]+", v):
        erreurs.append(f"{quoi} : « {v} » n'est pas une adresse http(s).")
        return ""
    try:                      # 0.10.2 : « http://nas:80a » arrêtait toute la veille ; écartée dès la lecture
        urlsplit(v).port
    except ValueError:
        erreurs.append(f"{quoi} : « {v} » a un port invalide.")
        return ""
    return v[:-1] if v.endswith("/") and v.count("/") == 3 else v    # « http://hôte/ » → « http://hôte »


def _cadre(valeur) -> bool | None:
    """« cadre: true » force le cadre, « cadre: false » l'interdit ; absent ou « auto » : l'Anneau essaie."""
    if isinstance(valeur, bool):
        return valeur
    return {"oui": True, "non": False}.get(str(valeur or "").strip().lower())


def lire(chemin: Path) -> Fichier:
    """Lit le fichier ; une ligne fausse est écartée et signalée, le reste sert."""
    exemple = not chemin.is_file()
    source = EXEMPLE if exemple else chemin
    try:
        texte = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FichierInvalide(f"Le fichier des services est illisible : {exc}") from exc
    modifie = "" if exemple else datetime.fromtimestamp(chemin.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return comprendre(texte, exemple=exemple, modifie_le=modifie)


def importer(dossier: Path, texte: str) -> Fichier:
    """0.6 : remplace services.yaml par le texte reçu de Réglages. Le texte est d'abord compris en entier :
    un fichier illisible ou sans aucun service valable est refusé et rien n'est touché. L'ancien fichier est
    gardé sous le nom services.precedent.yaml ; le nouveau est écrit à côté puis mis en place d'un coup."""
    if len(texte.encode("utf-8")) > TAILLE_MAX:
        raise FichierInvalide("Ce fichier est trop gros pour être un fichier de services (512 Ko au plus).")
    lu = comprendre(texte)
    if not lu.services:
        detail = " " + " ".join(lu.erreurs[:3]) if lu.erreurs else ""
        raise FichierInvalide("Ce fichier ne contient aucun service valable : rien n'a été changé." + detail)
    cible, neuf = dossier / NOM, dossier / (NOM + ".nouveau")
    try:
        neuf.write_text(texte, encoding="utf-8")
        if cible.is_file():
            os.replace(cible, dossier / PRECEDENT)
        os.replace(neuf, cible)
    except OSError as exc:
        neuf.unlink(missing_ok=True)
        raise OSError(f"Le dossier de données de l'Anneau n'accepte pas l'écriture : {exc}") from exc
    return lire(cible)


def comprendre(texte: str, exemple: bool = False, modifie_le: str = "") -> Fichier:
    """Le texte d'un fichier de services devient un Fichier, sans rien lire ni écrire sur le disque."""
    try:
        brut = yaml.safe_load(texte) or {}
    except yaml.YAMLError as exc:
        raise FichierInvalide(f"Le fichier des services est illisible : {exc}") from exc
    if not isinstance(brut, dict):
        raise FichierInvalide("Le fichier des services doit contenir des rubriques (familles, services…).")
    erreurs: list[str] = []
    familles = []
    for f in brut.get("familles") or []:
        nom = str((f or {}).get("nom", "")).strip() if isinstance(f, dict) else str(f).strip()
        if nom:
            familles.append({"nom": nom, "cle": cle(nom), "icone": str(f.get("icone", "")) if isinstance(f, dict) else ""})
    connues = {f["nom"] for f in familles}
    machines = []
    for m in brut.get("machines") or []:
        nom = str((m or {}).get("nom", "")).strip()
        if nom:
            famille = str(m.get("famille", "")).strip()
            machines.append(Machine(nom=nom, cle=cle(nom), sonde=_adresse(m.get("sonde"), f"Machine {nom}", erreurs),
                                    famille=famille if famille in connues else ""))
    noms_machines = {m.nom for m in machines}
    services, vus = [], set()
    for s in brut.get("services") or []:
        if not isinstance(s, dict) or not str(s.get("nom", "")).strip():
            erreurs.append("Un service sans nom a été écarté.")
            continue
        nom = str(s["nom"]).strip()
        famille = str(s.get("famille", "")).strip()
        if famille not in connues:
            erreurs.append(f"{nom} : famille « {famille} » inconnue, service écarté.")
            continue
        if cle(nom) in vus:
            erreurs.append(f"{nom} : nom en double, second écarté.")
            continue
        locale = _adresse(s.get("locale"), nom, erreurs)
        if not locale:
            erreurs.append(f"{nom} : pas d'adresse locale, service écarté.")
            continue
        machine = str(s.get("machine", "")).strip()
        if machine and machine not in noms_machines:
            erreurs.append(f"{nom} : machine « {machine} » inconnue, ignorée.")
            machine = ""
        vus.add(cle(nom))
        services.append(Service(nom=nom, cle=cle(nom), famille=famille, locale=locale,
                                privee=_adresse(s.get("privee"), nom, erreurs), sonde=_adresse(s.get("sonde"), nom, erreurs),
                                icone=str(s.get("icone", "")).strip(), cadre=_cadre(s.get("cadre")),
                                machine=machine, arret_attendu=bool(s.get("arret_attendu", False)),
                                sauvegarde=s.get("sauvegarde", True) is not False))
    reglages = brut.get("reglages") or {}
    try:
        seuil = float(reglages.get("seuil_disque", 99.8))
    except (TypeError, ValueError):
        erreurs.append("seuil_disque illisible : 99,8 % est gardé.")
        seuil = 99.8
    try:
        silence = int(reglages.get("silence_ha", 90))
        if silence < 2:
            raise ValueError
    except (TypeError, ValueError):
        erreurs.append("silence_ha illisible (un nombre de minutes, 2 au moins) : 90 minutes sont gardées.")
        silence = 90
    return Fichier(
        familles=tuple(familles), machines=tuple(machines), services=tuple(services), seuil_disque=seuil, silence_ha=silence,
        hotes_prives=tuple(str(h).strip().lower() for h in (reglages.get("hotes_prives") or []) if str(h).strip()),
        hote_local=str(reglages.get("hote_local", "")).strip().lower(),
        famille_ha=str(reglages.get("famille_ha", "")).strip() if str(reglages.get("famille_ha", "")).strip() in connues else "",
        lu_le=datetime.now().astimezone().isoformat(timespec="seconds"),
        modifie_le=modifie_le,
        exemple=exemple, erreurs=tuple(erreurs))
