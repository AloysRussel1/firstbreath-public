"""Étape 3 : POST /captures/{id}/traiter répond tout de suite ; GET /captures/{id}/etat suit le traitement."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import database, services
from backend.main import app

PAGE_6 = Path(__file__).resolve().parents[2] / "data/Paper Registry/dossiers_specimen_10_patientes-06.png"
pytestmark = pytest.mark.skipif(not PAGE_6.exists(), reason="data/ absent")


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def extraction_lente(monkeypatch):
    """extract_page() réelle (fournisseur simulé) précédée d'une attente, pour observer EN_ATTENTE_IA."""
    import extraction.pipeline as pipeline

    vraie, appels = pipeline.extract_page, []

    def lente(image_path):
        appels.append(image_path)
        time.sleep(1.5)
        return vraie(image_path)

    monkeypatch.setattr(pipeline, "extract_page", lente)
    return appels


def envoyer_page_6(api, session="session-async"):
    reponse = api.post("/captures", files={"image": ("page6.png", PAGE_6.read_bytes(), "image/png")},
                       data={"session_id": session, "page_no": "6", "sage_femme_id": "sf_01"})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["capture_id"]


def attendre_fin(api, capture_id, delai=15):
    fin = time.monotonic() + delai
    while time.monotonic() < fin:
        etat = api.get(f"/captures/{capture_id}/etat").json()
        if etat["termine"]:
            return etat
        time.sleep(0.1)
    raise AssertionError("le traitement ne s'est pas terminé à temps")


def test_traiter_repond_tout_de_suite_puis_etat_passe_a_traite_ou_a_reviser(api, extraction_lente):
    capture_id = envoyer_page_6(api)

    debut = time.monotonic()
    reponse = api.post(f"/captures/{capture_id}/traiter")
    duree = time.monotonic() - debut
    corps = reponse.json()
    assert reponse.status_code == 200
    assert duree < 1.0, f"/traiter a mis {duree:.2f} s alors que l'extraction dure 1,5 s"
    assert corps["etat"] == "EN_ATTENTE_IA"
    # Champs conservés temporairement pour l'interface actuelle.
    assert corps["extraction_status"] == "EN_ATTENTE_IA"
    assert corps["dossier"]["etat"] == "EN_ATTENTE_IA"
    assert corps["duree_estimee_s"] == services.DUREE_PAGE_S  # page connue, pas GROSSESSE_ACTUELLE

    pendant = api.get(f"/captures/{capture_id}/etat").json()
    assert pendant["etat"] == "EN_ATTENTE_IA" and not pendant["termine"] and pendant["progression"] < 1

    # Un second appel pendant le traitement ne relance rien.
    assert api.post(f"/captures/{capture_id}/traiter").json()["etat"] == "EN_ATTENTE_IA"

    final = attendre_fin(api, capture_id)
    assert final["etat"] in ("TRAITE_IA", "A_REVISER")
    assert final["progression"] == 1.0 and final["type_page"] == "PP_PRECOCE_NOUVEAU_NE"
    assert final["ecoule_s"] >= 1.5  # durée réelle mesurée (horodatages à la milliseconde)
    assert final["dossier"]["etat"] == final["etat"]
    assert len(extraction_lente) == 1


def test_echec_traitement_propose_la_saisie_manuelle(api, monkeypatch):
    import extraction.pipeline as pipeline
    from extraction.client import EchecTraitement

    def echoue(image_path):
        raise EchecTraitement("sortie tronquée à tous les niveaux d'effort")

    monkeypatch.setattr(pipeline, "extract_page", echoue)
    capture_id = envoyer_page_6(api, session="session-echec")
    api.post(f"/captures/{capture_id}/traiter")
    final = attendre_fin(api, capture_id)
    assert final["etat"] == "ECHEC_TRAITEMENT"
    assert "saisie manuelle" in final["detail"]
    assert final["dossier"]["etat"] == "ECHEC_TRAITEMENT"


def test_traitement_interrompu_par_un_redemarrage_passe_en_echec(api):
    capture_id = envoyer_page_6(api, session="session-arret")
    services.demarrer_traitement(capture_id)  # EN_ATTENTE_IA, mais aucune tâche lancée
    assert services.reprendre_interrompus() == 1
    etat = api.get(f"/captures/{capture_id}/etat").json()
    assert etat["etat"] == "ECHEC_TRAITEMENT" and "redémarrage" in etat["detail"]
    with database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM captures WHERE etat_traitement = 'EN_ATTENTE_IA'").fetchone()[0] == 0


def test_traitements_paralleles_ne_perdent_aucune_page(api, monkeypatch):
    """Plusieurs extractions simultanées sur le même dossier : aucune page ne doit en écraser une autre."""
    import extraction.pipeline as pipeline

    registre = PAGE_6.parent
    fichiers = ["dossiers_specimen_10_patientes-01.png", "dossiers_specimen_10_patientes-02.png",
                "dossiers_specimen_10_patientes-05.png", "dossiers_specimen_10_patientes-06.png"]
    vraie = pipeline.extract_page

    def lente(chemin):
        resultat = vraie(chemin)
        time.sleep(0.3)  # élargit la fenêtre de concurrence entre lecture et écriture du dossier
        return resultat

    monkeypatch.setattr(pipeline, "extract_page", lente)
    monkeypatch.setattr(services, "EXECUTEUR", __import__("concurrent.futures").futures.ThreadPoolExecutor(max_workers=4))
    ids = []
    for n, f in enumerate(fichiers, start=1):
        r = api.post("/captures", files={"image": (f, (registre / f).read_bytes(), "image/png")},
                     data={"session_id": "session-parallele", "page_no": str(n), "sage_femme_id": "sf_01"})
        ids.append(r.json()["capture_id"])
    for c in ids:
        api.post(f"/captures/{c}/traiter")
    for c in ids:
        attendre_fin(api, c)
    dossier = api.get(f"/captures/{ids[0]}/etat").json()["dossier"]
    assert sorted(p["page_no"] for p in dossier["pages"]) == [1, 2, 3, 4]


def test_etat_capture_inconnue(api):
    assert api.get("/captures/inconnue/etat").status_code == 404
