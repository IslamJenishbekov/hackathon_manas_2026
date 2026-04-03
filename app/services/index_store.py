import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class PersonShadowRecord:
    person_id: int
    full_name: str
    normalized_name: str
    birth_year: int | None
    death_year: int | None
    region: str | None
    district: str | None
    occupation: str | None
    charge: str | None
    arrest_date: str | None
    sentence: str | None
    sentence_date: str | None
    rehabilitation_date: str | None
    biography: str | None
    source: str | None
    status: str | None
    search_text: str
    raw_payload: dict[str, Any]


@dataclass
class RetrievedPersonRecord:
    person_id: int
    full_name: str
    normalized_name: str
    birth_year: int | None
    death_year: int | None
    region: str | None
    district: str | None
    occupation: str | None
    charge: str | None
    arrest_date: str | None
    sentence: str | None
    sentence_date: str | None
    rehabilitation_date: str | None
    biography: str | None
    source: str | None
    status: str | None
    search_text: str
    raw_payload: dict[str, Any]


@dataclass
class IndexDocumentRecord:
    document_id: int
    person_id: int
    filename: str
    source_link: str | None
    raw_text: str
    doc_type: str
    primary_full_name: str | None
    primary_normalized_name: str | None
    primary_birth_year: int | None
    primary_region: str | None
    primary_charge: str | None
    embedding_model: str
    chunk_count: int
    warnings: list[str]


@dataclass
class IndexEntityRecord:
    document_id: int
    normalized_name: str
    raw_name: str | None
    birth_year: int | None
    role: str


@dataclass
class IndexChunkRecord:
    document_id: int
    chunk_index: int
    chunk_text: str
    char_start: int
    char_end: int
    embedding: list[float]


@dataclass
class RetrievedEntityRecord:
    document_id: int
    normalized_name: str
    raw_name: str | None
    birth_year: int | None
    role: str


@dataclass
class RetrievedChunkRecord:
    document_id: int
    chunk_index: int
    chunk_text: str
    char_start: int
    char_end: int
    embedding: list[float]
    doc_type: str
    filename: str
    source_link: str | None
    person_id: int


@dataclass
class RetrievedDocumentRecord:
    document_id: int
    person_id: int
    filename: str
    source_link: str | None
    raw_text: str
    doc_type: str
    primary_full_name: str | None
    primary_normalized_name: str | None
    primary_birth_year: int | None


class SQLiteIndexStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS persons_shadow (
                    person_id INTEGER PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    birth_year INTEGER,
                    death_year INTEGER,
                    region TEXT,
                    district TEXT,
                    occupation TEXT,
                    charge TEXT,
                    arrest_date TEXT,
                    sentence TEXT,
                    sentence_date TEXT,
                    rehabilitation_date TEXT,
                    biography TEXT,
                    status TEXT,
                    source TEXT,
                    search_text TEXT NOT NULL DEFAULT '',
                    raw_payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    document_id INTEGER PRIMARY KEY,
                    person_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    source_link TEXT,
                    raw_text TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    primary_full_name TEXT,
                    primary_normalized_name TEXT,
                    primary_birth_year INTEGER,
                    primary_region TEXT,
                    primary_charge TEXT,
                    embedding_model TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    warnings_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS document_entities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    normalized_name TEXT NOT NULL,
                    raw_name TEXT,
                    birth_year INTEGER,
                    role TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_text TEXT NOT NULL,
                    char_start INTEGER NOT NULL,
                    char_end INTEGER NOT NULL,
                    embedding_json TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_persons_shadow_name
                    ON persons_shadow(normalized_name);
                CREATE INDEX IF NOT EXISTS idx_persons_shadow_name_birth_year
                    ON persons_shadow(normalized_name, birth_year);
                CREATE INDEX IF NOT EXISTS idx_persons_shadow_rehabilitation_date
                    ON persons_shadow(rehabilitation_date);
                CREATE INDEX IF NOT EXISTS idx_documents_person_id
                    ON documents(person_id);
                CREATE INDEX IF NOT EXISTS idx_document_entities_document_id
                    ON document_entities(document_id);
                CREATE INDEX IF NOT EXISTS idx_document_entities_name
                    ON document_entities(normalized_name);
                CREATE INDEX IF NOT EXISTS idx_document_entities_name_birth_year
                    ON document_entities(normalized_name, birth_year);
                CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                    ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_document_id_chunk_index
                    ON chunks(document_id, chunk_index);
                """
            )
            self._ensure_legacy_columns(connection)

    def upsert_persons_shadow(self, persons: list[PersonShadowRecord]) -> None:
        if not persons:
            return

        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO persons_shadow (
                    person_id,
                    full_name,
                    normalized_name,
                    birth_year,
                    death_year,
                    region,
                    district,
                    occupation,
                    charge,
                    arrest_date,
                    sentence,
                    sentence_date,
                    rehabilitation_date,
                    biography,
                    status,
                    source,
                    search_text,
                    raw_payload_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(person_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    normalized_name = excluded.normalized_name,
                    birth_year = excluded.birth_year,
                    death_year = excluded.death_year,
                    region = excluded.region,
                    district = excluded.district,
                    occupation = excluded.occupation,
                    charge = excluded.charge,
                    arrest_date = excluded.arrest_date,
                    sentence = excluded.sentence,
                    sentence_date = excluded.sentence_date,
                    rehabilitation_date = excluded.rehabilitation_date,
                    biography = excluded.biography,
                    status = excluded.status,
                    source = excluded.source,
                    search_text = excluded.search_text,
                    raw_payload_json = excluded.raw_payload_json,
                    updated_at = excluded.updated_at
                """,
                [
                    (
                        person.person_id,
                        person.full_name,
                        person.normalized_name,
                        person.birth_year,
                        person.death_year,
                        person.region,
                        person.district,
                        person.occupation,
                        person.charge,
                        person.arrest_date,
                        person.sentence,
                        person.sentence_date,
                        person.rehabilitation_date,
                        person.biography,
                        person.status,
                        person.source,
                        person.search_text,
                        json.dumps(person.raw_payload, ensure_ascii=False),
                        now,
                    )
                    for person in persons
                ],
            )

    def get_person_records(self, *, person_ids: list[int] | None = None) -> list[RetrievedPersonRecord]:
        query = """
            SELECT
                person_id,
                full_name,
                normalized_name,
                birth_year,
                death_year,
                region,
                district,
                occupation,
                charge,
                arrest_date,
                sentence,
                sentence_date,
                rehabilitation_date,
                biography,
                source,
                status,
                search_text,
                raw_payload_json
            FROM persons_shadow
        """
        params: list[object] = []
        if person_ids:
            placeholders = ", ".join("?" for _ in person_ids)
            query += f" WHERE person_id IN ({placeholders})"
            params.extend(person_ids)
        query += " ORDER BY person_id"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            RetrievedPersonRecord(
                person_id=row[0],
                full_name=row[1],
                normalized_name=row[2],
                birth_year=row[3],
                death_year=row[4],
                region=row[5],
                district=row[6],
                occupation=row[7],
                charge=row[8],
                arrest_date=row[9],
                sentence=row[10],
                sentence_date=row[11],
                rehabilitation_date=row[12],
                biography=row[13],
                source=row[14],
                status=row[15],
                search_text=row[16],
                raw_payload=json.loads(row[17]),
            )
            for row in rows
        ]

    def find_related_document_ids(
        self,
        *,
        person_ids: list[int] | None = None,
        normalized_names: list[str] | None = None,
    ) -> list[int]:
        matched_ids: set[int] = set()

        with self._connect() as connection:
            if person_ids:
                placeholders = ", ".join("?" for _ in person_ids)
                rows = connection.execute(
                    f"SELECT document_id FROM documents WHERE person_id IN ({placeholders})",
                    person_ids,
                ).fetchall()
                matched_ids.update(row[0] for row in rows)

            if normalized_names:
                placeholders = ", ".join("?" for _ in normalized_names)
                rows = connection.execute(
                    f"""
                    SELECT DISTINCT document_id
                    FROM document_entities
                    WHERE normalized_name IN ({placeholders})
                    """,
                    normalized_names,
                ).fetchall()
                matched_ids.update(row[0] for row in rows)

        return sorted(matched_ids)

    def reindex_document(
        self,
        document: IndexDocumentRecord,
        entities: list[IndexEntityRecord],
        chunks: list[IndexChunkRecord],
    ) -> None:
        now = datetime.now(UTC).isoformat()

        with self._connect() as connection:
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (document.document_id,))
            connection.execute(
                "DELETE FROM document_entities WHERE document_id = ?",
                (document.document_id,),
            )
            connection.execute(
                """
                INSERT INTO documents (
                    document_id,
                    person_id,
                    filename,
                    source_link,
                    raw_text,
                    doc_type,
                    primary_full_name,
                    primary_normalized_name,
                    primary_birth_year,
                    primary_region,
                    primary_charge,
                    embedding_model,
                    chunk_count,
                    warnings_json,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    person_id = excluded.person_id,
                    filename = excluded.filename,
                    source_link = excluded.source_link,
                    raw_text = excluded.raw_text,
                    doc_type = excluded.doc_type,
                    primary_full_name = excluded.primary_full_name,
                    primary_normalized_name = excluded.primary_normalized_name,
                    primary_birth_year = excluded.primary_birth_year,
                    primary_region = excluded.primary_region,
                    primary_charge = excluded.primary_charge,
                    embedding_model = excluded.embedding_model,
                    chunk_count = excluded.chunk_count,
                    warnings_json = excluded.warnings_json,
                    updated_at = excluded.updated_at
                """,
                (
                    document.document_id,
                    document.person_id,
                    document.filename,
                    document.source_link,
                    document.raw_text,
                    document.doc_type,
                    document.primary_full_name,
                    document.primary_normalized_name,
                    document.primary_birth_year,
                    document.primary_region,
                    document.primary_charge,
                    document.embedding_model,
                    document.chunk_count,
                    json.dumps(document.warnings, ensure_ascii=False),
                    now,
                ),
            )

            connection.executemany(
                """
                INSERT INTO document_entities (
                    document_id,
                    normalized_name,
                    raw_name,
                    birth_year,
                    role
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        entity.document_id,
                        entity.normalized_name,
                        entity.raw_name,
                        entity.birth_year,
                        entity.role,
                    )
                    for entity in entities
                ],
            )

            connection.executemany(
                """
                INSERT INTO chunks (
                    document_id,
                    chunk_index,
                    chunk_text,
                    char_start,
                    char_end,
                    embedding_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.chunk_text,
                        chunk.char_start,
                        chunk.char_end,
                        json.dumps(chunk.embedding),
                    )
                    for chunk in chunks
                ],
            )

    def get_entity_records(self) -> list[RetrievedEntityRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_id, normalized_name, raw_name, birth_year, role
                FROM document_entities
                ORDER BY id
                """
            ).fetchall()
        return [
            RetrievedEntityRecord(
                document_id=row[0],
                normalized_name=row[1],
                raw_name=row[2],
                birth_year=row[3],
                role=row[4],
            )
            for row in rows
        ]

    def get_chunks(
        self,
        *,
        document_ids: list[int] | None = None,
        doc_types: list[str] | None = None,
    ) -> list[RetrievedChunkRecord]:
        query = """
            SELECT
                c.document_id,
                c.chunk_index,
                c.chunk_text,
                c.char_start,
                c.char_end,
                c.embedding_json,
                d.doc_type,
                d.filename,
                d.source_link,
                d.person_id
            FROM chunks c
            JOIN documents d ON d.document_id = c.document_id
        """
        conditions: list[str] = []
        params: list[object] = []

        if document_ids:
            placeholders = ", ".join("?" for _ in document_ids)
            conditions.append(f"c.document_id IN ({placeholders})")
            params.extend(document_ids)

        if doc_types:
            placeholders = ", ".join("?" for _ in doc_types)
            conditions.append(f"d.doc_type IN ({placeholders})")
            params.extend(doc_types)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY c.document_id, c.chunk_index"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            RetrievedChunkRecord(
                document_id=row[0],
                chunk_index=row[1],
                chunk_text=row[2],
                char_start=row[3],
                char_end=row[4],
                embedding=json.loads(row[5]),
                doc_type=row[6],
                filename=row[7],
                source_link=row[8],
                person_id=row[9],
            )
            for row in rows
        ]

    def get_document_records(
        self,
        *,
        person_ids: list[int] | None = None,
        doc_types: list[str] | None = None,
    ) -> list[RetrievedDocumentRecord]:
        query = """
            SELECT
                document_id,
                person_id,
                filename,
                source_link,
                raw_text,
                doc_type,
                primary_full_name,
                primary_normalized_name,
                primary_birth_year
            FROM documents
        """
        conditions: list[str] = []
        params: list[object] = []

        if person_ids:
            placeholders = ", ".join("?" for _ in person_ids)
            conditions.append(f"person_id IN ({placeholders})")
            params.extend(person_ids)

        if doc_types:
            placeholders = ", ".join("?" for _ in doc_types)
            conditions.append(f"doc_type IN ({placeholders})")
            params.extend(doc_types)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY document_id"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            RetrievedDocumentRecord(
                document_id=row[0],
                person_id=row[1],
                filename=row[2],
                source_link=row[3],
                raw_text=row[4],
                doc_type=row[5],
                primary_full_name=row[6],
                primary_normalized_name=row[7],
                primary_birth_year=row[8],
            )
            for row in rows
        ]

    def _ensure_legacy_columns(self, connection: sqlite3.Connection) -> None:
        self._ensure_column(connection, "persons_shadow", "occupation", "TEXT")
        self._ensure_column(connection, "persons_shadow", "arrest_date", "TEXT")
        self._ensure_column(connection, "persons_shadow", "sentence", "TEXT")
        self._ensure_column(connection, "persons_shadow", "sentence_date", "TEXT")
        self._ensure_column(connection, "persons_shadow", "rehabilitation_date", "TEXT")
        self._ensure_column(connection, "persons_shadow", "search_text", "TEXT NOT NULL DEFAULT ''")
        self._ensure_column(connection, "documents", "source_link", "TEXT")
        self._ensure_column(
            connection,
            "persons_shadow",
            "raw_payload_json",
            "TEXT NOT NULL DEFAULT '{}'",
        )

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_definition: str,
    ) -> None:
        existing_columns = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
