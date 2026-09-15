from __future__ import annotations

from enum import Enum

from app.schemas.create_dossier import StoredDossierRecord


class DocumentType(str, Enum):
    LIASSE_FISCALE = "LIASSE_FISCALE"
    PROFORMA = "PROFORMA"
    REGISTRE_COMMERCE = "REGISTRE_COMMERCE"
    RELEVE_BANCAIRE = "RELEVE_BANCAIRE"
    PIECE_IDENTITE = "PIECE_IDENTITE"
    AUTRE = "AUTRE"


def _kind(name: str) -> DocumentType:
    n = (name or "").lower()
    if "proforma" in n or "facture" in n:
        return DocumentType.PROFORMA
    if "liasse" in n or "bilan" in n or "cpc" in n:
        return DocumentType.LIASSE_FISCALE
    if "relev" in n or "bancaire" in n:
        return DocumentType.RELEVE_BANCAIRE
    if "rc" in n or "commerce" in n or "kbis" in n:
        return DocumentType.REGISTRE_COMMERCE
    if "cin" in n:
        return DocumentType.PIECE_IDENTITE
    return DocumentType.AUTRE


def evaluate_checklist(record: StoredDossierRecord) -> dict:
    present = {_kind(f.name) for f in record.files}
    if any(f.category == "proforma" for f in record.files):
        present.add(DocumentType.PROFORMA)
    requirements = [
        {"type": DocumentType.LIASSE_FISCALE.value, "required": True, "required_for": "FINANCIAL_ANALYSIS", "reason": "Liasse nécessaire au scoring financier."},
        {"type": DocumentType.PROFORMA.value, "required": True, "required_for": "FINAL_DECISION", "reason": "Proforma nécessaire à la décision."},
        {"type": DocumentType.RELEVE_BANCAIRE.value, "required": False, "required_for": "BEHAVIORAL_ANALYSIS", "reason": "Relevés nécessaires à l'axe comportemental."},
        {"type": DocumentType.REGISTRE_COMMERCE.value, "required": False, "required_for": "FINAL_DECISION", "reason": "RC dossier facultatif si identité bilan présente."},
    ]
    missing = [r for r in requirements if r["required"] and DocumentType(r["type"]) not in present]
    extraction_ok = bool(record.analyse)
    scoring_ok = bool((record.analyse or {}).get("readiness", {}).get("ready_for_automatic_scoring"))
    decision_ok = not missing
    n_req = max(len([r for r in requirements if r["required"]]), 1)
    n_ok = n_req - len(missing)
    return {
        "requirements": requirements,
        "present": [t.value for t in present],
        "missing": missing,
        "document_completeness_pct": round(100 * n_ok / n_req),
        "extraction_completeness_pct": 100 if extraction_ok else 0,
        "scoring_completeness_pct": 100 if scoring_ok else 0,
        "decision_completeness_pct": 100 if decision_ok else 0,
    }


def documents_ready_for_decision(record: StoredDossierRecord) -> bool:
    kinds = {_kind(f.name) for f in record.files}
    if any(f.category == "proforma" for f in record.files):
        kinds.add(DocumentType.PROFORMA)
    return DocumentType.PROFORMA in kinds and DocumentType.LIASSE_FISCALE in kinds
