"""Les tests utilisent une base et un dossier de fichiers temporaires, jamais ceux du poste.

Les variables sont posées avant le premier import de l'application (pytest charge ce fichier
en premier) : app.core.config les lit à l'import.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DATA = Path(tempfile.mkdtemp(prefix="wafabail-tests-"))

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TEST_DATA / 'wafabail.db').as_posix()}"
os.environ["DOSSIERS_STORE_PATH"] = str(_TEST_DATA / "dossiers.json")
os.environ["FILES_DIR"] = str(_TEST_DATA / "files")
