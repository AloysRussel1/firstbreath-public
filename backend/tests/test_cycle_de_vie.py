"""Cycle de vie complet : CAPTURE -> ... -> SYNCHRONISE, avec panne de synchronisation et reprise ;
nouvelle page après validation ; code de liaison choisi par la sage-femme."""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from backend import database, services
from backend.constants import FORBIDDEN_FIELD_NAMES
from backend.main import app

SF = {"X-Sage-Femme-Id": "sf_01", "X-Role": "SAGE_FEMME"}


@pytest.fixture
def api(monkeypatch):
    import extraction.pipeline as pipeline

    monkeypatch.setattr(pipeline, "extract_page", lambda chemin: {"type_page": "IDENTIFICATION", "champs": [
        {"champ": "identification.numero_fiche", "valeur": "2026-700-001", "statut": "CONNU", "confiance": 0.98, "page_source": 1},
        {"champ": "identification.region", "valeur": "Oriental", "statut": "CONNU", "confiance": 0.97, "page_source": 1},
    ]})
    with TestClient(app) as client:
        yield client


def envoyer_et_lire(api, session: str, page: int = 1, octets: bytes | None = None) -> dict:
    image = octets or b"\xff\xd8\xff" + f"{session}-{page}".encode()
    envoi = api.post("/captures", files={"image": ("p.jpg", image, "image/jpeg")},
                     data={"session_id": session, "page_no": str(page), "sage_femme_id": "sf_01"}).json()
    api.post(f"/captures/{envoi['capture_id']}/traiter", headers=SF)
    for _ in range(100):
        etat = api.get(f"/captures/{envoi['capture_id']}/etat").json()
        if etat["termine"]:
            return etat
        time.sleep(0.05)
    raise AssertionError("traitement non terminé")


def test_cycle_complet_jusqu_a_synchronise_avec_panne_et_reprise(api):
    etat = envoyer_et_lire(api, "cycle")
    dossier_id = etat["dossier"]["dossier_id"]
    assert etat["dossier"]["etat"] == "TRAITE_IA"
    assert api.post(f"/dossiers/{dossier_id}/enregistrer", headers=SF).status_code == 409  # pas encore validé
    assert api.post(f"/dossiers/{dossier_id}/validate", headers=SF).json()["dossier"]["etat"] == "VALIDE"
    assert api.post(f"/dossiers/{dossier_id}/lier", headers=SF, json={"choix": "nouvelle"}).json()["dossier"]["etat"] == "PATIENTE_LIEE"
    assert api.post(f"/dossiers/{dossier_id}/enregistrer", headers=SF).json()["dossier"]["etat"] == "ENREGISTRE"

    panne = api.post("/synchronisation", headers=SF, json={"simuler_panne": True}).json()
    assert panne == {"synchronises": [], "echecs": [dossier_id]}
    assert services.get_record(dossier_id)["etat"] == "ECHEC_SYNCHRONISATION"

    reprise = api.post("/synchronisation", headers=SF).json()
    assert reprise == {"synchronises": [dossier_id], "echecs": []}
    assert services.get_record(dossier_id)["etat"] == "SYNCHRONISE"
    assert api.post("/synchronisation", headers=SF).json() == {"synchronises": [], "echecs": []}  # rien à renvoyer

    etats = [t["to_state"] for t in api.get(f"/dossiers/{dossier_id}/historique").json()["transitions"]]
    assert etats == ["EN_ATTENTE_IA", "TRAITE_IA", "VALIDE", "PATIENTE_LIEE", "ENREGISTRE", "ECHEC_SYNCHRONISATION", "SYNCHRONISE"]

    # La copie envoyée au système central ne contient ni image ni identifiant direct.
    with database.connect() as db:
        copie = json.loads(db.execute("SELECT payload FROM systeme_central WHERE dossier_id = ?", (dossier_id,)).fetchone()["payload"])
    texte = json.dumps(copie)
    assert "image" not in texte and "storage_path" not in texte and "sage_femme_id" not in texte
    assert not any(f'.{nom}"' in texte for nom in FORBIDDEN_FIELD_NAMES)
    assert copie["patiente_code"] and copie["pages"][0]["champs"][0]["champ"] == "identification.numero_fiche"


def test_la_synchronisation_ne_touche_que_les_dossiers_de_la_sage_femme(api):
    etat = envoyer_et_lire(api, "autre")
    dossier_id = etat["dossier"]["dossier_id"]
    api.post(f"/dossiers/{dossier_id}/validate", headers=SF)
    api.post(f"/dossiers/{dossier_id}/enregistrer", headers=SF)  # enregistré sans liaison (« Je ne sais pas »)
    autre = {"X-Sage-Femme-Id": "sf_99", "X-Role": "SAGE_FEMME"}
    assert api.post("/synchronisation", headers=autre).json()["synchronises"] == []
    assert api.post("/synchronisation", headers=SF).json()["synchronises"] == [dossier_id]


def test_une_page_ajoutee_apres_validation_renvoie_le_dossier_en_revision(api):
    etat = envoyer_et_lire(api, "ajout")
    dossier_id = etat["dossier"]["dossier_id"]
    api.post(f"/dossiers/{dossier_id}/validate", headers=SF)
    suivante = envoyer_et_lire(api, "ajout", page=2)
    assert suivante["etat"] in ("TRAITE_IA", "A_REVISER")
    etats = [t["to_state"] for t in api.get(f"/dossiers/{dossier_id}/historique").json()["transitions"]]
    assert etats[-3:] == ["A_REVISER", "EN_ATTENTE_IA", suivante["dossier"]["etat"]]


def test_code_de_liaison_choisi_par_la_sage_femme(api):
    a = envoyer_et_lire(api, "code-a")["dossier"]["dossier_id"]
    api.post(f"/dossiers/{a}/validate", headers=SF)
    r = api.post(f"/dossiers/{a}/lier", headers=SF, json={"choix": "nouvelle", "code": "kmp 7x4"})
    assert r.status_code == 200 and r.json()["code"] == "KMP-7X4"

    b = envoyer_et_lire(api, "code-b")["dossier"]["dossier_id"]
    api.post(f"/dossiers/{b}/validate", headers=SF)
    assert api.post(f"/dossiers/{b}/lier", headers=SF, json={"choix": "nouvelle", "code": "KMP-7X4"}).status_code == 409  # déjà pris
    assert api.post(f"/dossiers/{b}/lier", headers=SF, json={"choix": "nouvelle", "code": "ABO-123"}).status_code == 422  # O et 1 exclus
