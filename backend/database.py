"""Small SQLite persistence layer for the hackathon backend."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from backend.constants import DB_PATH


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Transaction BEGIN IMMEDIATE : les lectures-modifications-écritures du dossier (plusieurs
    extractions en parallèle) sont sérialisées ; sans cela, une page pouvait en écraser une autre."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
        if connection.in_transaction:  # executescript (initialize) valide déjà de lui-même
            connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def initialize() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                state TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(owner_id, session_id)
            );
            CREATE TABLE IF NOT EXISTS captures (
                id TEXT PRIMARY KEY,
                record_id TEXT NOT NULL REFERENCES records(id),
                page_no INTEGER NOT NULL,
                image_id TEXT NOT NULL,
                image_hash TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                idempotency_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                UNIQUE(record_id, page_no, image_hash)
            );
            CREATE INDEX IF NOT EXISTS captures_by_hash ON captures(image_hash);
            CREATE TABLE IF NOT EXISTS transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL REFERENCES records(id),
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                reason TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS field_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL REFERENCES records(id),
                field_key TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patients (
                id TEXT PRIMARY KEY,
                record_number TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS duplicate_reports (
                id TEXT PRIMARY KEY,
                existing_capture_id TEXT NOT NULL REFERENCES captures(id),
                proposed_session_id TEXT NOT NULL,
                proposed_page_no INTEGER NOT NULL,
                actor_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                decision TEXT
            );
            -- Système de santé central SIMULÉ : copies anonymisées des dossiers synchronisés.
            CREATE TABLE IF NOT EXISTS systeme_central (
                dossier_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                synchronise_le TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS acces_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_id TEXT NOT NULL REFERENCES captures(id),
                role TEXT NOT NULL,
                demandeur_id TEXT,
                autorise INTEGER NOT NULL,
                date TEXT NOT NULL
            );
            """
        )
        _ajouter_colonnes(db, "captures", CAPTURE_TRAITEMENT)
        _ajouter_colonnes(db, "patients", {"code": "TEXT"})
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS patients_par_code ON patients(code) WHERE code IS NOT NULL")
        # Captures antérieures à la colonne sage_femme_id : la sage-femme est le propriétaire du dossier.
        db.execute("UPDATE captures SET sage_femme_id = (SELECT owner_id FROM records WHERE records.id = captures.record_id) "
                   "WHERE sage_femme_id IS NULL")


# Suivi du traitement de chaque capture (ajouté aux bases existantes par _ajouter_colonnes).
CAPTURE_TRAITEMENT = {
    "etat_traitement": "TEXT NOT NULL DEFAULT 'CAPTURE'",
    "type_page": "TEXT",
    "debut_traitement": "TEXT",
    "fin_traitement": "TEXT",
    "duree_estimee_s": "INTEGER",
    "detail_traitement": "TEXT",
    "sage_femme_id": "TEXT",
}


def _ajouter_colonnes(db: sqlite3.Connection, table: str, colonnes: dict[str, str]) -> None:
    """Migration minimale : ajoute les colonnes manquantes d'une table existante."""
    existantes = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    for nom, definition in colonnes.items():
        if nom not in existantes:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {nom} {definition}")

