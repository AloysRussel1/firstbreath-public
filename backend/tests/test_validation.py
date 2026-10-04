"""La validation dit précisément ce qui la bloque ; /schema dit si la lecture est réelle."""
from __future__ import annotations

import time

from fastapi.testclient import TestClient

from backend.main import app

SF = {"X-Sage-Femme-Id": "sf_01", "X-Role": "SAGE_FEMME"}


def test_questions_restantes_bloquent_la_validation_jusqu_a_la_reponse(monkeypatch):
    import extraction.pipeline as pipeline

    monkeypatch.setattr(pipeline, "extract_page", lambda chemin: {"type_page": "IDENTIFICATION", "champs": [
        {"champ": "identification.numero_fiche", "valeur": "2026-823-001", "statut": "CONNU", "confiance": 0.98, "page_source": 1},
        {"champ": "identification.region", "valeur": "Oriental", "statut": "CONNU", "confiance": 0.80, "page_source": 1},
        {"champ": "identification.province", "valeur": "Oujda", "statut": "A_REVISER", "confiance": 0.95, "page_source": 1},
    ]})
    with TestClient(app) as api:
        envoi = api.post("/captures", files={"image": ("p.jpg", b"\xff\xd8\xffvalidation", "image/jpeg")},
                         data={"session_id": "v", "page_no": "1", "sage_femme_id": "sf_01"}).json()
        api.post(f"/captures/{envoi['capture_id']}/traiter", headers=SF)
        for _ in range(100):
            if api.get(f"/captures/{envoi['capture_id']}/etat").json()["termine"]:
                break
            time.sleep(0.05)
        dossier_id = envoi["dossier"]["dossier_id"]

        r = api.post(f"/dossiers/{dossier_id}/validate", headers=SF).json()
        assert r["can_validate"] is False and r["dossier"]["etat"] == "A_REVISER"
        assert r["blocages"] == [{"code": "questions", "champs": ["identification.region", "identification.province"], "n": 2}]

        # Réponses de la sage-femme : confirmer la région, corriger la province.
        for champ, valeur in (("identification.region", "Oriental"), ("identification.province", "Oujda-Angad")):
            api.patch(f"/dossiers/{dossier_id}/champs", headers=SF, json={"champ": champ, "valeur": valeur, "statut": "CONNU", "confiance": 1})
        r = api.post(f"/dossiers/{dossier_id}/validate", headers=SF).json()
        assert r["can_validate"] is True and r["blocages"] == [] and r["dossier"]["etat"] == "VALIDE"


def test_schema_indique_si_la_lecture_est_reelle():
    with TestClient(app) as api:
        assert api.get("/schema").json()["fournisseur_extraction"] == "simule"  # conftest : jamais d'appel payant
