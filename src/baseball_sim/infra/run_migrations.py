from __future__ import annotations

import argparse
import json

from baseball_sim.config import get_settings
from baseball_sim.infra.migrations import apply_migrations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply pending SQL migrations.")
    parser.add_argument("--dsn", default=None, help="Override PostgreSQL DSN.")
    parser.add_argument(
        "--migrations-dir", default=None, help="Override migrations directory path."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    dsn = args.dsn or settings.db_dsn
    migrations_dir = args.migrations_dir or settings.migrations_dir

    result = apply_migrations(dsn=dsn, migrations_dir=migrations_dir)
    print(
        json.dumps(
            {
                "applied_versions": result.applied_versions,
                "skipped_versions": result.skipped_versions,
                "migrations_dir": migrations_dir,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
