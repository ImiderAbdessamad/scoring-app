from __future__ import annotations

import json
from pathlib import Path

from app.db.session import init_database
from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta
from app.db.repositories import dossier_repository, job_repository, memo_repository
from app.services.analyse_job_store import AnalysisDocumentRef, ScoringJob


def test_sqlite_repository_persistence():
    init_database()
    record = StoredDossierRecord(
        id="ABC-2026-1000",
        name="TEST SA",
        sector="Câbles électriques",
        identifiantFiscal="52601461",
        amount=1,
        duration=12,
        score=0,
        status="pending",
        analyst="A",
        date="15/09/2026",
        ice="003120883000059",
        nature="mobilier",
        valeurBien=1,
        apport=10,
        fournisseur="F",
        proformaReference="P",
        natureBien="X",
        etat="neuf",
        valeurHt=1,
        valeurTtc=1,
        files=[StoredFileMeta(name="bilan.pdf", objectKey="k", size=10, contentType="application/pdf", category="entreprise", sha256="abc")],
    )
    dossier_repository.create(record)
    loaded = dossier_repository.get("ABC-2026-1000")
    assert loaded is not None
    assert loaded.identifiantFiscal == "52601461"
    assert loaded.sector == "Câbles électriques"


def test_job_persists_after_repository_reload():
    init_database()
    dossier_repository.create(
        StoredDossierRecord(
            id="D1",
            name="T",
            sector="Industrie",
            amount=1,
            duration=12,
            score=0,
            status="pending",
            analyst="A",
            date="15/09/2026",
            ice="1",
            nature="mobilier",
            valeurBien=1,
            apport=0,
            fournisseur="F",
            proformaReference="P",
            natureBien="X",
            etat="neuf",
            valeurHt=1,
            valeurTtc=1,
            files=[],
        )
    )
    job = ScoringJob(
        job_id="job1",
        dossier_id="D1",
        filename="a.pdf",
        primary_document=AnalysisDocumentRef("d", "key", "a.pdf", "sha"),
        status="queued",
    )
    job_repository.upsert_from_job(job)
    row = job_repository.get("job1")
    assert row is not None
    docs = json.loads(row.documents_json)
    assert "pdf_bytes" not in docs
    assert docs["primary"]["object_key"] == "key"


def test_memo_signature_persisted():
    init_database()
    dossier_repository.create(
        StoredDossierRecord(
            id="D-MEMO",
            name="T",
            sector="Industrie",
            amount=1,
            duration=12,
            score=0,
            status="pending",
            analyst="A",
            date="15/09/2026",
            ice="1",
            nature="mobilier",
            valeurBien=1,
            apport=0,
            fournisseur="F",
            proformaReference="P",
            natureBien="X",
            etat="neuf",
            valeurHt=1,
            valeurTtc=1,
            files=[],
        )
    )
    memo = memo_repository.create(dossier_id="D-MEMO", content_json="{}", analysis_fingerprint="fp")
    signed = memo_repository.sign(memo.id, signed_by="Analyste", signed_role="analyste", content_hash="deadbeef")
    assert signed is not None
    assert signed.status == "SIGNED"
    assert signed.content_hash == "deadbeef"


def test_document_replace_marks_stale():
    from app.services.workspace_builder import analysis_source_fingerprint, overlay_live_documents
    from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta

    def rec(sha: str) -> StoredDossierRecord:
        return StoredDossierRecord(
            id="D1",
            name="T",
            sector="Industrie",
            amount=1,
            duration=12,
            score=0,
            status="review",
            analyst="A",
            date="15/09/2026",
            ice="1",
            nature="mobilier",
            valeurBien=1,
            apport=0,
            fournisseur="F",
            proformaReference="P",
            natureBien="X",
            etat="neuf",
            valeurHt=1,
            valeurTtc=1,
            files=[StoredFileMeta(name="bilan.pdf", objectKey="k", size=10, contentType="application/pdf", category="entreprise", sha256=sha)],
        )

    old = rec("aaa")
    new = rec("bbb")
    ws = {"analysisFingerprint": analysis_source_fingerprint(old), "scoring": {"score": 10}}
    overlay = overlay_live_documents(new, ws)
    assert overlay["analysisStale"] is True
