"""0.19 : les thèmes des réglages (frontend/src/lib/reglages/themes.js), essayés avec Node : adresses, redirections,
résumé de chaque thème (chiffre, phrase, pastille). Sauté si Node n'est pas installé."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

THEMES = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "reglages" / "themes.js"
node = shutil.which("node")
pytestmark = pytest.mark.skipif(not node, reason="Node absent")


def js(code: str):
    script = f"import * as t from {json.dumps(THEMES.as_uri())};\nconst sortie = (() => {{ {code} }})();\nconsole.log(JSON.stringify(sortie));"
    r = subprocess.run([node, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_adresses_et_redirections():
    a = js("""return ['#/reglages', '#/reglages/stack', '#/reglages/stack/exports', '#/variables', '#/sauvegardes', '#/carte',
                      '#/reglages/inconnu', '#/', ''].map(t.lireAdresse)""")
    assert [(x["page"], x["theme"], x["section"], x["adresse"]) for x in a] == [
        ("reglages", "", "", "#/reglages"), ("reglages", "stack", "", "#/reglages/stack"),
        ("reglages", "stack", "exports", "#/reglages/stack/exports"), ("reglages", "stack", "", "#/reglages/stack"),
        ("reglages", "sauvegardes", "liste", "#/reglages/sauvegardes/liste"), ("reglages", "maison", "", "#/reglages/maison"),
        ("reglages", "", "", "#/reglages"), ("anneau", "", "", "#/"), ("anneau", "", "", "")]


def test_resume_sans_lecture_ne_devine_rien():
    r = js("return t.resumer({})")
    assert set(r) == {"services", "stack", "sauvegardes", "connexions", "maison"}
    assert all(v["chiffre"] == "—" and v["signal"] is None for v in r.values())


def test_resume_et_pastilles():
    r = js("""
      const maintenant = Date.parse('2026-11-26T12:00:00Z')
      return t.resumer({
        etat: { familles: [{ services: [{ a_jour: false }, {}] }, { services: [{}] }],
                fraicheur: { erreurs: ['x'], ha_attendu: true, ha_recu_le: '' },
                volumes: [{ nom: 'Volume 1', machine: 'Synology', pourcentage: 99.9, etat: 'panne' }, { nom: 'Data', pourcentage: 40 }] },
        stack: { present: true, variables: [1, 2, 3], services: [1] },
        exports: [{ nom: '2026-10-01-120000.age' }], cle: 'age1x',
        https: { https: false, garde: true },
        sauvegardes: { heure: '03:30', derniere: { le: '2026-11-26T03:30:00+01:00', automatique: true, applis: ['a', 'b'], ratees: { c: 'x' } } },
        connexions: { services: [{ nom: 'Portainer', etat: 'repond' }, { nom: 'GitHub', etat: 'ne_repond_pas' }, { nom: 'HA', etat: 'pas_relie' }] },
        carte: { etat: { erreur: '' } },
      }, maintenant)""")
    assert r["services"]["chiffre"] == 3 and r["services"]["signal"] == {"niveau": "panne", "texte": "1 ligne écartée"}
    assert r["stack"]["chiffre"] == 3 and r["stack"]["signal"] == {"niveau": "action", "texte": "https requis pour chiffrer"}
    assert r["sauvegardes"]["chiffre"] == 2 and r["sauvegardes"]["signal"] == {"niveau": "traiter", "texte": "1 appli non lue"}
    assert r["connexions"]["chiffre"] == "2/3" and r["connexions"]["signal"]["niveau"] == "panne"
    assert r["maison"]["chiffre"] == "99,9" and r["maison"]["signal"] == {"niveau": "panne", "texte": "1 volume plein"}


def test_export_vieux_et_https_ok():
    r = js("""return t.resumer({ stack: { present: true, variables: [], services: [] }, exports: [{ nom: '2026-10-01-1.age' }],
                                 https: { https: true, garde: true } }, Date.parse('2026-11-26T12:00:00Z'))""")
    assert r["stack"]["signal"] == {"niveau": "traiter", "texte": "Export de plus de 30 jours"}
