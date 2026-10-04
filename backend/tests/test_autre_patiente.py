"""Page d'une autre patiente dans un registre : le N° du registre n'est pas écrasé ; la page peut être
retirée, ou placée dans un nouveau registre sans renvoyer la photo."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app

SF = {"X-Sage-Femme-Id": "sf_01", "X-Role": "SAGE_FEMME"}
NUMEROS = {b"page-a": "2026-111-001", b"page-b": "2026-222-002"}


@pytest.fixture
def api(monkeypatch):
    import extraction.pipeline as pipeline

    def lecture(chemin):
        contenu = open(chemin, "rb").read()
        numero = next(n for cle, n in NUMEROS.items() if cle in contenu)
        return {"type_page": "IDENTIFICATION", "champs": [
            {"champ": "identification.numero_fiche", "valeur": numero, "statut": "CONNU", "confiance": 0.98, "page_source": 1}]}

    monkeypatch.setattr(pipeline, "extract_page", lecture)
    with TestClient(app) as client:
        yield client


def lire(api, session, page, marque):
    envoi = api.post("/captures", files={"image": ("p.jpg", b"\xff\xd8\xff" + marque, "image/jpeg")},
                     data={"session_id": session, "page_no": str(page), "sage_femme_id": "sf_01"}).json()
    api.post(f"/captures/{envoi['capture_id']}/traiter", headers=SF)
    for _ in range(100):
        etat = api.get(f"/captures/{envoi['capture_id']}/etat").json()
        if etat["termine"]:
            return envoi["capture_id"], etat["dossier"]
        time.sleep(0.05)
    raise AssertionError("lecture non terminée")


def test_le_numero_du_registre_n_est_pas_ecrase_puis_la_page_est_retiree(api):
    _, dossier = lire(api, "r", 1, b"page-a")
    _, dossier = lire(api, "r", 2, b"page-b")
    assert dossier["numero_fiche"] == "2026-111-001"  # la première page d'identification fait foi
    lue = {p["page_no"]: next(c["valeur"] for c in p["champs"] if c["champ"] == "identification.numero_fiche") for p in dossier["pages"]}
    assert lue == {1: "2026-111-001", 2: "2026-222-002"}  # l'interface compare et prévient

    r = api.post(f"/dossiers/{dossier['dossier_id']}/pages/2/retirer", headers=SF).json()["dossier"]
    assert [p["page_no"] for p in r["pages"]] == [1] and r["pages_retirees"][0]["page_no"] == 2
    assert api.post(f"/dossiers/{dossier['dossier_id']}/pages/9/retirer", headers=SF).status_code == 404


def test_la_page_est_placee_dans_un_nouveau_registre_sans_renvoyer_la_photo(api):
    _, dossier = lire(api, "r1", 1, b"page-a")
    capture_b, _ = lire(api, "r1", 2, b"page-b")

    r = api.post(f"/captures/{capture_b}/nouveau-registre", headers=SF, json={"session_id": "r2", "page_no": 1}).json()
    nouveau, ancien = r["dossier"], r["ancien_dossier"]
    assert nouveau["numero_fiche"] == "2026-222-002" and [p["page_no"] for p in nouveau["pages"]] == [1]
    assert nouveau["etat"] == "TRAITE_IA" and [c["capture_id"] for c in nouveau["captures"]] == [capture_b]
    assert [p["page_no"] for p in ancien["pages"]] == [1] and ancien["numero_fiche"] == "2026-111-001"
    assert api.get(f"/captures/{capture_b}").json()["dossier_id"] == nouveau["dossier_id"]
    with database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 2  # aucune capture créée ni perdue
    # Une session qui a déjà un dossier est refusée ; une capture inconnue aussi.
    assert api.post(f"/captures/{capture_b}/nouveau-registre", headers=SF, json={"session_id": "r1", "page_no": 3}).status_code == 409
    assert api.post("/captures/inconnue/nouveau-registre", headers=SF, json={"session_id": "r9"}).status_code == 404
