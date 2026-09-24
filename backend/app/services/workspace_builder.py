"""Construit le workspace d'analyse (charts, ratios, synthèse) pour le front."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from app.schemas.analyse import ScoringAnalysisResult
from app.schemas.create_dossier import StoredDossierRecord
from app.services.ratio_engine import RATIO_METADATA
from app.services.scoring_engine import (
    AXE1_PENALTY_NON_CONFORME,
    AXE1_PENALTY_SURVEILLER,
    AXE1_RATIO_KEYS,
)
from app.services.synthese_builder import build_synthese, empty_synthese

_STATUS_LABEL = {
    "pending": "Docs en attente",
    "analyzing": "En analyse",
    "ready": "Prêt",
    "review": "Revue",
    "approved": "Approuvé",
    "reserved": "Sous réserve",
    "rejected": "Rejeté",
}

_RATIO_UI_STATUS = {
    "Conforme": "GOOD",
    "À surveiller": "WARN",
    "Non conforme": "BAD",
    "Non calculable": "WARN",
}

def analysis_source_fingerprint(record: StoredDossierRecord) -> str:
    parts = [
        f"{f.category}|{getattr(f, 'sha256', None) or ''}|{f.name}|{f.size}|{f.objectKey}|{getattr(f, 'version', 1)}"
        for f in record.files
    ]
    return hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:24]


def _file_kind(name: str) -> str:
    n = name.lower()
    if "proforma" in n or "facture" in n:
        return "proforma"
    if "liasse" in n or "bilan" in n or "cpc" in n:
        return "liasse"
    if "relev" in n or "bancaire" in n:
        return "releves"
    if "rc" in n or "commerce" in n or "kbis" in n:
        return "rc"
    if "cin" in n:
        return "cin"
    return "piece"


def _documents(record: StoredDossierRecord, result: ScoringAnalysisResult | None) -> dict[str, Any]:
    items = []
    extractions: dict[str, Any] = {}
    for index, file in enumerate(record.files):
        doc_id = f"doc-{index}-{file.name}"
        size_ko = max(1, round(file.size / 1024))
        kind = _file_kind(file.name)
        items.append({
            "id": doc_id,
            "name": file.name,
            "meta": f"{(file.contentType.split('/')[-1] or 'fichier').upper()} · {size_ko} Ko",
            "confidence": None if result is None else (int(round(result.completeness_pct)) if kind == "liasse" else None),
            "uploadName": file.name,
        })

    identity_fields = []
    if result is not None:
        company = result.document.company
        identity = result.document.identity
        exercise = result.document.exercise
        years = result.years
        period = exercise.label or " — ".join(
            part for part in (identity.period_start, identity.period_end) if part
        ) or " — ".join(years.labels)
        declaration = " ".join(
            part for part in (identity.declaration_date, identity.declaration_time) if part
        )
        identity_fields = [
            {"label": "Raison sociale", "value": identity.raison_sociale or company.raison_sociale or "—", "source": "Bilan — identification", "confidence": None},
            {"label": "N° tiers", "value": (result.client_lookup.primary.tiers if result.client_lookup and result.client_lookup.primary else None) or "—", "source": "API IA clients", "confidence": 95 if result.client_lookup and result.client_lookup.primary and result.client_lookup.primary.tiers else 0},
            {"label": "ICE", "value": identity.ice or company.ice or "—", "source": "Bilan — identification", "confidence": None},
            {"label": "Identifiant fiscal", "value": identity.identifiant_fiscal or company.identifiant_fiscal or record.identifiantFiscal or "—", "source": "Bilan — identification", "confidence": None},
            {"label": "Taxe professionnelle", "value": identity.taxe_professionnelle or company.taxe_professionnelle or "—", "source": "Bilan — identification", "confidence": 90 if identity.taxe_professionnelle else 0},
            {"label": "RC", "value": company.rc or record.rc or "—", "source": "Bilan / dossier", "confidence": 80 if (company.rc or record.rc) else 0},
            {"label": "Ville", "value": identity.ville or company.ville or "—", "source": "Bilan — identification", "confidence": 90 if identity.ville else 0},
            {"label": "Adresse", "value": identity.adresse or company.adresse or "—", "source": "Bilan — identification", "confidence": 90 if identity.adresse else 0},
            {"label": "Activité", "value": identity.activite or company.activite or "—", "source": "Bilan — identification", "confidence": 90 if identity.activite else 0},
            {"label": "Secteur", "value": identity.secteur or "—", "source": "Bilan — identification", "confidence": 70 if identity.secteur else 0},
            {"label": "Période", "value": period or "—", "source": "Bilan — identification", "confidence": 90 if identity.period_end or exercise.fin else 0},
            {"label": "Date de déclaration", "value": declaration or identity.declaration_date or "—", "source": "Bilan — identification", "confidence": 90 if identity.declaration_date else 0},
            {"label": "Référence", "value": identity.reference or "—", "source": "Bilan — identification", "confidence": 90 if identity.reference else 0},
        ]
        fields = list(identity_fields)
        for field in result.fields:
            if field.code == "TYPE_RESULTAT":
                value = field.note or "—"
            elif field.value is None:
                value = "—"
            else:
                value = _mad(field.value)
            evidence = field.evidence[0] if field.evidence else None
            source = (
                f"p. {evidence.page_number}" if evidence and evidence.page_number else field.source
            )
            if field.value_n1 is not None:
                source = f"{source} · N-1 {_mad(field.value_n1)}"
            fields.append({
                "label": field.label,
                "value": value,
                "source": source,
                "confidence": int(round(field.confidence * 100)),
            })
        liasse_item = next(
            (item for item in items if _file_kind(item["name"]) == "liasse"),
            items[0] if items else None,
        )
        if liasse_item is not None:
            extractions[liasse_item["id"]] = {
                "title": result.document.filename,
                "flag": f"Extraction · {result.completeness_pct:.0f} % · {years.available_count} exercice(s)",
                "fields": fields,
            }

    present = len(items)
    default_id = ""
    if result is not None:
        default_id = next(
            (item["id"] for item in items if _file_kind(item["name"]) == "liasse"),
            items[0]["id"] if items else "",
        )
    elif items:
        default_id = items[0]["id"]
    present_kinds = { _file_kind(item["name"]) for item in items }
    required = [
        {"id": "liasse", "name": "Liasse fiscale", "ok": "liasse" in present_kinds},
        {"id": "proforma", "name": "Proforma", "ok": "proforma" in present_kinds or any(f.category == "proforma" for f in record.files)},
        {"id": "rc", "name": "RC", "ok": "rc" in present_kinds or bool(record.rc)},
        {"id": "releves", "name": "Relevés bancaires", "ok": "releves" in present_kinds},
    ]
    from app.services.document_checklist import evaluate_checklist

    checklist = evaluate_checklist(record)
    missing = [
        {"id": r["type"], "name": r["type"], "meta": r["reason"]}
        for r in checklist["missing"]
    ]
    present_req = checklist["document_completeness_pct"]
    completeness = checklist["document_completeness_pct"]
    return {
        "present": present,
        "total": len(required),
        "completenessPct": completeness,
        "items": items,
        "missing": missing,
        "required": required,
        "extractions": extractions,
        "defaultDocId": default_id,
    }


def overlay_live_documents(record: StoredDossierRecord, workspace: dict[str, Any] | None) -> dict[str, Any]:
    """Met à jour la liste des fichiers sans perdre les extractions déjà calculées."""
    base = dict(workspace) if workspace else empty_workspace(record)
    fresh = _documents(record, None)
    old_docs = (workspace or {}).get("documents") or {}
    old_items = old_docs.get("items") or []
    old_ext = old_docs.get("extractions") or {}
    by_name: dict[str, Any] = {}
    for item in old_items:
        ext = old_ext.get(item.get("id"))
        if ext and item.get("name"):
            by_name[item["name"]] = ext
    for item in fresh["items"]:
        kept = by_name.get(item["name"])
        if kept:
            fresh["extractions"][item["id"]] = kept
            item["confidence"] = kept.get("confidence")
    if not fresh["defaultDocId"] and fresh["items"]:
        fresh["defaultDocId"] = fresh["items"][-1]["id"]
    current_fp = analysis_source_fingerprint(record)
    stored_fp = (workspace or {}).get("analysisFingerprint")
    stale = bool(stored_fp and stored_fp != current_fp)
    base["analysisStale"] = stale
    if stale:
        base["staleMessage"] = "Le document financier a changé. Relancez l'analyse."
        scoring = dict(base.get("scoring") or {})
        scoring.update({
            "stale": True,
            "provisional": True,
            "score": 0,
            "scoreRaw": None,
            "classe": "",
            "recommendation": "Analyse à relancer — le document financier a changé.",
            "summary": "Les données financières affichées ne sont plus valides. Relancez l'analyse.",
        })
        base["scoring"] = scoring
        base["ratios"] = {"calcTime": "—", "conformCount": 0, "watchCount": 0, "items": [], "aggregates": [], "fiscal": []}
        base["factorielle"] = []
        base["yearLabels"] = ["—", "N-1", "N"]
        base["financialStatements"] = None
        base["fiscalAnalysis"] = None
        base["capitalAnalysis"] = None
        base["quality"] = None
        base["readiness"] = None
        base["controls"] = []
    base["documents"] = fresh
    base["header"] = _header(record)
    return base


def _mad(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}".replace(".", ",") + " M MAD"
    return f"{value:,.0f}".replace(",", " ") + " MAD"


def _kdh(value: float | None) -> str:
    """Montants de l'étude / Excel « En KDH ». None reste « — », 0 reste 0."""
    if value is None:
        return "—"
    if abs(value) < 1000:
        body = f"{value:,.0f}".replace(",", " ") if float(value).is_integer() else f"{value:,.2f}".replace(",", " ")
        return f"{body} MAD"
    kdh = value / 1000.0
    if abs(kdh) >= 1000:
        return f"{kdh / 1000:.1f}".replace(".", ",") + " MDH"
    if abs(kdh) < 1:
        return f"{kdh:.2f}".replace(".", ",") + " KDH"
    body = f"{kdh:,.0f}".replace(",", " ")
    return f"{body} KDH"


def _chart_amount(field: Any, *, previous: bool) -> float | None:
    """Affichage graphique : valeur observée, sinon usable. Jamais 0 à la place de None."""
    if field is None:
        return None
    period = field.previous if previous else field.current
    if period is None:
        return None
    if period.observed_value is not None:
        return float(period.observed_value)
    if period.usable_value is not None:
        return float(period.usable_value)
    return None


def _chart_bar_pct(value: float | None, maximum: float) -> int:
    if value is None or maximum <= 0:
        return 0
    return max(8, int(round(100 * abs(value) / maximum)))


def _short(value: float | None) -> str:
    return _kdh(value)


def _dec_opt(value: float | None):
    from decimal import Decimal

    if value is None:
        return None
    return Decimal(str(value))


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}".replace(".", ",") + " %"


def _fmt_ratio(key: str, value: float | None) -> str:
    meta = RATIO_METADATA.get(key, {})
    unit = meta.get("unit", "")
    if value is None:
        return "—"
    if unit == "%":
        return _pct(value)
    if unit == "x":
        return f"{value:.2f}".replace(".", ",") + "x"
    if unit in {"j", "ans"}:
        return f"{value:.0f} {unit}"
    return f"{value:.2f}".replace(".", ",")


def _bar_pct(key: str, value: float | None, status: str) -> int:
    if value is None:
        return 8
    if status == "Conforme":
        return 82
    if status == "À surveiller":
        return 48
    if status == "Non conforme":
        return 22
    return 12


def _ratios_block(result: ScoringAnalysisResult, record: StoredDossierRecord | None = None) -> dict[str, Any]:
    items = []
    ratios = dict(result.ratios)
    if record is not None and "endettement_global_apres_operation" not in ratios:
        from app.services.ratio_engine import endettement_global_apres_operation

        extra = endettement_global_apres_operation(
            None,
            _dec_opt(result.ratio_inputs.get("dettes_financement")),
            _dec_opt(float(record.amount) if record.amount else None),
            _dec_opt(result.ratio_inputs.get("fonds_propres")),
        )
        ratios["endettement_global_apres_operation"] = {
            "value": extra.get("value"),
            "status": extra.get("status"),
            "reason": extra.get("reason"),
        }

    conform = watch = 0
    for key, meta in RATIO_METADATA.items():
        raw = ratios.get(key)
        if raw is None:
            continue
        status_fr = raw.get("status") or "Non calculable"
        if status_fr == "Non calculable" and raw.get("value") is None and key == "endettement_global_apres_operation":
            continue
        ui = _RATIO_UI_STATUS.get(status_fr, "WARN")
        if status_fr == "Conforme":
            conform += 1
        elif status_fr == "À surveiller":
            watch += 1
        value = raw.get("value")
        items.append({
            "label": meta["label"],
            "formula": meta["formula"],
            "threshold": meta["threshold"],
            "value": _fmt_ratio(key, value),
            "status": ui,
            "barPct": _bar_pct(key, value, status_fr),
            "interpretation": raw.get("reason")
            or f"Statut {status_fr.lower()} au regard du seuil {meta['threshold']}.",
        })

    inp = result.ratio_inputs
    years = result.years
    year_n = years.labels[2] if years.labels else "N"
    fiscal = [
        {"label": f"CA ({year_n})", "value": _kdh(inp.get("chiffre_affaires")), "tone": "neutral"},
        {"label": "Résultat net", "value": _kdh(inp.get("resultat_net")), "tone": "ok" if (inp.get("resultat_net") or 0) >= 0 else "warn"},
        {"label": "CAF", "value": _kdh(inp.get("caf")), "tone": "ok" if (inp.get("caf") or 0) >= 0 else "warn"},
        {"label": "Total bilan", "value": _kdh(inp.get("total_bilan")), "tone": "neutral"},
        {"label": "Fonds propres", "value": _kdh(inp.get("fonds_propres")), "tone": "neutral"},
        {"label": "Endettement à terme", "value": _kdh(inp.get("dettes_financement")), "tone": "warn" if (inp.get("dettes_financement") or 0) > (inp.get("fonds_propres") or 0) * 2 else "neutral"},
        {"label": "FDR", "value": _kdh(inp.get("fdr")), "tone": "ok" if (inp.get("fdr") or 0) >= 0 else "warn"},
        {"label": "BFR", "value": _kdh(inp.get("bfr")), "tone": "neutral"},
        {"label": "Trésorerie nette", "value": _kdh(inp.get("tresorerie_nette")), "tone": "ok" if (inp.get("tresorerie_nette") or 0) >= 0 else "warn"},
        {"label": "Immobilisations", "value": _kdh(inp.get("actifs_immobilises")), "tone": "neutral"},
    ]
    return {
        "calcTime": "< 1 s",
        "conformCount": conform,
        "watchCount": watch,
        "items": items,
        "fiscal": fiscal,
        "aggregates": fiscal,
        "unit": "KDH",
    }


def _scoring_block(record: StoredDossierRecord, result: ScoringAnalysisResult, ratios: dict[str, Any]) -> dict[str, Any]:
    decision = result.decision
    score_status = decision.get("score_status") or ("PARTIAL" if decision.get("provisional") else "FINAL")
    score_raw = decision.get("final_score") if score_status == "FINAL" else decision.get("partial_score")
    if score_raw is None:
        score_raw = result.score_raw if result.score_raw is not None else decision.get("score")
    score = score_raw if score_raw is not None else 0
    axe1 = result.axes.get("financier") or {}
    n_grid = max(int(axe1.get("ratios_expected") or len(AXE1_RATIO_KEYS)), 1)
    conforme_pct = round(100.0 / n_grid, 1)
    factors = []
    for key in axe1.get("ratios_conformes") or []:
        label = RATIO_METADATA.get(key, {}).get("label", key)
        factors.append({"label": label, "impact": conforme_pct})
    for key in axe1.get("ratios_a_surveiller") or []:
        label = RATIO_METADATA.get(key, {}).get("label", key)
        factors.append({"label": label, "impact": -AXE1_PENALTY_SURVEILLER})
    for key in axe1.get("ratios_non_conformes") or []:
        label = RATIO_METADATA.get(key, {}).get("label", key)
        factors.append({"label": label, "impact": -AXE1_PENALTY_NON_CONFORME})
    if not factors:
        completeness = float(result.completeness_pct or 0)
        factors = [{"label": "Complétude d'extraction", "impact": round(completeness - 50, 1)}]

    labels = result.years.labels or ["—", "N-1", "N"]
    by_code = {item.code: item for item in result.fields}
    ca_field = by_code.get("CHIFFRE_AFFAIRES")
    rn_field = by_code.get("RESULTAT_NET")
    columns = [
        (labels[1] if len(labels) > 1 else "N-1", _chart_amount(ca_field, previous=True), _chart_amount(rn_field, previous=True)),
        (labels[2] if len(labels) > 2 else "N", _chart_amount(ca_field, previous=False), _chart_amount(rn_field, previous=False)),
    ]
    points = []
    cas = [abs(ca) for _, ca, _ in columns if ca is not None]
    rns = [abs(rn) for _, _, rn in columns if rn is not None]
    max_ca = max(cas) if cas else 0
    max_rn = max(rns) if rns else 0
    for year, ca_v, rn_v in columns:
        if year in {"—", "N-2"} and ca_v is None and rn_v is None:
            continue
        points.append({
            "year": year,
            "caLabel": _kdh(ca_v),
            "rnLabel": _kdh(rn_v),
            "caHeightPct": _chart_bar_pct(ca_v, max_ca),
            "rnHeightPct": _chart_bar_pct(rn_v, max_rn),
        })

    growth = result.ratios.get("croissance_ca") or {}
    growth_v = growth.get("value")
    series_years = [lab for lab in labels if lab not in {"—", "N-2"}]
    series_txt = " / ".join(series_years) if series_years else ", ".join(labels)
    exercise = result.document.exercise
    period = exercise.label or (f"Du {exercise.debut} au {exercise.fin}" if exercise.debut and exercise.fin else "")
    period_suffix = f" · {period}" if period else ""
    caption = (
        f"Série {series_txt}{period_suffix} — CA "
        f"{('en hausse' if (growth_v or 0) > 0 else 'en repli')} ({_pct(growth_v)} vs N-1)."
        if growth_v is not None
        else f"Série {series_txt}{period_suffix} : {result.years.available_count} exercice(s) renseigné(s) sur la liasse."
    )

    calculable = int(axe1.get("ratios_calculables") or 0)
    if calculable <= 0:
        calculable = (
            len(axe1.get("ratios_conformes") or [])
            + len(axe1.get("ratios_a_surveiller") or [])
            + len(axe1.get("ratios_non_conformes") or [])
        )
    ratios_ok = len(axe1.get("ratios_conformes") or [])
    ratios_total = calculable or len(AXE1_RATIO_KEYS)

    return {
        "score": score if score_raw is not None else 0,
        "scoreRaw": score_raw,
        "scoreStatus": score_status,
        "financialScore": decision.get("financial_score"),
        "behavioralScore": decision.get("behavioral_score"),
        "sectorScore": decision.get("sector_score"),
        "partialScore": decision.get("partial_score"),
        "finalScore": decision.get("final_score"),
        "classe": decision.get("classe") or "",
        "recommendation": decision.get("recommandation") or decision.get("decision") or "—",
        "riskLabel": decision.get("decision") or "—",
        "riskLevel": decision.get("risk_level") or "",
        "provisional": score_status != "FINAL",
        "summary": (
            f"{record.name} — extraction {result.completeness_pct:.0f} % des postes financiers. "
            f"Score composite {score_raw:.2f}/100, classe {decision.get('classe', '—')} « {decision.get('decision', '—')} ». "
            f"{decision.get('axe2_note') or 'Les ratios financiers sont calculés sur les 11 ratios de l’axe 1.'}"
        ),
        "ratiosOk": ratios_ok,
        "ratiosTotal": ratios_total,
        "dossierCompletenessPct": int(result.completeness_pct),
        "factors": factors[:8],
        "trend": points,
        "trendCaption": caption,
        "attention": build_synthese(result, nouveau_financement=float(record.amount or 0) or None),
    }


def _pipeline(result: ScoringAnalysisResult | None, score: int) -> dict[str, Any]:
    steps = [
        {"label": "Réception & indexation", "meta": "MinIO"},
        {"label": "OCR & extraction des documents", "meta": "liasse fiscale"},
        {"label": "Identification du contribuable", "meta": "en-tête bilan"},
        {"label": "Lecture des tableaux", "meta": "PyMuPDF / OCR"},
        {"label": "Mapping canonique", "meta": "bilan / CPC / ESG"},
        {"label": "CAF & contrôles", "meta": "ESG + arithmétique"},
        {"label": "Analyse financière & ratios", "meta": "11 ratios"},
        {"label": "Quality gate", "meta": "valeurs utilisables"},
        {"label": "Score composite & mémo", "meta": "75 / 15 / 10"},
    ]
    if result is None:
        return {
            "policyVersion": "Politique scoring Wafabail",
            "steps": steps,
            "fullTrace": [],
            "initialStep": 0,
            "initialScore": 0,
        }
    doc = result.document
    trace = [
        {"type": "in", "text": f"Liasse « {doc.filename} » — {doc.pages_total} page(s)", "step": 0},
        {"type": "ok", "text": f"{doc.pages_processed} page(s) financières extraites", "step": 1},
        {"type": "ok", "text": f"Complétude {result.completeness_pct:.0f} % — {len(result.fields)} postes", "step": 4},
    ]
    failed = [c for c in result.controls if c.status == "failed"]
    if failed:
        trace.append({"type": "warn", "text": f"{len(failed)} contrôle(s) comptable(s) en écart", "step": 5})
    else:
        trace.append({"type": "ok", "text": "Contrôles comptables cohérents", "step": 5})
    for warning in result.warnings[:4]:
        trace.append({"type": "warn", "text": warning, "step": 6})
    if result.readiness.ready_for_automatic_scoring:
        trace.append({"type": "res", "text": f"Score composite {score}/100", "step": 8})
    else:
        trace.append({"type": "warn", "text": "Analyse terminée — revue manuelle requise", "step": 8})
    return {
        "policyVersion": "Politique scoring Wafabail",
        "steps": steps,
        "fullTrace": trace,
        "initialStep": len(steps),
        "initialScore": score,
    }


def _bien(record: StoredDossierRecord) -> dict[str, Any]:
    apport_pct = record.apport
    financed = None
    if record.amount and record.apport is not None:
        financed = max(0.0, float(record.amount) - float(record.amount) * float(record.apport) / 100.0)
    return {
        "title": record.natureBien or record.nature,
        "subtitle": f"{record.sector} · {record.fournisseur}",
        "assetValueLabel": _mad(record.valeurBien or record.amount),
        "financedLabel": _mad(financed),
        "durationLabel": f"{record.duration} mois",
        "residualLabel": None,
        "units": [{
            "qty": "1",
            "designation": record.natureBien or record.nature,
            "marque": "—",
            "modele": record.etat,
            "annee": "—",
            "valeur": _mad(record.valeurTtc or record.valeurBien),
        }],
        "totalTtcLabel": _mad(record.valeurTtc),
        "specs": [
            {"key": "Fournisseur", "value": record.fournisseur},
            {"key": "Réf. proforma", "value": record.proformaReference or "—"},
            {"key": "Nature", "value": record.nature},
            {"key": "État", "value": record.etat},
            {"key": "Durée du contrat", "value": f"{record.duration} mois"},
            {"key": "Apport", "value": f"{apport_pct:.0f} %"},
        ],
        "schedule": [],
        "estimateNote": "Échéancier et valeur résiduelle contractuels non fournis — aucune estimation n'est présentée comme donnée réelle.",
        "totalCostLabel": _mad(financed),
        "creditCostLabel": "—",
        "guarantees": [
            {"ok": True, "title": "Bien identifié", "detail": record.natureBien or "Bien financé renseigné au dossier."},
        ],
    }


def _factorielle(result: ScoringAnalysisResult, record: StoredDossierRecord | None = None) -> list[dict[str, Any]]:
    series = result.years.series or {}
    labels = result.years.labels or ["—", "N-1", "N"]

    def row(label: str, key: str) -> dict[str, Any]:
        values = list(series.get(key) or [None, None, None])
        while len(values) < 3:
            values.insert(0, None)
        n2, n1, n = values[0], values[1], values[2]
        var = None
        if n is not None and n1 not in (None, 0):
            var = (n - n1) / abs(n1)
        tone = "flat"
        if var is not None:
            tone = "up" if var >= 0.02 else "down" if var <= -0.02 else "flat"
        return {
            "label": label,
            "y1": _kdh(n2),
            "y2": _kdh(n1),
            "y3": _kdh(n),
            "variation": _pct(var) if var is not None else "—",
            "variationTone": tone,
        }

    def ratio_items(keys: list[str]) -> list[dict[str, Any]]:
        out = []
        for key in keys:
            raw = result.ratios.get(key) or {}
            meta = RATIO_METADATA.get(key, {})
            status_fr = raw.get("status") or "Non calculable"
            out.append({
                "label": meta.get("label", key),
                "value": _fmt_ratio(key, raw.get("value")),
                "status": _RATIO_UI_STATUS.get(status_fr, "WARN"),
                "formula": meta.get("formula", ""),
                "threshold": meta.get("threshold", ""),
            })
        return out

    exercise = result.document.exercise
    period = exercise.label or (
        f"Du {exercise.debut} au {exercise.fin}" if exercise.debut and exercise.fin else ""
    )
    unit = f"KDH · {period}" if period else "KDH (Excel note commerciale)"

    endett_n = (series.get("endettement_terme") or [None, None, None])
    while len(endett_n) < 3:
        endett_n.insert(0, None)
    nouveau = float(record.amount) if record and record.amount else None
    global_n = None if endett_n[2] is None and nouveau is None else (endett_n[2] or 0) + (nouveau or 0)
    global_n1 = endett_n[1]
    global_row = {
        "label": "Endettement global après opération",
        "y1": _kdh(endett_n[0]),
        "y2": _kdh(global_n1),
        "y3": _kdh(global_n),
        "variation": "—",
        "variationTone": "flat",
    }
    nouveau_row = {
        "label": "Nouveau financement (objet du dossier)",
        "y1": "—",
        "y2": "—",
        "y3": _kdh(nouveau),
        "variation": "—",
        "variationTone": "flat",
    }

    axes = [
        {
            "num": "01",
            "title": "1) Évolution de l'activité",
            "unit": unit,
            "yearLabels": labels,
            "rows": [
                row("Chiffre d'affaires", "chiffre_affaires"),
                row("Résultat d'exploitation", "resultat_exploitation"),
                row("Résultat net", "resultat_net"),
                row("CAF", "caf"),
            ],
            "ratios": ratio_items(["croissance_ca", "caf_sur_ca", "rentabilite_commerciale"]),
        },
        {
            "num": "02",
            "title": "2) Structure financière",
            "unit": unit,
            "yearLabels": labels,
            "rows": [
                row("Immobilisations nettes", "actifs_immobilises"),
                row("Fonds propres", "fonds_propres"),
                row("Total bilan", "total_bilan"),
                row("Dettes de financement", "endettement_terme"),
                row("FDR", "fdr"),
                row("BFR", "bfr"),
                row("Trésorerie nette", "tresorerie_nette"),
            ],
            "ratios": ratio_items(["autonomie_financiere", "ratio_endettement", "capacite_remboursement"]),
        },
        {
            "num": "03",
            "title": "3) Liquidité et cycle d'exploitation",
            "unit": unit,
            "yearLabels": labels,
            "rows": [
                row("Stocks", "stocks"),
                row("Clients", "clients"),
                row("Fournisseurs", "fournisseurs"),
                row("FDR", "fdr"),
                row("Trésorerie nette", "tresorerie_nette"),
            ],
            "ratios": ratio_items(["fdr_sur_ca", "tresorerie_jours_ca", "delais_clients", "delais_fournisseurs", "delais_stocks"]),
        },
        {
            "num": "04",
            "title": "4) Endettement global après opération",
            "unit": unit,
            "yearLabels": labels,
            "rows": [
                row("Endettement à terme / CMT", "endettement_terme"),
                nouveau_row,
                global_row,
            ],
            "ratios": ratio_items(["endettement_global_apres_operation", "ratio_endettement"]),
        },
    ]
    return axes


def _comportement(result: ScoringAnalysisResult) -> dict[str, Any]:
    axe = result.axes.get("comportemental") or {}
    available = axe.get("status") not in {None, "not_provided"} and axe.get("score") is not None
    return {
        "score": axe.get("score") if available else None,
        "status": "AVAILABLE" if available else "NOT_AVAILABLE",
        "available": available,
        "profileLabel": "Données bancaires non extraites" if not available else "Axe comportemental",
        "summary": (
            "Axe comportemental non calculé — relevés bancaires non analysés."
            if not available
            else (axe.get("note") or "")
        ),
        "metrics": [
            {"label": "Incidents", "value": "n/c", "tone": "neutral", "sub": "Non fourni"},
            {"label": "Domiciliation CA", "value": "n/c", "tone": "neutral", "sub": "Relevés requis"},
            {"label": "Jours débit", "value": "n/c", "tone": "neutral", "sub": "Relevés requis"},
            {"label": "Écart flux / CA", "value": "n/c", "tone": "neutral", "sub": "Relevés requis"},
        ],
        "months": [],
        "signals": [
            {"tone": "warn", "title": "Axe 2 non noté", "detail": axe.get("note") or "Joindre 6 mois de relevés pour activer le score comportemental."},
        ],
    }


def _benchmark(record: StoredDossierRecord, result: ScoringAnalysisResult) -> dict[str, Any]:
    axe = result.axes.get("sectoriel") or {}
    if axe.get("status") == "NO_BENCHMARK" or axe.get("score") is None:
        return {
            "sectorLabel": record.sector,
            "sampleSize": None,
            "status": "NO_BENCHMARK",
            "caption": "Référentiel sectoriel non disponible pour ce secteur.",
            "rows": [],
            "aboveMedianLabel": "Non disponible",
            "comparables": [],
            "meta": axe.get("meta") or {},
        }
    for item in axe.get("comparaisons") or []:
        key = item.get("indicateur")
        meta = RATIO_METADATA.get(key, {})
        client = item.get("valeur")
        median = item.get("mediane")
        tone = "ok" if item.get("statut") == "Conforme" else "bad"
        rows.append({
            "label": meta.get("label", key),
            "client": _fmt_ratio(key, client),
            "median": _fmt_ratio(key, median),
            "clientPct": min(100, int(round(abs(client or 0) * 100))) if client is not None else 8,
            "medianPct": min(100, int(round(abs(median or 0) * 100))) if median is not None else 8,
            "tone": tone,
            "percentile": item.get("statut") or "—",
        })
    above = sum(1 for r in rows if r["tone"] == "ok")
    return {
        "sectorLabel": record.sector,
            "sampleSize": len(rows),
        "caption": "Comparaison aux médianes du panel sectoriel (axe 3, poids 10 %).",
        "rows": rows,
        "aboveMedianLabel": f"{above}/{len(rows)} indicateur(s) au-dessus de la médiane" if rows else "Aucun indicateur comparable",
        "comparables": [],
    }


def _memo(record: StoredDossierRecord, result: ScoringAnalysisResult, scoring: dict[str, Any], ratios: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    identity = result.document.identity
    axes = _factorielle(result, record)
    activity_rows = axes[0]["rows"] if axes else []
    year_headers = list(result.years.labels or ["—", "N-1", "N"])
    return {
        "title": "Mémo d'analyse crédit-bail",
        "subtitle": record.name,
        "refLine": f"{record.id} · {record.sector}",
        "recommendation": scoring["recommendation"],
        "scoreLine": f"Score {scoring['score']}/100 — {result.decision.get('classe', '')}",
        "clientGrid": [
            {"label": "N° tiers", "value": (result.client_lookup.primary.tiers if result.client_lookup and result.client_lookup.primary else None) or "—"},
            {"label": "ICE", "value": identity.ice or result.document.company.ice or record.ice or "—"},
            {"label": "Identifiant fiscal", "value": identity.identifiant_fiscal or "—"},
            {"label": "Taxe professionnelle", "value": identity.taxe_professionnelle or "—"},
            {"label": "RC", "value": result.document.company.rc or record.rc or "—"},
            {"label": "Adresse", "value": identity.adresse or "—"},
            {"label": "Ville", "value": identity.ville or "—"},
            {"label": "Activité", "value": identity.activite or "—"},
            {"label": "Période", "value": result.document.exercise.label or "—"},
            {"label": "Déclaration", "value": " ".join(p for p in (identity.declaration_date, identity.declaration_time) if p) or "—"},
            {"label": "Référence", "value": identity.reference or "—"},
            {"label": "Montant", "value": _mad(record.amount)},
            {"label": "Durée", "value": f"{record.duration} mois"},
        ],
        "sections": [
            {
                "title": "Synthèse",
                "paragraphs": [scoring["summary"]],
            },
            {
                "title": "1) Évolution de l'activité (KDH)",
                "table": {
                    "headers": ["Poste"] + year_headers,
                    "rows": [
                        [r["label"], r["y1"], r["y2"], r["y3"]]
                        for r in activity_rows
                    ],
                },
                "tableNote": "Source liasse — formules Excel « DEPOULLEMENT BILAN / Bilans - Analyse ».",
            },
            {
                "title": "Ratios (grille crédit-bail)",
                "table": {
                    "headers": ["Ratio", "Formule", "Valeur", "Seuil", "Statut"],
                    "rows": [
                        [
                            item["label"],
                            item.get("formula") or "",
                            item["value"],
                            item.get("threshold") or "",
                            "Conforme" if item["status"] == "GOOD" else "À surveiller" if item["status"] == "WARN" else "Non conforme",
                        ]
                        for item in ratios.get("items") or []
                    ],
                },
            },
            {
                "title": "Points d'attention",
                "paragraphs": scoring.get("attention", {}).get("pointsVigilance") or [],
                "chips": [
                    {"ok": ratios["conformCount"] >= max(1, len(ratios["items"]) // 2), "label": "Ratios conformes", "value": f"{ratios['conformCount']}/{len(ratios['items'])}"},
                    {"ok": result.completeness_pct >= 70, "label": "Complétude extraction", "value": f"{result.completeness_pct:.0f} %"},
                ],
            },
            {
                "title": "Conclusion",
                "conclusionBanner": f"{scoring['recommendation']} — Score {scoring['score']}/100 — {result.decision.get('classe') or ''}",
            },
        ],
        "signerName": record.analyst,
        "signerRole": "Analyste crédit-bail",
        "signedAt": now,
    }


def _copilot(record: StoredDossierRecord, scoring: dict[str, Any], result: ScoringAnalysisResult) -> dict[str, Any]:
    return {
        "welcomeMessage": (
            f"Bonjour, je suis le copilote Qwen pour {record.name} "
            f"(score {scoring['score']}/100). Posez une question sur les ratios, les risques ou la synthèse."
        ),
        "chips": [
            {"label": "Pourquoi ce score ?", "intent": "pourquoi"},
            {"label": "Risques", "intent": "risque"},
            {"label": "Complétude", "intent": "complet"},
            {"label": "Secteur", "intent": "secteur"},
        ],
        "qa": {
            "pourquoi": scoring["summary"],
            "risque": " ".join(result.warnings[:3]) or "Aucun signal bloquant remonté par les contrôles.",
            "complet": f"Complétude d'extraction {result.completeness_pct:.0f} % sur les postes financiers.",
            "secteur": f"Benchmark {record.sector} — {result.axes.get('sectoriel', {}).get('score', 'n/c')}/100.",
            "fallback": "Je m'appuie sur l'extraction de la liasse, les 11 ratios et le copilote.",
        },
    }


def _header(record: StoredDossierRecord, result: ScoringAnalysisResult | None = None) -> dict[str, Any]:
    company = result.document.company if result else None
    identity = result.document.identity if result else None
    ice = (identity.ice if identity else None) or (company.ice if company else None) or record.ice or "—"
    rc = (company.rc if company else None) or record.rc or "—"
    if_id = (identity.identifiant_fiscal if identity else None) or (company.identifiant_fiscal if company else None)
    name = (identity.raison_sociale if identity and identity.raison_sociale else None) or (
        company.raison_sociale if company and company.raison_sociale else None
    ) or record.name
    tiers = None
    if result and result.client_lookup and result.client_lookup.primary:
        tiers = result.client_lookup.primary.tiers
        if not name and result.client_lookup.primary.raison_sociale:
            name = result.client_lookup.primary.raison_sociale
    ville = (identity.ville if identity else None) or (company.ville if company else None) or (
        identity.adresse if identity else None
    )
    bits = [record.sector]
    if tiers:
        bits.append(f"Tiers {tiers}")
    if ice and ice != "—":
        bits.append(f"ICE {ice}")
    if if_id:
        bits.append(f"IF {if_id}")
    if rc and rc != "—":
        bits.append(f"RC {rc}")
    if identity and identity.activite:
        bits.append(identity.activite)
    if record.source == "pvc" and record.noDemande:
        bits.append(f"PVC {record.noDemande}")
    return {
        "id": record.id,
        "shortCode": record.id.split("-")[-1],
        "companyName": name,
        "subtitle": " · ".join(bits),
        "status": record.status,
        "statusLabel": _STATUS_LABEL.get(record.status, record.status),
        "analyst": record.analyst,
        "amountFinanced": record.amount,
        "assetValue": record.valeurBien or record.amount,
        "durationMonths": record.duration,
        "apportPct": record.apport,
        "location": ville or "Maroc",
        "source": record.source,
        "noDemande": record.noDemande,
        "noPv": record.noPv,
        "tiers": tiers,
        "clientLookupStatus": result.client_lookup.status if result and result.client_lookup else None,
    }


def empty_workspace(record: StoredDossierRecord) -> dict[str, Any]:
    documents = _documents(record, None)
    bien = _bien(record)
    return {
        "header": _header(record),
        "pipeline": _pipeline(None, 0),
        "documents": documents,
        "scoring": {
            "score": record.score,
            "classe": "",
            "recommendation": "Lancez l'analyse pour extraire la liasse et calculer le score.",
            "riskLabel": "En attente d'extraction",
            "summary": "Aucune extraction n'a encore été exécutée sur ce dossier. Le bouton Relancer lance l'analyse de la liasse (identité, bilan, CPC, CAF).",
            "ratiosOk": 0,
            "ratiosTotal": 11,
            "dossierCompletenessPct": 0,
            "factors": [],
            "trend": [],
            "trendCaption": "Les graphiques s'afficheront après l'extraction de la liasse.",
            "attention": empty_synthese(),
        },
        "ratios": {"calcTime": "—", "conformCount": 0, "watchCount": 0, "items": [], "fiscal": []},
        "bien": bien,
        "factorielle": [],
        "yearLabels": ["—", "N-1", "N"],
        "comportement": {
            "score": None,
            "status": "NOT_AVAILABLE",
            "available": False,
            "profileLabel": "Non calculé",
            "summary": "Axe comportemental non calculé — relevés bancaires non analysés.",
            "metrics": [],
            "months": [],
            "signals": [],
        },
        "benchmark": {
            "sectorLabel": record.sector,
            "sampleSize": 0,
            "status": "NO_BENCHMARK",
            "caption": "Référentiel sectoriel non disponible pour ce secteur.",
            "rows": [],
            "aboveMedianLabel": "—",
            "comparables": [],
        },
        "memo": {
            "title": "Mémo d'analyse",
            "subtitle": record.name,
            "refLine": record.id,
            "recommendation": "Analyse non lancée",
            "scoreLine": "—",
            "clientGrid": [],
            "sections": [],
            "signerName": record.analyst,
            "signerRole": "Analyste crédit-bail",
            "signedAt": "",
        },
        "copilot": {
            "welcomeMessage": "Je suis le copilote Qwen. Posez une question sur ce dossier : dès que l'analyse est prête, je m'appuie sur le score et les ratios.",
            "chips": [
                {"label": "Pourquoi ce score ?", "intent": "pourquoi"},
                {"label": "Risques", "intent": "risque"},
                {"label": "Complétude", "intent": "complet"},
                {"label": "Secteur", "intent": "secteur"},
            ],
            "qa": {"pourquoi": "", "risque": "", "complet": "", "secteur": "", "fallback": "Analyse non disponible."},
        },
    }


def _financial_statements(result: ScoringAnalysisResult) -> dict[str, Any]:
    labels = result.years.labels or ["—", "N-1", "N"]
    groups = {
        "actif": ("Bilan Actif", []),
        "passif": ("Bilan Passif", []),
        "cpc": ("CPC", []),
        "esg": ("ESG", []),
        "derive": ("Soldes intermédiaires", []),
    }
    for field in result.fields:
        src = (field.source or "").lower()
        if "actif" in src:
            bucket = "actif"
        elif "passif" in src:
            bucket = "passif"
        elif src == "cpc":
            bucket = "cpc"
        elif src == "esg":
            bucket = "esg"
        else:
            bucket = "derive"
        evidence = field.current.evidence[0] if field.current.evidence else None
        groups[bucket][1].append({
            "code": field.code,
            "label": field.label,
            "n1": field.previous.observed_value if field.previous else None,
            "n": field.current.observed_value,
            "n1Usable": bool(field.previous and field.previous.usable),
            "nUsable": field.current.usable,
            "n1Status": field.previous.status if field.previous else "missing",
            "nStatus": field.current.status,
            "source": field.source,
            "page": evidence.page_number if evidence else None,
            "confidence": field.current.confidence,
            "evidence": [item.model_dump() for item in field.current.evidence],
        })
    return {
        "yearLabels": labels,
        "actif": groups["actif"][1],
        "passif": groups["passif"][1],
        "cpc": groups["cpc"][1],
        "esg": groups["esg"][1],
        "synthese": groups["derive"][1],
    }


def build_workspace(record: StoredDossierRecord, result: ScoringAnalysisResult) -> dict[str, Any]:
    documents = _documents(record, result)
    ratios = _ratios_block(result, record)
    scoring = _scoring_block(record, result, ratios)
    identity = result.document.identity
    period = {
        "start": identity.period_start,
        "end": identity.period_end,
        "label": result.document.exercise.label,
        "yearN": result.years.years[2] if result.years.years else None,
        "yearN1": result.years.years[1] if len(result.years.years) > 1 else None,
    }
    try:
        from app.services.sector_analysis_service import sector_analysis_service

        sector = sector_analysis_service.for_workspace(record, result)
    except Exception:
        sector = {"status": "UNAVAILABLE", "warnings": ["Analyse sectorielle temporairement indisponible."], "scoring": {"status": "NOT_CALIBRATED", "includedInFinalScore": False, "score": None}}
    return {
        "header": _header(record, result),
        "pipeline": _pipeline(result, int(round(float(scoring["score"] or 0)))),
        "documents": documents,
        "scoring": scoring,
        "ratios": ratios,
        "bien": _bien(record),
        "factorielle": _factorielle(result, record),
        "yearLabels": result.years.labels,
        "period": period,
        "comportement": _comportement(result),
        "sectorAnalysis": sector,
        "benchmark": {
            "sectorLabel": (sector.get("sector") or {}).get("label") or record.sector,
            "sampleSize": None,
            "status": "NO_BENCHMARK",
            "caption": "Le score sectoriel n’est pas calibré. L’analyse HCP est informative.",
            "rows": [],
            "aboveMedianLabel": "Non intégré au score",
            "comparables": [],
            "meta": {"source": "HCP"},
        },
        "memo": _memo(record, result, scoring, ratios),
        "copilot": _copilot(record, scoring, result),
        "financialStatements": _financial_statements(result),
        "fiscalAnalysis": result.fiscal_analysis.model_dump(),
        "capitalAnalysis": result.capital_analysis.model_dump(),
        "quality": result.quality.model_dump(),
        "readiness": result.readiness.model_dump(),
        "controls": [item.model_dump() for item in result.controls],
        "clientLookup": result.client_lookup.model_dump(mode="json") if result.client_lookup else None,
        "analysisFingerprint": analysis_source_fingerprint(record),
        "analysisStale": False,
    }
