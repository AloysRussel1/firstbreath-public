from __future__ import annotations

from pathlib import Path

import pytest

from backend import database, services


JPEG = b"\xff\xd8\xff" + b"firstbreath-test-image"


def capture(session="session-a", page=1, image=JPEG, key=None, content_type="image/jpeg"):
    return services.create_capture(
        image_bytes=image,
        content_type=content_type,
        session_id=session,
        page_no=page,
        actor_id="midwife-1",
        idempotency_key=key,
    )


def test_capture_is_idempotent_and_duplicate_hash_is_flagged():
    first = capture()
    replay = capture()
    assert replay["capture_id"] == first["capture_id"]
    assert replay["idempotent_replay"] is True
    assert replay["dossier"]["dossier_id"] == first["dossier"]["dossier_id"]

    duplicate = capture(session="session-b")
    assert duplicate["duplicate_suspected"] is True
    assert duplicate["etat_capture"] == "DOUBLON_SUSPECTE"
    assert duplicate["dossier"]["dossier_id"] == first["dossier"]["dossier_id"]


def test_invalid_image_is_rejected():
    with pytest.raises(services.ServiceError) as error:
        capture(image=b"not an image")
    assert error.value.status_code == 415


PAGE_6 = Path(__file__).resolve().parents[2] / "data/Paper Registry/dossiers_specimen_10_patientes-06.png"


@pytest.mark.skipif(not PAGE_6.exists(), reason="data/ absent")
def test_real_page_goes_through_extract_page_and_keeps_all_schema_keys():
    uploaded = capture(image=PAGE_6.read_bytes(), page=6, content_type="image/png")
    result = services.process_capture(uploaded["capture_id"])
    page = result["dossier"]["pages"][0]
    keys = {field["champ"] for field in page["champs"]}
    assert page["type_page"] == "PP_PRECOCE_NOUVEAU_NE"
    # vaccins_du_jour contient « cin » : l'ancien filtre par sous-chaîne l'écartait à tort.
    assert "pp_precoce.nouveau_ne.vaccins_du_jour" in keys
    assert len(keys) == 11
    # Fournisseur simulé : confiance 0, donc tout est à réviser.
    assert result["extraction_status"] == "A_REVISER"


def test_manual_field_has_audit_trail_and_allows_explicit_validation():
    uploaded = capture()
    record_id = uploaded["dossier"]["dossier_id"]
    # Image de test illisible : l'extraction échoue, la saisie manuelle prend le relais.
    assert services.process_capture(uploaded["capture_id"])["extraction_status"] == "ECHEC_TRAITEMENT"

    record = services.patch_field(record_id, {
        "champ": "identification.numero_fiche",
        "valeur": "F-2026-014",
        "statut": "CONNU",
        "confiance": 1,
        "page_no": 1,
        "type_page": "IDENTIFICATION",
    }, "midwife-1")
    assert record["numero_fiche"] == "F-2026-014"
    assert record["etat"] == "REVISION_MANUELLE_REQUISE"
    assert services.validation_result(record)["can_validate"] is True
    history = services.record_history(record_id)
    assert history["field_changes"][0]["field_key"] == "identification.numero_fiche"

    validated = services.validate_record(record_id, "midwife-1")
    assert validated["can_validate"] is True
    assert validated["dossier"]["etat"] == "VALIDE"


def test_private_or_unknown_fields_cannot_be_saved():
    uploaded = capture()
    record_id = uploaded["dossier"]["dossier_id"]
    with pytest.raises(services.ServiceError):
        services.patch_field(record_id, {
            "champ": "identification.telephone",
            "valeur": "0601020304",
            "statut": "CONNU",
            "confiance": 1,
            "page_no": 1,
            "type_page": "IDENTIFICATION",
        }, "midwife-1")
    with pytest.raises(services.ServiceError):
        services.patch_field(record_id, {
            "champ": "identification.champ_inexistant",
            "valeur": "secret",
            "statut": "CONNU",
            "confiance": 1,
            "page_no": 1,
            "type_page": "IDENTIFICATION",
        }, "midwife-1")


def test_sync_replay_does_not_create_a_second_capture():
    created = capture()
    result = services.sync_records({"captures": [{"capture_id": created["capture_id"]}]})
    assert result["accepted"] == 1
    assert result["results"][0]["idempotent_replay"] is True
    with database.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 1
