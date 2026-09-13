from __future__ import annotations

import json
import threading
from datetime import date, datetime
from pathlib import Path

from app.core.config import settings
from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta
from app.schemas.dossier import Dossier

_lock = threading.Lock()
_records: list[StoredDossierRecord] | None = None


def _path() -> Path:
    path = settings.dossiers_store_path
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _load() -> list[StoredDossierRecord]:
    global _records
    if _records is not None:
        return _records
    path = _path()
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        _records = [StoredDossierRecord.model_validate(item) for item in raw]
    else:
        _records = []
    return _records


def _save(records: list[StoredDossierRecord]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.model_dump() for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_created() -> list[StoredDossierRecord]:
    with _lock:
        return list(_load())


def prepend(record: StoredDossierRecord) -> None:
    global _records
    with _lock:
        records = _load()
        records = [record, *[r for r in records if r.id != record.id]]
        _save(records)
        _records = records


def get_by_id(dossier_id: str) -> StoredDossierRecord | None:
    with _lock:
        for record in _load():
            if record.id == dossier_id:
                return record
    return None


def get_by_no_demande(no_demande: str) -> StoredDossierRecord | None:
    needle = (no_demande or "").strip()
    if not needle:
        return None
    with _lock:
        for record in _load():
            if record.noDemande == needle or record.id == needle:
                return record
    return None


def replace_file(
    dossier_id: str,
    target_name: str,
    new_file: StoredFileMeta,
) -> StoredDossierRecord | None:
    global _records
    with _lock:
        records = _load()
        for i, record in enumerate(records):
            if record.id != dossier_id:
                continue
            files = list(record.files)
            replaced = False
            for j, existing in enumerate(files):
                if existing.name == target_name:
                    files[j] = new_file
                    replaced = True
                    break
            if not replaced:
                files.append(new_file)
            updated = record.model_copy(update={"files": files})
            records[i] = updated
            _save(records)
            _records = records
            return updated
    return None


def update_analyse(dossier_id: str, **patch: object) -> StoredDossierRecord | None:
    global _records
    with _lock:
        records = _load()
        for i, record in enumerate(records):
            if record.id != dossier_id:
                continue
            mapped = {}
            if "analyse_job_id" in patch:
                mapped["analyseJobId"] = patch["analyse_job_id"]
            if "analyse_status" in patch:
                mapped["analyseStatus"] = patch["analyse_status"]
            if "analyse" in patch:
                mapped["analyse"] = patch["analyse"]
            if "score" in patch:
                mapped["score"] = patch["score"]
            if "status" in patch:
                mapped["status"] = patch["status"]
            if "ice" in patch:
                mapped["ice"] = patch["ice"]
            if "rc" in patch:
                mapped["rc"] = patch["rc"]
            if "name" in patch:
                mapped["name"] = patch["name"]
            if "sector" in patch:
                mapped["sector"] = patch["sector"]
            updated = record.model_copy(update=mapped)
            records[i] = updated
            _save(records)
            _records = records
            return updated
    return None


def update_status(dossier_id: str, status: str) -> StoredDossierRecord | None:
    global _records
    today = date.today().strftime("%d/%m/%Y")
    with _lock:
        records = _load()
        for i, record in enumerate(records):
            if record.id != dossier_id:
                continue
            patch: dict = {"status": status}
            if status in {"approved", "rejected", "reserved", "review"}:
                patch["decisionDate"] = today
            elif status == "pending":
                patch["decisionDate"] = None
            updated = record.model_copy(update=patch)
            records[i] = updated
            _save(records)
            _records = records
            return updated
    return None


def _days_ago(date_str: str) -> int:
    try:
        created = datetime.strptime(date_str, "%d/%m/%Y").date()
        return max(0, (date.today() - created).days)
    except ValueError:
        return 0


def to_list_item(record: StoredDossierRecord) -> Dossier:
    from app.services.analyse_job_store import job_store

    progress = None
    job = job_store.get_for_dossier(record.id)
    if job:
        progress = job.progress_pct
    return Dossier(
        id=record.id,
        name=record.name,
        sector=record.sector,
        amount=record.amount,
        duration=record.duration,
        score=record.score,
        status=record.status,
        analyst=record.analyst,
        receivedDaysAgo=_days_ago(record.date),
        date=record.date,
        urgency=record.urgency,
        receivedLabel=record.receivedLabel,
        analyseStatus=record.analyseStatus,
        analyseProgressPct=progress,
        source=record.source,
        noDemande=record.noDemande,
        noPv=record.noPv,
        classe=((record.analyse or {}).get("scoring") or {}).get("classe"),
        riskLevel=((record.analyse or {}).get("scoring") or {}).get("riskLevel"),
    )
