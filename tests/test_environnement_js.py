"""0.20 : le homelab avec ses valeurs (frontend/src/lib/environnement.js : resoudre, sansBlocMarkdown), essayé avec Node.
Mêmes règles que Docker Compose ; commentaires jamais touchés. Sauté si Node n'est pas installé."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "environnement.js"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(not node, reason="Node absent")


def js(code: str):
    script = f"import * as e from {json.dumps(ENV.as_uri())};\nconst sortie = (() => {{ {code} }})();\nconsole.log(JSON.stringify(sortie));"
    r = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


HOMELAB = """# Variable à créer : ${MAISON_PASSWORD} (ce commentaire ne doit pas changer)
services:
  anneau:
    environment:
      - TZ=${TZ}
      - MAISON_PASSWORD=${MAISON_PASSWORD}          # mot de passe ${MAISON_PASSWORD} commun
      - CLE=${ANNEAU_CLE:-}
      - URL=${ANNEAU_HA_URL:-http://192.0.2.29:8123}
      - VIDE=${VIDE-defaut}
      - ABSENTE=${ABSENTE}
      - DOLLAR=$$HOME
      - 'GUILLEMETS=${TZ} # pas un commentaire'
"""


def test_regles_de_compose_et_commentaires_intacts():
    r = js(f"""return e.resoudre({json.dumps(HOMELAB)}, {{ TZ: 'Europe/Paris', MAISON_PASSWORD: 's3cret', ANNEAU_HA_URL: '', VIDE: '' }})""")
    lignes = r["texte"].split("\n")
    assert lignes[0] == "# Variable à créer : ${MAISON_PASSWORD} (ce commentaire ne doit pas changer)"
    assert lignes[4] == "      - TZ=Europe/Paris"
    assert lignes[5] == "      - MAISON_PASSWORD=s3cret          # mot de passe ${MAISON_PASSWORD} commun"
    assert lignes[6] == "      - CLE="
    assert lignes[7] == "      - URL=http://192.0.2.29:8123"           # :- avec valeur vide → défaut
    assert lignes[8] == "      - VIDE="                                  # - avec valeur vide → la valeur vide
    assert lignes[9] == "      - ABSENTE=${ABSENTE}"
    assert lignes[10] == "      - DOLLAR=$$HOME"
    assert lignes[11] == "      - 'GUILLEMETS=Europe/Paris # pas un commentaire'"
    assert r["manquantes"] == ["ABSENTE"]
    assert r["remplacees"] == ["TZ", "MAISON_PASSWORD", "VIDE"]


def test_sans_valeurs_rien_ne_change_sauf_les_defauts():
    r = js(f"""return e.resoudre({json.dumps(HOMELAB)}, {{}})""")
    assert "${TZ}" in r["texte"] and "URL=http://192.0.2.29:8123" in r["texte"]
    assert set(r["manquantes"]) == {"TZ", "MAISON_PASSWORD", "ABSENTE"}


def test_bloc_markdown_retire():
    r = js("""return e.sansBlocMarkdown('Texte\\n```yaml\\nservices:\\n  a:\\n```\\n')""")
    assert r == "Texte\nservices:\n  a:\n"
