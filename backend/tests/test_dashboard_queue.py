"""File d'attente du tableau de bord : dossiers à analyser et analyses en cours, rien d'autre."""
from __future__ import annotations

from app.schemas.create_dossier import StoredDossierRecord
from app.services.dashboard_service import QUEUE_STATUSES, compute_queue


def _record(dossier_id: str, status: str, urgency: str = "normale") -> StoredDossierRecord:
    return StoredDossierRecord(
        id=dossier_id, name=f"STE {dossier_id}", sector="Transport", identifiantFiscal="1",
        amount=100000, duration=48, score=0, status=status, analyst="A", date="01/10/2026",
        ice="", nature="mobilier", valeurBien=1, apport=0, fournisseur="F", proformaReference="P",
        natureBien="X", etat="neuf", valeurHt=1, valeurTtc=1, urgency=urgency, files=[],
    )


def test_queue_keeps_only_dossiers_to_analyse_or_in_progress():
    records = [
        _record("A", "pending"),
        _record("B", "analyzing"),
        _record("C", "review"),
        _record("D", "approved"),
        _record("E", "ready"),
    ]
    waiting = [r for r in records if r.status in QUEUE_STATUSES]
    queue = compute_queue(waiting)

    assert {item.id for item in queue} == {"A", "B", "E"}
    stages = {item.id: item.stage for item in queue}
    assert stages == {"A": "todo", "B": "analyzing", "E": "todo"}


def test_analyses_in_progress_come_first_then_urgent():
    queue = compute_queue([
        _record("A", "pending"),
        _record("B", "pending", urgency="haute"),
        _record("C", "analyzing"),
    ])
    assert [item.id for item in queue] == ["C", "B", "A"]
