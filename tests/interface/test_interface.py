"""Tests d'écran de l'Anneau, sur PC et sur iPhone, contre un faux réseau."""
from __future__ import annotations

import json
import re
import shutil
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
    assert colonne.get_by_role("button").count() == 7 and colonne.inner_text().strip() == ""   # six familles et les réglages, en icônes
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


def test_3d_les_reglages_en_bas_de_la_colonne(page):
    """0.5.1 : un service ouvert, les réglages restent à portée, tout en bas de la colonne (au bout de la ligne sur téléphone)."""
    ouvrir_service(page, "Photos", "Photothèque")
    colonne = page.get_by_role("navigation", name="Familles")
    reglages = colonne.get_by_role("button", name="Réglages")
    boite, derniere = reglages.bounding_box(), colonne.get_by_role("button").nth(5).bounding_box()
    if page.ecran == "pc":
        assert boite["y"] > page.viewport_size["height"] * 0.8 and boite["x"] < 120     # en bas à gauche
    else:
        assert boite["x"] > derniere["x"]                                                # au bout de la ligne
    reglages.click()
    page.get_by_role("heading", level=1, name="Réglages").wait_for()
    page.evaluate("location.hash = ''")                                              # retour pour les essais suivants
    page.locator("svg.anneau, button[aria-label=\"Revenir à l'anneau\"]").first.wait_for()
    if page.locator("svg.anneau").count() == 0:
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


def test_8_reglages_importer_le_fichier(page, monde):
    """0.6 : le fichier se choisit dans Réglages, se confirme, remplace l'ancien ; un mauvais fichier est refusé."""
    page.get_by_role("button", name="Réglages").click()
    page.get_by_role("heading", level=1, name="Réglages").wait_for()
    bloc = page.get_by_role("region", name="Fichier des services")
    actuel = (monde[1] / "data" / "services.yaml").read_text(encoding="utf-8")
    champ = page.get_by_label("Choisir un fichier services.yaml")
    # un mauvais fichier : refusé, rien ne change
    champ.set_input_files({"name": "faux.yaml", "mimeType": "text/yaml", "buffer": b"familles: ["})
    bloc.get_by_role("button", name="Remplacer").click()
    page.locator("#message", has_text="illisible").wait_for()
    assert (monde[1] / "data" / "services.yaml").read_text(encoding="utf-8") == actuel
    # annuler ne touche à rien
    bloc.get_by_role("button", name="Annuler").click()
    bloc.get_by_role("button", name="Importer un fichier").wait_for()
    # le bon fichier, avec un service de moins
    lignes = [l for l in actuel.splitlines() if "Musique" not in l]
    champ.set_input_files({"name": "services.yaml", "mimeType": "text/yaml", "buffer": "\n".join(lignes).encode()})
    assert "services.yaml" in bloc.get_by_role("group", name="Import à confirmer").inner_text()
    bloc.get_by_role("button", name="Remplacer").click()
    page.locator("#message", has_text="Fichier importé : 11 service(s).").wait_for()
    assert "11 service(s) dans 6 famille(s)" in bloc.inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # on remet le fichier complet pour l'écran suivant
    champ.set_input_files({"name": "services.yaml", "mimeType": "text/yaml", "buffer": actuel.encode()})
    bloc.get_by_role("button", name="Remplacer").click()
    page.locator("#message", has_text="Fichier importé : 12 service(s).").wait_for()
    assert "services.precedent.yaml" in page.locator("#message").inner_text()
    page.get_by_role("link", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


def test_9_reglages_sauvegarde_et_tuile_a_traiter(page, monde):
    """0.8 : Réglages › Sauvegarde (heure, collecte), Restaurer, et la tuile « Sauvegarde ratée ».
    0.10 : la liste des fichiers et la clé passent dans les pages Sauvegardes et Variables (tests 10 et 11)."""
    page.get_by_role("button", name="Réglages").first.click()
    page.get_by_role("heading", level=1, name="Réglages").wait_for()
    bloc = page.get_by_role("region", name="Sauvegarde")
    page.get_by_label("Heure de la collecte").fill("04:10")
    bloc.get_by_role("button", name="Enregistrer l'heure").click()
    page.locator("#message-sauvegarde", has_text="Collecte chaque jour à 04:10.").wait_for()
    bloc.get_by_role("button", name="Sauvegarder maintenant").click()
    page.locator("#message-sauvegarde", has_text="Sauvegarde faite : 1 appli(s) lue(s), 2 ratée(s).").wait_for()
    assert "anneau" in bloc.get_by_role("group", name="Dernière collecte").inner_text()
    assert "MAISON_JETON est vide" in bloc.get_by_label("Applis non lues").inner_text()
    assert "sauvegarde(s) gardée(s)" in bloc.inner_text() and "Export chiffré des variables" in bloc.inner_text()
    assert bloc.get_by_role("link", name="Voir les sauvegardes").count() == 1
    # Restaurer : l'heure revient à celle de la sauvegarde
    rest = page.get_by_role("region", name="Restaurer")
    page.get_by_label("Heure de la collecte").fill("05:00")
    bloc.get_by_role("button", name="Enregistrer l'heure").click()
    page.locator("#message-sauvegarde", has_text="05:00").wait_for()
    rest.get_by_role("button", name="Voir les différences").click()        # les dates sont relues après la collecte
    rest.get_by_label("Différences").wait_for()
    assert "05:00 → 04:10" in rest.get_by_label("Différences").inner_text()
    rest.get_by_role("button", name="Restaurer", exact=True).click()
    page.locator("#message-restaurer", has_text="restaurés").wait_for()
    assert page.get_by_label("Heure de la collecte").input_value() == "04:10"
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # la tuile « Sauvegarde ratée », en or, mène aux Réglages
    page.get_by_role("link", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()
    tuile = page.get_by_role("region", name="À traiter")
    assert "Sauvegarde ratée" in tuile.inner_text() and "2 appli(s) non lue(s) : Arbre, Répertoire" in tuile.inner_text()
    assert "Tout va bien" in page.locator("svg.anneau").text_content()                # pas une panne
    assert page.evaluate("document.documentElement.scrollWidth") <= ECRANS[page.ecran]["width"]
    tuile.get_by_role("button", name="Voir : Sauvegarde ratée").click()
    page.get_by_role("heading", level=1, name="Réglages").wait_for()
    page.get_by_role("link", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


def test_10_page_sauvegardes(page):
    """0.10 : chaque sauvegarde se déplie (versions, réglages, différences, ratées) ; le seul endroit qui les liste."""
    page.goto(page.url.split("#")[0] + "#/sauvegardes")
    page.get_by_role("heading", level=1, name="Sauvegardes").wait_for()
    liste = page.get_by_label("Liste des sauvegardes")
    liste.get_by_role("button").first.click()
    region = page.get_by_role("region", name=re.compile("^Sauvegarde du "))
    region.get_by_label("Réglages de L'Anneau").wait_for()
    assert "heure_sauvegarde" in region.inner_text()
    assert "2 appli(s) ratée(s)" in region.get_by_role("alert", name="Applis ratées").inner_text()
    assert region.get_by_role("link", name="Télécharger").count() == 1
    page.get_by_label("Seulement les applis qui ont changé").check()
    page.get_by_label("Seulement les applis qui ont changé").uncheck()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("link", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


STACK = """services:
  repertoire:
    image: essai
    environment:
      - TZ=${TZ}
      - MAISON_PASSWORD=${MAISON_PASSWORD}
      - VEILLE=${VEILLE_HEURE:-03:00}
"""


def test_11_page_variables(page, monde, tmp_path):
    """0.10 : homelab.yml importé, paire de clés (privée montrée une fois, jamais gardée), chiffrer et ranger l'export,
    l'ouvrir avec la clé privée, copie pour Portainer ; compatible avec l'outil age ; aucun débordement."""
    page.goto(page.url.split("#")[0] + "#/variables")
    page.get_by_role("heading", level=1, name="Variables").wait_for()
    assert page.evaluate("window.isSecureContext")                              # 127.0.0.1 compte comme sûr
    assert page.get_by_role("alert", name="Page non sûre").count() == 0
    # un homelab.yml avec une valeur en clair est refusé, le bon est accepté
    page.get_by_label("Choisir homelab.yml").set_input_files({"name": "homelab.yml", "mimeType": "text/yaml",
        "buffer": STACK.replace("${MAISON_PASSWORD}", "motdepasse-en-clair").encode()})
    page.locator("#message-variables", has_text="valeur écrite en clair").wait_for()
    page.get_by_label("Choisir homelab.yml").set_input_files({"name": "homelab.yml", "mimeType": "text/yaml", "buffer": STACK.encode()})
    page.locator("#message-variables", has_text="1 service(s), 3 variable(s)").wait_for()
    # paire de clés : la privée est montrée, puis effacée une fois la paire adoptée
    page.get_by_role("button", name="Générer une paire de clés").click()
    privee = page.get_by_label("Clé privée neuve").input_value()
    assert privee.startswith("AGE-SECRET-KEY-1")
    page.get_by_role("button", name="Utiliser cette paire").click()
    page.locator("#message-variables", has_text="Range d'abord").wait_for()
    page.get_by_label("Je l'ai rangée hors de la maison").check()
    if page.get_by_label("Remplacer la clé actuelle", exact=False).count():     # 2e écran : une clé est déjà posée
        page.get_by_role("button", name="Utiliser cette paire").click()
        page.locator("#message-variables", has_text="Une clé est déjà posée").wait_for()
        page.get_by_label("Remplacer la clé actuelle", exact=False).check()
    page.get_by_role("button", name="Utiliser cette paire").click()
    page.locator("#message-variables", has_text="Nouvelle clé publique enregistrée").wait_for()
    assert privee not in page.content()
    assert "Empreinte" in page.get_by_label("Clé publique", exact=True).inner_text()
    # chiffrer et ranger : seul du texte chiffré part
    envois = []
    page.on("request", lambda r: envois.append(r.post_data or "") if r.method in ("POST", "PUT") else None)
    page.get_by_label("Export de Portainer à chiffrer").fill("TZ=Europe/Paris\nMAISON_PASSWORD=secret-de-test-123456\nANCIENNE=1\n")
    page.get_by_role("button", name="Chiffrer et ranger").click()
    page.locator("#message-variables", has_text="Export chiffré et rangé").wait_for()
    assert envois and all("secret-de-test" not in e for e in envois) and any("BEGIN AGE ENCRYPTED FILE" in e for e in envois)
    assert page.get_by_label("Export de Portainer à chiffrer").input_value() == ""
    # le fichier rangé s'ouvre avec l'outil age et la clé privée
    nom = page.get_by_label("Liste des exports").locator("label").first.inner_text().split(" · ")[0].strip()
    rangé = next((monde[1] / "data" / "sauvegardes" / "variables").glob(nom))
    if shutil.which("age"):                                                   # installé par la construction sur GitHub
        (tmp_path / "cle.txt").write_text(privee + "\n")
        clair = subprocess.run(["age", "-d", "-i", str(tmp_path / "cle.txt"), str(rangé)], capture_output=True, text=True)
        assert clair.returncode == 0 and "MAISON_PASSWORD=secret-de-test-123456" in clair.stdout
    # l'ouvrir dans la page : valeurs masquées, manquantes, inconnues, copie pour Portainer
    page.get_by_label("Clé privée (jamais gardée ni envoyée)").fill(privee)
    page.get_by_role("button", name="Ouvrir", exact=True).click()
    page.locator("#message-variables", has_text="ouvert : 3 variable(s)").wait_for()
    assert page.get_by_label("Clé privée (jamais gardée ni envoyée)").input_value() == ""
    groupe = page.get_by_role("group", name="Valeurs ouvertes")
    assert "ANCIENNE" in groupe.inner_text() and "Toutes les variables à remplir ont une valeur." in groupe.inner_text()
    page.get_by_label("Chercher une variable").fill("MAISON")
    assert "secret-de-test" not in page.get_by_label("Liste des variables").inner_text()
    page.get_by_role("button", name="Afficher la valeur de MAISON_PASSWORD").click()
    assert "secret-de-test-123456" in page.get_by_label("Liste des variables").inner_text()
    assert "obsidian://open?vault=Maison" in page.get_by_role("link", name="Note dans Obsidian").first.get_attribute("href")
    groupe.get_by_role("button", name="Voir le texte").click()
    texte = page.get_by_label("Texte à recoller dans Portainer").input_value()
    assert texte == "TZ=Europe/Paris\nMAISON_PASSWORD=secret-de-test-123456\n"           # ANCIENNE omise, VEILLE_HEURE facultative absente
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # rien n'est gardé par le navigateur, et « Oublier » efface tout
    garde = page.evaluate("JSON.stringify(localStorage) + JSON.stringify(sessionStorage)")
    assert privee not in garde and "secret-de-test" not in garde
    groupe.get_by_role("button", name="Oublier les valeurs").click()
    assert "secret-de-test" not in page.content()
    # 0.11.2 (audit M7) : remplacer une clé déjà posée se confirme
    page.get_by_label("Ou poser une clé publique (age1…)").fill("age1" + "q" * 58)
    page.get_by_role("button", name="Enregistrer la clé").click()
    page.locator("#message-variables", has_text="Une clé est déjà posée").wait_for()
    page.get_by_label("Remplacer la clé actuelle", exact=False).check()
    page.get_by_role("button", name="Enregistrer la clé").click()
    page.locator("#message-variables", has_text="Clé publique enregistrée.").wait_for()
    assert "q" * 58 in page.get_by_label("Clé publique", exact=True).inner_text()
    page.get_by_role("link", name="Revenir à l'anneau").click()
    page.locator("svg.anneau").wait_for()


def test_12_carte_de_la_maison_depuis_les_reglages(page):
    """0.11 : la carte (ex-Atlas) s'ouvre depuis Réglages ; graphe sur PC, liste sur iPhone ; voyants des tuiles."""
    page.goto(page.url.split("#")[0] + "#/reglages")
    page.get_by_role("region", name="Carte de la maison").wait_for()
    page.get_by_role("link", name="Ouvrir la carte").click()
    page.get_by_role("heading", name="Carte de la maison").wait_for()
    if page.ecran == "pc":
        page.locator(".svelte-flow__node-service").first.wait_for()
        assert page.locator(".svelte-flow__node-service").count() == 6
        page.locator(".svelte-flow__node-service", has_text="Arbre").first.click()
        panneau = page.get_by_role("complementary", name="Service Arbre")
        panneau.wait_for()
        assert "Répertoire" in panneau.text_content()
    else:
        page.get_by_role("button", name=re.compile("Répertoire")).click()
        page.get_by_text("Rôle de Répertoire.").wait_for()
        assert page.locator("text=Grand NAS").count() >= 1
    page.screenshot(path=f"/tmp/carte-{page.ecran}.png", full_page=False)


# ---------------------------------------------------------------- 0.12 : santé des tâches de fond

def _iso(il_y_a_s):
    from datetime import datetime, timedelta
    return (datetime.now().astimezone() - timedelta(seconds=il_y_a_s)).isoformat(timespec="seconds")


def _sante(monde, taches):
    corps = {"ok": True, "version": "2.40.0", "version_socle": "0.9.0", "taches": taches,
             "copie_base": {"le": _iso(3600), "ok": True, "bases": ["repertoire.db"], "taille": 40960}}
    (monde[1] / "sante.json").write_text(json.dumps({"s=repertoire": corps}), encoding="utf-8")


def _tache(nom, etat="ok", type_="reguliere", reussite=60, essai=60, erreur=None, message=None):
    t = {"nom": nom, "type": type_, "periode_s": 3600 if type_ == "reguliere" else None, "etat": etat,
         "derniere_reussite": _iso(reussite) if reussite else None, "dernier_essai": _iso(essai) if essai else None,
         "derniere_erreur": _iso(erreur) if erreur else None}
    return {**t, "message": message} if message else t


def _attendre_rang(page, present, texte=""):
    for _ in range(40):
        page.reload()
        page.locator("svg.anneau").wait_for()
        rang = page.get_by_role("region", name="À surveiller")
        if (rang.count() > 0 and texte in rang.inner_text()) if present else rang.count() == 0:
            return rang
        time.sleep(0.4)
    pytest.fail("Le rang « À surveiller » n'est pas dans l'état attendu.")


def test_13_tuile_a_surveiller_phrase_fiche_et_vu(page, monde):
    """0.12 : une tâche régulière en retard rend la tuile orange, avec sa phrase écrite sur la tuile (PC et iPhone),
    jamais « en panne » ; la fiche détaille ; « Vu » l'éteint jusqu'au prochain changement."""
    page.goto(page.url.split("#")[0] + "#/")
    synchro, nettoyage = f"synchro-{page.ecran}", f"nettoyage-{page.ecran}"   # noms propres à chaque écran (serveur partagé)
    import_ = _tache("import-livres", type_="demande", etat="erreur", reussite=None, essai=600, erreur=600,
                     message="ValueError: fichier illisible")
    _sante(monde, [_tache(synchro, etat="en_retard", reussite=3 * 3600 + 200), import_])
    rang = _attendre_rang(page, True, "Répertoire")
    phrase = f"{synchro} n'a pas réussi depuis 3 h"
    assert phrase in rang.inner_text()
    assert page.get_by_role("region", name="En panne").count() == 0 and "Tout va bien" in page.locator("svg.anneau").text_content()
    # la phrase écrite sur la tuile, sans survol
    famille(page, "Proches").click()
    if page.ecran == "pc":
        assert "surveiller" in page.locator("text.service", has_text="Répertoire").get_attribute("class")
        assert "à surveiller" in page.locator("text.phrase-service").text_content()   # la phrase entière : rang à côté
        assert page.locator("text.phrase-service").is_visible() and phrase in page.locator("text.phrase-service title").text_content()
    else:
        tuile = page.locator(".dessous").get_by_role("button", name=re.compile("Répertoire"))
        assert phrase in tuile.inner_text() and tuile.locator(".phrase-tuile").is_visible()
    famille(page, "Proches").click()
    # la fiche : tâches, dernière erreur d'une tâche à la demande, copie, socle
    rang.get_by_role("button", name="Voir : Répertoire").click()
    fiche = page.locator(".fiche-etat")
    fiche.wait_for()
    texte = fiche.inner_text()
    assert synchro in texte and "en retard" in texte and "import-livres" in texte and "à la demande" in texte
    assert "dernière erreur il y a" in texte and "ValueError: fichier illisible" in texte
    assert "repertoire.db" in texte and "Socle 0.9.0" in texte
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=f"/tmp/sante-{page.ecran}.png")
    # « Vu »
    fiche.get_by_role("button", name="Vu", exact=True).click()
    fiche.get_by_text("Vu : la tuile redeviendra orange").wait_for()
    assert page.locator(".pastilles .vu").count() == 1
    page.get_by_role("button", name="Revenir à l'anneau").click()
    _attendre_rang(page, False)
    # autre chose casse : orange de nouveau
    _sante(monde, [_tache(synchro, etat="en_retard", reussite=3 * 3600 + 200), _tache(nettoyage, etat="bloquee", essai=7300), import_])
    rang = _attendre_rang(page, True, "(+1)")
    # tout se répare : plus rien
    _sante(monde, [_tache(synchro), import_])
    _attendre_rang(page, False)


def test_14_bandeau_veille_de_l_anneau_arretee(page, monde):
    """0.12 : la veille de l'Anneau ne finit plus ses tours depuis plus de 10 min : bandeau orange en haut."""
    page.goto(page.url.split("#")[0] + "#/")
    (monde[1] / "avance.txt").write_text("700")
    (monde[1] / "arret.txt").write_text("")
    try:
        for _ in range(40):
            page.reload()
            page.locator("svg.anneau").wait_for()
            if page.get_by_role("alert").filter(has_text="La veille de l'Anneau est arrêtée depuis").count():
                break
            time.sleep(0.4)
        else:
            pytest.fail("Le bandeau de veille arrêtée n'est pas apparu.")
        assert page.locator(".bandeau").is_visible()
    finally:
        (monde[1] / "arret.txt").unlink()
        (monde[1] / "avance.txt").unlink()
    for _ in range(40):
        page.reload()
        page.locator("svg.anneau").wait_for()
        if not page.locator(".bandeau").count():
            return
        time.sleep(0.4)
    pytest.fail("Le bandeau de veille arrêtée ne s'est pas effacé.")


def _api(page, chemin):
    return page.evaluate("c => fetch(c, { credentials: 'same-origin' }).then(r => r.json())", chemin)


def _attendre(page, condition, quoi):
    for _ in range(60):
        if condition():
            return
        time.sleep(0.25)
    pytest.fail(quoi)


def test_15_nouveautes_de_la_nuit_puis_vu_et_section_versions(page, monde):
    """0.13 : la veille voit la version d'une tuile changer ; à l'ouverture suivante, la fenêtre « Mis à jour depuis votre
    dernière visite » le dit, et disparaît après « Vu » (PC et iPhone). Réglages › Versions et la fiche disent le retard
    en mots, sans orange."""
    page.goto(page.url.split("#")[0] + "#/")
    page.locator("svg.anneau").wait_for()
    avant, apres = ("3.1.0", "3.2.0") if page.ecran == "pc" else ("3.5.0", "3.6.0")   # serveur partagé par les deux écrans
    fichier = monde[1] / "sante.json"

    def version_arbre(v):
        corps = json.loads(fichier.read_text(encoding="utf-8")) if fichier.is_file() else {}
        corps["s=arbre"] = {"ok": True, "version": v}
        fichier.write_text(json.dumps(corps), encoding="utf-8")

    version_arbre(avant)
    _attendre(page, lambda: any(t["nom"] == "Arbre" and t["version"] == avant for t in _api(page, "/api/versions")["tuiles"]),
              "La veille n'a pas lu la version d'Arbre.")
    version_arbre(apres)
    _attendre(page, lambda: any(c["tuile"] == "Arbre" and c["vers"] == apres for c in _api(page, "/api/versions/nouveautes")["changements"]),
              "Le changement de version d'Arbre n'est pas au journal.")
    # nouvelle ouverture de l'Anneau : la fenêtre
    page.reload()
    fenetre = page.get_by_role("dialog", name="Mis à jour depuis votre dernière visite")
    fenetre.wait_for()
    texte = fenetre.inner_text()
    assert "Arbre" in texte and f"→ {apres}" in texte and re.search(r"\((cette nuit|aujourd'hui|hier|le \d\d/\d\d), \d\d:\d\d\)", texte)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=f"/tmp/nouveautes-{page.ecran}.png")
    fenetre.get_by_role("button", name="Vu", exact=True).click()
    fenetre.wait_for(state="detached")
    page.reload()
    page.locator("svg.anneau").wait_for()
    time.sleep(0.5)
    assert page.get_by_role("dialog").count() == 0                       # vu : plus rien à la réouverture
    # Réglages › Versions
    page.goto(page.url.split("#")[0] + "#/reglages")
    section = page.get_by_role("region", name="Versions")
    section.get_by_role("row", name=re.compile("Arbre")).wait_for()
    ligne = section.get_by_role("row", name=re.compile("Arbre")).inner_text()
    assert apres in ligne and "9.0.0" in ligne and "pas encore en service" in ligne
    assert "2.40.0" in section.get_by_role("row", name=re.compile("Répertoire")).inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    # la fiche de la tuile : le retard en mots, jamais d'orange
    page.goto(page.url.split("#")[0] + "#/")
    page.locator("svg.anneau").wait_for()
    assert page.get_by_role("region", name="À surveiller").count() == 0
    ouvrir_service(page, "Proches", "Arbre")
    bouton = page.get_by_role("button", name="État", exact=True)
    assert "surveiller" not in (bouton.get_attribute("class") or "")
    bouton.click()
    fiche = page.locator(".fiche-etat")
    fiche.wait_for()
    assert f"Version {apres} — dernière publiée 9.0.0 : pas encore en service" in fiche.inner_text()
    page.get_by_role("button", name="Revenir à l'anneau").click()
