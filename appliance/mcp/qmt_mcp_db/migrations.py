"""Numbered SQL migration runner (012).

Applies `migrations/*.sql` in filename order, tracking applied versions in a
`schema_migrations` table. Idempotent: already-applied files are skipped.
"""

from __future__ import annotations

import pathlib

MIG_DIR = pathlib.Path(__file__).parent / "migrations"


def migration_files() -> list[pathlib.Path]:
    return sorted(MIG_DIR.glob("*.sql"))


def apply_migrations(engine) -> list[str]:
    engine.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    applied = {r["version"] for r in engine.fetch("SELECT version FROM schema_migrations")}
    newly: list[str] = []
    for path in migration_files():
        version = path.name
        if version in applied:
            continue
        engine.execute(path.read_text(encoding="utf-8"))
        engine.execute("INSERT INTO schema_migrations (version) VALUES ($1)", version)
        newly.append(version)
    return newly
