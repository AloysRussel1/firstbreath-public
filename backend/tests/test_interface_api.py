"""Routes utilisées par l'interface conversationnelle : /schema enrichi et « tout confirmer »."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.constants import STATUTS
from backend.main import app

PAGE_1 = Path(__file__).resolve().parents[2] / "data/Paper Registry/dossiers_specimen_10_patientes-01.png"


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def test_schema_fournit_les_libelles_des_visites_et_le_seuil(api):
    schema = api.get("/schema").json()
    assert len(schema["visites"]["index"]) == 9 and len(schema["visites"]["champs"]) == 16
    assert schema["visites"]["champs"]["age_gestationnel_sa"]["label_fr"]
    assert schema["pages"]["GROSSESSE_ACTUELLE"][-1] == "grossesse.visites[*]"
    assert schema["seuil_question_suivi"] == STATUTS["seuil_question_suivi"] == 0.92 and len(schema["statuts_champ"]) == 6
    assert "identification.numero_fiche" in schema["fields"]  # clés existantes conservées


@pytest.mark.skipif(not PAGE_1.exists(), reason="data/ absent")
def test_tout_confirmer_ne_confirme_que_les_champs_fiables(api, monkeypatch):
    import extraction.pipeline as pipeline

    monkeypatch.setattr(pipeline, "extract_page", lambda chemin: {"type_page": "IDENTIFICATION", "champs": [
        {"champ": "identification.numero_fiche", "valeur": "2026-823-001", "statut": "CONNU", "confiance": 0.97, "page_source": 1},
        {"champ": "identification.region", "valeur": "Rabat-Salé-Kénitra", "statut": "CONNU", "confiance": 0.60, "page_source": 1},
        {"champ": "identification.province", "valeur": "Kénitra", "statut": "A_REVISER", "confiance": 0.90, "page_source": 1},
    ]})
    envoi = api.post("/captures", files={"image": ("p1.png", PAGE_1.read_bytes(), "image/png")},
                     data={"session_id": "s", "page_no": "1", "sage_femme_id": "sf_01"}).json()
    api.post(f"/captures/{envoi['capture_id']}/traiter")
    for _ in range(100):
        if api.get(f"/captures/{envoi['capture_id']}/etat").json()["termine"]:
            break
        time.sleep(0.05)

    r = api.post(f"/dossiers/{envoi['dossier']['dossier_id']}/confirmer", headers={"X-Sage-Femme-Id": "sf_01"}, json={})
    corps = r.json()
    assert r.status_code == 200 and corps["confirmes"] == 1
    assert corps["ignores_non_fiables"] == ["identification.province", "identification.region"]
    champs = {c["champ"]: c for c in corps["dossier"]["pages"][0]["champs"]}
    assert champs["identification.numero_fiche"]["confirme"] is True
    assert champs["identification.numero_fiche"]["confirme_par"] == "sf_01"
    assert "confirme" not in champs["identification.province"]
    # Un second « tout confirmer » ne reconfirme rien.
    assert api.post(f"/dossiers/{envoi['dossier']['dossier_id']}/confirmer", json={}).json()["confirmes"] == 0
