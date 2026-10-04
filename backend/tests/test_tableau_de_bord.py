"""GET /tableau-de-bord : dossiers validés seulement, cases de moins de 5 dossiers masquées."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend import services
from backend.main import app


def dossier(session: str, vih: str | None, tension: str, valider: bool = True) -> str:
    envoi = services.create_capture(image_bytes=b"\xff\xd8\xff" + session.encode(), content_type="image/jpeg",
                                    session_id=session, page_no=1, actor_id="sf_01")
    dossier_id = envoi["dossier"]["dossier_id"]
    services.process_capture(envoi["capture_id"])  # image illisible : saisie manuelle

    def saisir(champ, valeur, page_no, type_page):
        services.patch_field(dossier_id, {"champ": champ, "valeur": valeur, "statut": "CONNU", "confiance": 1,
                                          "page_no": page_no, "type_page": type_page}, "sf_01")

    saisir("identification.numero_fiche", f"2026-500-{session}", 1, "IDENTIFICATION")
    if vih:
        saisir("grossesse.tests.vih", vih, 2, "GROSSESSE_ACTUELLE")
    saisir("grossesse.visites[0].tension", tension, 2, "GROSSESSE_ACTUELLE")
    saisir("grossesse.visites[1].tension", tension, 2, "GROSSESSE_ACTUELLE")  # même dossier : compté une fois
    if valider:
        assert services.validate_record(dossier_id, "sf_01")["dossier"]["etat"] == "VALIDE"
    return dossier_id


def test_tableau_masque_les_petits_effectifs_et_ignore_les_dossiers_non_valides():
    for i in range(6):
        dossier(f"n{i}", "NEGATIF", "125/80")
    for i in range(2):
        dossier(f"p{i}", "POSITIF", "150/95")
    for i in range(3):
        dossier(f"x{i}", "POSITIF", "150/95", valider=False)  # non validés : jamais comptés

    with TestClient(app) as api:
        tableau = api.get("/tableau-de-bord").json()
    assert tableau["seuil_anonymat"] == 5 and tableau["dossiers"]["effectif"] == 8
    indic = {i["id"]: i for i in tableau["indicateurs"]}

    vih = {c["categorie"]: c for c in indic["vih"]["cases"]}
    assert vih["NEGATIF"]["effectif"] == 6 and vih["NEGATIF"]["masque"] is False
    assert vih["POSITIF"] == {"categorie": "POSITIF", "effectif": None, "masque": True,
                              "message": "Effectif insuffisant pour préserver l'anonymat"}
    assert vih["NON_RENSEIGNE"]["masque"] is True  # 0 dossier : masqué aussi

    systolique = {(c["min"], c["max"]): c for c in indic["tension_systolique"]["cases"]}
    assert systolique[(120, 140)]["effectif"] == 6  # 6 dossiers, 12 mesures
    assert systolique[(140, 160)]["masque"] is True  # 2 dossiers validés seulement
    assert indic["tension_diastolique"]["dossiers_mesures"]["effectif"] == 8
    assert indic["temperature_mere"]["dossiers_mesures"]["masque"] is True
    assert {"syphilis", "hepatite_c", "temperature_nouveau_ne"} <= set(indic)


def test_tableau_vide_entierement_masque():
    with TestClient(app) as api:
        tableau = api.get("/tableau-de-bord").json()
    assert tableau["dossiers"]["masque"] is True and tableau["dossiers"]["effectif"] is None
    assert all(c["masque"] for i in tableau["indicateurs"] for c in i["cases"])


CSV = services.CSV_DEMONSTRATION


@pytest.mark.skipif(not CSV.exists(), reason="data/ absent")
def test_source_de_demonstration_calculee_depuis_le_csv_synthetique():
    with TestClient(app) as api:
        tableau = api.get("/tableau-de-bord", params={"source": "demo"}).json()
    assert tableau["source"] == "demo" and tableau["synthetique"] is True and tableau["dossiers"]["effectif"] == 200
    depistage = {d["id"]: d for d in tableau["depistage"]}
    # VIH : 190 dépistées sur 200 (95 %), 3 positives -> masqué, aucun pourcentage publié.
    assert depistage["vih"]["depistees"]["effectif"] == 190 and depistage["vih"]["part_depistees"] == 95.0
    assert depistage["vih"]["positifs"]["masque"] is True and depistage["vih"]["part_positifs"] is None
    # Syphilis : 9 positives sur 193 dépistées -> publié.
    assert depistage["syphilis"]["positifs"]["effectif"] == 9 and depistage["syphilis"]["part_positifs"] == 4.7
    indic = {i["id"]: i for i in tableau["indicateurs"]}
    assert indic["tension_systolique"]["dossiers_mesures"]["effectif"] == 200
    assert indic["temperature_mere"]["disponible"] is False  # pas de température dans le CSV


def test_source_inconnue_refusee():
    with TestClient(app) as api:
        assert api.get("/tableau-de-bord", params={"source": "autre"}).status_code == 422
        tableau = api.get("/tableau-de-bord").json()
    assert tableau["source"] == "dossiers" and tableau["synthetique"] is False
    assert all(d["part_depistees"] is None for d in tableau["depistage"])  # aucun dossier : rien n'est publié
