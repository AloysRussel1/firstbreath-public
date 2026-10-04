"""Capture, extraction, validation, and patient-linking services."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend import database
from backend.constants import (
    ALLOWED_FIELD_STATUSES,
    ALLOWED_PAGE_TYPES,
    ALLOWED_RECORD_STATES,
    CONFIDENCE_THRESHOLD,
    DATA_DIR,
    IMAGE_DIR,
    PROJECT_ROOT,
    MAX_UPLOAD_BYTES,
    REQUIRED_FIELDS,
    definition,
    valider_dossier,
    valider_page,
)


class ServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


TRANSITIONS = {
    "CAPTURE": {"EN_ATTENTE_IA", "A_REVISER", "REVISION_MANUELLE_REQUISE", "DOUBLON_SUSPECTE"},
    "EN_ATTENTE_IA": {"TRAITE_IA", "A_REVISER", "ECHEC_TRAITEMENT", "REVISION_MANUELLE_REQUISE"},
    "TRAITE_IA": {"A_REVISER", "VALIDE", "EN_ATTENTE_IA"},
    "A_REVISER": {"EN_ATTENTE_IA", "VALIDE", "REVISION_MANUELLE_REQUISE"},
    "ECHEC_TRAITEMENT": {"EN_ATTENTE_IA", "REVISION_MANUELLE_REQUISE"},
    "REVISION_MANUELLE_REQUISE": {"EN_ATTENTE_IA", "A_REVISER", "VALIDE"},
    "DOUBLON_SUSPECTE": {"A_REVISER", "REVISION_MANUELLE_REQUISE"},
    "VALIDE": {"PATIENTE_LIEE", "ENREGISTRE", "A_REVISER"},
    "PATIENTE_LIEE": {"ENREGISTRE", "A_REVISER"},
    "ENREGISTRE": {"SYNCHRONISE", "ECHEC_SYNCHRONISATION", "A_REVISER"},
    "SYNCHRONISE": {"A_REVISER"},
    "ECHEC_SYNCHRONISATION": {"SYNCHRONISE", "ECHEC_SYNCHRONISATION", "A_REVISER"},
}

PHONE_PATTERN = re.compile(r"\b0[5-7](?:[ .-]?\d{2}){4}\b")
CIN_PATTERN = re.compile(r"\b[A-Z]{1,2}\d{5,6}\b", re.IGNORECASE)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def horodatage_precis() -> str:
    """Début et fin de traitement à la milliseconde (une extraction simulée dure moins d'une seconde)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _read_record_row(row: Any) -> dict[str, Any] | None:
    return json.loads(row["payload"]) if row else None


def get_record(record_id: str) -> dict[str, Any] | None:
    with database.connect() as db:
        row = db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone()
    return _read_record_row(row)


def _save_record(db: Any, record: dict[str, Any]) -> None:
    timestamp = now_iso()
    db.execute(
        "UPDATE records SET state = ?, payload = ?, updated_at = ? WHERE id = ?",
        (record["etat"], _dump(record), timestamp, record["dossier_id"]),
    )


def _transition(db: Any, record: dict[str, Any], target: str, actor_id: str, reason: str) -> None:
    if target not in ALLOWED_RECORD_STATES:
        raise ServiceError(422, f"Unsupported record state: {target}")
    source = record["etat"]
    if source == target:
        return
    if target not in TRANSITIONS.get(source, set()):
        raise ServiceError(409, f"Invalid state transition: {source} -> {target}")
    changed_at = now_iso()
    db.execute(
        "INSERT INTO transitions(record_id, from_state, to_state, changed_at, actor_id, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (record["dossier_id"], source, target, changed_at, actor_id, reason[:240]),
    )
    record["historique_etats"].append({"de": source, "vers": target, "date": changed_at, "acteur": actor_id, "raison": reason[:240]})
    record["etat"] = target


def _new_record(session_id: str, actor_id: str) -> dict[str, Any]:
    timestamp = now_iso()
    record_id = str(uuid.uuid4())
    return {
        "dossier_id": record_id,
        "patiente_id": None,
        "numero_fiche": None,
        "sage_femme_id": actor_id,
        "session_id": session_id,
        "etat": "CAPTURE",
        "pages": [],
        "captures": [],
        "historique_etats": [{"de": None, "vers": "CAPTURE", "date": timestamp, "acteur": actor_id, "raison": "Nouvelle capture"}],
    }


def _looks_private(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(PHONE_PATTERN.search(value) or CIN_PATTERN.search(value))


def validate_image(content: bytes, content_type: str | None = None) -> str:
    if not content:
        raise ServiceError(400, "The uploaded image is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ServiceError(413, f"Image exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        extension, expected_type = ".png", "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        extension, expected_type = ".jpg", "image/jpeg"
    else:
        raise ServiceError(415, "Unsupported file. Upload a valid JPG or PNG image.")
    if content_type and content_type not in (expected_type, "application/octet-stream"):
        raise ServiceError(415, "The file content does not match its declared image type.")
    return extension


def create_capture(
    *,
    image_bytes: bytes,
    content_type: str | None,
    session_id: str,
    page_no: int,
    actor_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    extension = validate_image(image_bytes, content_type)
    if not session_id.strip() or len(session_id) > 160:
        raise ServiceError(422, "session_id is required and must be shorter than 160 characters.")
    if not actor_id.strip() or len(actor_id) > 160:
        raise ServiceError(422, "sage_femme_id is required and must be shorter than 160 characters.")
    if page_no < 1 or page_no > 80:
        raise ServiceError(422, "page_no must be between 1 and 80.")

    image_hash = hashlib.sha256(image_bytes).hexdigest()
    raw_key = idempotency_key or f"{actor_id}:{session_id}:{page_no}:{image_hash}"
    idem_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    timestamp = now_iso()

    with database.connect() as db:
        repeated = db.execute("SELECT id, record_id FROM captures WHERE idempotency_hash = ?", (idem_hash,)).fetchone()
        if repeated:
            row = db.execute("SELECT payload FROM records WHERE id = ?", (repeated["record_id"],)).fetchone()
            return {"capture_id": repeated["id"], "dossier": _read_record_row(row), "duplicate_suspected": False, "idempotent_replay": True}

        same_page = db.execute(
            "SELECT c.id, c.record_id FROM captures c JOIN records r ON r.id = c.record_id WHERE c.image_hash = ? AND c.page_no = ? AND r.owner_id = ? AND r.session_id = ?",
            (image_hash, page_no, actor_id, session_id),
        ).fetchone()
        if same_page:
            row = db.execute("SELECT payload FROM records WHERE id = ?", (same_page["record_id"],)).fetchone()
            return {"capture_id": same_page["id"], "dossier": _read_record_row(row), "duplicate_suspected": False, "idempotent_replay": True}

        duplicate = db.execute("SELECT id, record_id FROM captures WHERE image_hash = ? LIMIT 1", (image_hash,)).fetchone()
        if duplicate:
            report_id = str(uuid.uuid4())
            db.execute(
                "INSERT INTO duplicate_reports(id, existing_capture_id, proposed_session_id, proposed_page_no, actor_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (report_id, duplicate["id"], session_id, page_no, actor_id, timestamp),
            )
            row = db.execute("SELECT payload FROM records WHERE id = ?", (duplicate["record_id"],)).fetchone()
            return {
                "capture_id": duplicate["id"],
                "duplicate_report_id": report_id,
                "dossier": _read_record_row(row),
                "duplicate_suspected": True,
                "idempotent_replay": False,
                "etat_capture": "DOUBLON_SUSPECTE",
            }

        record_row = db.execute(
            "SELECT payload FROM records WHERE owner_id = ? AND session_id = ?",
            (actor_id, session_id),
        ).fetchone()
        record = _read_record_row(record_row)
        new_record = record is None
        if new_record:
            record = _new_record(session_id, actor_id)
            db.execute(
                "INSERT INTO records(id, owner_id, session_id, state, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (record["dossier_id"], actor_id, session_id, record["etat"], _dump(record), timestamp, timestamp),
            )

        image_id = str(uuid.uuid4())
        capture_id = str(uuid.uuid4())
        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        storage_path = IMAGE_DIR / f"{image_id}{extension}"
        storage_path.write_bytes(image_bytes)
        record["captures"].append({"capture_id": capture_id, "page_no": page_no, "image_id": image_id,
                                   "image_hash": f"sha256:{image_hash}", "date_capture": timestamp,
                                   "sage_femme_id": actor_id, "etat": "CAPTURE", "type_page": None})
        try:
            db.execute(
                "INSERT INTO captures(id, record_id, page_no, image_id, image_hash, storage_path, idempotency_hash, created_at, sage_femme_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (capture_id, record["dossier_id"], page_no, image_id, image_hash, str(storage_path), idem_hash, timestamp, actor_id),
            )
            _save_record(db, record)
        except Exception:
            storage_path.unlink(missing_ok=True)
            raise

    return {"capture_id": capture_id, "dossier": record, "duplicate_suspected": False, "idempotent_replay": False, "etat_capture": "CAPTURE"}


def _get_capture(capture_id: str) -> Any | None:
    with database.connect() as db:
        return db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()


# ---------- Traitement d'une capture (asynchrone) ----------
# États d'une capture : CAPTURE -> EN_ATTENTE_IA -> TRAITE_IA | A_REVISER | ECHEC_TRAITEMENT
# | REVISION_MANUELLE_REQUISE (vocabulaire de shared/statuts.json).
FINAUX_PAR_GRAVITE = ("ECHEC_TRAITEMENT", "REVISION_MANUELLE_REQUISE", "A_REVISER", "TRAITE_IA")
RELANCABLES = ("CAPTURE", "ECHEC_TRAITEMENT", "REVISION_MANUELLE_REQUISE")
DUREE_GROSSESSE_S, DUREE_PAGE_S, DUREE_INCONNUE_S = 70, 15, 20
EXECUTEUR = ThreadPoolExecutor(max_workers=int(os.getenv("FIRSTBREATH_TRAITEMENTS_SIMULTANES", "2")),
                               thread_name_prefix="extraction")


def duree_estimee(image_path: Path) -> int:
    """Environ 70 s pour GROSSESSE_ACTUELLE, 10 à 20 s pour les autres pages (type connu par sha256)."""
    try:
        from extraction.pipeline import type_page_connu

        type_page = type_page_connu(str(image_path))
    except Exception:
        type_page = None
    if type_page is None:
        return DUREE_INCONNUE_S
    return DUREE_GROSSESSE_S if type_page == "GROSSESSE_ACTUELLE" else DUREE_PAGE_S


def demarrer_traitement(capture_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Passe la capture en EN_ATTENTE_IA. Ne relance pas une capture en cours ou déjà traitée."""
    capture = _get_capture(capture_id)
    if not capture:
        raise ServiceError(404, "Capture not found.")
    record = get_record(capture["record_id"])
    if not record:
        raise ServiceError(404, "Record not found.")
    actor = actor_id or record["sage_femme_id"]
    image_path = Path(capture["storage_path"])
    if not image_path.is_file():
        raise ServiceError(404, "Original image is missing from private storage.")

    lancer = capture["etat_traitement"] in RELANCABLES
    if lancer:
        with database.connect() as db:
            record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record["dossier_id"],)).fetchone())
            if record["etat"] != "EN_ATTENTE_IA" and "EN_ATTENTE_IA" not in TRANSITIONS.get(record["etat"], set()):
                # Page ajoutée à un dossier validé (ou enregistré, synchronisé…) : il devra être revalidé.
                _transition(db, record, "A_REVISER", actor, "Nouvelle page ajoutée : le dossier doit être revalidé")
            _transition(db, record, "EN_ATTENTE_IA", actor, "Traitement demandé")
            _maj_capture_dossier(record, capture_id, "EN_ATTENTE_IA")
            _save_record(db, record)
            db.execute(
                "UPDATE captures SET etat_traitement = 'EN_ATTENTE_IA', debut_traitement = ?, fin_traitement = NULL, "
                "duree_estimee_s = ?, detail_traitement = NULL WHERE id = ?",
                (horodatage_precis(), duree_estimee(image_path), capture_id),
            )
    return {**etat_capture(capture_id), "lancer": lancer, "acteur": actor}


def traiter_en_fond(capture_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Pour POST /captures/{id}/traiter : répond tout de suite, l'extraction tourne dans un fil séparé."""
    demarre = demarrer_traitement(capture_id, actor_id)
    if demarre["lancer"]:
        EXECUTEUR.submit(executer_traitement, capture_id, demarre["acteur"])
    return {k: v for k, v in demarre.items() if k not in ("lancer", "acteur")}


def process_capture(capture_id: str, actor_id: str | None = None) -> dict[str, Any]:
    """Version synchrone (utilisée par /sync et les tests) : démarre et attend la fin."""
    demarre = demarrer_traitement(capture_id, actor_id)
    if demarre["lancer"]:
        executer_traitement(capture_id, demarre["acteur"])
    etat = etat_capture(capture_id)
    return {"dossier": etat["dossier"], "extraction_status": etat["etat"], "detail": etat["detail"]}


def executer_traitement(capture_id: str, actor: str) -> None:
    """Extraction puis enregistrement ; ne lève jamais (tâche de fond)."""
    type_page = None
    try:
        etat, detail, type_page = _extraire_et_enregistrer(_get_capture(capture_id), actor)
    except Exception as exc:  # noqa: BLE001 — toute erreur doit finir en état explicite
        etat = "ECHEC_TRAITEMENT"
        if getattr(exc, "etat", None) == "ECHEC_TRAITEMENT":
            detail = "Lecture impossible malgré les nouveaux essais : saisie manuelle requise. L'image est conservée."
        else:
            detail = "L'extraction a échoué : saisie manuelle requise. L'image est conservée."
    _terminer(capture_id, etat, detail, type_page, actor)


def _terminer(capture_id: str, etat: str, detail: str | None, type_page: str | None, actor: str) -> None:
    """Enregistre l'état final de la capture ; le dossier ne sort d'EN_ATTENTE_IA que quand toutes
    ses captures sont terminées, vers l'issue la plus grave (échec > révision manuelle > à réviser > traité)."""
    with database.connect() as db:
        db.execute(
            "UPDATE captures SET etat_traitement = ?, fin_traitement = ?, detail_traitement = ?, "
            "type_page = COALESCE(?, type_page) WHERE id = ?",
            (etat, horodatage_precis(), detail, type_page, capture_id),
        )
        record_id = db.execute("SELECT record_id FROM captures WHERE id = ?", (capture_id,)).fetchone()["record_id"]
        etats = [row["etat_traitement"] for row in db.execute("SELECT etat_traitement FROM captures WHERE record_id = ?", (record_id,))]
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        _maj_capture_dossier(record, capture_id, etat, type_page)
        if record["etat"] == "EN_ATTENTE_IA" and "EN_ATTENTE_IA" not in etats:
            cible = next(e for e in FINAUX_PAR_GRAVITE if e in etats or e == "TRAITE_IA")
            _transition(db, record, cible, actor, detail or "Extraction terminée ; données structurées validées")
        _save_record(db, record)


def _maj_capture_dossier(record: dict[str, Any], capture_id: str, etat: str, type_page: str | None = None) -> None:
    """Reporte l'état (et le type de page) d'une capture dans la liste des captures du dossier."""
    for item in record.get("captures", []):
        if item.get("capture_id") == capture_id:
            item["etat"] = etat
            if type_page:
                item["type_page"] = type_page


# ---------- Métadonnées et image d'origine d'une capture ----------
ROLES = ("SAGE_FEMME", "SUPERVISEUR")


def capture_info(capture_id: str) -> dict[str, Any]:
    """Pour GET /captures/{id} : métadonnées de la capture, sans l'image."""
    capture = _get_capture(capture_id)
    if not capture:
        raise ServiceError(404, "Capture not found.")
    return {
        "capture_id": capture_id,
        "dossier_id": capture["record_id"],
        "page_no": capture["page_no"],
        "etat": capture["etat_traitement"],
        "type_page": capture["type_page"],
        "image_id": capture["image_id"],
        "image_sha256": capture["image_hash"],
        "date_capture": capture["created_at"],
        "sage_femme_id": capture["sage_femme_id"],
        "image": f"/captures/{capture_id}/image",
    }


def lire_image(capture_id: str, role: str | None, demandeur_id: str | None) -> tuple[Path, str]:
    """Image d'origine d'une capture, selon le rôle :
    SUPERVISEUR -> toutes les images ; SAGE_FEMME -> seulement les images qu'elle a capturées.
    Chaque demande (autorisée ou non) est journalisée dans acces_images.

    Limite : rôle et identifiant viennent d'en-têtes HTTP déclaratifs (prototype) ;
    en production, ils viendraient d'une authentification.
    """
    capture = _get_capture(capture_id)
    if not capture:
        raise ServiceError(404, "Capture not found.")
    if role is None:
        raise ServiceError(401, "En-tête X-Role requis (SAGE_FEMME ou SUPERVISEUR).")
    if role not in ROLES:
        autorise, refus = False, ServiceError(403, "Rôle non autorisé à consulter les images.")
    elif role == "SAGE_FEMME" and (not demandeur_id or demandeur_id != capture["sage_femme_id"]):
        autorise, refus = False, ServiceError(403, "Une sage-femme ne peut consulter que les images qu'elle a capturées.")
    else:
        autorise, refus = True, None
    with database.connect() as db:
        db.execute("INSERT INTO acces_images(capture_id, role, demandeur_id, autorise, date) VALUES (?, ?, ?, ?, ?)",
                   (capture_id, role[:40], (demandeur_id or "")[:160], int(autorise), now_iso()))
    if refus:
        raise refus
    chemin = Path(capture["storage_path"])
    if not chemin.is_file():
        raise ServiceError(404, "Original image is missing from private storage.")
    return chemin, "image/png" if chemin.suffix == ".png" else "image/jpeg"


def etat_capture(capture_id: str) -> dict[str, Any]:
    """Pour GET /captures/{id}/etat : état, progression (0 à 1) et durée estimée."""
    capture = _get_capture(capture_id)
    if not capture:
        raise ServiceError(404, "Capture not found.")
    etat = capture["etat_traitement"]
    ecoule = None
    progression = 0.0
    if capture["debut_traitement"]:
        fin = datetime.fromisoformat(capture["fin_traitement"]) if capture["fin_traitement"] else datetime.now(timezone.utc)
        ecoule = round((fin - datetime.fromisoformat(capture["debut_traitement"])).total_seconds(), 1)
    if etat == "EN_ATTENTE_IA":
        # Estimation : jamais 100 % tant que le traitement n'est pas fini.
        progression = round(min(0.95, (ecoule or 0) / max(capture["duree_estimee_s"] or DUREE_INCONNUE_S, 1)), 2)
    elif etat in FINAUX_PAR_GRAVITE:
        progression = 1.0
    return {
        "capture_id": capture_id,
        "dossier_id": capture["record_id"],
        "etat": etat,
        "extraction_status": etat,  # temporaire : ancien nom attendu par l'interface
        "termine": etat in FINAUX_PAR_GRAVITE,
        "progression": progression,
        "duree_estimee_s": capture["duree_estimee_s"],
        "ecoule_s": ecoule,
        "type_page": capture["type_page"],
        "detail": capture["detail_traitement"],
        "suivi": f"/captures/{capture_id}/etat",
        "dossier": get_record(capture["record_id"]),  # temporaire : l'interface lit encore le dossier ici
    }


def reprendre_interrompus() -> int:
    """Au démarrage : une capture restée EN_ATTENTE_IA a été interrompue par un arrêt du serveur."""
    with database.connect() as db:
        ids = [row["id"] for row in db.execute("SELECT id FROM captures WHERE etat_traitement = 'EN_ATTENTE_IA'")]
    for capture_id in ids:
        _terminer(capture_id, "ECHEC_TRAITEMENT", "Traitement interrompu par un redémarrage du serveur : relancer.", None, "systeme")
    return len(ids)


def _extraire_et_enregistrer(capture: Any, actor: str) -> tuple[str, str | None, str | None]:
    """Appelle extract_page(), filtre et valide, puis range la page dans le dossier.

    Renvoie (état de la capture, détail, type de page). Les exceptions de extract_page()
    (dont EchecTraitement) remontent à executer_traitement.
    """
    # Import paresseux : l'API démarre même si les dépendances d'extraction manquent.
    from extraction.pipeline import extract_page

    extracted = extract_page(str(Path(capture["storage_path"])))
    if not isinstance(extracted, dict) or extracted.get("type_page") not in ALLOWED_PAGE_TYPES or not isinstance(extracted.get("champs"), list):
        return "REVISION_MANUELLE_REQUISE", "Résultat d'extraction incompatible avec shared/CONTRAT.md : saisie manuelle.", None

    clean_fields = []
    for field in extracted["champs"]:
        if not isinstance(field, dict) or not isinstance(field.get("champ"), str):
            continue
        # Clés interdites : rejetées plus bas par valider_page (règle unique de shared/valider.py).
        if _looks_private(field.get("valeur")):
            continue
        clean = {key: field.get(key) for key in ("champ", "valeur", "statut", "confiance")}
        clean["page_source"] = field.get("page_source", capture["page_no"])
        confidence = clean.get("confiance")
        if isinstance(confidence, (int, float)) and confidence < CONFIDENCE_THRESHOLD and clean.get("statut") == "CONNU":
            clean["statut"] = "A_REVISER"
        clean["source"] = "ai"
        errors, _ = valider_page({"type_page": extracted["type_page"], "champs": [clean]})
        if not errors:
            clean_fields.append(clean)

    if not clean_fields:
        return "REVISION_MANUELLE_REQUISE", "Aucun champ sûr et valide n'a été extrait : saisie manuelle.", extracted["type_page"]

    page = {
        "page_no": capture["page_no"],
        "type_page": extracted["type_page"],
        "image_id": capture["image_id"],
        "image_hash": f"sha256:{capture['image_hash']}",
        "date_capture": capture["created_at"],
        "champs": clean_fields,
    }
    errors, _ = valider_page(page)
    if errors:
        return "REVISION_MANUELLE_REQUISE", "La page extraite n'a pas passé shared/valider.py et n'a pas été enregistrée.", extracted["type_page"]

    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (capture["record_id"],)).fetchone())
        previous_page = next((item for item in record["pages"] if item["page_no"] == page["page_no"]), None)
        if previous_page and previous_page.get("image_hash") != page["image_hash"]:
            return ("REVISION_MANUELLE_REQUISE", "Nouvelle photo d'une page déjà capturée : choisir s'il faut remplacer la page existante.",
                    extracted["type_page"])

        if previous_page:
            manual_keys = {item["champ"] for item in previous_page["champs"] if item.get("source") == "manual"}
            ai_by_key = {item["champ"]: item for item in clean_fields}
            previous_page["champs"] = [ai_by_key.get(item["champ"], item) if item["champ"] not in manual_keys else item for item in previous_page["champs"]]
        else:
            record["pages"].append(page)

        number_field = next((field for field in clean_fields if field["champ"] == "identification.numero_fiche" and field["statut"] == "CONNU"), None)
        # Le N° du registre vient de sa première page d'identification : une page portant un autre N° (autre
        # patiente ?) ne l'écrase pas ; l'interface le signale et la sage-femme décide.
        if number_field and not record.get("numero_fiche"):
            record["numero_fiche"] = number_field["valeur"]
        _save_record(db, record)
    result_state = "A_REVISER" if any(field["statut"] in ("A_REVISER", "ILLISIBLE", "INCONNU") for field in clean_fields) else "TRAITE_IA"
    return result_state, None, extracted["type_page"]


def validation_result(record: dict[str, Any]) -> dict[str, Any]:
    """Ce qui empêche la validation, sous une forme que l'interface peut expliquer.

    blocages : liste de {code, ...} parmi
      - champs_obligatoires : champs requis absents, vides ou pas encore sûrs ({champs: [...]}) ;
      - questions           : champs douteux pas encore confirmés ni corrigés ({champs: [...], n}) ;
      - donnees_invalides   : le dossier ne passe pas shared/valider.py ({erreurs: [...]}).
    """
    latest: dict[str, dict[str, Any]] = {}
    for page in record.get("pages", []):
        for field in page.get("champs", []):
            latest[field["champ"]] = field
    missing = []
    for key in REQUIRED_FIELDS:
        field = latest.get(key)
        sur = field and field.get("valeur") is not None and field.get("statut") == "CONNU" and (
            field.get("confiance", 0) >= CONFIDENCE_THRESHOLD or field.get("confirme") or field.get("source") == "manual")
        if not sur:
            missing.append(key)
    a_verifier = [field["champ"] for page in record.get("pages", []) for field in page.get("champs", []) if _douteux(field)]
    a_verifier = [cle for cle in dict.fromkeys(a_verifier) if cle not in missing]
    errors, _ = valider_dossier(record)
    blocages = []
    if missing:
        blocages.append({"code": "champs_obligatoires", "champs": missing})
    if a_verifier:
        blocages.append({"code": "questions", "champs": a_verifier, "n": len(a_verifier)})
    if errors:
        blocages.append({"code": "donnees_invalides", "erreurs": errors})
    return {
        "can_validate": not blocages,
        "missing_fields": missing,
        "champs_a_verifier": a_verifier,
        "blocages": blocages,
        "reason": None if not blocages else "Required fields are missing, doubtful fields are unanswered, or data is invalid.",
        "validation_errors": errors,
    }


def patch_field(record_id: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    field_key = payload.get("champ")
    status = payload.get("statut", "CONNU")
    value = payload.get("valeur")
    confidence = payload.get("confiance", 1.0)
    if not isinstance(field_key, str) or not definition(field_key):
        raise ServiceError(422, "champ must be a key defined in shared/schema_champs.json.")
    # Clés interdites : absentes du schéma (refusées ci-dessus) et rejetées par valider_page ci-dessous.
    if _looks_private(value):
        raise ServiceError(422, "Direct patient identifiers cannot be stored.")
    if status not in ALLOWED_FIELD_STATUSES:
        raise ServiceError(422, "Invalid field status.")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ServiceError(422, "confiance must be between 0 and 1.")
    if status == "CONNU" and confidence < CONFIDENCE_THRESHOLD:
        status = "A_REVISER"
    if status == "CONNU" and value is not None and definition(field_key).get("type") == "tension":
        # The common validator expects a normalized SYS/DIA representation.
        value = str(value).replace(" ", "")

    record = get_record(record_id)
    if not record:
        raise ServiceError(404, "Record not found.")
    page_no = payload.get("page_no")
    page_type = payload.get("type_page")
    if page_no is None:
        page_no = next((page["page_no"] for page in record["pages"] if any(item["champ"] == field_key for item in page["champs"])), None)
    page = next((item for item in record["pages"] if item["page_no"] == page_no), None)
    if page is None:
        if page_no is None or page_type not in ALLOWED_PAGE_TYPES:
            raise ServiceError(422, "For a new page, provide a valid page_no and type_page.")
        definition_key = field_key
        belongs_to_page = definition_key.startswith({
            "IDENTIFICATION": "identification.", "ANTECEDENTS": ("profil.", "antecedents.", "obstetrique.", "vaccination.", "depistage."),
            "GROSSESSE_ACTUELLE": ("grossesse.",), "ACCOUCHEMENT": ("accouchement.", "nouveau_ne."),
            "PP_PRECOCE_MERE": ("pp_precoce.mere.",), "PP_PRECOCE_NOUVEAU_NE": ("pp_precoce.nouveau_ne.",),
            "PP_TARDIF_MERE": ("pp_tardif.mere.",), "PP_TARDIF_NOUVEAU_NE": ("pp_tardif.nouveau_ne.",),
        }[page_type])
        if not belongs_to_page:
            raise ServiceError(422, "champ does not belong to the supplied type_page.")
        capture = None
        with database.connect() as db:
            capture = db.execute("SELECT * FROM captures WHERE record_id = ? AND page_no = ? ORDER BY created_at DESC LIMIT 1", (record_id, page_no)).fetchone()
        page = {
            "page_no": page_no,
            "type_page": page_type,
            "image_id": capture["image_id"] if capture else None,
            "image_hash": f"sha256:{capture['image_hash']}" if capture else None,
            "date_capture": capture["created_at"] if capture else now_iso(),
            "champs": [],
        }
        record["pages"].append(page)
    elif page_type and page["type_page"] != page_type:
        raise ServiceError(409, "type_page does not match the existing page.")

    definition_info = definition(field_key)
    candidate = {"champ": field_key, "valeur": value, "statut": status, "confiance": float(confidence), "page_source": page_no, "source": "manual", "modifie_par": actor_id, "date_modification": now_iso()}
    errors, _ = valider_page({"type_page": page["type_page"], "champs": [candidate]})
    if errors:
        # Détail lisible pour le diagnostic (ex. « tension : valeur '11/7' ne respecte pas le type tension ») ;
        # l'interface affiche son propre message simple selon le type du champ.
        raise ServiceError(422, f"Invalid field value: {errors[0]}")

    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        existing_page = next((item for item in record["pages"] if item["page_no"] == page_no), None)
        if existing_page is None:
            record["pages"].append(page)
            existing_page = page
        old = next((item for item in existing_page["champs"] if item["champ"] == field_key), None)
        old_value = _dump(old) if old else None
        if old:
            old.update(candidate)
        else:
            existing_page["champs"].append(candidate)
        db.execute(
            "INSERT INTO field_history(record_id, field_key, old_value, new_value, actor_id, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (record_id, field_key, old_value, _dump(candidate), actor_id, candidate["date_modification"]),
        )
        if field_key == "identification.numero_fiche" and status == "CONNU":
            record["numero_fiche"] = value
        if record["etat"] == "ECHEC_TRAITEMENT":
            # Repli : l'extraction a échoué, la sage-femme saisit les champs à la main.
            _transition(db, record, "REVISION_MANUELLE_REQUISE", actor_id, "Saisie manuelle après échec du traitement")
        errors, _ = valider_dossier(record)
        if errors:
            raise ServiceError(422, "Updated record failed shared validation.")
        _save_record(db, record)
    return record


def confirmer_champs(record_id: str, cles: list[str] | None, actor_id: str) -> dict[str, Any]:
    """« Tout confirmer » : confirme en un seul geste les champs FIABLES (CONNU, confiance >= seuil).

    Les champs douteux (A_REVISER, ILLISIBLE, sous le seuil…) ne sont jamais confirmés ainsi :
    ils passent par une question une à une. Chaque confirmation est historisée.
    """
    if cles is not None and (not isinstance(cles, list) or not all(isinstance(c, str) for c in cles)):
        raise ServiceError(422, "champs must be a list of field keys.")
    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        if not record:
            raise ServiceError(404, "Record not found.")
        date_confirmation = now_iso()
        confirmes, ignores = [], []
        for page in record["pages"]:
            for champ in page["champs"]:
                if cles is not None and champ["champ"] not in cles:
                    continue
                fiable = champ["statut"] == "CONNU" and champ.get("confiance", 0) >= CONFIDENCE_THRESHOLD
                if not fiable:
                    ignores.append(champ["champ"])
                    continue
                if champ.get("confirme"):
                    continue
                champ.update(confirme=True, confirme_par=actor_id, date_confirmation=date_confirmation)
                confirmes.append(champ["champ"])
                db.execute(
                    "INSERT INTO field_history(record_id, field_key, old_value, new_value, actor_id, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (record_id, champ["champ"], None, _dump({"confirme": True, "valeur": champ["valeur"]}), actor_id, date_confirmation),
                )
        _save_record(db, record)
    return {"dossier": record, "confirmes": len(confirmes), "ignores_non_fiables": sorted(set(ignores))}


def validate_record(record_id: str, actor_id: str) -> dict[str, Any]:
    with database.connect() as db:
        row = db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone()
        record = _read_record_row(row)
        if not record:
            raise ServiceError(404, "Record not found.")
        result = validation_result(record)
        if not result["can_validate"]:
            return {"dossier": record, **result}
        _transition(db, record, "VALIDE", actor_id, "Dossier complet confirmé par la sage-femme")
        record["valide_le"] = now_iso()
        _save_record(db, record)
    return {"dossier": record, "can_validate": True, "missing_fields": [], "champs_a_verifier": [], "blocages": [],
            "reason": None, "validation_errors": []}


# Code de liaison : court, aléatoire, recopié à la main sur le registre papier.
# Alphabet sans 0/O ni 1/I (confusions à la lecture et à la recopie).
ALPHABET_CODE = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ETATS_VALIDES = ("VALIDE", "PATIENTE_LIEE", "ENREGISTRE", "SYNCHRONISE", "ECHEC_SYNCHRONISATION")


def generer_code(db: Any) -> str:
    while True:
        brut = "".join(secrets.choice(ALPHABET_CODE) for _ in range(6))
        code = f"{brut[:3]}-{brut[3:]}"
        if not db.execute("SELECT 1 FROM patients WHERE code = ?", (code,)).fetchone():
            return code


def normaliser_code(code: Any) -> str | None:
    """« abc 234 », « ABC-234 » -> « ABC-234 » ; None si la saisie ne peut pas être un code."""
    if not isinstance(code, str):
        return None
    brut = re.sub(r"[^A-Za-z0-9]", "", code).upper()
    if len(brut) != 6 or any(c not in ALPHABET_CODE for c in brut):
        return None
    return f"{brut[:3]}-{brut[3:]}"


def _visites(db: Any, patient_id: str) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT payload, created_at FROM records WHERE json_extract(payload, '$.patiente_id') = ? ORDER BY created_at",
        (patient_id,),
    ).fetchall()
    return [_resume_dossier(json.loads(row["payload"]), row["created_at"]) for row in rows]


def _candidat(db: Any, patient: Any, raison: str) -> dict[str, Any]:
    visites = _visites(db, patient["id"])
    return {
        "patiente_id": patient["id"],
        "code": patient["code"],
        "numero_fiche": patient["record_number"],
        "nb_visites": len(visites),
        "derniere_visite": max((v["date"] for v in visites), default=patient["created_at"]),
        "raison": raison,
    }


def match_patients(numero_fiche: str | None = None, code: str | None = None) -> list[dict[str, Any]]:
    """Candidats proposés à la sage-femme (même code et/ou même N° de fiche). Jamais de liaison automatique."""
    code = normaliser_code(code) if code else None
    candidats: dict[str, dict[str, Any]] = {}
    with database.connect() as db:
        if code:
            for row in db.execute("SELECT * FROM patients WHERE code = ?", (code,)).fetchall():
                candidats[row["id"]] = _candidat(db, row, "code")
        if numero_fiche:
            for row in db.execute("SELECT * FROM patients WHERE record_number = ? ORDER BY created_at", (numero_fiche,)).fetchall():
                if row["id"] in candidats:
                    candidats[row["id"]]["raison"] = "code_et_numero"
                else:
                    candidats[row["id"]] = _candidat(db, row, "numero_fiche")
    return list(candidats.values())


def link_patient(record_id: str, choice: dict[str, Any], actor_id: str) -> dict[str, Any]:
    record = get_record(record_id)
    if not record:
        raise ServiceError(404, "Record not found.")
    if record["etat"] not in ETATS_VALIDES:
        raise ServiceError(409, "Validate the record before linking a patient.")
    patient_id = choice.get("patiente_id")
    decision = choice.get("choix")
    code = None
    if patient_id:
        with database.connect() as db:
            patient = db.execute("SELECT id, record_number, code FROM patients WHERE id = ?", (patient_id,)).fetchone()
        if not patient:
            raise ServiceError(404, "Patient record not found.")
        meme_code = patient["code"] is not None and normaliser_code(choice.get("code")) == patient["code"]
        if record.get("numero_fiche") and patient["record_number"] != record["numero_fiche"] and not meme_code:
            raise ServiceError(409, "Selected patient is not a matching candidate for this record number or code.")
        code = patient["code"]
    elif decision == "nouvelle":
        if not record.get("numero_fiche"):
            raise ServiceError(422, "The record number is required before creating a patient link.")
        patient_id = str(uuid.uuid4())  # identifiant interne aléatoire, jamais dérivé de données personnelles
        code_choisi = choice.get("code")
        if code_choisi is not None and normaliser_code(code_choisi) is None:
            raise ServiceError(422, "The link code must have 6 characters without 0, O, 1 or I.")
        with database.connect() as db:
            code = normaliser_code(code_choisi) if code_choisi else generer_code(db)
            if db.execute("SELECT 1 FROM patients WHERE code = ?", (code,)).fetchone():
                raise ServiceError(409, "This link code is already used by another patient.")
            db.execute("INSERT INTO patients(id, record_number, created_at, code) VALUES (?, ?, ?, ?)",
                       (patient_id, record["numero_fiche"], now_iso(), code))
    elif decision == "inconnu":
        return {"dossier": record, "decision": "inconnu", "patient_created": False, "code": None}
    else:
        raise ServiceError(422, "Provide patiente_id, choix='nouvelle', or choix='inconnu'.")

    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        record["patiente_id"] = patient_id
        record["patiente_code"] = code
        if record["etat"] == "VALIDE":
            _transition(db, record, "PATIENTE_LIEE", actor_id, "Correspondance explicitement choisie par la sage-femme")
        _save_record(db, record)
    return {"dossier": record, "decision": "lier", "patient_created": decision == "nouvelle", "code": code}


def _douteux(champ: dict[str, Any]) -> bool:
    if champ.get("confirme") or champ.get("source") == "manual":
        return False
    if champ.get("statut") in ("A_REVISER", "ILLISIBLE"):
        return True
    return champ.get("statut") == "CONNU" and (champ.get("confiance") or 0) < CONFIDENCE_THRESHOLD


def _resume_dossier(record: dict[str, Any], created_at: str) -> dict[str, Any]:
    pages = sorted(record.get("pages", []), key=lambda p: p["page_no"])
    return {
        "dossier_id": record["dossier_id"],
        "etat": record["etat"],
        "numero_fiche": record.get("numero_fiche"),
        "patiente_id": record.get("patiente_id"),
        "patiente_code": record.get("patiente_code"),
        "sage_femme_id": record.get("sage_femme_id"),
        "date": created_at,
        "valide_le": record.get("valide_le"),
        "nb_pages": len(pages),
        "types_page": [page["type_page"] for page in pages],
        "a_verifier": sum(_douteux(c) for page in pages for c in page.get("champs", [])),
    }


def _filtre_role(role: str | None, demandeur_id: str | None) -> tuple[str, tuple]:
    """SUPERVISEUR : tous les dossiers ; SAGE_FEMME : seulement les siens."""
    if role == "SUPERVISEUR":
        return "", ()
    return "WHERE owner_id = ?", (demandeur_id or "",)


def lister_dossiers(role: str | None, demandeur_id: str | None) -> list[dict[str, Any]]:
    clause, params = _filtre_role(role, demandeur_id)
    with database.connect() as db:
        rows = db.execute(f"SELECT payload, created_at FROM records {clause} ORDER BY created_at DESC", params).fetchall()
    return [_resume_dossier(json.loads(row["payload"]), row["created_at"]) for row in rows]


def lister_patientes(role: str | None, demandeur_id: str | None) -> list[dict[str, Any]]:
    """Patientes (par code de liaison) et historique des visites visibles pour ce rôle."""
    visibles = {d["dossier_id"] for d in lister_dossiers(role, demandeur_id)}
    with database.connect() as db:
        patients = db.execute("SELECT * FROM patients ORDER BY created_at DESC").fetchall()
        resultat = []
        for patient in patients:
            visites = [v for v in _visites(db, patient["id"]) if v["dossier_id"] in visibles]
            if not visites:
                continue
            resultat.append({
                "patiente_id": patient["id"],
                "code": patient["code"],
                "numero_fiche": patient["record_number"],
                "creee_le": patient["created_at"],
                "visites": visites,
            })
    return resultat


def renumeriser(record_id: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
    """Nouvelle photo d'une page déjà saisie : la sage-femme choisit, champ par champ, ce qui remplace l'existant.

    Les champs choisis sont copiés de la nouvelle page vers l'ancienne (historisés) ; la nouvelle page est
    retirée du dossier, sa capture reste conservée pour la traçabilité.
    """
    ancienne_no, nouvelle_no, cles = payload.get("ancienne_page"), payload.get("nouvelle_page"), payload.get("champs", [])
    if not isinstance(ancienne_no, int) or not isinstance(nouvelle_no, int) or ancienne_no == nouvelle_no:
        raise ServiceError(422, "ancienne_page and nouvelle_page must be two different page numbers.")
    if not isinstance(cles, list) or not all(isinstance(c, str) for c in cles):
        raise ServiceError(422, "champs must be a list of field keys.")
    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        if not record:
            raise ServiceError(404, "Record not found.")
        ancienne = next((p for p in record["pages"] if p["page_no"] == ancienne_no), None)
        nouvelle = next((p for p in record["pages"] if p["page_no"] == nouvelle_no), None)
        if ancienne is None or nouvelle is None:
            raise ServiceError(404, "Page not found in this record.")
        if ancienne["type_page"] != nouvelle["type_page"]:
            raise ServiceError(409, "The two pages are not of the same type.")
        nouveaux = {c["champ"]: c for c in nouvelle["champs"]}
        inconnus = [c for c in cles if c not in nouveaux]
        if inconnus:
            raise ServiceError(422, f"Fields absent from the new page: {', '.join(inconnus[:5])}")
        date = now_iso()
        for cle in cles:
            candidat = {**nouveaux[cle], "page_source": ancienne_no, "source": "renumerisation",
                        "modifie_par": actor_id, "date_modification": date}
            candidat.pop("confirme", None)
            ancien = next((c for c in ancienne["champs"] if c["champ"] == cle), None)
            db.execute(
                "INSERT INTO field_history(record_id, field_key, old_value, new_value, actor_id, changed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (record_id, cle, _dump(ancien) if ancien else None, _dump(candidat), actor_id, date),
            )
            if ancien:
                ancien.clear()
                ancien.update(candidat)
            else:
                ancienne["champs"].append(candidat)
            if cle == "identification.numero_fiche" and candidat["statut"] == "CONNU":
                record["numero_fiche"] = candidat["valeur"]
        record["pages"] = [p for p in record["pages"] if p["page_no"] != nouvelle_no]
        record.setdefault("renumerisations", []).append(
            {"ancienne_page": ancienne_no, "nouvelle_page": nouvelle_no, "image_id": nouvelle.get("image_id"),
             "champs": cles, "date": date, "acteur": actor_id})
        if cles and record["etat"] in ETATS_VALIDES:
            _transition(db, record, "A_REVISER", actor_id, "Page renumérisée : le dossier doit être revalidé")
        errors, _ = valider_dossier(record)
        if errors:
            raise ServiceError(422, "Updated record failed shared validation.")
        _save_record(db, record)
    return {"dossier": record, "remplaces": len(cles)}


def sync_records(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("captures", [])
    if not isinstance(items, list):
        raise ServiceError(422, "captures must be an array.")
    results = []
    for item in items:
        if not isinstance(item, dict):
            results.append({"ok": False, "detail": "Each capture must be an object."})
            continue
        try:
            capture_id = item.get("capture_id")
            if capture_id:
                existing = _get_capture(str(capture_id))
                if existing:
                    record = get_record(existing["record_id"])
                    results.append({"ok": True, "capture_id": existing["id"], "dossier_id": record["dossier_id"], "idempotent_replay": True, "etat": record["etat"]})
                    continue
            import base64

            encoded = item.get("image_base64")
            if not isinstance(encoded, str):
                raise ServiceError(422, "image_base64 is required for a new offline capture.")
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError):
                raise ServiceError(422, "image_base64 is invalid.") from None
            created = create_capture(
                image_bytes=image_bytes,
                content_type=item.get("content_type"),
                session_id=str(item.get("session_id", "")),
                page_no=int(item.get("page_no", 0)),
                actor_id=str(item.get("sage_femme_id", "")),
                idempotency_key=str(capture_id or item.get("idempotency_key") or "") or None,
            )
            if created.get("duplicate_suspected"):
                results.append({"ok": True, "duplicate_suspected": True, "duplicate_report_id": created["duplicate_report_id"], "dossier_id": created["dossier"]["dossier_id"], "etat": "DOUBLON_SUSPECTE"})
                continue
            result = process_capture(created["capture_id"])
            results.append({"ok": True, "capture_id": created["capture_id"], "dossier_id": result["dossier"]["dossier_id"], "idempotent_replay": created["idempotent_replay"], "etat": result["dossier"]["etat"], "detail": result["detail"]})
        except ServiceError as exc:
            results.append({"ok": False, "detail": exc.detail})
        except (ValueError, TypeError):
            results.append({"ok": False, "detail": "Capture metadata is invalid."})
    return {"results": results, "accepted": sum(item["ok"] for item in results), "failed": sum(not item["ok"] for item in results)}


def sync_status() -> dict[str, Any]:
    with database.connect() as db:
        rows = db.execute("SELECT state, COUNT(*) AS count FROM records GROUP BY state").fetchall()
    return {"online": True, "records_by_state": {row["state"]: row["count"] for row in rows}}


def record_history(record_id: str) -> dict[str, Any]:
    with database.connect() as db:
        transitions = db.execute("SELECT from_state, to_state, changed_at, actor_id, reason FROM transitions WHERE record_id = ? ORDER BY id", (record_id,)).fetchall()
        fields = db.execute("SELECT field_key, old_value, new_value, actor_id, changed_at FROM field_history WHERE record_id = ? ORDER BY id", (record_id,)).fetchall()
    return {
        "transitions": [dict(row) for row in transitions],
        "field_changes": [{**dict(row), "old_value": json.loads(row["old_value"]) if row["old_value"] else None, "new_value": json.loads(row["new_value"])} for row in fields],
    }


def resolve_duplicate(report_id: str, decision: str) -> dict[str, Any]:
    if decision not in ("garder_existant", "ignorer"):
        raise ServiceError(422, "Supported duplicate decisions are garder_existant and ignorer.")
    with database.connect() as db:
        report = db.execute("SELECT * FROM duplicate_reports WHERE id = ?", (report_id,)).fetchone()
        if not report:
            raise ServiceError(404, "Duplicate report not found.")
        db.execute("UPDATE duplicate_reports SET decision = ? WHERE id = ?", (decision, report_id))
        capture = db.execute("SELECT record_id FROM captures WHERE id = ?", (report["existing_capture_id"],)).fetchone()
    return {"duplicate_report_id": report_id, "decision": decision, "dossier": get_record(capture["record_id"])}


# ---------- Tableau de bord : agrégats anonymisés sur les dossiers validés ----------
SEUIL_ANONYMAT = 5
MESSAGE_ANONYMAT = "Effectif insuffisant pour préserver l'anonymat"
VISITE_TENSION = re.compile(r"^grossesse\.visites\[\d+\]\.tension$")
TENSIONS = ("pp_precoce.mere.tension", "pp_tardif.mere.tension")

# Intervalles descriptifs [borne basse incluse, borne haute exclue) ; aucune interprétation médicale.
INDICATEURS = [
    {"id": "tension_systolique", "unite": "mmHg", "bornes": [90, 120, 140, 160]},
    {"id": "tension_diastolique", "unite": "mmHg", "bornes": [60, 80, 90, 110]},
    {"id": "temperature_mere", "unite": "°C", "bornes": [36.0, 37.5, 38.0],
     "cles": ("pp_precoce.mere.temperature_c", "pp_tardif.mere.temperature_c")},
    {"id": "temperature_nouveau_ne", "unite": "°C", "bornes": [36.5, 37.5],
     "cles": ("pp_precoce.nouveau_ne.temperature_c", "pp_tardif.nouveau_ne.temperature_c")},
]
SEROLOGIES = {"vih": "grossesse.tests.vih", "syphilis": "grossesse.tests.syphilis", "hepatite_c": "grossesse.tests.hepatite_c"}


def _intervalles(bornes: list[float]) -> list[tuple[float | None, float | None]]:
    limites = [None, *bornes, None]
    return list(zip(limites[:-1], limites[1:]))


def _case(effectif: int, **champs: Any) -> dict[str, Any]:
    """Case du tableau : l'effectif n'est publié que s'il atteint le seuil d'anonymat."""
    masque = effectif < SEUIL_ANONYMAT
    return {**champs, "effectif": None if masque else effectif, "masque": masque,
            "message": MESSAGE_ANONYMAT if masque else None}


def _valeurs_connues(record: dict[str, Any]) -> dict[str, list[Any]]:
    valeurs: dict[str, list[Any]] = {}
    for page in record.get("pages", []):
        for champ in page.get("champs", []):
            if champ.get("statut") == "CONNU" and champ.get("valeur") is not None:
                valeurs.setdefault(champ["champ"], []).append(champ["valeur"])
    return valeurs


def _tension(valeur: Any) -> tuple[float, float] | None:
    m = re.fullmatch(r"\s*(\d{2,3})\s*/\s*(\d{2,3})\s*", str(valeur))
    return (float(m.group(1)), float(m.group(2))) if m else None


# Données de démonstration : CSV synthétique fourni par les organisateurs (200 lignes, lecture seule).
CSV_DEMONSTRATION = PROJECT_ROOT / "data" / "maternal_registry_synthetic.csv"
COLONNES_DEMO = {"vih": "hiv test result", "syphilis": "syphilis test result", "hepatite_c": "hepatitis c test result"}


def _nombres(valeurs: list[Any]) -> list[float]:
    nombres = []
    for v in valeurs:
        try:
            nombres.append(float(str(v).replace(",", ".")))
        except ValueError:
            continue
    return nombres


def _profils_dossiers() -> list[dict[str, Any]]:
    """Un profil par dossier validé : tensions, températures et sérologies lues avec certitude."""
    places = ",".join("?" for _ in ETATS_VALIDES)
    with database.connect() as db:
        rows = db.execute(f"SELECT payload FROM records WHERE state IN ({places})", ETATS_VALIDES).fetchall()
    profils = []
    for row in rows:
        valeurs = _valeurs_connues(json.loads(row["payload"]))
        tensions = [t for cle, vs in valeurs.items() if VISITE_TENSION.match(cle) or cle in TENSIONS for t in map(_tension, vs) if t]
        profil = {"tension_systolique": [t[0] for t in tensions], "tension_diastolique": [t[1] for t in tensions]}
        for ind in INDICATEURS:
            if "cles" in ind:
                profil[ind["id"]] = _nombres([v for cle in ind["cles"] for v in valeurs.get(cle, [])])
        for nom, cle in SEROLOGIES.items():
            profil[nom] = next((v for v in valeurs.get(cle, []) if v in ("POSITIF", "NEGATIF")), None)
        profils.append(profil)
    return profils


def _profils_demonstration() -> list[dict[str, Any]]:
    """Un profil par ligne du CSV synthétique (pas de température dans ce fichier)."""
    import csv

    if not CSV_DEMONSTRATION.is_file():
        raise ServiceError(404, "Demonstration data (data/maternal_registry_synthetic.csv) is not available.")
    with CSV_DEMONSTRATION.open(encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))
    resultat = {"0": "NEGATIF", "1": "POSITIF"}
    return [{
        "tension_systolique": _nombres([l.get("mean systolic bp (mmhg)", "")]),
        "tension_diastolique": _nombres([l.get("mean diastolic bp (mmhg)", "")]),
        **{nom: resultat.get((l.get(colonne) or "").strip()) for nom, colonne in COLONNES_DEMO.items()},
    } for l in lignes]


def _part(numerateur: int, denominateur: int) -> float | None:
    """Pourcentage publié seulement si numérateur et dénominateur atteignent le seuil d'anonymat."""
    if numerateur < SEUIL_ANONYMAT or denominateur < SEUIL_ANONYMAT:
        return None
    return round(100 * numerateur / denominateur, 1)


def tableau_de_bord(source: str = "dossiers") -> dict[str, Any]:
    """Agrégats anonymisés. source = « dossiers » (dossiers validés : VALIDE et au-delà) ou « demo »
    (CSV synthétique des organisateurs, signalé comme tel).

    Chaque case compte des dossiers distincts (un dossier compte une fois par case, même avec plusieurs
    mesures) ; toute case de moins de SEUIL_ANONYMAT dossiers est masquée, total compris, et aucun
    pourcentage n'est calculé à partir d'une case masquée.
    """
    if source not in ("dossiers", "demo"):
        raise ServiceError(422, "source must be 'dossiers' or 'demo'.")
    profils = _profils_dossiers() if source == "dossiers" else _profils_demonstration()
    total = len(profils)

    indicateurs = []
    for ind in INDICATEURS:
        disponible = source == "dossiers" or ind["id"].startswith("tension")
        par_dossier = [pr.get(ind["id"], []) for pr in profils]
        cases = []
        for bas, haut in _intervalles(ind["bornes"]):
            effectif = sum(any((bas is None or x >= bas) and (haut is None or x < haut) for x in xs) for xs in par_dossier)
            cases.append(_case(effectif, min=bas, max=haut))
        mesures = sum(bool(xs) for xs in par_dossier)
        indicateurs.append({"id": ind["id"], "type": "intervalles", "unite": ind["unite"], "disponible": disponible,
                            "dossiers_mesures": _case(mesures), "cases": cases,
                            "masquage": any(c["masque"] for c in cases)})
    depistage = []
    for nom in SEROLOGIES:
        comptes = {"POSITIF": 0, "NEGATIF": 0, "NON_RENSEIGNE": 0}
        for pr in profils:
            comptes[pr.get(nom) or "NON_RENSEIGNE"] += 1
        depistees = comptes["POSITIF"] + comptes["NEGATIF"]
        cases = [_case(n, categorie=categorie) for categorie, n in comptes.items()]
        indicateurs.append({"id": nom, "type": "categories", "unite": None, "disponible": True,
                            "dossiers_mesures": _case(depistees), "cases": cases, "masquage": any(c["masque"] for c in cases)})
        depistage.append({"id": nom, "depistees": _case(depistees), "part_depistees": _part(depistees, total),
                          "positifs": _case(comptes["POSITIF"]), "part_positifs": _part(comptes["POSITIF"], depistees)})
    return {"source": source, "synthetique": source == "demo", "seuil_anonymat": SEUIL_ANONYMAT,
            "message_masque": MESSAGE_ANONYMAT, "etats_retenus": list(ETATS_VALIDES) if source == "dossiers" else None,
            "dossiers": _case(total), "depistage": depistage, "indicateurs": indicateurs}


# ---------- Enregistrement et synchronisation avec le système de santé (simulé) ----------
# ENREGISTRE : dossier validé (relié ou non), enregistré dans le registre numérique du centre.
# SYNCHRONISE : copie anonymisée transmise au système de santé central. Ici, le système central est simulé
# par la table systeme_central ; une panne simulée fait passer le dossier en ECHEC_SYNCHRONISATION,
# et une nouvelle tentative le synchronise. L'envoi est idempotent (un dossier = une ligne).
A_SYNCHRONISER = ("ENREGISTRE", "ECHEC_SYNCHRONISATION")


def enregistrer(record_id: str, actor_id: str) -> dict[str, Any]:
    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        if not record:
            raise ServiceError(404, "Record not found.")
        if record["etat"] in ("ENREGISTRE", "SYNCHRONISE", "ECHEC_SYNCHRONISATION"):
            return {"dossier": record, "deja_enregistre": True}
        if record["etat"] not in ("VALIDE", "PATIENTE_LIEE"):
            raise ServiceError(409, "Validate the record before saving it.")
        _transition(db, record, "ENREGISTRE", actor_id, "Dossier enregistré dans le registre numérique du centre")
        record["enregistre_le"] = now_iso()
        _save_record(db, record)
    return {"dossier": record, "deja_enregistre": False}


def _copie_anonymisee(record: dict[str, Any]) -> dict[str, Any]:
    """Ce qui part vers le système central : champs du schéma, code de liaison, dates ; ni image ni identifiant direct."""
    return {
        "dossier_id": record["dossier_id"],
        "patiente_code": record.get("patiente_code"),
        "valide_le": record.get("valide_le"),
        "pages": [{"type_page": page["type_page"], "champs": [{k: c.get(k) for k in ("champ", "valeur", "statut")} for c in page["champs"]]}
                  for page in record.get("pages", [])],
    }


def synchroniser(role: str | None, demandeur_id: str | None, simuler_panne: bool = False) -> dict[str, Any]:
    clause, params = _filtre_role(role, demandeur_id)
    places = ",".join("?" for _ in A_SYNCHRONISER)
    condition = f"{clause} {'AND' if clause else 'WHERE'} state IN ({places})"
    synchronises, echecs = [], []
    with database.connect() as db:
        rows = db.execute(f"SELECT payload FROM records {condition}", (*params, *A_SYNCHRONISER)).fetchall()
        for row in rows:
            record = json.loads(row["payload"])
            acteur = demandeur_id or "systeme"
            if simuler_panne:
                _transition(db, record, "ECHEC_SYNCHRONISATION", acteur, "Système de santé central injoignable (panne simulée) : nouvelle tentative plus tard")
                echecs.append(record["dossier_id"])
            else:
                date = now_iso()
                db.execute("INSERT INTO systeme_central(dossier_id, payload, synchronise_le) VALUES (?, ?, ?) "
                           "ON CONFLICT(dossier_id) DO UPDATE SET payload = excluded.payload, synchronise_le = excluded.synchronise_le",
                           (record["dossier_id"], _dump(_copie_anonymisee(record)), date))
                _transition(db, record, "SYNCHRONISE", acteur, "Copie anonymisée transmise au système de santé")
                record["synchronise_le"] = date
                synchronises.append(record["dossier_id"])
            _save_record(db, record)
    return {"synchronises": synchronises, "echecs": echecs}


# ---------- Page d'une autre patiente : la retirer, ou la placer dans un nouveau registre ----------
def retirer_page(record_id: str, page_no: int, actor_id: str) -> dict[str, Any]:
    """Retire une page du dossier (la capture et l'image restent conservées et tracées)."""
    with database.connect() as db:
        record = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (record_id,)).fetchone())
        if not record:
            raise ServiceError(404, "Record not found.")
        page = next((p for p in record["pages"] if p["page_no"] == page_no), None)
        if page is None:
            raise ServiceError(404, "Page not found in this record.")
        record["pages"] = [p for p in record["pages"] if p["page_no"] != page_no]
        record.setdefault("pages_retirees", []).append(
            {"page_no": page_no, "type_page": page["type_page"], "image_id": page.get("image_id"), "date": now_iso(), "acteur": actor_id})
        _save_record(db, record)
    return {"dossier": record}


def deplacer_capture(capture_id: str, session_id: str, page_no: int, actor_id: str) -> dict[str, Any]:
    """Place une capture déjà lue (et sa page) dans un nouveau registre de la même sage-femme.

    Évite de renvoyer la photo (elle serait signalée comme doublon). Le nouveau dossier reprend le cycle de
    vie de la capture : CAPTURE -> EN_ATTENTE_IA -> TRAITE_IA ou A_REVISER.
    """
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 160:
        raise ServiceError(422, "session_id is required.")
    if not isinstance(page_no, int) or page_no < 1:
        raise ServiceError(422, "page_no must be a positive integer.")
    with database.connect() as db:
        capture = db.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
        if not capture:
            raise ServiceError(404, "Capture not found.")
        if capture["etat_traitement"] not in ("TRAITE_IA", "A_REVISER"):
            raise ServiceError(409, "Only a capture that has been read can be moved.")
        ancien = _read_record_row(db.execute("SELECT payload FROM records WHERE id = ?", (capture["record_id"],)).fetchone())
        if db.execute("SELECT 1 FROM records WHERE owner_id = ? AND session_id = ?", (ancien["sage_femme_id"], session_id)).fetchone():
            raise ServiceError(409, "This session already has a record.")
        page = next((p for p in ancien["pages"] if p["page_no"] == capture["page_no"]), None)
        ancien["pages"] = [p for p in ancien["pages"] if p["page_no"] != capture["page_no"]]
        entree = next((c for c in ancien["captures"] if c["capture_id"] == capture_id), None)
        ancien["captures"] = [c for c in ancien["captures"] if c["capture_id"] != capture_id]
        ancien.setdefault("pages_retirees", []).append(
            {"page_no": capture["page_no"], "deplacee_vers_session": session_id, "date": now_iso(), "acteur": actor_id})
        _save_record(db, ancien)

        nouveau = _new_record(session_id, ancien["sage_femme_id"])
        timestamp = now_iso()
        db.execute(
            "INSERT INTO records(id, owner_id, session_id, state, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nouveau["dossier_id"], ancien["sage_femme_id"], session_id, nouveau["etat"], _dump(nouveau), timestamp, timestamp),
        )
        if page:
            page = {**page, "page_no": page_no, "champs": [{**c, "page_source": page_no} for c in page["champs"]]}
            nouveau["pages"].append(page)
            numero = next((c for c in page["champs"] if c["champ"] == "identification.numero_fiche" and c["statut"] == "CONNU"), None)
            if numero:
                nouveau["numero_fiche"] = numero["valeur"]
        if entree:
            nouveau["captures"].append({**entree, "page_no": page_no})
        raison = f"Page déplacée depuis le registre {ancien['dossier_id']} (autre patiente)"
        _transition(db, nouveau, "EN_ATTENTE_IA", actor_id, raison)
        _transition(db, nouveau, capture["etat_traitement"], actor_id, raison)
        db.execute("UPDATE captures SET record_id = ?, page_no = ? WHERE id = ?", (nouveau["dossier_id"], page_no, capture_id))
        _save_record(db, nouveau)
    return {"dossier": nouveau, "ancien_dossier": ancien}
