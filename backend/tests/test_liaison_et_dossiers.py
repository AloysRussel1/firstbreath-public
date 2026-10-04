"""Code de liaison, correspondances, listes /dossiers et /patientes, renumérisation d'une page."""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from backend import services
from backend.main import app

SF1 = {"X-Sage-Femme-Id": "sf_01", "X-Role": "SAGE_FEMME"}
SF2 = {"X-Sage-Femme-Id": "sf_02", "X-Role": "SAGE_FEMME"}
SUP = {"X-Sage-Femme-Id": "sup_01", "X-Role": "SUPERVISEUR"}


@pytest.fixture
def api():
    with TestClient(app) as client:
        yield client


def dossier_valide(session: str, numero: str, sage_femme: str = "sf_01") -> str:
    """Dossier validé par saisie manuelle (image de test illisible : l'extraction échoue)."""
    image = b"\xff\xd8\xff" + f"{session}-{numero}".encode()
    envoi = services.create_capture(image_bytes=image, content_type="image/jpeg", session_id=session,
                                    page_no=1, actor_id=sage_femme)
    dossier_id = envoi["dossier"]["dossier_id"]
    services.process_capture(envoi["capture_id"])
    services.patch_field(dossier_id, {"champ": "identification.numero_fiche", "valeur": numero, "statut": "CONNU",
                                      "confiance": 1, "page_no": 1, "type_page": "IDENTIFICATION"}, sage_femme)
    assert services.validate_record(dossier_id, sage_femme)["dossier"]["etat"] == "VALIDE"
    return dossier_id


def test_code_de_liaison_court_aleatoire_sans_caracteres_ambigus(api):
    codes = set()
    for i in range(6):
        dossier_id = dossier_valide(f"s{i}", f"2026-100-00{i}")
        r = api.post(f"/dossiers/{dossier_id}/lier", headers=SF1, json={"choix": "nouvelle"}).json()
        assert r["patient_created"] is True and r["dossier"]["etat"] == "PATIENTE_LIEE"
        assert re.fullmatch(r"[A-HJ-NP-Z2-9]{3}-[A-HJ-NP-Z2-9]{3}", r["code"])
        assert r["dossier"]["patiente_code"] == r["code"]
        codes.add(r["code"])
    assert len(codes) == 6
    assert services.normaliser_code(" abc 234 ") == "ABC-234"
    assert services.normaliser_code("ABO-234") is None  # O n'existe pas dans l'alphabet


def test_visite_suivante_proposee_par_code_ou_numero_jamais_liee_automatiquement(api):
    premiere = dossier_valide("v1", "2026-416-002")
    code = api.post(f"/dossiers/{premiere}/lier", headers=SF1, json={"choix": "nouvelle"}).json()["code"]

    # Visite suivante : N° de fiche relu différemment, mais même code recopié sur le papier.
    suivante = dossier_valide("v2", "2026-A16-002")
    assert services.get_record(suivante)["patiente_id"] is None  # rien n'est lié sans décision
    candidats = api.get("/patientes/correspondances", params={"code": code.replace("-", "").lower()}).json()["candidates"]
    assert len(candidats) == 1 and candidats[0]["raison"] == "code" and candidats[0]["nb_visites"] == 1
    assert api.get("/patientes/correspondances", params={"numero_fiche": "2026-416-002"}).json()["candidates"][0]["code"] == code
    assert api.get("/patientes/correspondances").status_code == 422

    patiente_id = candidats[0]["patiente_id"]
    # Sans le code, le N° de fiche différent interdit la liaison.
    assert api.post(f"/dossiers/{suivante}/lier", headers=SF1, json={"patiente_id": patiente_id}).status_code == 409
    r = api.post(f"/dossiers/{suivante}/lier", headers=SF1, json={"patiente_id": patiente_id, "code": code}).json()
    assert r["decision"] == "lier" and r["patient_created"] is False and r["code"] == code

    # « Je ne sais pas » : aucun changement.
    troisieme = dossier_valide("v3", "2026-416-002")
    assert api.post(f"/dossiers/{troisieme}/lier", headers=SF1, json={"choix": "inconnu"}).json()["dossier"]["etat"] == "VALIDE"

    patientes = api.get("/patientes", headers=SF1).json()["patientes"]
    assert len(patientes) == 1 and patientes[0]["code"] == code
    assert [v["dossier_id"] for v in patientes[0]["visites"]] == [premiere, suivante]


def test_liste_des_dossiers_selon_le_role(api):
    a = dossier_valide("r1", "2026-200-001", "sf_01")
    b = dossier_valide("r2", "2026-200-002", "sf_02")
    api.post(f"/dossiers/{b}/lier", headers=SF2, json={"choix": "nouvelle"})

    mes = api.get("/dossiers", headers=SF1).json()["dossiers"]
    assert [d["dossier_id"] for d in mes] == [a]
    assert mes[0]["etat"] == "VALIDE" and mes[0]["numero_fiche"] == "2026-200-001" and mes[0]["types_page"] == ["IDENTIFICATION"]
    assert {d["dossier_id"] for d in api.get("/dossiers", headers=SUP).json()["dossiers"]} == {a, b}
    # La patiente de sf_02 n'apparaît pas pour sf_01, mais apparaît pour le superviseur.
    assert api.get("/patientes", headers=SF1).json()["patientes"] == []
    assert len(api.get("/patientes", headers=SUP).json()["patientes"]) == 1


def test_renumerisation_ne_remplace_que_les_champs_choisis(api):
    dossier_id = dossier_valide("n1", "2026-300-001")
    # Nouvelle photo de la page d'identification, rangée en page 2.
    for champ, valeur in (("identification.region", "Oriental"), ("identification.province", "Oujda-Angad")):
        services.patch_field(dossier_id, {"champ": champ, "valeur": valeur, "statut": "CONNU", "confiance": 0.9,
                                          "page_no": 2, "type_page": "IDENTIFICATION"}, "sf_01")

    r = api.post(f"/dossiers/{dossier_id}/renumerisation", headers=SF1,
                 json={"ancienne_page": 1, "nouvelle_page": 2, "champs": ["identification.region"]})
    assert r.status_code == 200, r.text
    dossier = r.json()["dossier"]
    assert [p["page_no"] for p in dossier["pages"]] == [1]
    champs = {c["champ"]: c for c in dossier["pages"][0]["champs"]}
    assert champs["identification.region"]["valeur"] == "Oriental"
    assert champs["identification.region"]["source"] == "renumerisation"
    assert "identification.province" not in champs  # non choisi : ignoré
    assert dossier["renumerisations"][0]["champs"] == ["identification.region"]
    historique = api.get(f"/dossiers/{dossier_id}/historique").json()["field_changes"]
    assert historique[-1]["field_key"] == "identification.region"
    # Pages absentes ou numéros identiques : refus explicite.
    assert api.post(f"/dossiers/{dossier_id}/renumerisation", json={"ancienne_page": 1, "nouvelle_page": 2, "champs": []}).status_code == 404
    assert api.post(f"/dossiers/{dossier_id}/renumerisation", json={"ancienne_page": 1, "nouvelle_page": 1, "champs": []}).status_code == 422
