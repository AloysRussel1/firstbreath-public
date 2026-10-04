"""Étape 5 : parcours complet en fournisseur simulé, de l'envoi des photos jusqu'au dossier validé.

Envoi de 3 pages de la patiente 1 dans une même session -> /traiter -> suivi de /etat -> dossier
(3 pages, conforme à shared/valider.py) -> correction du N° de fiche -> validation -> image d'origine.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from shared.valider import valider_dossier

REGISTRE = Path(__file__).resolve().parents[2] / "data/Paper Registry"
PAGES = {1: "dossiers_specimen_10_patientes-01.png",   # IDENTIFICATION
         3: "dossiers_specimen_10_patientes-03.png",   # GROSSESSE_ACTUELLE
         6: "dossiers_specimen_10_patientes-06.png"}   # PP_PRECOCE_NOUVEAU_NE
pytestmark = pytest.mark.skipif(not (REGISTRE / PAGES[1]).exists(), reason="data/ absent")


def test_parcours_complet_de_la_photo_au_dossier_valide():
    with TestClient(app) as api:
        captures = []
        for page_no, fichier in PAGES.items():
            r = api.post("/captures", files={"image": (fichier, (REGISTRE / fichier).read_bytes(), "image/png")},
                         data={"session_id": "visite-1", "page_no": str(page_no), "sage_femme_id": "sf_01"})
            assert r.status_code == 200 and r.json()["etat_capture"] == "CAPTURE"
            captures.append(r.json()["capture_id"])
        dossier_id = api.get(f"/captures/{captures[0]}").json()["dossier_id"]
        assert all(api.get(f"/captures/{c}").json()["dossier_id"] == dossier_id for c in captures)  # 1 session = 1 dossier

        for c in captures:
            assert api.post(f"/captures/{c}/traiter").json()["etat"] == "EN_ATTENTE_IA"
        assert api.get(f"/captures/{captures[1]}/etat").json()["duree_estimee_s"] == 70  # GROSSESSE_ACTUELLE

        fin = time.monotonic() + 30
        etats = {}
        while time.monotonic() < fin and len(etats) < len(captures):
            for c in captures:
                e = api.get(f"/captures/{c}/etat").json()
                if e["termine"]:
                    etats[c] = e
            time.sleep(0.05)
        assert len(etats) == 3 and all(e["etat"] in ("TRAITE_IA", "A_REVISER") for e in etats.values())

        dossier = api.get(f"/dossiers/{dossier_id}").json()
        assert sorted(p["type_page"] for p in dossier["pages"]) == ["GROSSESSE_ACTUELLE", "IDENTIFICATION", "PP_PRECOCE_NOUVEAU_NE"]
        assert len([c for p in dossier["pages"] for c in p["champs"]]) == 8 + 160 + 11
        assert valider_dossier(dossier)[0] == []
        assert dossier["etat"] == "A_REVISER"  # fournisseur simulé : confiance 0, tout est à vérifier
        assert api.get(f"/dossiers/{dossier_id}/validation").json()["can_validate"] is False

        # La validation explique ce qui l'empêche : N° de fiche absent et champs douteux sans réponse.
        blocages = {b["code"]: b for b in api.get(f"/dossiers/{dossier_id}/validation").json()["blocages"]}
        assert blocages["champs_obligatoires"]["champs"] == ["identification.numero_fiche"]
        assert blocages["questions"]["n"] == 8 + 160 + 11 - 1

        # La sage-femme corrige le N° de fiche : il reste les questions.
        r = api.patch(f"/dossiers/{dossier_id}/champs", headers={"X-Sage-Femme-Id": "sf_01"},
                      json={"champ": "identification.numero_fiche", "valeur": "2026-823-001", "statut": "CONNU", "confiance": 1})
        assert r.status_code == 200 and [b["code"] for b in r.json()["validation"]["blocages"]] == ["questions"]
        # Elle répond aux autres questions (« vide sur le papier ») : plus rien ne bloque.
        for page in r.json()["dossier"]["pages"]:
            for champ in page["champs"]:
                if champ["champ"] != "identification.numero_fiche":
                    api.patch(f"/dossiers/{dossier_id}/champs", headers={"X-Sage-Femme-Id": "sf_01"},
                              json={"champ": champ["champ"], "valeur": None, "statut": "NON_FOURNI", "confiance": 1, "page_no": page["page_no"]})
        assert api.get(f"/dossiers/{dossier_id}/validation").json() | {"validation_errors": []} == {
            "can_validate": True, "missing_fields": [], "champs_a_verifier": [], "blocages": [], "reason": None, "validation_errors": []}
        valide = api.post(f"/dossiers/{dossier_id}/validate", headers={"X-Sage-Femme-Id": "sf_01"}).json()
        assert valide["dossier"]["etat"] == "VALIDE" and valide["dossier"]["numero_fiche"] == "2026-823-001"

        historique = api.get(f"/dossiers/{dossier_id}/historique").json()
        assert [t["to_state"] for t in historique["transitions"]][-2:] == ["A_REVISER", "VALIDE"]
        image = api.get(f"/captures/{captures[0]}/image", headers={"X-Role": "SUPERVISEUR"})
        assert image.status_code == 200 and image.content == (REGISTRE / PAGES[1]).read_bytes()
