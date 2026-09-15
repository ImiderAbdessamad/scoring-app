#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1] / "app"
bad = []
for path in root.rglob("*.py"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "from app.legacy" in text or "import app.legacy" in text:
        bad.append(str(path))
if bad:
    print("Imports legacy interdits :")
    print("\n".join(bad))
    sys.exit(1)
print("OK — aucun import legacy")
