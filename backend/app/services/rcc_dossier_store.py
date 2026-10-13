"""Dossiers RCC (poste branché sur le pipeline scoring WFB).

Les dossiers sont gardés en mémoire pour la rapidité et enregistrés dans la base SQLite
(tables rcc_dossiers / rcc_audit_events, voir rcc_persistence) : ils survivent aux
redémarrages de l'API.
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.schemas.analyse import RCC_ELEMENTS, SCORING_EXTRA_ELEMENTS, ScoringAnalysisResult
from app.services import rcc_persistence
from app.services.ia_clients_service import resolve_tiers
from app.services.rcc_projection import build_identite, clean_activite, export_rcc_clean, project_rcc_result

STATUS_LABELS = {
    "pending": "À réviser",
    "validated": "Validé",
    "rejected": "Rejeté",
    "escalated": "Arbitrage demandé",
}

logger = logging.getLogger(__name__)

FIELD_LABELS = {
    code: label for _, code, label, _ in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RccOverride:
    field_code: str
    original_value: float | None
    corrected_value: float | None
    edited_by: str
    edited_at: str
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "field_code": self.field_code,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "edited_by": self.edited_by,
            "edited_at": self.edited_at,
            "verified": self.verified,
        }


@dataclass
class RccDossier:
    id: str
    job_id: str | None
    client_name: str
    ice: str | None
    credit_amount: float | None
    exercice_date: str | None
    status: str
    created_at: str
    updated_at: str
    sector: str | None
    filename: str | None
    pdf_path: str | None
    completeness_pct: float
    result: dict[str, Any] | None
    scoring_result: Any
    identite: dict[str, Any] = field(default_factory=dict)
    overrides: list[RccOverride] = field(default_factory=list)
    motif: str | None = None
    comment: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None
    bilans_push: dict[str, Any] | None = None

    origin: str = "rcc"

    def summary(self) -> dict[str, Any]:
        # N° tiers réellement retenu pour Ekip (vide tant qu'un choix est attendu).
        tiers = resolve_tiers(self.identite)
        return {
            "id": self.id,
            "job_id": self.job_id,
            "client_name": self.client_name,
            "ice": self.ice,
            "credit_amount": self.credit_amount,
            "exercice_date": self.exercice_date,
            "status": self.status,
            "status_label": STATUS_LABELS.get(self.status, self.status),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sector": clean_activite(self.identite.get("secteur"), self.sector),
            "filename": self.filename,
            "has_document": bool(self.pdf_path and Path(self.pdf_path).exists()),
            "completeness_pct": self.completeness_pct,
            "override_count": len(self.overrides),
            "motif": self.motif,
            "comment": self.comment,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "identite": {**self.identite, "tiers": tiers},
            "identifiant_fiscal": self.identite.get("identifiant_fiscal"),
            "taxe_professionnelle": self.identite.get("taxe_professionnelle"),
            "adresse": self.identite.get("adresse"),
            "ville": self.identite.get("ville"),
            "activite": clean_activite(self.identite.get("activite")),
            "period_start": self.identite.get("period_start"),
            "period_end": self.identite.get("period_end") or self.exercice_date,
            "declaration_date": self.identite.get("declaration_date"),
            "declaration_time": self.identite.get("declaration_time"),
            "reference": self.identite.get("reference"),
            "tiers": tiers,
            "tiers_source": self.identite.get("tiers_source"),
            "client_lookup": self.identite.get("client_lookup"),
            "rc": self.identite.get("rc"),
            "bilans_push": self.bilans_push,
            "origin": self.origin,
        }

    def detail(self) -> dict[str, Any]:
        data = self.summary()
        data["result"] = self.result
        data["overrides"] = [item.as_dict() for item in self.overrides]
        return data


_NOT_SERIALIZED = {"overrides", "scoring_result"}


def dossier_to_payload(dossier: "RccDossier") -> dict[str, Any]:
    """Dossier → dict JSON (résultat scoring complet inclus, pour l'export et l'envoi Ekip)."""
    data = {f.name: getattr(dossier, f.name) for f in fields(dossier) if f.name not in _NOT_SERIALIZED}
    data["overrides"] = [item.as_dict() for item in dossier.overrides]
    scoring = dossier.scoring_result
    data["scoring_result"] = scoring.model_dump(mode="json") if hasattr(scoring, "model_dump") else None
    return data


def dossier_from_payload(data: dict[str, Any]) -> "RccDossier":
    scoring = None
    if data.get("scoring_result"):
        try:
            scoring = ScoringAnalysisResult.model_validate(data["scoring_result"])
        except Exception:
            logger.warning("Résultat scoring illisible pour le dossier RCC %s.", data.get("id"))
    known = {f.name for f in fields(RccDossier)} - _NOT_SERIALIZED
    values = {key: value for key, value in data.items() if key in known}
    return RccDossier(
        **values,
        overrides=[RccOverride(**item) for item in data.get("overrides") or []],
        scoring_result=scoring,
    )


_SEQ_RE = re.compile(r"^RCC-\d{4}-(\d+)$")


class RccDossierStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, RccDossier] = {}
        self._by_job: dict[str, str] = {}
        self._seq = 0
        self._audit: list[dict[str, Any]] = []
        self._hidden_scoring: set[str] = set()
        self._loaded = False
        self._pdf_dir = settings.files_dir / "rcc-pdfs"
        self._pdf_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_loaded(self) -> None:
        """Recharge, au premier accès, les dossiers et l'audit enregistrés en base."""
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            dossiers, audit = rcc_persistence.load_all()
            for data in dossiers:
                try:
                    dossier = dossier_from_payload(data)
                except Exception:
                    logger.exception("Dossier RCC illisible en base : %s", data.get("id"))
                    continue
                self._items[dossier.id] = dossier
                if dossier.job_id:
                    self._by_job[dossier.job_id] = dossier.id
                match = _SEQ_RE.match(dossier.id)
                if match:
                    self._seq = max(self._seq, int(match.group(1)))
            self._audit = audit + self._audit
            self._hidden_scoring |= rcc_persistence.load_hidden_scoring()

    def _persist(self, dossier: RccDossier) -> None:
        rcc_persistence.save_dossier(dossier_to_payload(dossier))

    def add_audit(self, event: dict[str, Any]) -> None:
        """Ajoute un évènement à la piste d'audit (mémoire + base)."""
        with self._lock:
            self._ensure_loaded()
            self._audit.append(event)
            rcc_persistence.add_audit(event)

    def save_pdf(self, job_id: str, content: bytes) -> Path:
        path = self._pdf_dir / f"{job_id}.pdf"
        path.write_bytes(content)
        return path

    def find_by_job(self, job_id: str) -> RccDossier | None:
        self._ensure_loaded()
        with self._lock:
            dossier_id = self._by_job.get(job_id)
            return self._items.get(dossier_id) if dossier_id else None

    def get(self, dossier_id: str) -> RccDossier | None:
        self._ensure_loaded()
        with self._lock:
            return self._items.get(dossier_id)

    def put(self, dossier: RccDossier) -> RccDossier:
        self._ensure_loaded()
        with self._lock:
            self._items[dossier.id] = dossier
            if dossier.job_id:
                self._by_job[dossier.job_id] = dossier.id
            self._persist(dossier)
            return dossier

    def _next_id(self) -> str:
        year = datetime.now(timezone.utc).year
        self._seq += 1
        return f"RCC-{year}-{self._seq:04d}"

    def create_from_job(
        self,
        *,
        job_id: str,
        scoring_result: Any,
        filename: str,
        pdf_bytes: bytes | None,
        actor: str,
        client_name: str | None = None,
        ice: str | None = None,
        credit_amount: float | None = None,
        exercice_date: str | None = None,
        sector: str | None = None,
    ) -> RccDossier:
        existing = self.find_by_job(job_id)
        if existing is not None:
            return existing
        projected = project_rcc_result(scoring_result)
        identite = projected.get("identite") or build_identite(scoring_result)
        now = _now()
        pdf_path = None
        if pdf_bytes:
            pdf_path = str(self.save_pdf(job_id, pdf_bytes))
        with self._lock:
            dossier_id = self._next_id()
            dossier = RccDossier(
                id=dossier_id,
                job_id=job_id,
                client_name=client_name or identite.get("raison_sociale") or filename,
                ice=ice or identite.get("ice"),
                credit_amount=credit_amount,
                exercice_date=exercice_date or identite.get("period_end"),
                status="pending",
                created_at=now,
                updated_at=now,
                sector=sector or identite.get("activite") or identite.get("secteur"),
                filename=filename,
                pdf_path=pdf_path,
                completeness_pct=scoring_result.completeness_pct,
                result=projected,
                scoring_result=scoring_result,
                identite=identite,
            )
            self._items[dossier_id] = dossier
            self._by_job[job_id] = dossier_id
            self._persist(dossier)
            self.add_audit(
                {
                    "kind": "event",
                    "timestamp": now,
                    "actor": actor,
                    "dossier_id": dossier_id,
                    "client_name": dossier.client_name,
                    "field_code": None,
                    "field_label": None,
                    "before": None,
                    "after": None,
                    "action": "Ingestion",
                }
            )
            return dossier

    def list_dossiers(
        self,
        *,
        status: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        self._ensure_loaded()
        with self._lock:
            items = list(self._items.values())
        counts = {"pending": 0, "validated": 0, "rejected": 0, "escalated": 0, "all": len(items)}
        for item in items:
            if item.status in counts:
                counts[item.status] += 1
        if status and status != "all":
            items = [item for item in items if item.status == status]
        if search:
            needle = search.lower()
            items = [
                item
                for item in items
                if needle in item.id.lower()
                or needle in (item.client_name or "").lower()
                or needle in (item.ice or "").lower()
                or needle in (item.identite.get("identifiant_fiscal") or "").lower()
                or needle in (item.identite.get("taxe_professionnelle") or "").lower()
                or needle in (item.identite.get("reference") or "").lower()
            ]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        total = len(items)
        page = items[offset : offset + limit]
        return [item.summary() for item in page], total, counts

    def patch(
        self,
        dossier_id: str,
        payload: dict[str, Any],
        actor: str,
    ) -> RccDossier | None:
        self._ensure_loaded()
        with self._lock:
            dossier = self._items.get(dossier_id)
            if dossier is None:
                return None
            before_status = dossier.status
            for key in ("client_name", "sector", "credit_amount", "exercice_date", "motif", "comment"):
                if key in payload and payload[key] is not None:
                    setattr(dossier, key, payload[key])
            if payload.get("status"):
                dossier.status = payload["status"]
                dossier.decided_by = actor
                dossier.decided_at = _now()
            dossier.updated_at = _now()
            self._persist(dossier)
            if payload.get("status") and payload["status"] != before_status:
                self.add_audit(
                    {
                        "kind": "event",
                        "timestamp": dossier.updated_at,
                        "actor": actor,
                        "dossier_id": dossier.id,
                        "client_name": dossier.client_name,
                        "field_code": None,
                        "field_label": None,
                        "before": before_status,
                        "after": dossier.status,
                        "action": STATUS_LABELS.get(dossier.status, dossier.status),
                    }
                )
            return dossier

    def set_tiers(self, dossier_id: str, tiers: str, source: str, actor: str) -> RccDossier | None:
        """N° tiers choisi dans le référentiel (`selected`) ou saisi (`manual`), tracé dans l'audit."""
        self._ensure_loaded()
        with self._lock:
            dossier = self._items.get(dossier_id)
            if dossier is None:
                return None
            before = resolve_tiers(dossier.identite)
            dossier.identite = {**dossier.identite, "tiers": tiers, "tiers_source": source}
            dossier.updated_at = _now()
            self._persist(dossier)
            self.add_audit(
                {
                    "kind": "event",
                    "timestamp": dossier.updated_at,
                    "actor": actor,
                    "dossier_id": dossier.id,
                    "client_name": dossier.client_name,
                    "field_code": None,
                    "field_label": "N° tiers",
                    "before": before,
                    "after": tiers,
                    "action": "N° tiers choisi" if source == "selected" else "N° tiers saisi",
                }
            )
            return dossier

    def set_identite(self, dossier_id: str, identite: dict[str, Any], action: str, actor: str) -> RccDossier | None:
        """Remplace l'identité (ex. référentiel clients relancé), tracé dans l'audit."""
        self._ensure_loaded()
        with self._lock:
            dossier = self._items.get(dossier_id)
            if dossier is None:
                return None
            before = resolve_tiers(dossier.identite)
            dossier.identite = identite
            dossier.updated_at = _now()
            self._persist(dossier)
            self.add_audit(
                {
                    "kind": "event",
                    "timestamp": dossier.updated_at,
                    "actor": actor,
                    "dossier_id": dossier.id,
                    "client_name": dossier.client_name,
                    "field_code": None,
                    "field_label": "Référentiel clients",
                    "before": before,
                    "after": resolve_tiers(identite),
                    "action": action,
                }
            )
            return dossier

    def mark_bilans_push(self, dossier_id: str, payload: dict[str, Any]) -> RccDossier | None:
        self._ensure_loaded()
        with self._lock:
            dossier = self._items.get(dossier_id)
            if dossier is None:
                return None
            dossier.bilans_push = payload
            dossier.updated_at = _now()
            self._persist(dossier)
            return dossier

    def save_overrides(
        self,
        dossier_id: str,
        overrides: list[dict[str, Any]],
        actor: str,
    ) -> RccDossier | None:
        self._ensure_loaded()
        with self._lock:
            dossier = self._items.get(dossier_id)
            if dossier is None:
                return None
            by_code = {item.field_code: item for item in dossier.overrides}
            fields = {item["code"]: item for item in (dossier.result or {}).get("fields", [])}
            now = _now()
            for raw in overrides:
                code = raw["field_code"]
                original = fields.get(code, {}).get("value")
                item = RccOverride(
                    field_code=code,
                    original_value=original,
                    corrected_value=raw.get("corrected_value"),
                    edited_by=actor,
                    edited_at=now,
                    verified=bool(raw.get("verified")),
                )
                by_code[code] = item
                self.add_audit(
                    {
                        "kind": "correction",
                        "timestamp": now,
                        "actor": actor,
                        "dossier_id": dossier.id,
                        "client_name": dossier.client_name,
                        "field_code": code,
                        "field_label": FIELD_LABELS.get(code, code),
                        "before": None if original is None else str(original),
                        "after": None if item.corrected_value is None else str(item.corrected_value),
                        "action": "Vérification" if item.verified else "Correction",
                    }
                )
            dossier.overrides = list(by_code.values())
            dossier.updated_at = now
            self._persist(dossier)
            return dossier

    def delete(self, dossier_id: str) -> bool:
        self._ensure_loaded()
        with self._lock:
            dossier = self._items.pop(dossier_id, None)
            if dossier is None:
                return False
            if dossier.job_id:
                self._by_job.pop(dossier.job_id, None)
            rcc_persistence.delete_dossier(dossier_id)
            return True

    def is_hidden_scoring(self, dossier_id: str) -> bool:
        self._ensure_loaded()
        with self._lock:
            return dossier_id in self._hidden_scoring

    def hide_scoring(self, dossier_id: str, client_name: str, actor: str) -> None:
        """Masque un dossier Étude de risque dans RCC (le dossier scoring n'est pas touché)."""
        self._ensure_loaded()
        with self._lock:
            if dossier_id in self._hidden_scoring:
                return
            now = _now()
            self._hidden_scoring.add(dossier_id)
            rcc_persistence.hide_scoring(dossier_id, actor, now)
            self.add_audit(
                {
                    "kind": "event",
                    "timestamp": now,
                    "actor": actor,
                    "dossier_id": dossier_id,
                    "client_name": client_name,
                    "field_code": None,
                    "field_label": None,
                    "before": None,
                    "after": None,
                    "action": "Masqué dans RCC (dossier Étude de risque)",
                }
            )

    def audit_all(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        with self._lock:
            return list(reversed(self._audit))

    def audit_for(self, dossier_id: str) -> list[dict[str, Any]]:
        self._ensure_loaded()
        with self._lock:
            return [item for item in reversed(self._audit) if item["dossier_id"] == dossier_id]


def effective_values(dossier: RccDossier) -> dict[str, Optional[float]]:
    values: dict[str, Optional[float]] = {}
    for item in (dossier.result or {}).get("fields", []):
        values[item["code"]] = item.get("value")
    for override in dossier.overrides:
        if override.corrected_value is not None:
            values[override.field_code] = override.corrected_value
    return values


def export_dossier_clean(dossier: RccDossier) -> dict[str, Any]:
    identite = dict(dossier.identite or {})
    if dossier.scoring_result is None:
        return {
            **identite,
            "raison_sociale": identite.get("raison_sociale") or dossier.client_name,
            "ice": identite.get("ice") or dossier.ice,
            "tiers": resolve_tiers(identite),
            "postes": {},
        }
    payload = export_rcc_clean(dossier.scoring_result)
    values = effective_values(dossier)
    for code, value in values.items():
        key = code.lower()
        if key in payload["postes"]:
            payload["postes"][key]["n"] = value
    payload.update({key: identite.get(key, payload.get(key)) for key in identite})
    payload["raison_sociale"] = payload.get("raison_sociale") or dossier.client_name
    payload["ice"] = payload.get("ice") or dossier.ice
    # N° tiers retenu (unique, choisi ou saisi) : celui envoyé à Ekip.
    payload["tiers"] = resolve_tiers(identite)
    payload["dossier_id"] = dossier.id
    payload["statut"] = dossier.status
    return payload


rcc_dossier_store = RccDossierStore()
