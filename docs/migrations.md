# Migrations

## Command
Apply pending migrations:

```bash
python -m baseball_sim.infra.run_migrations
```

Optional overrides:

```bash
python -m baseball_sim.infra.run_migrations --dsn postgresql://... --migrations-dir migrations
```

## Rules
- Migration files use `{version}_{name}.sql` naming.
- Version is numeric and compared in ascending order.
- Applied versions are tracked in `schema_migrations`.
- Existing applied versions must keep matching SQL checksum.
- Each migration is applied in its own transaction.
- Runner acquires a PostgreSQL advisory lock to prevent concurrent migration runs.
