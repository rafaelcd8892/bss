from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

_MIGRATION_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<version>\d+)_(?P<name>[A-Za-z0-9_]+)\.sql$"
)
_DOLLAR_QUOTE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
_ADVISORY_LOCK_ID: Final[int] = 882_420_671


class CursorProtocol(Protocol):
    def execute(self, query: str, params: tuple[Any, ...] | None = None) -> Any: ...

    def fetchall(self) -> list[tuple[Any, ...]]: ...

    def __enter__(self) -> CursorProtocol: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


class TransactionProtocol(Protocol):
    def __enter__(self) -> TransactionProtocol: ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


class ConnectionProtocol(Protocol):
    def cursor(self) -> CursorProtocol: ...

    def transaction(self) -> TransactionProtocol: ...


@dataclass(frozen=True)
class MigrationFile:
    version: str
    name: str
    path: Path
    checksum_sha256: str


@dataclass(frozen=True)
class MigrationReport:
    applied_versions: list[str]
    skipped_versions: list[str]


def collect_migration_files(migrations_dir: str | Path) -> list[MigrationFile]:
    directory = Path(migrations_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Migrations directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Migrations path is not a directory: {directory}")

    migrations: list[MigrationFile] = []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        match = _MIGRATION_FILE_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        sql_text = path.read_text(encoding="utf-8")
        migrations.append(
            MigrationFile(
                version=match.group("version"),
                name=match.group("name"),
                path=path,
                checksum_sha256=hashlib.sha256(sql_text.encode("utf-8")).hexdigest(),
            )
        )
    migrations.sort(key=lambda item: (int(item.version), item.version))
    return migrations


def pending_migrations(
    *,
    migrations: list[MigrationFile],
    applied_versions: set[str],
) -> list[MigrationFile]:
    return [migration for migration in migrations if migration.version not in applied_versions]


def split_sql_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buffer: list[str] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    in_block_comment = False
    in_dollar_quote_tag: str | None = None

    i = 0
    size = len(sql_text)
    while i < size:
        char = sql_text[i]
        next_char = sql_text[i + 1] if i + 1 < size else ""

        if in_dollar_quote_tag is not None:
            if sql_text.startswith(in_dollar_quote_tag, i):
                buffer.append(in_dollar_quote_tag)
                i += len(in_dollar_quote_tag)
                in_dollar_quote_tag = None
                continue
            buffer.append(char)
            i += 1
            continue

        if in_line_comment:
            buffer.append(char)
            if char == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            buffer.append(char)
            if char == "*" and next_char == "/":
                buffer.append(next_char)
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue

        if not in_single_quote and not in_double_quote:
            if char == "-" and next_char == "-":
                buffer.append(char)
                buffer.append(next_char)
                i += 2
                in_line_comment = True
                continue
            if char == "/" and next_char == "*":
                buffer.append(char)
                buffer.append(next_char)
                i += 2
                in_block_comment = True
                continue
            if char == "$":
                tag_match = _DOLLAR_QUOTE_PATTERN.match(sql_text[i:])
                if tag_match is not None:
                    tag = tag_match.group(0)
                    in_dollar_quote_tag = tag
                    buffer.append(tag)
                    i += len(tag)
                    continue

        if char == "'" and not in_double_quote:
            if in_single_quote and next_char == "'":
                buffer.append(char)
                buffer.append(next_char)
                i += 2
                continue
            in_single_quote = not in_single_quote
            buffer.append(char)
            i += 1
            continue

        if char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            buffer.append(char)
            i += 1
            continue

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(buffer).strip()
            if statement != "":
                statements.append(statement)
            buffer = []
            i += 1
            continue

        buffer.append(char)
        i += 1

    trailing_statement = "".join(buffer).strip()
    if trailing_statement != "":
        statements.append(trailing_statement)
    return statements


def strip_explicit_transaction_wrappers(statements: list[str]) -> list[str]:
    if len(statements) < 2:
        return statements

    first = statements[0].strip().upper()
    last = statements[-1].strip().upper()
    starts_tx = first in {"BEGIN", "BEGIN TRANSACTION", "START TRANSACTION"}
    ends_tx = last in {"COMMIT", "END"}
    if starts_tx and ends_tx:
        return statements[1:-1]
    return statements


def apply_migrations(
    *,
    dsn: str,
    migrations_dir: str | Path,
) -> MigrationReport:
    import psycopg

    migrations = collect_migration_files(migrations_dir)
    applied_versions: list[str] = []
    skipped_versions: list[str] = []

    with psycopg.connect(dsn) as conn:
        _acquire_migration_lock(conn)
        try:
            _ensure_schema_migrations_table(conn)
            existing_migrations = _fetch_applied_migrations(conn)

            for migration in migrations:
                existing_checksum = existing_migrations.get(migration.version)
                if existing_checksum is not None:
                    if existing_checksum != migration.checksum_sha256:
                        raise RuntimeError(
                            "Migration checksum mismatch for version "
                            f"{migration.version}: expected {existing_checksum}, "
                            f"found {migration.checksum_sha256}"
                        )
                    skipped_versions.append(migration.version)
                    continue

                _apply_single_migration(conn, migration)
                applied_versions.append(migration.version)
                existing_migrations[migration.version] = migration.checksum_sha256
        finally:
            _release_migration_lock(conn)

    return MigrationReport(
        applied_versions=applied_versions,
        skipped_versions=skipped_versions,
    )


def _ensure_schema_migrations_table(conn: ConnectionProtocol) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum_sha256 TEXT NOT NULL,
                applied_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


def _fetch_applied_migrations(conn: ConnectionProtocol) -> dict[str, str]:
    with conn.cursor() as cursor:
        cursor.execute("SELECT version, checksum_sha256 FROM schema_migrations")
        rows = cursor.fetchall()

    versions: dict[str, str] = {}
    for row in rows:
        if len(row) >= 2:
            versions[str(row[0])] = str(row[1])
    return versions


def _apply_single_migration(conn: ConnectionProtocol, migration: MigrationFile) -> None:
    sql_text = migration.path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    statements_to_execute = strip_explicit_transaction_wrappers(statements)

    with conn.transaction():
        with conn.cursor() as cursor:
            for statement in statements_to_execute:
                cursor.execute(statement)
            cursor.execute(
                """
                INSERT INTO schema_migrations (version, name, checksum_sha256)
                VALUES (%s, %s, %s)
                """,
                (migration.version, migration.name, migration.checksum_sha256),
            )


def _acquire_migration_lock(conn: ConnectionProtocol) -> None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_ID,))


def _release_migration_lock(conn: ConnectionProtocol) -> None:
    with conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_ID,))
