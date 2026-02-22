from pathlib import Path

from baseball_sim.infra.migrations import (
    collect_migration_files,
    pending_migrations,
    split_sql_statements,
    strip_explicit_transaction_wrappers,
)


def test_collect_migration_files_sorts_and_filters(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ignore", encoding="utf-8")
    (tmp_path / "0002_add_index.sql").write_text("SELECT 2;", encoding="utf-8")
    (tmp_path / "0001_init.sql").write_text("SELECT 1;", encoding="utf-8")

    files = collect_migration_files(tmp_path)

    assert [item.version for item in files] == ["0001", "0002"]
    assert [item.name for item in files] == ["init", "add_index"]
    assert all(len(item.checksum_sha256) == 64 for item in files)


def test_split_sql_statements_handles_semicolons_in_literals() -> None:
    sql = """
    BEGIN;
    CREATE TABLE demo (note TEXT DEFAULT 'a;b');
    INSERT INTO demo (note) VALUES ('x;y');
    COMMIT;
    """
    statements = split_sql_statements(sql)

    assert statements[0] == "BEGIN"
    assert statements[1].startswith("CREATE TABLE demo")
    assert statements[2].startswith("INSERT INTO demo")
    assert statements[3] == "COMMIT"


def test_strip_transaction_wrappers() -> None:
    statements = ["BEGIN", "CREATE TABLE x (id INT)", "COMMIT"]
    stripped = strip_explicit_transaction_wrappers(statements)
    assert stripped == ["CREATE TABLE x (id INT)"]


def test_pending_migrations_filters_applied(tmp_path: Path) -> None:
    (tmp_path / "0001_init.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0002_more.sql").write_text("SELECT 2;", encoding="utf-8")
    files = collect_migration_files(tmp_path)

    pending = pending_migrations(migrations=files, applied_versions={"0001"})

    assert [item.version for item in pending] == ["0002"]
