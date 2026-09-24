"""Pipeline scoring — extracteur financier V6 + ratios + note 3 axes.

L'extraction de la liasse (identité, bilan, CPC, ESG/CAF) est déléguée à
`financial_pdf_extractor-V6_corrected.py`, sans modification de ce fichier.
Ce module projette le JSON V6 vers le contrat API Scoring existant.
"""
from __future__ import annotations

import asyncio
import logging
import queue
import re
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from app import config
from app.schemas.analyse import (
    RCC_ELEMENTS,
    SCORING_EXTRA_ELEMENTS,
    AccountingControlView,
    CompanyInfo,
    DocumentSummary,
    ExerciseInfo,
    ExtractedField,
    ExtractionSummary,
    FieldEvidence,
    FinancialPageAudit,
    ScoringAnalysisResult,
    YearsBlock,
)
from app.services import ocr_lab_core_v10 as engine
from app.services import ratio_engine, scoring_engine
from app.services.identity_extract import _extract_rc
from app.services.quality_gate import evaluate_quality
from app.services.v6_extractor_bridge import run_v6_from_bytes
from app.services.v6_result_mapper import (
    document_from_v6,
    extraction_summary,
    identity_from_v6,
    identity_warnings,
    map_capital_analysis,
    map_controls,
    map_fields,
    map_fiscal_analysis,
    map_page_audit,
)

logger = logging.getLogger(__name__)

ProgressEmitter = Callable[[str, dict[str, Any]], None]

# --- Correspondances moteur → API -------------------------------------------

# Codes d'évidence internes du moteur alimentant chaque poste RCC
# (miroir de `resolve_rcc` / `_propagate_validation_status`).
_EVIDENCE_CODES: dict[str, list[str]] = {
    "ACTIFS_IMMOBILISES": ["ACTIFS_IMMOBILISES"],
    "TOTAL_BILAN": ["TOTAL_ACTIF"],
    "CHIFFRE_AFFAIRES": ["CHIFFRE_AFFAIRES", "VENTES_BIENS_SERVICES", "VENTES_MARCHANDISES"],
    "CA_EXPORT": ["EXPORT_MARCHANDISES", "EXPORT_BIENS", "EXPORT_SERVICES"],
    "DETTES_BANCAIRES_MLT": ["DETTES_FINANCEMENT"],
    "DETTES_BANCAIRES_CT": ["DETTES_BANCAIRES_CT"],
    "PASSIF_CIRCULANT": ["PASSIF_CIRCULANT"],
    "DETTES_FOURNISSEURS": ["FOURNISSEURS"],
    "COMPTE_COURANT_ASSOCIES": ["COMPTE_COURANT_ASSOCIES"],
    "TRESORERIE_PASSIF": ["TRESORERIE_PASSIF"],
    "ACTIF_CIRCULANT": ["ACTIF_CIRCULANT"],
    "CREANCES_CLIENTS": ["CLIENTS"],
    "TRESORERIE_ACTIF": ["TRESORERIE_ACTIF"],
    "CAISSE": ["CAISSE"],
    "ACHATS_REVENDUS": ["ACHATS_REVENDUS", "ACHATS_REVENDUS_TOTAL"],
    "ACHATS_CONSOMMES": ["ACHATS_CONSOMMES", "ACHATS_CONSOMMES_TOTAL"],
    "AUTRES_CHARGES_EXTERNES": ["AUTRES_CHARGES_EXTERNES", "AUTRES_CHARGES_EXTERNES_TOTAL"],
    "CHARGES_INTERETS": ["CHARGES_INTERETS"],
    "RESULTAT_NET": ["RESULTAT_NET"],
    "TYPE_RESULTAT": [],
    "FONDS_PROPRES": ["FONDS_PROPRES"],
    "STOCKS": ["STOCKS"],
    "RESULTAT_EXPLOITATION": ["RESULTAT_EXPLOITATION"],
    "DOTATIONS_EXPLOITATION": ["DOTATIONS_EXPLOITATION"],
    "CAF": ["CAF", "CAPACITE_AUTOFINANCEMENT"],
}

_EVIDENCE_TO_RCC: dict[str, str] = {
    code: rcc_code
    for rcc_code, codes in _EVIDENCE_CODES.items()
    for code in codes
}
_EVIDENCE_TO_RCC["TOTAL_PASSIF"] = "TOTAL_BILAN"
_EVIDENCE_TO_RCC["PASSIF_TOTAL_I"] = "PASSIF_CIRCULANT"

# Colonne portant la valeur de l'exercice courant, par type de page
# (identique à `engine.value_from_row`).
_VALUE_COLUMNS: dict[str, list[str]] = {
    "BILAN_ACTIF": ["NET_N"],
    "BILAN_PASSIF": ["EXERCICE_N"],
    "CPC": ["TOTAL_N", "OP_N"],
    "DETAIL_CPC": ["EXERCICE_N"],
}
_N1_COLUMN: dict[str, str] = {
    "BILAN_ACTIF": "NET_N1",
    "BILAN_PASSIF": "EXERCICE_N1",
    "CPC": "TOTAL_N1",
    "DETAIL_CPC": "EXERCICE_N1",
}
# Postes pour lesquels l'exercice N-1 est lu sur la même ligne de la liasse.
_N1_CODES = frozenset({
    "CHIFFRE_AFFAIRES",
    "CA_EXPORT",
    "RESULTAT_NET",
    "TOTAL_BILAN",
    "DETTES_BANCAIRES_MLT",
    "DETTES_BANCAIRES_CT",
    "FONDS_PROPRES",
    "ACTIFS_IMMOBILISES",
    "RESULTAT_EXPLOITATION",
    "DOTATIONS_EXPLOITATION",
    "STOCKS",
    "CREANCES_CLIENTS",
    "DETTES_FOURNISSEURS",
    "TRESORERIE_ACTIF",
    "TRESORERIE_PASSIF",
    "ACTIF_CIRCULANT",
    "PASSIF_CIRCULANT",
    "CAF",
})

# Statuts du moteur → statuts de l'API (confirmed|derived|ambiguous|conflicting|missing).
_STATUS_MAP: dict[str, str] = {
    "confirmed": "confirmed",
    "cross_validated": "confirmed",
    "low_confidence": "ambiguous",
    "needs_review": "ambiguous",
    "derived": "derived",
    "partial": "derived",
    "proxy": "derived",
    "blank_on_form": "missing",
    "missing": "missing",
    "conflicting": "conflicting",
    "conflicting_blank_vs_value": "conflicting",
}

# Statut moteur → mention affichée en badge sur la ligne du poste. Volontairement
# court : le détail chiffré part dans les avertissements d'extraction.
_NOTE_FR: dict[str, str] = {
    "cross_validated": "Recoupé sur 2 pages",
    "low_confidence": "Lecture à confirmer",
    "needs_review": "Contrôle non levé",
    "derived": "Calculé depuis les lignes imprimées",
    "partial": "Somme partielle",
    "blank_on_form": "Ligne vide sur la liasse",
    "conflicting": "Valeurs divergentes",
    "conflicting_blank_vs_value": "Cellule vide contre montant",
}

_PROXY_NOTES: dict[str, str] = {
    "DETTES_BANCAIRES_MLT": "Proxy : dettes de financement",
    "CHIFFRE_AFFAIRES": "Proxy : ligne de ventes",
}

_CONTROL_LABELS: dict[str, str] = {
    "ACTIF_ROW_BRUT_MINUS_AMORT_EQUALS_NET": "Bilan actif : Brut − Amortissements = Net",
    "CPC_OPS_SUM_TO_TOTAL_N": "CPC : opérations de l'exercice + exercices antérieurs = total",
    "BILAN_ACTIF_I_PLUS_II_PLUS_III_EQUALS_TOTAL": "Bilan actif : immobilisé + circulant + trésorerie = total actif",
    "BILAN_PASSIF_I_PLUS_II_PLUS_III_EQUALS_TOTAL": "Bilan passif : permanent + circulant + trésorerie = total passif",
    "CPC_VENTES_SUM_EQUALS_CHIFFRE_AFFAIRES": "CPC : ventes marchandises + ventes biens et services = chiffre d'affaires",
    "TOTAL_ACTIF_EQUALS_TOTAL_PASSIF": "Total Actif = Total Passif",
    "RESULTAT_NET_RESOLVED_EQUALS_PASSIF": "Résultat net du CPC = résultat net inscrit au passif",
}
# L'écran de validation cherche ce code pour la bannière d'équilibre du bilan.
_CONTROL_CODES: dict[str, str] = {
    "TOTAL_ACTIF_EQUALS_TOTAL_PASSIF": "bilan_equilibre",
    "ACTIF_ROW_BRUT_MINUS_AMORT_EQUALS_NET": "actif_brut_amort_net",
    "CPC_OPS_SUM_TO_TOTAL_N": "cpc_operations_total",
    "BILAN_ACTIF_I_PLUS_II_PLUS_III_EQUALS_TOTAL": "bilan_actif_totaux",
    "BILAN_PASSIF_I_PLUS_II_PLUS_III_EQUALS_TOTAL": "bilan_passif_totaux",
    "CPC_VENTES_SUM_EQUALS_CHIFFRE_AFFAIRES": "cpc_ventes_chiffre_affaires",
    "RESULTAT_NET_RESOLVED_EQUALS_PASSIF": "resultat_net",
}
# Contrôles produits ligne par ligne : agrégés en une seule vue lisible.
_ROW_LEVEL_CHECKS = frozenset(
    {"ACTIF_ROW_BRUT_MINUS_AMORT_EQUALS_NET", "CPC_OPS_SUM_TO_TOTAL_N"}
)

_RCC_LABELS: dict[str, str] = {
    code: label for _, code, label, _ in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)
}


# --- Utilitaires -------------------------------------------------------------


def _clean(value: Any) -> Any:
    """Neutralise les NaN/NaT que pandas produit sur les colonnes creuses."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _to_float(value: Any) -> float | None:
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    parsed = engine.parse_amount(str(value))
    return float(parsed) if parsed is not None else None


def _first_page(value: Any) -> int | None:
    """Le moteur peut renvoyer « 3 » ou « 3,4 » pour un poste multi-pages."""
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    for chunk in str(value).replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            return int(chunk)
    return None


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ")


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    return [
        {key: _clean(val) for key, val in record.items()}
        for record in frame.to_dict("records")
    ]


def _row_value(row: engine.EvidenceRow) -> tuple[str | None, str | None]:
    """Cellule (valeur brute, nom de colonne) portant l'exercice courant."""
    for column in _VALUE_COLUMNS.get(row.page_type, []):
        raw = row.cells.get(column)
        if raw and engine.parse_amount(raw) is not None:
            return raw, column
    return row.cells.get("TEXT"), None


# --- Client moteur -----------------------------------------------------------


def build_client() -> engine.OllamaClient:
    """Client Ollama du moteur v10, paramétré par la configuration de l'app."""
    engine.REQUEST_TIMEOUT = config.RCC_REQUEST_TIMEOUT_SECONDS
    engine.KEEP_ALIVE = config.RCC_KEEP_ALIVE
    engine.RENDER_DPI = config.RCC_RENDER_DPI
    engine.EXTRACT_MAX_SIDE = config.RCC_EXTRACT_MAX_SIDE
    return engine.OllamaClient(
        base_url=config.RCC_OLLAMA_URL,
        model=config.RCC_VISION_MODEL,
        mapper_model=config.RCC_MAPPER_MODEL,
        adjudicator_model=config.RCC_ADJUDICATOR_MODEL,
        ocr_model=config.RCC_OCR_MODEL,
        verify_model=config.RCC_VERIFY_MODEL,
    )


# --- Projection moteur → RccAnalysisResult -----------------------------------


def _identification(evidence: list[engine.EvidenceRow]) -> tuple[CompanyInfo, ExerciseInfo]:
    values: dict[str, str] = {}
    for row in evidence:
        if row.page_type != "IDENTIFICATION":
            continue
        raw = (row.cells.get("TEXT") or "").strip()
        if raw and row.field_code not in values:
            values[row.field_code] = raw

    ice = values.get("ICE")
    if ice:
        digits = re.sub(r"\D", "", ice)
        ice = digits if len(digits) == 15 else ice
    rc = values.get("RC")
    ville = values.get("VILLE")
    if ville and re.match(r"^\d{2,3}\.\d{2}\.\d{2}", ville.strip()):
        ville = None

    debut = values.get("EXERCICE_DEBUT")
    fin = values.get("EXERCICE_FIN")
    label = None
    if debut and fin:
        label = f"Du {debut} au {fin}"
    elif fin:
        label = f"Clôture au {fin}"

    return (
        CompanyInfo(
            raison_sociale=values.get("RAISON_SOCIALE"),
            identifiant_fiscal=values.get("IDENTIFIANT_FISCAL"),
            ice=ice,
            rc=rc,
            adresse=values.get("ADRESSE"),
            ville=ville,
        ),
        ExerciseInfo(debut=debut, fin=fin, label=label),
    )


def _page_audit(
    audit_rows: list[dict[str, Any]],
    evidence: list[engine.EvidenceRow],
) -> list[FinancialPageAudit]:
    rows_by_page: dict[int, int] = {}
    for row in evidence:
        rows_by_page[row.page] = rows_by_page.get(row.page, 0) + 1

    pages: list[FinancialPageAudit] = []
    for record in audit_rows:
        page_no = int(record.get("page") or 0)
        page_type = str(record.get("page_type") or "AUTRE")
        if page_type not in engine.ALL_PAGE_TYPES:
            page_type = "AUTRE"
        error = record.get("extraction_error")
        candidates = rows_by_page.get(page_no, 0)

        if error:
            status = "failed"
        elif page_type not in engine.RELEVANT_PAGE_TYPES:
            status = "skipped"
        elif candidates:
            status = "processed"
        else:
            status = "empty"

        rotation = record.get("rotation")
        orientation = int(rotation) % 360 if rotation is not None else 0
        if orientation not in {0, 90, 180, 270}:
            orientation = 0

        strategy = str(record.get("mode") or "scan_glm")
        mode = record.get("scan_extraction_mode")
        if mode:
            strategy = f"{strategy}:{mode}"

        pages.append(
            FinancialPageAudit(
                page_number=page_no,
                detected_type=page_type,  # type: ignore[arg-type]
                orientation=orientation,  # type: ignore[arg-type]
                extraction_status=status,  # type: ignore[arg-type]
                extraction_strategy=strategy,
                candidates_count=candidates,
                error=str(error) if error else None,
            )
        )
    return pages


def _field_evidence(
    code: str,
    evidence: list[engine.EvidenceRow],
    *,
    limit: int = 6,
) -> list[FieldEvidence]:
    wanted = set(_EVIDENCE_CODES.get(code, []))
    rows = [row for row in evidence if row.field_code in wanted]
    rows.sort(key=lambda r: (-(r.confidence or 0.0), r.page))

    items: list[FieldEvidence] = []
    seen: set[tuple[Any, ...]] = set()
    for row in rows[: limit * 2]:
        raw_value, column = _row_value(row)
        key = (row.page, row.raw_label, raw_value, column)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            FieldEvidence(
                page_number=row.page,
                raw_label=row.raw_label,
                raw_value=raw_value,
                column_name=column,
                page_type=row.page_type,
                confidence=row.confidence,
                source_excerpt=row.mapping_note or row.source,
            )
        )
        if len(items) >= limit:
            break
    return items


def _value_n1(code: str, value: float | None, evidence: list[engine.EvidenceRow]) -> float | None:
    if code not in _N1_CODES:
        return None
    wanted = set(_EVIDENCE_CODES.get(code, []))
    candidates = [row for row in evidence if row.field_code in wanted]
    if value is not None:
        matched = [
            row
            for row in candidates
            if (v := engine.value_from_row(row)) is not None and abs(float(v) - value) < 0.01
        ]
        candidates = matched or candidates
    for row in sorted(candidates, key=lambda r: (-(r.confidence or 0.0), r.page)):
        column = _N1_COLUMN.get(row.page_type)
        if not column:
            continue
        parsed = engine.parse_amount(row.cells.get(column))
        if parsed is not None:
            return float(parsed)
    return None


def _note_fr(code: str, engine_status: str) -> str | None:
    if engine_status == "proxy":
        return _PROXY_NOTES.get(code, "Valeur approchée")
    return _NOTE_FR.get(engine_status)


def _build_fields(
    rcc_rows: list[dict[str, Any]],
    evidence: list[engine.EvidenceRow],
) -> list[ExtractedField]:
    by_code = {str(row.get("code")): row for row in rcc_rows}
    fields: list[ExtractedField] = []

    for number, code, label, source in RCC_ELEMENTS:
        record = by_code.get(code, {})
        engine_status = str(record.get("status") or "missing")
        raw_value = _clean(record.get("value"))
        # Un contrôle non levé ne doit pas transformer une cellule vide en
        # « à vérifier » : le poste reste manquant.
        if engine_status == "needs_review" and (code == "TYPE_RESULTAT" or _to_float(raw_value) is None):
            engine_status = "missing"
        status = _STATUS_MAP.get(engine_status, "missing")
        confidence = float(record.get("confidence") or 0.0)

        if code == "TYPE_RESULTAT":
            # Poste non numérique : « Bénéficiaire », « Déficitaire » ou « Nul »
            # est porté par la note, que l'interface rend sous forme de tag.
            fields.append(
                ExtractedField(
                    number=number, code=code, label=label, source=source,
                    value=None, status=status, confidence=confidence,
                    note=str(raw_value) if raw_value else None,
                )
            )
            continue

        value = _to_float(raw_value)
        if engine_status == "needs_review":
            # Un contrôle non levé ne doit pas passer pour une lecture sûre.
            confidence = min(confidence, 0.5)

        fields.append(
            ExtractedField(
                number=number,
                code=code,
                label=label,
                source=source,
                value=value,
                status=status,
                note=_note_fr(code, engine_status),
                confidence=max(0.0, min(1.0, confidence)),
                value_n1=_value_n1(code, value, evidence),
                evidence=_field_evidence(code, evidence),
            )
        )

    for number, code, label, source in SCORING_EXTRA_ELEMENTS:
        if source == "Dérivé":
            continue
        fields.append(_field_from_evidence(number, code, label, source, evidence))

    fields.extend(_derived_fields(fields))
    return fields


def _field_from_evidence(
    number: int,
    code: str,
    label: str,
    source: str,
    evidence: list[engine.EvidenceRow],
) -> ExtractedField:
    wanted = set(_EVIDENCE_CODES.get(code, [code]))
    rows = [row for row in evidence if row.field_code in wanted]
    chosen = None
    value = None
    for row in sorted(rows, key=lambda item: (-(item.confidence or 0.0), item.page)):
        parsed = engine.value_from_row(row)
        if parsed is not None:
            chosen = row
            value = float(parsed)
            break
    if chosen is None:
        blank = [row for row in rows if engine.row_present_but_current_blank(row)]
        note = "Ligne vide sur la liasse" if blank else None
        return ExtractedField(
            number=number, code=code, label=label, source=source,
            status="missing", note=note, evidence=_field_evidence(code, evidence),
        )
    confidence = max(0.0, min(1.0, chosen.confidence or 0.0))
    status = "confirmed" if confidence >= 0.8 else "ambiguous"
    return ExtractedField(
        number=number,
        code=code,
        label=label,
        source=source,
        value=value,
        status=status,
        confidence=confidence,
        value_n1=_value_n1(code, value, evidence),
        evidence=_field_evidence(code, evidence),
    )


def _usable(field: ExtractedField | None) -> float | None:
    if field is None or not field.current.usable:
        return None
    return field.current.usable_value


def _n1_of(field: ExtractedField | None) -> float | None:
    if field is None or field.previous is None or not field.previous.usable:
        return None
    return field.previous.usable_value


def _derived_fields(fields: list[ExtractedField]) -> list[ExtractedField]:
    by_code = {item.code: item for item in fields}
    extra: list[ExtractedField] = []

    mlt = _usable(by_code.get("DETTES_BANCAIRES_MLT"))
    ct = _usable(by_code.get("DETTES_BANCAIRES_CT"))
    mlt_n1 = _n1_of(by_code.get("DETTES_BANCAIRES_MLT"))
    ct_n1 = _n1_of(by_code.get("DETTES_BANCAIRES_CT"))
    if mlt is not None:
        extra.append(
            ExtractedField(
                number=26, code="ENDETTEMENT_TERME", label="Endettement à terme",
                source="Dérivé", value=round(mlt, 2), status="derived",
                confidence=by_code["DETTES_BANCAIRES_MLT"].confidence,
                note="Dettes de financement (MLT) — poste Excel « endettement à terme »",
                value_n1=mlt_n1,
            )
        )
    if mlt is not None and ct is not None:
        n1 = None if mlt_n1 is None or ct_n1 is None else round(mlt_n1 + ct_n1, 2)
        extra.append(
            ExtractedField(
                number=25, code="DETTES_FINANCIERES", label="Dettes financières (MLT+CT)",
                source="Dérivé", value=round(mlt + ct, 2), status="derived",
                confidence=min(
                    by_code["DETTES_BANCAIRES_MLT"].confidence,
                    by_code["DETTES_BANCAIRES_CT"].confidence,
                ),
                note="Somme dettes bancaires MLT + CT",
                value_n1=n1,
            )
        )
    elif mlt is not None:
        extra.append(
            ExtractedField(
                number=25, code="DETTES_FINANCIERES", label="Dettes financières (MLT+CT)",
                source="Dérivé", value=round(mlt, 2), status="derived",
                confidence=by_code["DETTES_BANCAIRES_MLT"].confidence,
                note="Dettes MLT (CT non lu)",
                value_n1=mlt_n1,
            )
        )

    actif = _usable(by_code.get("TRESORERIE_ACTIF"))
    passif = _usable(by_code.get("TRESORERIE_PASSIF"))
    if actif is not None and passif is not None:
        ta_n1 = _n1_of(by_code.get("TRESORERIE_ACTIF"))
        tp_n1 = _n1_of(by_code.get("TRESORERIE_PASSIF"))
        extra.append(
            ExtractedField(
                number=27, code="TRESORERIE_NETTE", label="Trésorerie nette",
                source="Dérivé", value=round(actif - passif, 2), status="derived",
                confidence=0.9,
                note="Trésorerie actif − trésorerie passif",
                value_n1=None if ta_n1 is None or tp_n1 is None else round(ta_n1 - tp_n1, 2),
            )
        )

    fp = _usable(by_code.get("FONDS_PROPRES"))
    immo = _usable(by_code.get("ACTIFS_IMMOBILISES"))
    if fp is not None and mlt is not None and immo is not None:
        fp_n1 = _n1_of(by_code.get("FONDS_PROPRES"))
        immo_n1 = _n1_of(by_code.get("ACTIFS_IMMOBILISES"))
        extra.append(
            ExtractedField(
                number=28, code="FDR", label="Fonds de roulement",
                source="Dérivé", value=round(fp + mlt - immo, 2), status="derived",
                confidence=0.85,
                note="(Fonds propres + dettes MLT) − actifs immobilisés",
                value_n1=(
                    None
                    if fp_n1 is None or mlt_n1 is None or immo_n1 is None
                    else round(fp_n1 + mlt_n1 - immo_n1, 2)
                ),
            )
        )

    ac = _usable(by_code.get("ACTIF_CIRCULANT"))
    pc = _usable(by_code.get("PASSIF_CIRCULANT"))
    if ac is not None and pc is not None:
        ac_n1 = _n1_of(by_code.get("ACTIF_CIRCULANT"))
        pc_n1 = _n1_of(by_code.get("PASSIF_CIRCULANT"))
        extra.append(
            ExtractedField(
                number=29, code="BFR", label="Besoin en fonds de roulement",
                source="Dérivé", value=round(ac - pc, 2), status="derived",
                confidence=0.85,
                note="Actif circulant − passif circulant",
                value_n1=(
                    None if ac_n1 is None or pc_n1 is None else round(ac_n1 - pc_n1, 2)
                ),
            )
        )

    rn = _usable(by_code.get("RESULTAT_NET"))
    dap = _usable(by_code.get("DOTATIONS_EXPLOITATION"))
    caf_field = by_code.get("CAF")
    caf = _usable(caf_field)
    if caf is None and rn is not None and dap is not None:
        rn_n1 = _n1_of(by_code.get("RESULTAT_NET"))
        dap_n1 = _n1_of(by_code.get("DOTATIONS_EXPLOITATION"))
        derived_caf = ExtractedField(
                number=30, code="CAF", label="Capacité d'autofinancement",
                source="Dérivé", value=round(rn + dap, 2), status="derived",
                confidence=0.8,
                note="Proxy : résultat net + dotations d'exploitation",
                value_n1=(
                    None if rn_n1 is None or dap_n1 is None else round(rn_n1 + dap_n1, 2)
                ),
        )
        if caf_field is not None:
            fields[:] = [derived_caf if item.code == "CAF" else item for item in fields]
        else:
            extra.append(derived_caf)

    return extra


def _aggregate_row_control(check: str, rows: list[dict[str, Any]]) -> AccountingControlView:
    failed = [row for row in rows if str(row.get("status")) == "failed"]
    affected: list[str] = []
    for row in failed:
        rcc_code = _EVIDENCE_TO_RCC.get(str(row.get("field") or ""))
        if rcc_code and rcc_code not in affected:
            affected.append(rcc_code)

    worst = max(
        (abs(_to_float(row.get("difference")) or 0.0) for row in failed),
        default=0.0,
    )
    if failed:
        details = ", ".join(
            f"page {_first_page(row.get('page')) or '?'} · {row.get('field')}"
            for row in failed[:4]
        )
        message = (
            f"{len(failed)} ligne(s) en écart sur {len(rows)} vérifiée(s) — {details}"
        )
    else:
        message = f"{len(rows)} ligne(s) vérifiée(s), toutes cohérentes."

    return AccountingControlView(
        code=_CONTROL_CODES.get(check, check.lower()),
        status="failed" if failed else "passed",
        label=_CONTROL_LABELS.get(check, check),
        difference=worst if failed else 0.0,
        tolerance=float(engine.ROBUST_ARITH_TOL),
        affected_fields=affected,
        message=message,
    )


def _build_controls(control_rows: list[dict[str, Any]]) -> list[AccountingControlView]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in control_rows:
        grouped.setdefault(str(row.get("check")), []).append(row)

    controls: list[AccountingControlView] = []
    for check, rows in grouped.items():
        if check in _ROW_LEVEL_CHECKS:
            controls.append(_aggregate_row_control(check, rows))
            continue

        row = rows[0]
        expected = _to_float(row.get("expected"))
        observed = _to_float(row.get("observed"))
        difference = _to_float(row.get("difference"))
        passed = str(row.get("status")) == "passed"
        rcc_code = _EVIDENCE_TO_RCC.get(str(row.get("field") or ""))
        message = (
            "Contrôle vérifié."
            if passed
            else f"Écart de {_fmt(abs(difference) if difference is not None else None)} MAD "
            f"(attendu {_fmt(expected)}, lu {_fmt(observed)})."
        )
        controls.append(
            AccountingControlView(
                code=_CONTROL_CODES.get(check, check.lower()),
                status="passed" if passed else "failed",
                label=_CONTROL_LABELS.get(check, check),
                expected=expected,
                observed=observed,
                difference=difference,
                tolerance=float(engine.ROBUST_ARITH_TOL),
                affected_fields=[rcc_code] if rcc_code else [],
                message=message,
            )
        )

    controls.sort(key=lambda c: (c.status != "failed", c.label))
    return controls


def _build_warnings(
    pages: Iterable[FinancialPageAudit],
    fields: Iterable[ExtractedField],
    controls: Iterable[AccountingControlView],
) -> list[str]:
    warnings: list[str] = []

    failed_pages = [page.page_number for page in pages if page.extraction_status == "failed"]
    if failed_pages:
        warnings.append(
            "Pages non exploitées : "
            + ", ".join(str(p) for p in failed_pages)
            + " — les postes qu'elles portent peuvent manquer."
        )

    conflicting = [f.label for f in fields if f.status == "conflicting"]
    if conflicting:
        warnings.append("Valeurs divergentes à arbitrer : " + ", ".join(conflicting) + ".")

    to_review = [
        f.label
        for f in fields
        if f.value is not None and f.status == "ambiguous"
    ]
    if to_review:
        warnings.append("Lectures à confirmer : " + ", ".join(to_review) + ".")

    for control in controls:
        if control.status == "failed":
            warnings.append(f"Contrôle comptable en écart — {control.label} : {control.message}")

    return warnings


def _dec(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _ratio_inputs(fields: list[ExtractedField]) -> dict[str, float | None]:
    by_code = {item.code: item for item in fields}
    ca = by_code.get("CHIFFRE_AFFAIRES")
    achats_rev_f = by_code.get("ACHATS_REVENDUS")
    achats_con_f = by_code.get("ACHATS_CONSOMMES")
    from app.domain.period_math import safe_sum_period_fields
    from app.schemas.analyse import PeriodFieldValue

    achats_sum = safe_sum_period_fields(
        [
            achats_rev_f.current if achats_rev_f else PeriodFieldValue(status="missing"),
            achats_con_f.current if achats_con_f else PeriodFieldValue(status="missing"),
        ]
    )
    achats = achats_sum.usable_value if achats_sum.usable else None
    return {
        "fonds_propres": _usable(by_code.get("FONDS_PROPRES")),
        "total_bilan": _usable(by_code.get("TOTAL_BILAN")),
        "chiffre_affaires": _usable(ca),
        "ca_n1": _n1_of(ca),
        "resultat_net": _usable(by_code.get("RESULTAT_NET")),
        "dettes_financieres": _usable(by_code.get("DETTES_FINANCIERES")),
        "dettes_financement": _usable(by_code.get("ENDETTEMENT_TERME"))
        or _usable(by_code.get("DETTES_BANCAIRES_MLT")),
        "caf": _usable(by_code.get("CAF")),
        "fdr": _usable(by_code.get("FDR")),
        "bfr": _usable(by_code.get("BFR")),
        "tresorerie_nette": _usable(by_code.get("TRESORERIE_NETTE")),
        "clients": _usable(by_code.get("CREANCES_CLIENTS")),
        "fournisseurs": _usable(by_code.get("DETTES_FOURNISSEURS")),
        "achats": achats,
        "resultat_exploitation": _usable(by_code.get("RESULTAT_EXPLOITATION")),
        "actifs_immobilises": _usable(by_code.get("ACTIFS_IMMOBILISES")),
        "stocks": _usable(by_code.get("STOCKS")),
        "dotations": _usable(by_code.get("DOTATIONS_EXPLOITATION")),
    }


def _serialize_ratio(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": result.get("value"),
        "status": result.get("status"),
        "reason": result.get("reason"),
        "numerator": result.get("numerator"),
        "denominator": result.get("denominator"),
        "validity_status": result.get("validity_status"),
    }


def _compute_scoring(fields: list[ExtractedField]) -> tuple[dict[str, float | None], dict[str, Any], dict[str, Any], dict[str, Any]]:
    inputs = _ratio_inputs(fields)
    payload = {key: _dec(value) for key, value in inputs.items()}
    raw_ratios = ratio_engine.calculate_all_ratios(payload)
    raw_ratios["croissance_ca"] = ratio_engine.croissance_ca(
        payload.get("chiffre_affaires"), payload.get("ca_n1")
    )
    ratios = {key: _serialize_ratio(value) for key, value in raw_ratios.items()}

    axe1 = scoring_engine.score_axe1_from_ratios(raw_ratios)
    axe2 = scoring_engine.score_axe2_behavioral(provided_fields=set())
    axe3 = scoring_engine.score_axe3_sectoriel(raw_ratios, sector_medians=None)

    axe1_score = float(axe1["score"]) if axe1.get("score") is not None else None
    axe3_score = axe3.get("score")
    axe2_score = axe2.get("score")
    computed = scoring_engine.compute_scores(axe1_score, axe2_score, axe3_score)
    axe2_note = None
    if axe2_score is None:
        axe2_note = "Axe comportemental non noté : relevés bancaires non extraits."
    if computed["score_status"] == "NOT_CALCULABLE":
        risk = None
        grid_classe = None
    else:
        risk = {
            "A+": "faible",
            "A/B+": "faible",
            "B/B-": "modere",
            "C": "eleve",
            "D/F": "critique",
        }.get(computed.get("classe") or "", None)
        grid_classe = computed.get("classe")
    display_score = computed["final_score"] if computed["score_status"] == "FINAL" else computed["partial_score"]
    decision = {
        "score": display_score,
        "score_raw": display_score,
        "score_status": computed["score_status"],
        "financial_score": computed["financial_score"],
        "behavioral_score": computed["behavioral_score"],
        "sector_score": computed["sector_score"],
        "partial_score": computed["partial_score"],
        "final_score": computed["final_score"],
        "classe": grid_classe,
        "decision": computed.get("decision_label"),
        "recommandation": computed.get("algorithmic_recommendation"),
        "risk_level": risk,
        "blocking_status": "NOT_CHECKED",
        "axe2_note": axe2_note,
        "provisional": computed["score_status"] != "FINAL",
        "missing_axes": computed["missing_axes"],
    }
    axes = {
        "financier": {**axe1, "weight": 0.75},
        "comportemental": {**axe2, "weight": 0.15, "note": axe2_note},
        "sectoriel": {**axe3, "weight": 0.10, "status": axe3.get("status") or "NOT_CALIBRATED"},
    }
    return inputs, ratios, axes, decision


_YEAR_SERIES_FIELDS: dict[str, str] = {
    "chiffre_affaires": "CHIFFRE_AFFAIRES",
    "resultat_net": "RESULTAT_NET",
    "fonds_propres": "FONDS_PROPRES",
    "total_bilan": "TOTAL_BILAN",
    "dettes_financieres": "DETTES_FINANCIERES",
    "endettement_terme": "ENDETTEMENT_TERME",
    "tresorerie_nette": "TRESORERIE_NETTE",
    "fdr": "FDR",
    "bfr": "BFR",
    "caf": "CAF",
    "valeur_ajoutee": "VALEUR_AJOUTEE",
    "ebe": "EBE",
    "stocks": "STOCKS",
    "clients": "CREANCES_CLIENTS",
    "fournisseurs": "DETTES_FOURNISSEURS",
    "actifs_immobilises": "ACTIFS_IMMOBILISES",
    "resultat_exploitation": "RESULTAT_EXPLOITATION",
    "dotations": "DOTATIONS_EXPLOITATION",
}


def _exercise_year(exercise: ExerciseInfo, filename: str = "") -> int | None:
    """Année de clôture lue sur la liasse (période du … au …), jamais le nom de fichier."""
    del filename
    for source in (exercise.fin, exercise.debut):
        if not source:
            continue
        match = re.search(r"(20\d{2})", str(source))
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2100:
                return year
    return None


def _series_column_filled(series: dict[str, list[float | None]], index: int) -> bool:
    return any(
        index < len(values) and values[index] is not None
        for values in series.values()
    )


def _year_labels(years: list[int | None], series: dict[str, list[float | None]]) -> list[str]:
    """N et N-1 = dates de la liasse ; N-2 seulement si une colonne (autre liasse) existe."""
    labels: list[str] = []
    for index, year in enumerate(years):
        if year is None:
            labels.append("N" if index == 2 else "N-1" if index == 1 else "—")
            continue
        if index == 0 and not _series_column_filled(series, 0):
            labels.append("—")
            continue
        labels.append(str(year))
    return labels


def _build_years(
    fields: list[ExtractedField],
    exercise: ExerciseInfo,
    filename: str,
) -> YearsBlock:
    year_n = _exercise_year(exercise, filename)
    if year_n:
        years: list[int | None] = [None, year_n - 1, year_n]
    else:
        years = [None, None, None]

    by_code = {item.code: item for item in fields}
    series: dict[str, list[float | None]] = {}
    for key, code in _YEAR_SERIES_FIELDS.items():
        field = by_code.get(code)
        series[key] = [None, _n1_of(field), _usable(field)]

    available = sum(1 for index in range(3) if _series_column_filled(series, index))
    return YearsBlock(
        labels=_year_labels(years, series),
        years=years,
        available_count=available,
        series=series,
    )


def merge_liasse_years(
    primary: ScoringAnalysisResult,
    extras: list[ScoringAnalysisResult],
) -> ScoringAnalysisResult:
    """Complète la colonne N-2 (et les trous) à partir d'autres liasses du dossier."""
    by_year: dict[int, dict[str, float | None]] = {}
    conflicts: list[str] = []

    def ingest(block: YearsBlock, source: str) -> None:
        for index, year in enumerate(block.years):
            if year is None:
                continue
            bucket = by_year.setdefault(year, {})
            for key, values in block.series.items():
                if index >= len(values) or values[index] is None:
                    continue
                incoming = values[index]
                existing = bucket.get(key, "__missing__")
                if existing == "__missing__" or existing is None and key not in bucket:
                    bucket[key] = incoming
                elif existing is None:
                    continue
                elif abs(float(existing) - float(incoming)) <= 0.01:
                    bucket[key] = incoming
                else:
                    bucket[key] = None
                    conflicts.append(f"SOURCE_CONFLICT:{year}:{key}")

    ingest(primary.years, "primary")
    for extra in extras:
        ingest(extra.years, "extra")

    if not by_year:
        return primary

    latest = max(by_year)
    ordered: list[int | None] = [latest - 2, latest - 1, latest]
    keys = set(primary.years.series)
    for column in by_year.values():
        keys.update(column)
    series = {
        key: [by_year.get(year, {}).get(key) if year is not None else None for year in ordered]
        for key in keys
    }
    years_out: list[int | None] = [
        year if year in by_year else None
        for year in ordered
    ]
    # N-1 reste l'exercice précédent de la liasse la plus récente, même sans montant.
    if years_out[1] is None:
        years_out[1] = latest - 1
    available = sum(1 for index in range(3) if _series_column_filled(series, index))
    if conflicts:
        current = list(getattr(primary, "warnings", None) or [])
        current.extend(list(dict.fromkeys(conflicts)))
        primary.warnings = current
    primary.years = YearsBlock(
        labels=_year_labels(years_out, series),
        years=years_out,
        available_count=available,
        series=series,
    )
    return primary


def build_result_from_v6(v6: dict[str, Any], filename: str) -> ScoringAnalysisResult:
    """Projette la sortie V6 (identité bilan + postes + CAF) vers l'API Scoring."""
    identity = identity_from_v6(v6.get("identity") or {})
    pages = map_page_audit(v6)
    fields = map_fields(v6.get("canonical") or {})
    fields.extend(_derived_fields(fields))
    document = document_from_v6(v6, filename, identity)
    year_n = _exercise_year(document.exercise, filename)
    controls = map_controls(v6.get("validations") or [], year_n=year_n)
    warnings = identity_warnings(v6, identity)
    warnings.extend(_build_warnings(pages, fields, controls))
    for item in v6.get("quality", {}).get("context_warnings") or []:
        warnings.append(str(item))
    if "caf" in (v6.get("missing_required_fields") or []):
        warnings.append("CAF non imprimée sur l'ESG — proxy RN + dotations si disponible.")
    ratio_inputs, ratios, axes, decision = _compute_scoring(fields)
    rc_blob = " ".join(
        str((v6.get("identity") or {}).get(key) or "")
        for key in ("raison_sociale", "adresse", "ville", "reference", "ice")
    )
    rc = _extract_rc(rc_blob) or _extract_rc(str(v6.get("identity") or ""))
    if rc:
        document.company.rc = rc
    years = _build_years(fields, document.exercise, filename)
    if axes["comportemental"].get("note"):
        warnings.append(axes["comportemental"]["note"])
    if years.available_count < 2:
        warnings.append("La liasse ne fournit que l'exercice N : la colonne N-1 reste vide.")
    elif years.available_count == 2:
        warnings.append(
            "Deux exercices lus sur la liasse (N et N-1). La colonne N-2 reste vide "
            "tant qu'une liasse plus ancienne n'est pas jointe au dossier."
        )

    found = sum(
        1
        for field in fields
        if (field.note if field.code == "TYPE_RESULTAT" else field.current.observed_value) is not None
        and field.status != "missing"
    )
    total = len(RCC_ELEMENTS) + len([item for item in SCORING_EXTRA_ELEMENTS if item[3] != "Dérivé"])
    fiscal = map_fiscal_analysis(v6)
    capital = map_capital_analysis(v6)
    result = ScoringAnalysisResult(
        document=document,
        extraction=extraction_summary(pages, warnings),
        fields=fields,
        completeness_pct=round(100.0 * found / max(total, 1), 1),
        warnings=warnings,
        controls=controls,
        ratio_inputs=ratio_inputs,
        ratios=ratios,
        axes=axes,
        decision=decision,
        years=years,
        fiscal_analysis=fiscal,
        capital_analysis=capital,
        score_raw=float(decision.get("score") or 0),
    )
    quality, readiness = evaluate_quality(result)
    result.quality = quality
    result.readiness = readiness
    result.decision["provisional"] = not readiness.ready_for_automatic_scoring
    if not readiness.ready_for_automatic_scoring:
        warnings.append("Quality gate : revue manuelle requise — le score n'est pas une décision automatique.")
        result.warnings = warnings
        result.extraction.warnings = warnings
    from app.services.ia_clients_service import enrich_result_with_ia_client

    return enrich_result_with_ia_client(result)


def build_result(
    *,
    filename: str,
    audit_frame: Any,
    rcc_frame: Any,
    controls_frame: Any,
    evidence: list[engine.EvidenceRow],
    pages_total: int,
) -> ScoringAnalysisResult:
    """Projette la sortie du moteur v10 puis calcule ratios et score."""
    audit_rows = _records(audit_frame)
    pages = _page_audit(audit_rows, evidence)
    fields = _build_fields(_records(rcc_frame), evidence)
    controls = _build_controls(_records(controls_frame))
    company, exercise = _identification(evidence)
    warnings = _build_warnings(pages, fields, controls)
    ratio_inputs, ratios, axes, decision = _compute_scoring(fields)
    years = _build_years(fields, exercise, filename)
    if axes["comportemental"].get("note"):
        warnings.append(axes["comportemental"]["note"])
    if years.available_count < 2:
        warnings.append(
            "La liasse ne fournit que l'exercice N : la colonne N-1 reste vide."
        )
    elif years.available_count == 2:
        warnings.append(
            "Deux exercices lus sur la liasse (N et N-1). La colonne N-2 reste vide "
            "tant qu'une liasse plus ancienne n'est pas jointe au dossier."
        )

    found = sum(
        1
        for field in fields
        if (field.note if field.code == "TYPE_RESULTAT" else field.value) is not None
        and field.status != "missing"
    )
    total = len(RCC_ELEMENTS) + len([item for item in SCORING_EXTRA_ELEMENTS if item[3] != "Dérivé"])

    document = DocumentSummary(
        filename=filename,
        pages_total=pages_total or len(pages),
        pages_processed=sum(1 for p in pages if p.extraction_status == "processed"),
        pages_skipped=sum(1 for p in pages if p.extraction_status in {"skipped", "empty"}),
        pages_failed=sum(1 for p in pages if p.extraction_status == "failed"),
        company=company,
        exercise=exercise,
    )
    extraction = ExtractionSummary(
        model=f"{engine.PIPELINE_VERSION} · {config.RCC_VISION_MODEL}",
        page_audit=pages,
        warnings=warnings,
    )

    from app.services.ia_clients_service import enrich_result_with_ia_client

    return enrich_result_with_ia_client(
        ScoringAnalysisResult(
            document=document,
            extraction=extraction,
            fields=fields,
            completeness_pct=round(100.0 * found / max(total, 1), 1),
            warnings=warnings,
            controls=controls,
            ratio_inputs=ratio_inputs,
            ratios=ratios,
            axes=axes,
            decision=decision,
            years=years,
        )
    )


def _run_engine(
    pdf_path: Path,
    *,
    max_pages: int | None,
    progress: Callable[[str, dict[str, Any]], None],
) -> tuple[Any, Any, Any, list[engine.EvidenceRow]]:
    client = build_client()
    audit, _rows, rcc, controls, evidence = engine.analyze_pdf(
        pdf_path,
        client=client,
        max_pages=max_pages,
        use_glm_verification=config.RCC_USE_GLM_VERIFICATION,
        use_reasoning_mapper=config.RCC_USE_REASONING_MAPPER,
        use_adjudicator=config.RCC_USE_ADJUDICATOR,
        progress=progress,
    )
    return audit, rcc, controls, evidence


async def analyze_scoring_document(
    pdf_bytes: bytes,
    filename: str,
    *,
    max_pages: int | None = None,
    emit: ProgressEmitter | None = None,
) -> ScoringAnalysisResult:
    def publish(event: str, data: dict[str, Any]) -> None:
        if emit is not None:
            emit(event, data)

    publish("pdf_validated", {"filename": filename})

    events: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue()

    def progress(event: str, data: dict[str, Any]) -> None:
        events.put((event, data))

    task = asyncio.create_task(
        asyncio.to_thread(
            run_v6_from_bytes,
            pdf_bytes,
            filename,
            max_pages=max_pages,
            ollama_url=config.RCC_OLLAMA_URL,
            progress=progress,
        )
    )

    def drain() -> None:
        while True:
            try:
                event, data = events.get_nowait()
            except queue.Empty:
                return
            publish(event, data)

    while not task.done():
        drain()
        await asyncio.sleep(0.2)
    drain()
    v6 = await task

    publish("resolving_fields", {"message": "Mapping des postes financiers"})
    publish("running_controls", {"message": "Contrôles comptables"})
    publish("calculating_ratios", {"message": "Calcul des ratios et du score"})
    result = build_result_from_v6(v6, filename)
    # Ne pas émettre result_ready ici : le SSE se ferme sur cet événement.
    # Le job store l'émet après persistance du workspace (charts prêts).
    publish(
        "scoring_computed",
        {
            "pages_processed": result.document.pages_processed,
            "completeness_pct": result.completeness_pct,
            "score": result.decision.get("score"),
        },
    )
    return result


async def run_scoring_job(job_id: str, *, store: Any, on_completed: Callable[[str, ScoringAnalysisResult], None] | None = None) -> None:
    job = store.get(job_id)
    pdf_bytes = getattr(job, "pdf_bytes", None) if job else None
    extra_pdfs = list(getattr(job, "extra_pdfs", None) or []) if job else []
    if job is not None and pdf_bytes is None:
        from app.services import minio_storage

        primary = getattr(job, "primary_document", None)
        if primary is None:
            return
        pdf_bytes = minio_storage.download_bytes(primary.object_key)
        extra_pdfs = []
        for extra in getattr(job, "extra_documents", None) or []:
            extra_pdfs.append((minio_storage.download_bytes(extra.object_key), extra.filename))
    if job is None or pdf_bytes is None:
        return

    store.update(
        job_id,
        status="processing",
        current_step="validating",
        message="Validation du PDF…",
        progress_pct=2,
    )
    store.emit(job_id, "job_started", {"filename": job.filename, "dossier_id": job.dossier_id})

    started = time.time()

    def emit(event: str, data: dict[str, Any]) -> None:
        step_map = {
            "pdf_validated": ("validating", 5, "PDF validé"),
            "pages_rendered": ("rendering", 10, "Pages analysées"),
            "page_classified": ("classifying", None, None),
            "page_extracted": ("extracting_page", None, None),
            "page_skipped": ("extracting_page", None, None),
            "page_failed": ("extracting_page", None, None),
            "resolving_fields": ("resolving", 86, "Résolution des postes financiers"),
            "running_controls": ("controls", 92, "Contrôles comptables"),
            "calculating_ratios": ("scoring", 96, "Calcul des ratios et du score"),
            "scoring_computed": ("scoring", 98, "Quality gate et scoring"),
            "result_ready": ("completed", 100, "Analyse terminée"),
        }
        step, pct, message = step_map.get(event, (None, None, None))
        updates: dict[str, Any] = {}
        if step:
            updates["current_step"] = step
        if pct is not None:
            updates["progress_pct"] = pct
        if message:
            updates["message"] = message
        if "page" in data:
            updates["current_page"] = data["page"]
            pages_total = job.pages_total or data.get("pages_total")
            if pages_total:
                updates["progress_pct"] = min(
                    85,
                    10 + int(75 * int(data["page"]) / max(int(pages_total), 1)),
                )
                updates["message"] = (
                    f"Page {data['page']}/{pages_total} — {data.get('page_type', '')}"
                )
        if event == "pages_rendered":
            total = data.get("pages_total") or data.get("count")
            updates["pages_total"] = total
            job.pages_total = total
        if event == "page_extracted":
            updates["pages_financial"] = (job.pages_financial or 0) + 1
            job.pages_financial = updates["pages_financial"]
        if event == "page_skipped":
            updates["pages_skipped"] = (job.pages_skipped or 0) + 1
            job.pages_skipped = updates["pages_skipped"]
        if event == "page_failed":
            updates["pages_failed"] = (job.pages_failed or 0) + 1
            job.pages_failed = updates["pages_failed"]
        if updates:
            store.update(job_id, **updates)
        store.emit(job_id, event, data)

    try:
        result = await analyze_scoring_document(
            pdf_bytes,
            job.filename,
            max_pages=job.max_pages,
            emit=emit,
        )
        extras: list[ScoringAnalysisResult] = []
        for extra_bytes, extra_name in extra_pdfs:
            emit(
                "calculating_ratios",
                {"message": f"Exercice complémentaire — {extra_name}"},
            )
            try:
                extra = await analyze_scoring_document(
                    extra_bytes,
                    extra_name,
                    max_pages=job.max_pages,
                    emit=None,
                )
                extras.append(extra)
            except Exception as extra_exc:  # noqa: BLE001
                logger.warning("Liasse complémentaire %s ignorée : %s", extra_name, extra_exc)
        if extras:
            result = merge_liasse_years(result, extras)
            result.warnings.append(
                f"{len(extras) + 1} liasse(s) fusionnée(s) pour la série pluriannuelle."
            )
        logger.info(
            "Job scoring %s terminé en %.0f s — score %s — %s%%",
            job_id,
            time.time() - started,
            result.decision.get("score"),
            result.completeness_pct,
        )
        ready = result.readiness.ready_for_automatic_scoring
        store.update(
            job_id,
            status="completed",
            progress_pct=100,
            current_step="completed",
            message="Analyse terminée" if ready else "Analyse terminée — revue manuelle requise",
            result=result,
            pdf_bytes=None,
        )
        if on_completed is not None:
            on_completed(job.dossier_id, result)
        store.emit(
            job_id,
            "result_ready",
            {"status": "completed", "score": result.decision.get("score")},
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Job scoring %s échoué", job_id)
        store.update(
            job_id,
            status="failed",
            current_step="failed",
            message="Échec de l'analyse",
            error=str(exc),
            pdf_bytes=None,
        )
        store.emit(job_id, "job_failed", {"error": str(exc)})
