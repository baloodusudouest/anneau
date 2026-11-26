"""0.10.1 : le lien https de l'avertissement « ouvert en http » de la page Variables.
Dans un fichier à part : il lance son propre navigateur (règle de nom anneau.test → 127.0.0.1), ce que Playwright
refuse tant que le navigateur des autres tests d'écran est ouvert."""
from __future__ import annotations

import re

import pytest

from tests.interface.test_interface import ECRANS, MDP, monde  # noqa: F401  (fixture : un Anneau de démonstration)

playwright = pytest.importorskip("playwright.sync_api")


def test_lien_https_quand_la_page_est_en_http(monde):
    """0.10.1 : ouvert par un nom autre que 127.0.0.1 (contexte non sûr), la page Variables (0.19 : Réglages › Stack) le dit ; si une tuile
    https permet de tirer l'adresse https de l'Anneau, l'avertissement donne un lien cliquable vers elle."""
    base, dossier = monde
    port = int(base.rsplit(":", 1)[1])
    fichier = dossier / "data" / "services.yaml"
    avant = fichier.read_text(encoding="utf-8")
    with playwright.sync_playwright() as p:
        b = p.chromium.launch(args=["--host-resolver-rules=MAP anneau.test 127.0.0.1"])
        pg = b.new_page(viewport=ECRANS["iphone"])
        pg.set_default_timeout(10000)
        pg.goto(f"http://anneau.test:{port}")
        pg.get_by_label(re.compile("Mot de passe")).fill(MDP)
        pg.get_by_role("button", name="Se connecter").click()
        pg.locator("svg.anneau").wait_for()
        assert pg.evaluate("window.isSecureContext") is False
        pg.goto(f"http://anneau.test:{port}/#/variables")
        alerte = pg.get_by_role("alert", name="Page non sûre")
        alerte.wait_for()
        assert "en http" in pg.locator("#vu-par-l-anneau").inner_text()           # 0.19 : vu par le serveur aussi
        assert "port 9094" in alerte.inner_text() and pg.locator("#lien-https").count() == 0   # aucune tuile https : texte seul
        try:
            fichier.write_text(avant + '  - { nom: Coffre, famille: Proches, locale: "https://nas.exemple.ts.net:9095", '
                                       'sonde: "http://127.0.0.1:8095/health", icone: carnet }\n', encoding="utf-8")
            assert pg.evaluate("fetch('/api/recharger', {method: 'POST'}).then(r => r.ok)")   # depuis la page : même nom
            pg.reload()
            lien = pg.locator("#lien-https")
            lien.wait_for()
            assert lien.get_attribute("href") == f"https://nas.exemple.ts.net:{port + 1000}/#/reglages/stack"
            assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        finally:
            fichier.write_text(avant, encoding="utf-8")
            pg.evaluate("fetch('/api/recharger', {method: 'POST'}).then(r => r.ok)")
            b.close()
