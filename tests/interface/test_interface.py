"""Tests d'écran de l'Anneau, sur PC et sur iPhone, contre un faux réseau."""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
RACINE = Path(__file__).resolve().parents[2]
MDP, SECRET = "essai-essai-essai", "secret-de-demonstration"
ECRANS = {"pc": {"width": 1280, "height": 860}, "iphone": {"width": 390, "height": 760}}


@pytest.fixture(scope="module")
def monde(tmp_path_factory):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    dossier = tmp_path_factory.mktemp("ui")
    proc = subprocess.Popen([sys.executable, "-m", "tests.interface.serveur", str(dossier), str(port)], cwd=RACINE)
    base = f"http://127.0.0.1:{port}"
    for _ in range(200):
        try:
            if urllib.request.urlopen(base + "/health", timeout=1).status == 200:
                break
        except OSError:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("L'Anneau de démonstration n'a pas démarré.")
    yield base, dossier
    proc.terminate()


@pytest.fixture(scope="module", params=list(ECRANS))
def page(monde, request):
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport=ECRANS[request.param])
        pg.set_default_timeout(10000)
        pg.ecran = request.param
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        pg.goto(monde[0])
        pg.get_by_label(re.compile("Mot de passe")).fill(MDP)
        pg.get_by_role("button", name="Se connecter").click()
        pg.locator("svg.anneau").wait_for()
        yield pg
        assert not erreurs, erreurs
        b.close()


def morts(monde, *adresses):
    (monde[1] / "morts.txt").write_text("\n".join(("s=calcul",) + adresses) + "\n")


def attendre_centre(page, texte):
    """L'écran se relit toutes les vingt secondes : pour le test, on recharge jusqu'à voir le centre attendu."""
    for _ in range(40):
        page.reload()
        page.locator("svg.anneau").wait_for()
        if texte in page.locator("svg.anneau").text_content():
            return
        time.sleep(0.4)
    pytest.fail(f"« {texte} » n'est pas apparu au centre de l'anneau.")


def famille(page, nom):
    return page.get_by_role("button", name=re.compile("^" + nom))


def ouvrir_service(page, nom_famille, nom):
    if not page.locator("svg.anneau").count():
        page.get_by_role("button", name="Revenir à l'anneau").click()
    if famille(page, nom_famille).get_attribute("aria-expanded") != "true":
        famille(page, nom_famille).click()
    if page.ecran == "pc":
        page.locator("text.service", has_text=nom).click()
    else:
        page.locator(".dessous").get_by_role("button", name=nom).click()
    page.get_by_role("region", name=nom).wait_for()


def test_1_l_anneau_porte_les_familles_en_texte(page):
    attendre_centre(page, "Tout va bien")
    assert [t.text_content().strip() for t in page.locator("text.famille").all()] == ["Proches", "Photos", "Médias", "Maison", "Collecte", "Machines"]
    assert page.locator("svg.anneau svg, svg.anneau image").count() == 0             # rien que du texte sur l'anneau
    assert "Dernière vérification il y a" in page.get_by_role("status").first.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth") <= ECRANS[page.ecran]["width"]


def test_2_toucher_une_famille_la_deplie(page):
    famille(page, "Médias").click()
    if page.ecran == "pc":
        page.locator("text.service", has_text="Statistiques").wait_for()
        assert [t.text_content().strip() for t in page.locator("text.service").all()] == ["Cinéma", "Statistiques", "Livres lus"]
    else:
        zone = page.locator(".dessous")
        assert zone.get_by_role("heading").inner_text() == "Médias"
        assert zone.get_by_role("button").count() == 3 and page.locator("text.service").count() == 0
    famille(page, "Médias").click()                                                  # la retoucher la replie
    assert famille(page, "Médias").get_attribute("aria-expanded") == "false"


def test_3_un_service_dans_le_cadre_un_autre_a_cote(page, monde):
    ouvrir_service(page, "Photos", "Photothèque")
    cadre = page.get_by_role("region", name="Photothèque").locator("iframe")
    assert cadre.get_attribute("src") == monde[0] + "/health?s=phototheque"          # il accepte le cadre
    assert "camera" in cadre.get_attribute("allow")                                   # l'appareil photo passe dans le cadre
    boite, ecran = cadre.bounding_box(), page.viewport_size
    if page.ecran != "pc":                                                           # sur téléphone, le service a toute la largeur
        assert boite["width"] >= ecran["width"] - 16 and boite["height"] >= ecran["height"] * 0.7
        barre = page.get_by_role("navigation", name="Familles").bounding_box()
        assert barre["y"] < boite["y"] and barre["height"] < 60                      # les familles sont en ligne, au-dessus
    colonne = page.get_by_role("navigation", name="Familles")
    assert colonne.get_by_role("button").count() == 6 and colonne.inner_text().strip() == ""   # des icônes, pas de noms
    assert colonne.get_by_role("button", name="Photos").get_attribute("aria-current") == "true"
    page.get_by_label("Services de Photos").get_by_role("button", name="Numérisation").click()
    fiche = page.get_by_role("region", name="Numérisation")
    assert fiche.locator("iframe:visible").count() == 0 and "Numérisation répond" in fiche.inner_text()
    assert "il interdit d'être affiché dans une autre page (X-Frame-Options : SAMEORIGIN)" in fiche.inner_text()
    with page.expect_popup() as fenetre:                                             # il s'ouvre à côté…
        fiche.get_by_role("button", name="Ouvrir Numérisation").click()
    assert "s=numerisation" in fenetre.value.url
    assert fenetre.value.evaluate("window.name") == "anneau-numerisation"            # …toujours dans la même fenêtre
    fenetre.value.close()
    colonne.get_by_role("button", name="Médias").click()                             # la colonne change de famille
    page.get_by_role("region", name="Cinéma").wait_for()
    page.get_by_role("button", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


def test_3b_le_bouton_du_milieu_ouvre_un_nouvel_onglet(page):
    if famille(page, "Photos").get_attribute("aria-expanded") != "true":
        famille(page, "Photos").click()
    cible = page.locator("text.service", has_text="Photothèque") if page.ecran == "pc" else page.locator(".dessous").get_by_role("button", name="Photothèque")
    with page.expect_popup() as onglet:
        cible.click(button="middle")
    assert "s=phototheque" in onglet.value.url
    onglet.value.close()
    assert page.locator("svg.anneau").count() == 1                                   # l'anneau n'a pas bougé
    ouvrir_service(page, "Photos", "Photothèque")                                    # et depuis les pastilles de la vue réduite
    with page.expect_popup() as onglet:
        page.get_by_label("Services de Photos").get_by_role("button", name="Numérisation").click(button="middle")
    assert "s=numerisation" in onglet.value.url
    onglet.value.close()
    assert page.get_by_role("region", name="Photothèque").count() == 1               # le service ouvert reste le même
    page.get_by_role("button", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


def test_3c_un_service_ouvert_reste_charge(page):
    """On change de service, on revient à l'anneau : le cadre déjà ouvert n'est pas rechargé."""
    if page.locator("svg.anneau").count() == 0:
        page.get_by_role("button", name="Revenir à l'anneau").click()
    ouvrir_service(page, "Photos", "Photothèque")
    cadre = page.locator("iframe[title='Photothèque']")
    cadre.wait_for()
    cadre.evaluate("f => f.dataset.temoin = 'moi'")                                  # une marque sur ce cadre-là
    page.get_by_label("Services de Photos").get_by_role("button", name="Numérisation").click()
    page.get_by_role("region", name="Numérisation").wait_for()
    assert cadre.is_hidden() and cadre.get_attribute("data-temoin") == "moi"         # caché, pas détruit
    assert "resté ouvert" in page.get_by_label("Services de Photos").get_by_role("button", name=re.compile("Photothèque")).inner_text()
    page.get_by_role("button", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()
    assert page.locator("iframe[title='Photothèque']").get_attribute("data-temoin") == "moi"   # toujours là derrière l'anneau
    ouvrir_service(page, "Photos", "Photothèque")
    assert cadre.is_visible() and cadre.get_attribute("data-temoin") == "moi"        # retrouvé tel quel
    page.get_by_label("Services de Photos").get_by_role("button", name=re.compile("Photothèque")).click()
    page.wait_for_function("document.querySelector(\"iframe[title='Photothèque']\").dataset.temoin === undefined")   # le toucher encore le recharge
    assert page.locator("iframe[title='Photothèque']").count() == 1
    page.get_by_role("button", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


def test_4_une_panne_s_ecrit_en_rouge_puis_se_clot(page, monde):
    morts(monde, "s=statistiques")
    attendre_centre(page, "1 en panne")
    assert "panne" in famille(page, "Médias").get_attribute("class")
    assert famille(page, "Médias").get_attribute("aria-label") == "Médias, en panne"   # dit en mots, pas seulement en couleur
    rang = page.get_by_role("region", name="En panne")
    assert "Statistiques ne répond plus" in rang.inner_text() and "Médias" in rang.inner_text()
    if rang.get_by_role("button").count():                                           # « Pris en compte » : une fois pour les deux écrans
        rang.get_by_role("button", name=re.compile("Pris en compte")).click()
    rang.get_by_text("pris en compte").wait_for()
    ouvrir_service(page, "Médias", "Statistiques")
    assert "Statistiques ne répond plus" in page.get_by_role("region", name="Statistiques").inner_text()
    page.get_by_role("button", name="Revenir à l'anneau").click()
    morts(monde)
    attendre_centre(page, "Tout va bien")
    assert page.get_by_role("region", name="En panne").count() == 0


def test_5_un_arret_attendu_n_alerte_pas(page):
    assert "panne" not in (famille(page, "Machines").get_attribute("class") or "")
    ouvrir_service(page, "Machines", "Ordinateur de calcul")
    assert "est éteint (arrêt attendu)" in page.get_by_role("region", name="Ordinateur de calcul").inner_text()
    page.get_by_role("button", name="Revenir à l'anneau").click()


def test_6_home_assistant_envoie_un_volume_plein_et_une_mise_a_jour(page, monde):
    def envoyer(pourcentage, maj):
        corps = json.dumps({"volumes": [{"machine": "Grand NAS", "nom": "Volume 1", "pourcentage": pourcentage}],
                            "mises_a_jour": [{"machine": "Grand NAS", "disponible": maj, "version": "8.1"}]}).encode()
        r = urllib.request.Request(monde[0] + "/api/ha/etat", data=corps, headers={"Content-Type": "application/json", "X-Anneau-Secret": SECRET})
        return json.loads(urllib.request.urlopen(r).read())
    envoyer(99.9, True)
    attendre_centre(page, "1 en panne")
    assert "Volume 1 de Grand NAS est plein à 99,9 %" in page.get_by_role("region", name="En panne").inner_text()
    assert "panne" in famille(page, "Machines").get_attribute("class")               # la famille de la machine
    assert "Mise à jour du système disponible pour Grand NAS (8.1)" in page.get_by_role("region", name="À faire quand tu veux").inner_text()
    assert envoyer(97, False)["pannes"] == 0
    attendre_centre(page, "Tout va bien")


def test_7_reglages_recharger_le_fichier(page):
    page.get_by_role("button", name="Réglages").click()
    page.get_by_role("heading", level=1, name="Réglages").wait_for()
    assert "12 service(s) dans 6 famille(s)" in page.get_by_role("region", name="Fichier des services").inner_text()
    assert "99,8 %" in page.get_by_role("region", name="Disques").inner_text()
    page.get_by_role("button", name="Recharger le fichier").click()
    page.locator("#message", has_text="Fichier relu : 12 service(s).").wait_for()
    page.get_by_role("link", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()
