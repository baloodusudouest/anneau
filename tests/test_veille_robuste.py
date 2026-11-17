"""0.10.2 (audit du 17/11/2026) : une tuile mal écrite n'arrête plus la veille ; un services.yaml illisible
n'empêche plus le démarrage. Adresses inventées."""
import asyncio

from fastapi.testclient import TestClient

from app import main, services, veille as veille_mod
from app.config import Config
from app.veille import Veille

MDP = "mot-de-passe-de-test"


def test_port_invalide_ecarte_a_la_lecture():
    f = services.comprendre('familles: [{nom: T}]\nservices:\n'
                            '  - {nom: Bon, famille: T, locale: "http://192.0.2.9", sonde: "http://192.0.2.9/health"}\n'
                            '  - {nom: Fautif, famille: T, locale: "http://192.0.2.9", sonde: "http://nas:80a/health"}\n')
    assert any("port invalide" in e for e in f.erreurs)
    fautif = next(s for s in f.services if s.nom == "Fautif")
    assert "80a" not in (fautif.a_sonder or "")


def test_une_sonde_qui_plante_ne_prive_pas_les_autres(tmp_path):
    f = services.comprendre('familles: [{nom: T}]\nservices:\n'
                            '  - {nom: Bon, famille: T, locale: "http://192.0.2.9", sonde: "http://192.0.2.9/health"}\n'
                            '  - {nom: Autre, famille: T, locale: "http://192.0.2.8", sonde: "http://192.0.2.8/health"}\n')

    async def sonder(adresse):
        if "192.0.2.8" in adresse:
            raise RuntimeError("erreur imprévue")
        return True, 5

    async def examiner(adresse):
        raise RuntimeError("erreur imprévue")

    v = Veille(tmp_path, f, sonder=sonder, examiner=examiner)
    asyncio.run(v.tour())
    assert v.derniere_sonde


def test_repond_ne_leve_jamais():
    assert asyncio.run(veille_mod.repond("http://nas:80a/health")) == (False, None)


def test_services_illisible_n_empeche_pas_le_demarrage(tmp_path):
    (tmp_path / "services.yaml").write_text("[", encoding="utf-8")
    main.ETAT.clear()
    main.ETAT["cfg"] = Config(password=MDP, data=tmp_path, static=tmp_path / "static", attente_connexion=False)
    try:
        with TestClient(main.app) as c:
            assert c.get("/health").status_code == 200
            assert any("illisible" in e for e in main.ETAT["veille"].fichier.erreurs)
    finally:
        main.ETAT.clear()
