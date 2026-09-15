# Notes de migration JSON → SQLite

Le store JSON `data/dossiers.json` reste en dual-write.

```
cd backend
python scripts/migrate_json_to_sqlite.py
```

- conserve les IDs
- n’efface pas dossiers.json
- documents = métadonnées + object_key MinIO, pas le fichier

Après validation, `dossier_store.py` reste façade (JSON + SQLite).
