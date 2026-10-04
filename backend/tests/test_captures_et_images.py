"""Étape 4 : état, sha256, date et sage-femme par capture ; image d'origine liée au dossier ;
accès à l'image selon le rôle ; doublons ; validation avant enregistrement."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app

PAGE_1 = Path(__file__).resolve().parents[2] / "data/Paper Registry/dossiers_specimen_10_patientes-01.png"
pytestmark = pytest.mark.skipif(not PAGE_1.exists(), reason="data/ absent")


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def envoyer(api, session="session-a", sage_femme="sf_01", page_no=1, image=None):
    image = image or PAGE_1.read_bytes()
    r = api.post("/captures", files={"image": ("page.png", image, "image/png")},
                 data={"session_id": session, "page_no": str(page_no), "sage_femme_id": sage_femme})
    assert r.status_code == 200, r.text
    return r.json()


def attendre_fin(api, capture_id, delai=15):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        etat = api.get(f"/captures/{capture_id}/etat").json()
        if etat["termine"]:
            return etat
        time.sleep(0.05)
    raise AssertionError("traitement non terminé")


def test_chaque_capture_a_etat_sha256_date_et_sage_femme(api):
    envoi = envoyer(api)
    info = api.get(f"/captures/{envoi['capture_id']}").json()
    assert info["etat"] == "CAPTURE"
    assert info["image_sha256"] == hashlib.sha256(PAGE_1.read_bytes()).hexdigest()
    assert info["sage_femme_id"] == "sf_01"
    assert info["date_capture"] and info["dossier_id"] == envoi["dossier"]["dossier_id"]

    # Le dossier référence la capture avec les mêmes informations.
    entree = envoi["dossier"]["captures"][0]
    assert entree["capture_id"] == envoi["capture_id"] and entree["sage_femme_id"] == "sf_01"
    assert entree["image_hash"] == f"sha256:{info['image_sha256']}"

    # L'état suit le traitement, dans la capture comme dans le dossier.
    api.post(f"/captures/{envoi['capture_id']}/traiter")
    final = attendre_fin(api, envoi["capture_id"])
    info = api.get(f"/captures/{envoi['capture_id']}").json()
    assert info["etat"] == final["etat"] and info["type_page"] == "IDENTIFICATION"
    dossier = api.get(f"/dossiers/{info['dossier_id']}").json()
    assert dossier["captures"][0]["etat"] == final["etat"]
    assert dossier["pages"][0]["image_id"] == info["image_id"]  # page liée à l'image d'origine


def test_acces_a_l_image_selon_le_role(api):
    capture_id = envoyer(api)["capture_id"]
    url = f"/captures/{capture_id}/image"
    original = PAGE_1.read_bytes()

    proprio = api.get(url, headers={"X-Role": "SAGE_FEMME", "X-Sage-Femme-Id": "sf_01"})
    assert proprio.status_code == 200 and proprio.content == original
    assert proprio.headers["cache-control"] == "no-store"
    assert api.get(url, headers={"X-Role": "SAGE_FEMME", "X-Sage-Femme-Id": "sf_02"}).status_code == 403
    assert api.get(url, headers={"X-Role": "SAGE_FEMME"}).status_code == 403
    assert api.get(url, headers={"X-Role": "SUPERVISEUR"}).content == original
    assert api.get(url, headers={"X-Role": "ADMIN"}).status_code == 403
    assert api.get(url).status_code == 401

    with database.connect() as db:
        lignes = db.execute("SELECT role, autorise FROM acces_images WHERE capture_id = ? ORDER BY id", (capture_id,)).fetchall()
    assert [(l["role"], l["autorise"]) for l in lignes] == [
        ("SAGE_FEMME", 1), ("SAGE_FEMME", 0), ("SAGE_FEMME", 0), ("SUPERVISEUR", 1), ("ADMIN", 0)]


def test_meme_image_deux_fois_doublon_suspecte_sans_second_traitement(api, monkeypatch):
    import extraction.pipeline as pipeline

    vraie, appels = pipeline.extract_page, []
    monkeypatch.setattr(pipeline, "extract_page", lambda chemin: appels.append(chemin) or vraie(chemin))

    premier = envoyer(api, session="session-a")
    api.post(f"/captures/{premier['capture_id']}/traiter")
    attendre_fin(api, premier["capture_id"])

    second = envoyer(api, session="session-b", sage_femme="sf_02")
    assert second["duplicate_suspected"] is True and second["etat_capture"] == "DOUBLON_SUSPECTE"
    assert second["capture_id"] == premier["capture_id"]  # aucune nouvelle capture
    api.post(f"/captures/{second['capture_id']}/traiter")  # capture déjà traitée : pas de relance
    attendre_fin(api, second["capture_id"])
    assert len(appels) == 1
    with database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM duplicate_reports").fetchone()[0] == 1


def test_seuls_les_champs_valides_sont_enregistres(api, monkeypatch):
    import extraction.pipeline as pipeline

    def sortie_partiellement_invalide(chemin):
        return {"type_page": "IDENTIFICATION", "champs": [
            {"champ": "identification.numero_fiche", "valeur": "2026-823-001", "statut": "CONNU", "confiance": 0.97, "page_source": 1},
            {"champ": "identification.mode_couverture", "valeur": "PEUT-ETRE", "statut": "CONNU", "confiance": 0.95, "page_source": 1},
            {"champ": "identification.telephone", "valeur": None, "statut": "NON_FOURNI", "confiance": 0.9, "page_source": 1},
        ]}

    monkeypatch.setattr(pipeline, "extract_page", sortie_partiellement_invalide)
    envoi = envoyer(api)
    api.post(f"/captures/{envoi['capture_id']}/traiter")
    final = attendre_fin(api, envoi["capture_id"])
    champs = [c["champ"] for c in final["dossier"]["pages"][0]["champs"]]
    assert champs == ["identification.numero_fiche"]  # choix invalide et clé interdite écartés
    assert final["etat"] == "TRAITE_IA"


def test_sortie_entierement_invalide_rien_n_est_enregistre(api, monkeypatch):
    import extraction.pipeline as pipeline

    monkeypatch.setattr(pipeline, "extract_page", lambda chemin: {"type_page": "IDENTIFICATION", "champs": [
        {"champ": "identification.nom", "valeur": "X", "statut": "CONNU", "confiance": 1, "page_source": 1}]})
    envoi = envoyer(api)
    api.post(f"/captures/{envoi['capture_id']}/traiter")
    final = attendre_fin(api, envoi["capture_id"])
    assert final["etat"] == "REVISION_MANUELLE_REQUISE"
    assert final["dossier"]["pages"] == []
