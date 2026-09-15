#!/usr/bin/env python3
"""Importe dossiers.json vers SQLite sans supprimer le JSON."""
from __future__ import annotations

import json
from pathlib import Path

from app.db.session import init_database
from app.db.repositories import dossier_repository
from app.schemas.create_dossier import StoredDossierRecord


def main() -> None:
    init_database()
    path = Path("data/dossiers.json")
    if not path.exists():
        print("Aucun dossiers.json")
        return
    raw = json.loads(path.read_text(encoding="utf-8"))
    ok = 0
    errors = []
    for item in raw:
        try:
            record = StoredDossierRecord.model_validate(item)
            dossier_repository.create(record)
            ok += 1
        except Exception as exc:
            errors.append((item.get("id"), str(exc)))
    print(f"Migrés : {ok}")
    print(f"Erreurs : {len(errors)}")
    for row in errors:
        print(row)
    print("dossiers.json conservé.")


if __name__ == "__main__":
    main()
