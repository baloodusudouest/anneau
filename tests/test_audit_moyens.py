"""0.10.4 (audit du 17/11/2026) : détection des valeurs en clair élargie, sans faux positif sur les images."""
from app.stack import RE_SENSIBLE


def test_valeurs_en_clair_detectees():
    for ligne in ("POSTGRES_PASSWORD=p@ss!w0rd#2026", "      - TS_AUTHKEY=tskey-auth-abc123",
                  "DB_PASSWD: hunter22", "WEBHOOK_URL=https://hooks.exemple/abc"):
        assert RE_SENSIBLE.search(ligne), ligne


def test_references_et_images_acceptees():
    for ligne in ("- PASSWORD=${MAISON_PASSWORD}", "image: docker.io/valkey/valkey:9@sha256:4963247afc4c",
                  "      - MAISON_JETON=${MAISON_JETON}"):
        assert not RE_SENSIBLE.search(ligne), ligne
