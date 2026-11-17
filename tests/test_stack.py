"""0.10 : homelab.yml déposé dans l'Anneau (variables attendues, téléchargement), téléchargement de services.yaml,
nom du coffre Obsidian, tuile « Export des variables ancien »."""
from datetime import datetime, timedelta

import pytest

from app import sauvegardes, stack
from tests.test_sauvegardes import ARMURE, CLE_AGE, client, connecter, env, faux, fichier  # noqa: F401  (fixtures)

STACK = """# Stack d'essai
services:

  carnet:
    image: ghcr.io/baloodusudouest/carnet:latest
    environment:
      - TZ=${TZ}
      - MAISON_PASSWORD=${MAISON_PASSWORD}         # mot de passe commun
      - CARNET_VEILLE_HEURE=${CARNET_VEILLE_HEURE:-03:00}
      - CARNET_ICLOUD_USER=${CARNET_ICLOUD_USER:-}
    volumes:
      - ${DOCKER_ROOT}/carnet:/data

  base:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: ${BASE_MOT_DE_PASSE}
      TZ: ${TZ}

networks:
  default: {}
"""


def test_services_et_variables():
    services, variables = stack.services_et_variables(STACK)
    assert services == ["carnet", "base"]
    v = {x["nom"]: x for x in variables}
    assert list(v) == ["TZ", "MAISON_PASSWORD", "CARNET_VEILLE_HEURE", "CARNET_ICLOUD_USER", "DOCKER_ROOT", "BASE_MOT_DE_PASSE"]
    assert v["TZ"]["defaut"] is None and v["TZ"]["services"] == ["carnet", "base"]
    assert v["CARNET_VEILLE_HEURE"]["defaut"] == "03:00"
    assert v["CARNET_ICLOUD_USER"]["defaut"] == ""            # facultative, vide par défaut
    assert v["BASE_MOT_DE_PASSE"]["services"] == ["base"]


@pytest.mark.parametrize("texte, attendu", [
    ("", "Aucun fichier"),
    ("rien: 1\n", "Aucun service"),
    ("---\ntype: fichier\n---\n```yaml\nservices:\n  a: {}\n```\n", "balisage Markdown"),
    ("services:\n  a:\n    environment:\n      - MAISON_JETON=k3J9sLq0Zr8vXy2Nw4Tb\n", "MAISON_JETON porte une valeur"),
    ("services:\n  a:\n    environment:\n      POSTGRES_PASSWORD: motdepasse-en-clair\n", "POSTGRES_PASSWORD porte une valeur"),
])
def test_stack_refusee(texte, attendu):
    with pytest.raises(stack.StackInvalide, match=attendu):
        stack.verifier(texte)


def test_un_commentaire_ou_une_reference_ne_sont_pas_des_secrets():
    texte = STACK + "# MAISON_JETON=exemple-dans-un-commentaire-1234\n"
    assert stack.verifier(texte)[0] == ["carnet", "base"]


def test_routes_stack(client):
    assert client.get("/api/stack").status_code == 401
    connecter(client)
    e = client.get("/api/stack").json()
    assert e["present"] is False and e["coffre"] == "Maison"
    assert client.get("/api/stack/fichier").status_code == 404
    r = client.post("/api/stack", json={"texte": STACK.replace("${TZ}", "Europe/Paris", 1) + "\n"})
    assert r.status_code == 200 and r.json()["present"]
    r = client.post("/api/stack", json={"texte": STACK.replace("${BASE_MOT_DE_PASSE}", "motdepasse-en-clair")})
    assert r.status_code == 422 and "valeur écrite en clair" in r.json()["detail"]
    assert client.post("/api/stack", json={"texte": STACK}).status_code == 200
    e = client.get("/api/stack").json()
    assert e["services"] == ["carnet", "base"] and len(e["variables"]) == 6
    f = client.get("/api/stack/fichier")
    assert f.status_code == 200 and f.text == STACK and "homelab.yml" in f.headers["content-disposition"]


def test_telecharger_services(client, tmp_path):
    connecter(client)
    f = client.get("/api/services/fichier")
    assert f.status_code == 200 and "Millésime" in f.text and "services.yaml" in f.headers["content-disposition"]
    (tmp_path / "services.yaml").unlink()
    assert client.get("/api/services/fichier").status_code == 404


def test_nom_du_coffre(client):
    connecter(client)
    assert client.put("/api/reglages", json={"reglages": {"coffre_obsidian": "Maison numérique"}}).json()["reglages"]["coffre_obsidian"] == "Maison numérique"
    assert client.put("/api/reglages", json={"reglages": {"coffre_obsidian": "a/b"}}).status_code == 400
    assert client.put("/api/reglages", json={"reglages": {"coffre_obsidian": ""}}).status_code == 400
    assert client.get("/api/stack").json()["coffre"] == "Maison numérique"


def test_tuile_export_ancien(tmp_path):
    t = datetime.now().astimezone()
    assert sauvegardes.a_traiter(tmp_path, t) == []                                   # sans clé publique : rien
    tuiles = sauvegardes.a_traiter(tmp_path, t, cle_publique=CLE_AGE)
    assert [x["phrase"] for x in tuiles] == ["Export des variables ancien"] and "aucun export" in tuiles[0]["detail"]
    sauvegardes.ranger_variables(tmp_path, ARMURE, t - timedelta(days=31))
    tuiles = sauvegardes.a_traiter(tmp_path, t, cle_publique=CLE_AGE)
    assert tuiles and "31 jours" in tuiles[0]["detail"]
    sauvegardes.ranger_variables(tmp_path, ARMURE, t - timedelta(days=2))
    assert sauvegardes.a_traiter(tmp_path, t, cle_publique=CLE_AGE) == []


def test_tuile_export_dans_l_etat(client):
    connecter(client)
    assert client.put("/api/cle-publique", json={"cle_publique": CLE_AGE}).status_code == 200
    phrases = [x["phrase"] for x in client.get("/api/etat").json()["a_traiter"]]
    assert "Export des variables ancien" in phrases
    assert client.post("/api/variables-chiffrees", content=ARMURE, headers={"Content-Type": "text/plain"}).status_code == 200
    phrases = [x["phrase"] for x in client.get("/api/etat").json()["a_traiter"]]
    assert "Export des variables ancien" not in phrases
