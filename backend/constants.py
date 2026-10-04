"""Shared project contract and backend configuration."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.valider import CHAMPS, SCHEMA, STATUTS, definition, valider_dossier, valider_page  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("FIRSTBREATH_DATA_DIR", BACKEND_DIR / "storage"))
IMAGE_DIR = DATA_DIR / "images"
DB_PATH = Path(os.getenv("FIRSTBREATH_DB_PATH", DATA_DIR / "firstbreath.sqlite3"))
MAX_UPLOAD_BYTES = int(os.getenv("FIRSTBREATH_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
CONFIDENCE_THRESHOLD = float(os.getenv("FIRSTBREATH_CONFIDENCE_THRESHOLD", STATUTS["seuil_question_suivi"]))


def load_required_fields() -> tuple[str, ...]:
    """The shared schema has no `required` flags; keep this policy configurable."""
    raw = os.getenv("FIRSTBREATH_REQUIRED_FIELDS", '["identification.numero_fiche"]')
    try:
        fields = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FIRSTBREATH_REQUIRED_FIELDS must be a JSON array of field keys") from exc
    if not isinstance(fields, list) or any(not isinstance(field, str) for field in fields):
        raise RuntimeError("FIRSTBREATH_REQUIRED_FIELDS must be a JSON array of field keys")
    unknown = [field for field in fields if definition(field) is None]
    if unknown:
        raise RuntimeError(f"Unknown required field keys: {', '.join(unknown)}")
    return tuple(fields)


REQUIRED_FIELDS = load_required_fields()
ALLOWED_FIELD_STATUSES = tuple(STATUTS["statuts_champ"])
ALLOWED_RECORD_STATES = tuple(STATUTS["etats_enregistrement"] + STATUTS["etats_echec"])
ALLOWED_PAGE_TYPES = tuple(STATUTS["types_page"])
FORBIDDEN_FIELD_NAMES = tuple(STATUTS["champs_interdits"])

