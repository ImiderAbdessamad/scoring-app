"""Jobs d'analyse scoring asynchrones (extracteur V6, SSE, navigation libre)."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncIterator, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app import config
from app.schemas.analyse import (
    AnalyseJobCreateResponse,
    AnalyseJobProgress,
    AnalyseStateResponse,
    BilanIdentityResponse,
    CopilotChatRequest,
    CopilotChatResponse,
    DossierSyntheseResponse,
    ScoringAnalysisResult,
)
from app.services import dossier_store, kafka_publisher, minio_storage
from app.services.analyse_job_store import job_store
from app.services.scoring_lab_pipeline import run_scoring_job
from app.services.workspace_builder import build_workspace, empty_workspace, overlay_live_documents

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyse scoring"])

_PIPELINE_LOCK = asyncio.Lock()


@router.post("/extract/identity", response_model=BilanIdentityResponse)
async def extract_bilan_identity(file: UploadFile = File(...)) -> BilanIdentityResponse:
    """Extrait ICE, RC, IF et raison sociale depuis le bilan / la liasse (en-tête V6)."""
    name = (file.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Déposez un PDF de bilan / liasse fiscale.")
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Le fichier n'est pas un PDF valide.")
    from app.services.identity_extract import extract_identity_from_pdf_bytes

    try:
        payload = await asyncio.to_thread(extract_identity_from_pdf_bytes, data)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Extraction d'identité bilan impossible")
        raise HTTPException(status_code=422, detail=f"Lecture du bilan impossible : {exc}") from exc
    return BilanIdentityResponse(**payload)


def _download_pdf(meta) -> bytes:
    try:
        data = minio_storage.download_bytes(meta.objectKey)
    except Exception as exc:
        logger.exception("Lecture MinIO impossible pour %s", meta.objectKey)
        raise HTTPException(status_code=503, detail=f"Impossible de lire le PDF : {exc}") from exc
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail=f"{meta.name} n'est pas un PDF valide.")
    return data


def _pick_liasses(record) -> tuple[AnalysisDocumentRef, list[AnalysisDocumentRef]]:
    from app.services.analyse_job_store import AnalysisDocumentRef
    from app.services.file_validation import sha256_bytes

    files = list(record.files)
    ranked = []
    for meta in files:
        name = (meta.name or "").lower()
        ctype = (meta.contentType or "").lower()
        is_pdf = name.endswith(".pdf") or "pdf" in ctype
        if not is_pdf:
            continue
        score = 0
        if "liasse" in name or "bilan" in name or "cpc" in name:
            score += 10
        year_hit = re.search(r"20\d{2}", name)
        if year_hit:
            score += 3 + int(year_hit.group(0)) - 2000
        if meta.category == "entreprise":
            score += 1
        ranked.append((score, meta))
    if not ranked:
        raise HTTPException(
            status_code=422,
            detail="Aucune liasse PDF n'est rattachée à ce dossier. Déposez un bilan / liasse fiscale.",
        )
    ranked.sort(key=lambda item: -item[0])
    chosen = ranked[0][1]
    extras: list[AnalysisDocumentRef] = []
    for _, meta in ranked[1:]:
        name = (meta.name or "").lower()
        if "liasse" in name or "bilan" in name or "cpc" in name:
            extras.append(
                AnalysisDocumentRef(
                    document_id=meta.objectKey,
                    object_key=meta.objectKey,
                    filename=meta.name,
                    sha256=getattr(meta, "sha256", None),
                )
            )
        if len(extras) >= 2:
            break
    primary = AnalysisDocumentRef(
        document_id=chosen.objectKey,
        object_key=chosen.objectKey,
        filename=chosen.name,
        sha256=getattr(chosen, "sha256", None),
    )
    return primary, extras


def _persist_result(dossier_id: str, result: ScoringAnalysisResult) -> None:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        return
    decision = result.decision or {}
    score_status = decision.get("score_status") or "PARTIAL"
    score_raw = decision.get("final_score") if score_status == "FINAL" else decision.get("partial_score")
    if score_raw is None:
        score_raw = result.score_raw
    score = int(round(float(score_raw))) if score_status == "FINAL" and score_raw is not None else 0
    job = job_store.get_for_dossier(dossier_id)
    ready = result.readiness.ready_for_automatic_scoring
    if record.status == "analyzing":
        next_status = "review" if ready else "review"
    else:
        next_status = record.status
    snapshot = record.model_copy(update={"status": next_status, "score": score})
    company = result.document.company
    ice = company.ice if company.ice and not (record.ice or "").strip() else None
    patch: dict = {}
    if ice:
        patch["ice"] = ice
        snapshot = snapshot.model_copy(update={"ice": ice})
    if company.rc and company.rc.strip() and not (record.rc or "").strip():
        patch["rc"] = company.rc.strip()
        snapshot = snapshot.model_copy(update={"rc": company.rc.strip()})
    if company.raison_sociale and company.raison_sociale.strip():
        patch["name"] = company.raison_sociale.strip()
        snapshot = snapshot.model_copy(update={"name": company.raison_sociale.strip()})
    if patch:
        dossier_store.update_analyse(dossier_id, **patch)
    workspace = build_workspace(snapshot, result)
    try:
        import hashlib
        import json

        from app.core.config import settings
        from app.db.repositories import analysis_run_repository
        from app.services.workspace_builder import analysis_source_fingerprint

        audit = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, default=str)
        digest = hashlib.sha256(audit.encode("utf-8")).hexdigest()
        object_key = f"audit/{dossier_id}/{job.job_id if job else 'run'}/v6_full_audit.json"
        try:
            from app.services import minio_storage

            minio_storage.upload_file(
                dossier_id=dossier_id,
                category="audit",
                filename=f"{job.job_id if job else 'run'}-v6_full_audit.json",
                data=__import__("io").BytesIO(audit.encode("utf-8")),
                length=len(audit.encode("utf-8")),
                content_type="application/json",
            )
        except Exception:
            object_key = None
        run = analysis_run_repository.create(
            dossier_id=dossier_id,
            job_id=job.job_id if job else None,
            extractor_version="v6",
            scoring_policy_version=settings.scoring_policy_version,
            analysis_fingerprint=analysis_source_fingerprint(snapshot),
            score_status=score_status,
            financial_score=decision.get("financial_score"),
            behavioral_score=decision.get("behavioral_score"),
            sector_score=decision.get("sector_score"),
            partial_score=decision.get("partial_score"),
            final_score=decision.get("final_score"),
            quality_json=json.dumps(result.quality.model_dump(), default=str),
            readiness_json=json.dumps(result.readiness.model_dump(), default=str),
            scoring_view_json=json.dumps(workspace.get("scoring") or {}, default=str),
            full_audit_object_key=object_key,
            full_audit_sha256=digest,
        )
        try:
            from app.services.sector_analysis_service import sector_analysis_service

            sector_payload = sector_analysis_service.analyze(
                record=snapshot, result=result, persist_run_id=run.id
            )
            workspace["sectorAnalysis"] = sector_payload.model_dump(mode="json")
        except Exception:
            logger.exception("Snapshot analyse sectorielle impossible")
    except Exception:
        logger.exception("Persistance AnalysisRun impossible")
    dossier_store.update_analyse(
        dossier_id,
        analyse_job_id=job.job_id if job else None,
        analyse_status="completed",
        analyse=workspace,
        score=score,
        status=next_status,
    )
    kafka_publisher.publish_scoring_event(
        "scoring.job.completed",
        job_id=job.job_id if job else "",
        dossier_id=dossier_id,
        filename=job.filename if job else None,
        score=score,
        classe=result.decision.get("classe"),
        decision=result.decision.get("decision"),
        recommandation=result.decision.get("recommandation"),
        completeness_pct=result.completeness_pct,
        pages_processed=result.document.pages_processed,
        pages_total=result.document.pages_total,
    )


async def _run_job_sequential(job_id: str) -> None:
    async with _PIPELINE_LOCK:
        job = job_store.get(job_id)
        if job:
            await asyncio.to_thread(
                kafka_publisher.publish_scoring_event,
                "scoring.job.started",
                job_id=job.job_id,
                dossier_id=job.dossier_id,
                filename=job.filename,
            )
        await run_scoring_job(job_id, store=job_store, on_completed=_persist_result)
    job = job_store.get(job_id)
    if job and job.status == "failed":
        record = dossier_store.get_by_id(job.dossier_id)
        if record is None:
            return
        next_status = "pending" if record.status == "analyzing" else record.status
        dossier_store.update_analyse(
            job.dossier_id,
            analyse_job_id=job.job_id,
            analyse_status="failed",
            status=next_status,
        )
        await asyncio.to_thread(
            kafka_publisher.publish_scoring_event,
            "scoring.job.failed",
            job_id=job.job_id,
            dossier_id=job.dossier_id,
            filename=job.filename,
            error=job.error,
        )


@router.post("/dossiers/{dossier_id}/analyse/jobs", response_model=AnalyseJobCreateResponse)
async def start_analyse_job(
    dossier_id: str,
    background_tasks: BackgroundTasks,
    max_pages: Optional[int] = None,
) -> AnalyseJobCreateResponse:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if max_pages is not None and (max_pages < 1 or max_pages > config.DIRECT_FINANCIAL_MAX_PAGES):
        raise HTTPException(status_code=422, detail="max_pages invalide")

    existing = job_store.get_for_dossier(dossier_id)
    if existing and existing.status in {"queued", "processing"}:
        return AnalyseJobCreateResponse(
            job_id=existing.job_id,
            dossier_id=dossier_id,
            status=existing.status,
            stream_url=f"/api/v1/analyse/jobs/{existing.job_id}/stream",
            result_url=f"/api/v1/analyse/jobs/{existing.job_id}/result",
            filename=existing.filename,
        )

    primary, extras = _pick_liasses(record)
    job = job_store.create(
        dossier_id=dossier_id,
        filename=primary.filename,
        max_pages=max_pages,
        primary_document=primary,
        extra_documents=extras,
    )
    previous = record.status
    dossier_store.update_analyse(
        dossier_id,
        analyse_job_id=job.job_id,
        analyse_status="processing",
        status="analyzing" if previous in {"pending", "ready", "analyzing"} else previous,
    )
    from app.jobs.factory import get_job_dispatcher

    await get_job_dispatcher(_run_job_sequential).dispatch_analysis(job.job_id)
    await asyncio.to_thread(
        kafka_publisher.publish_scoring_event,
        "scoring.job.queued",
        job_id=job.job_id,
        dossier_id=dossier_id,
        filename=primary.filename,
        company=record.name,
        sector=record.sector,
    )
    return AnalyseJobCreateResponse(
        job_id=job.job_id,
        dossier_id=dossier_id,
        status="queued",
        stream_url=f"/api/v1/analyse/jobs/{job.job_id}/stream",
        result_url=f"/api/v1/analyse/jobs/{job.job_id}/result",
        filename=primary.filename,
    )


@router.get("/dossiers/{dossier_id}/analyse", response_model=AnalyseStateResponse)
def get_analyse_state(dossier_id: str) -> AnalyseStateResponse:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    job = job_store.get_for_dossier(dossier_id)
    if record.status == "analyzing" and job is None:
        next_status = "ready" if record.analyse else "pending"
        updated = dossier_store.update_analyse(
            dossier_id,
            analyse_status="completed" if record.analyse else None,
            status=next_status,
        )
        if updated is not None:
            record = updated
        job = job_store.get_for_dossier(dossier_id)
    workspace = overlay_live_documents(record, record.analyse or empty_workspace(record))
    error = None
    progress = job_store.to_progress(job) if job else None
    if job and job.status == "failed":
        error = job.error
    if job and job.status == "completed" and job.result is not None and not record.analyse:
        workspace = build_workspace(record, job.result)
    try:
        from app.services.sector_analysis_service import sector_analysis_service

        live_result = job.result if job and getattr(job, "result", None) is not None else None
        workspace["sectorAnalysis"] = sector_analysis_service.analyze(
            record=record,
            result=live_result,
        ).model_dump(mode="json")
    except Exception:
        logger.exception("Analyse sectorielle live impossible")
    return AnalyseStateResponse(
        dossier_id=dossier_id,
        job=progress,
        workspace=workspace,
        error=error,
    )


def _attention_from_workspace(workspace: dict | None) -> dict:
    scoring = (workspace or {}).get("scoring") or {}
    attention = scoring.get("attention") or {}
    return {
        "points_forts": attention.get("pointsForts") or [],
        "points_vigilance": attention.get("pointsVigilance") or [],
        "score_final": attention.get("scoreFinal") or None,
    }


@router.get("/dossiers/{dossier_id}/synthese", response_model=DossierSyntheseResponse)
def get_dossier_synthese(dossier_id: str) -> DossierSyntheseResponse:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    job = job_store.get_for_dossier(dossier_id)
    job_status = job.status if job else (record.analyseStatus or "pending")
    attention = _attention_from_workspace(record.analyse)
    if job and job.status == "completed" and job.result is not None and not attention["score_final"]:
        from app.services.synthese_builder import build_synthese

        built = build_synthese(job.result, nouveau_financement=float(record.amount or 0) or None)
        attention = {
            "points_forts": built["pointsForts"],
            "points_vigilance": built["pointsVigilance"],
            "score_final": built["scoreFinal"],
        }

    message = None
    if job_status in {"queued", "processing"}:
        message = "Analyse en file d'attente ou en cours — les points d'attention seront disponibles à la fin du job."
    elif job_status == "failed":
        message = (job.error if job else None) or "L'analyse a échoué."
    elif not attention["score_final"]:
        message = "Aucune analyse n'a encore été exécutée sur ce dossier."
        job_status = job_status or "pending"

    decision = {}
    if record.analyse:
        scoring = record.analyse.get("scoring") or {}
        decision = {
            "score": scoring.get("score"),
            "classe": None,
            "decision": scoring.get("riskLabel"),
            "recommandation": scoring.get("recommendation"),
        }
    if job and job.result is not None:
        decision = job.result.decision or decision

    return DossierSyntheseResponse(
        dossier_id=dossier_id,
        status=job_status,
        job_id=job.job_id if job else record.analyseJobId,
        points_forts=attention["points_forts"],
        points_vigilance=attention["points_vigilance"],
        score_final=attention["score_final"],
        score=int(round(float(decision["score"]))) if decision.get("score") is not None else record.score or None,
        classe=decision.get("classe"),
        decision=decision.get("decision"),
        recommandation=decision.get("recommandation"),
        message=message,
    )


@router.post("/dossiers/{dossier_id}/copilot", response_model=CopilotChatResponse)
async def chat_copilot(dossier_id: str, payload: CopilotChatRequest) -> CopilotChatResponse:
    record = dossier_store.get_by_id(dossier_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    from app.services.copilot_service import ask_copilot

    try:
        result = await asyncio.to_thread(
            ask_copilot,
            record,
            payload.message,
            [item.model_dump() for item in payload.history],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Copilote Qwen a échoué")
        raise HTTPException(status_code=503, detail=f"Copilote Qwen indisponible : {exc}") from exc
    return CopilotChatResponse(**result)


@router.get("/analyse/jobs/{job_id}", response_model=AnalyseJobProgress)
def get_analyse_job(job_id: str) -> AnalyseJobProgress:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    return job_store.to_progress(job)


@router.get("/analyse/jobs/{job_id}/stream")
async def stream_analyse_job(job_id: str) -> StreamingResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    queue = job_store.subscribe(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Job introuvable.")

    async def event_generator() -> AsyncIterator[str]:
        try:
            progress = job_store.to_progress(job)
            yield f"event: job_status\ndata: {progress.model_dump_json()}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    current = job_store.get(job_id)
                    if current is None or current.status in {"completed", "failed"}:
                        break
                    continue
                event_type = event.get("event", "message")
                payload = json.dumps(event, ensure_ascii=False, default=str)
                yield f"event: {event_type}\ndata: {payload}\n\n"
                if event_type in {"result_ready", "job_failed"}:
                    break
        finally:
            job_store.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/analyse/jobs/{job_id}/result", response_model=ScoringAnalysisResult)
def get_analyse_result(job_id: str) -> ScoringAnalysisResult:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable ou expiré.")
    if job.status == "failed":
        raise HTTPException(status_code=422, detail=job.error or "Le job a échoué.")
    if job.status != "completed" or job.result is None:
        raise HTTPException(status_code=409, detail="Le résultat n'est pas encore disponible.")
    return job.result
