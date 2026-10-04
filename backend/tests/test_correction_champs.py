"""PATCH /dossiers/{id}/champs : une valeur au format du schéma passe ; sinon 422 avec un détail qui dit pourquoi.

L'interface convertit la saisie avant l'envoi (frontend/src/lib/saisie.js, testé par « npm test ») ; ici, on fixe le
contrat du serveur pour chaque type corrigé : date, nombre, tension, choix, liste de cases.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app

SF = {"X-Sage-Femme-Id": "sf_01", "X-Role": "SAGE_FEMME"}

# (champ, type de page, valeur convertie par l'interface, valeur brute telle que tapée, mot attendu dans le détail)
CAS = [
    ("grossesse.ddr", "GROSSESSE_ACTUELLE", "2026-01-15", "15/01/2026", "date"),
    ("profil.age", "ANTECEDENTS", 28, "28 ans", "entier"),
    ("grossesse.tests.glycemie_g_l", "GROSSESSE_ACTUELLE", 0.9, "0,9", "decimal"),
    ("pp_precoce.mere.tension", "PP_PRECOCE_MERE", "110/70", "11/7", "tension"),
    ("identification.type_etablissement", "IDENTIFICATION", "CSC", "Centre de santé", "choix"),
    ("identification.types_risque", "IDENTIFICATION", ["HTA", "ANEMIE"], "HTA, anémie", "liste_choix"),
]
PAGE_NO = {"IDENTIFICATION": 1, "ANTECEDENTS": 2, "GROSSESSE_ACTUELLE": 3, "PP_PRECOCE_MERE": 4}


@pytest.fixture()
def dossier(monkeypatch):
    import extraction.pipeline as pipeline

    monkeypatch.setattr(pipeline, "extract_page", lambda chemin: {"type_page": "IDENTIFICATION", "champs": [
        {"champ": "identification.numero_fiche", "valeur": "2026-823-009", "statut": "CONNU", "confiance": 0.98, "page_source": 1},
    ]})
    with TestClient(app) as api:
        envoi = api.post("/captures", files={"image": ("p.jpg", b"\xff\xd8\xffcorrection", "image/jpeg")},
                         data={"session_id": "corr", "page_no": "1", "sage_femme_id": "sf_01"}).json()
        api.post(f"/captures/{envoi['capture_id']}/traiter", headers=SF)
        for _ in range(100):
            if api.get(f"/captures/{envoi['capture_id']}/etat").json()["termine"]:
                break
            time.sleep(0.05)
        yield api, envoi["dossier"]["dossier_id"]


def corriger(api, dossier_id, champ, type_page, valeur):
    return api.patch(f"/dossiers/{dossier_id}/champs", headers=SF, json={
        "champ": champ, "valeur": valeur, "statut": "CONNU", "confiance": 1,
        "page_no": PAGE_NO[type_page], "type_page": type_page,
    })


@pytest.mark.parametrize("champ,type_page,convertie,brute,mot", CAS, ids=[c[4] for c in CAS])
def test_valeur_convertie_acceptee(dossier, champ, type_page, convertie, brute, mot):
    api, dossier_id = dossier
    r = corriger(api, dossier_id, champ, type_page, convertie)
    assert r.status_code == 200, r.json()
    page = next(p for p in r.json()["dossier"]["pages"] if p["page_no"] == PAGE_NO[type_page])
    enregistre = next(c for c in page["champs"] if c["champ"] == champ)
    assert enregistre["valeur"] == convertie and enregistre["statut"] == "CONNU" and enregistre["source"] == "manual"


@pytest.mark.parametrize("champ,type_page,convertie,brute,mot", CAS, ids=[c[4] for c in CAS])
def test_valeur_brute_refusee_avec_un_detail_explicite(dossier, champ, type_page, convertie, brute, mot):
    api, dossier_id = dossier
    r = corriger(api, dossier_id, champ, type_page, brute)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert champ in detail and f"type {mot}" in detail, detail
