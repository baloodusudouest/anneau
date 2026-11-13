"""La connexion commune : le cookie posé par l'Anneau ouvre l'appli si le mot de passe est le même."""
import hashlib
import hmac
import time

from app.auth import COMMUN, Sessions

MDP = "essai-essai-essai"


def cookie(mot_de_passe, expire):
    cle = hashlib.sha256(b"maison-session|" + mot_de_passe.encode()).digest()
    return f"{expire}.{hmac.new(cle, str(expire).encode(), hashlib.sha256).hexdigest()}"


def test_le_cookie_commun_ouvre_l_appli():
    s = Sessions("essai", MDP)
    dans_une_heure = int(time.time()) + 3600
    assert s.connecte({COMMUN: cookie(MDP, dans_une_heure)})
    assert s.connecte({COMMUN: s.creer_commun()})
    assert not s.connecte({})
    assert not s.connecte({COMMUN: cookie("un-autre-mot-de-passe", dans_une_heure)})       # autre mot de passe : refusé
    assert not s.connecte({COMMUN: cookie(MDP, int(time.time()) - 5)})                     # périmé : refusé
    assert not s.connecte({COMMUN: cookie(MDP, dans_une_heure).replace(str(dans_une_heure), str(dans_une_heure + 9))})
    for faux in ("", ".", "abc", "123", "123.", ".abc", "1.2.3"):
        assert not s.connecte({COMMUN: faux})


def test_l_anneau_pose_le_cookie_commun_et_le_retire(tmp_path):
    from fastapi.testclient import TestClient

    from app import main, services
    from app.config import Config
    from app.veille import Veille

    async def sonder(adresse):
        return True, 1

    async def examiner(adresse):
        return ""

    main.ETAT.clear()
    main.ETAT.update(cfg=Config(password=MDP, data=tmp_path, static=tmp_path / "static", secret_ha="", attente_connexion=False, veille=False),
                     veille=Veille(tmp_path, services.lire(tmp_path / "services.yaml"), sonder=sonder, examiner=examiner))
    with TestClient(main.app) as c:
        assert c.post("/api/connexion", json={"mot_de_passe": "mauvais-mot-de-passe"}).cookies.get(COMMUN) is None
        r = c.post("/api/connexion", json={"mot_de_passe": MDP})
        pose = r.headers.get_list("set-cookie")
        commun = next(x for x in pose if x.startswith(COMMUN + "="))
        assert "HttpOnly" in commun and "SameSite=strict" in commun and "Domain" not in commun
        valeur = c.cookies.get(COMMUN)
        assert Sessions("une-autre-appli", MDP).connecte({COMMUN: valeur})                 # une autre appli, même mot de passe
        assert not Sessions("une-autre-appli", "un-autre-mot-de-passe").connecte({COMMUN: valeur})
        c.post("/api/deconnexion")
        assert c.cookies.get(COMMUN) is None
    main.ETAT.clear()
