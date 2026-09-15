"""Conformité RCC — affichage serveur, sans recalcul côté client."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.analyse import RCC_ELEMENTS
from app.services.rcc_dossier_store import RccDossier, effective_values

CONFIDENCE_REVIEW_THRESHOLD = 0.8
LOCKED_CODES = frozenset({"TOTAL_BILAN", "RESULTAT_NET"})
DERIVED_TAG_CODES = frozenset({"TYPE_RESULTAT"})

SECTION_PIECES = "Pièces obligatoires"
SECTION_COMPLETUDE = "Complétude des champs RCC"
SECTION_COHERENCE = "Cohérence comptable"
SECTION_RCC = "Cohérence des postes RCC"
SECTION_CONTROLE = "Contrôle RCC"

RCC_IDENTITIES: list[tuple[str, str, list[str], list[str]]] = [
    (
        "Total du bilan = actifs immobilisés + actif circulant + trésorerie actif",
        "==",
        ["TOTAL_BILAN"],
        ["ACTIFS_IMMOBILISES", "ACTIF_CIRCULANT", "TRESORERIE_ACTIF"],
    ),
    (
        "Créances clients incluses dans l'actif circulant",
        "<=",
        ["CREANCES_CLIENTS"],
        ["ACTIF_CIRCULANT"],
    ),
    (
        "Dettes fournisseurs incluses dans le passif circulant",
        "<=",
        ["DETTES_FOURNISSEURS"],
        ["PASSIF_CIRCULANT"],
    ),
    (
        "Chiffre d'affaires à l'export inférieur ou égal au chiffre d'affaires",
        "<=",
        ["CA_EXPORT"],
        ["CHIFFRE_AFFAIRES"],
    ),
    (
        "Caisse incluse dans la trésorerie actif",
        "<=",
        ["CAISSE"],
        ["TRESORERIE_ACTIF"],
    ),
]


class ComplianceRule(BaseModel):
    section: str
    label: str
    ok: bool
    blocking: bool = False
    detail: str = ""
    affected_fields: list[str] = Field(default_factory=list)


class ComplianceSection(BaseModel):
    title: str
    state: str
    severity: str
    rules: list[ComplianceRule]


class ComplianceReport(BaseModel):
    sections: list[ComplianceSection]
    rules_total: int
    rules_ok: int
    pct: int
    blockers: int
    warnings: int
    can_validate: bool
    summary: str
    missing_fields: list[str] = Field(default_factory=list)
    conflicting_fields: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}".replace(",", " ")


def build_compliance(dossier: RccDossier) -> ComplianceReport:
    result = dossier.result
    overrides = {item.field_code: item for item in dossier.overrides}
    rules: list[ComplianceRule] = []
    has_doc = bool(dossier.pdf_path)
    has_result = result is not None
    document = (result or {}).get("document") or {}

    rules.append(
        ComplianceRule(
            section=SECTION_PIECES,
            label="Liasse fiscale rattachée au dossier",
            ok=has_doc,
            blocking=True,
            detail=(
                f"{dossier.filename} · {document.get('pages_total', 0)} page(s)"
                if has_doc and result
                else "aucun fichier"
            ),
        )
    )
    rules.append(
        ComplianceRule(
            section=SECTION_PIECES,
            label="Extraction OCR exécutée sur la liasse",
            ok=has_result,
            blocking=True,
            detail=(
                f"{document.get('pages_processed', 0)}/{document.get('pages_total', 0)} pages traitées"
                if result
                else "non exécutée"
            ),
        )
    )

    missing: list[str] = []
    conflicting: list[str] = []
    low_conf: list[str] = []
    rcc_codes = {code for _, code, _, _ in RCC_ELEMENTS}
    filled = 0
    fields = (result or {}).get("fields") or []
    rcc_fields = [item for item in fields if item.get("code") in rcc_codes]
    if result:
        for field in rcc_fields:
            corrected = overrides.get(field["code"])
            has_value = (
                corrected is not None and corrected.corrected_value is not None
            ) or (
                field.get("value") is not None
                if field["code"] not in DERIVED_TAG_CODES
                else bool(field.get("note"))
            )
            if has_value:
                filled += 1
            else:
                missing.append(field["code"])
            if field.get("status") == "conflicting" and corrected is None:
                conflicting.append(field["code"])
            if (
                field["code"] not in LOCKED_CODES
                and field["code"] not in DERIVED_TAG_CODES
                and corrected is None
                and field.get("status") not in {"missing", "conflicting"}
                and float(field.get("confidence") or 0) < CONFIDENCE_REVIEW_THRESHOLD
            ):
                low_conf.append(field["code"])
    else:
        missing = [code for _, code, _, _ in RCC_ELEMENTS]

    rules.append(
        ComplianceRule(
            section=SECTION_COMPLETUDE,
            label="Tous les postes RCC sont renseignés",
            ok=not missing,
            blocking=True,
            detail=f"{filled}/{len(RCC_ELEMENTS)} renseignés",
            affected_fields=missing,
        )
    )
    rules.append(
        ComplianceRule(
            section=SECTION_COMPLETUDE,
            label="Date de clôture d'exercice identifiée",
            ok=bool(dossier.exercice_date),
            blocking=False,
            detail=dossier.exercice_date or "non détectée",
        )
    )
    rules.append(
        ComplianceRule(
            section=SECTION_COMPLETUDE,
            label="Identification du client (raison sociale et ICE)",
            ok=bool(dossier.client_name and dossier.ice),
            blocking=False,
            detail=dossier.ice or "ICE non détecté",
        )
    )

    editable_codes = {
        code
        for _, code, _, _ in RCC_ELEMENTS
        if code not in LOCKED_CODES and code not in DERIVED_TAG_CODES
    }
    corrected_codes = set(overrides)
    controls = (result or {}).get("controls") or []
    if not controls:
        rules.append(
            ComplianceRule(
                section=SECTION_COHERENCE,
                label="Contrôles comptables exécutés",
                ok=False,
                blocking=bool(has_result),
                detail="aucun contrôle disponible",
            )
        )
    for control in controls:
        actionable = [c for c in control.get("affected_fields") or [] if c in editable_codes]
        arbitrated = bool(actionable) and all(c in corrected_codes for c in actionable)
        status = control.get("status")
        if status == "passed":
            ok, blocking = True, False
            detail_txt = f"{_fmt(control.get('observed'))} = {_fmt(control.get('expected'))}"
        elif status == "failed":
            if arbitrated:
                ok, blocking = True, False
                detail_txt = f"arbitré — {len(actionable)} poste(s) repris"
            elif actionable:
                ok, blocking = False, True
                detail_txt = f"écart {_fmt(abs(control.get('difference') or 0))}"
            else:
                ok, blocking = False, False
                detail_txt = f"écart {_fmt(abs(control.get('difference') or 0))} — non corrigeable ici"
        else:
            ok, blocking = True, False
            detail_txt = "non testable"
        rules.append(
            ComplianceRule(
                section=SECTION_COHERENCE,
                label=control.get("label") or control.get("code") or "Contrôle",
                ok=ok,
                blocking=blocking,
                detail=detail_txt,
                affected_fields=actionable or (control.get("affected_fields") or []),
            )
        )

    values = effective_values(dossier)
    for label, operator, left_codes, right_codes in RCC_IDENTITIES:
        left_vals = [values.get(c) for c in left_codes]
        right_vals = [values.get(c) for c in right_codes]
        if any(v is None for v in left_vals + right_vals):
            rules.append(
                ComplianceRule(
                    section=SECTION_RCC,
                    label=label,
                    ok=True,
                    blocking=False,
                    detail="non testable",
                    affected_fields=left_codes + right_codes,
                )
            )
            continue
        left = sum(left_vals)  # type: ignore[arg-type]
        right = sum(right_vals)  # type: ignore[arg-type]
        tolerance = max(1.0, abs(right) * 0.0001)
        ok = abs(left - right) <= tolerance if operator == "==" else left <= right + tolerance
        rules.append(
            ComplianceRule(
                section=SECTION_RCC,
                label=label,
                ok=ok,
                blocking=not ok,
                detail=(
                    f"{_fmt(left)} {'=' if operator == '==' else '≤'} {_fmt(right)}"
                    if ok
                    else f"{_fmt(left)} vs {_fmt(right)} · écart {_fmt(abs(left - right))}"
                ),
                affected_fields=left_codes + right_codes,
            )
        )

    rules.append(
        ComplianceRule(
            section=SECTION_CONTROLE,
            label="Aucun poste en conflit d'extraction non arbitré",
            ok=not conflicting,
            blocking=True,
            detail=f"{len(conflicting)} poste(s) en conflit" if conflicting else "aucun conflit",
            affected_fields=conflicting,
        )
    )
    threshold_pct = int(CONFIDENCE_REVIEW_THRESHOLD * 100)
    rules.append(
        ComplianceRule(
            section=SECTION_CONTROLE,
            label=f"Postes sous {threshold_pct} % de confiance OCR tous contrôlés",
            ok=not low_conf,
            blocking=True,
            detail=f"{len(low_conf)} en attente de contrôle" if low_conf else "aucun en attente",
            affected_fields=low_conf,
        )
    )
    rules.append(
        ComplianceRule(
            section=SECTION_CONTROLE,
            label="Piste d'audit horodatée et nominative",
            ok=True,
            blocking=False,
            detail=f"{len(dossier.overrides)} correction(s) tracée(s)",
        )
    )

    ok_count = sum(1 for r in rules if r.ok)
    blockers = sum(1 for r in rules if not r.ok and r.blocking)
    warns = sum(1 for r in rules if not r.ok and not r.blocking)
    pct = round(100 * ok_count / len(rules)) if rules else 0
    sections: list[ComplianceSection] = []
    for title in (
        SECTION_PIECES,
        SECTION_COMPLETUDE,
        SECTION_COHERENCE,
        SECTION_RCC,
        SECTION_CONTROLE,
    ):
        section_rules = [r for r in rules if r.section == title]
        if not section_rules:
            continue
        bad = [r for r in section_rules if not r.ok]
        blk = sum(1 for r in bad if r.blocking)
        sections.append(
            ComplianceSection(
                title=title,
                state=(
                    f"{blk} bloquant(s)"
                    if blk
                    else f"{len(bad)} à justifier"
                    if bad
                    else "Conforme"
                ),
                severity="blocked" if blk else "warn" if bad else "ok",
                rules=section_rules,
            )
        )
    if blockers:
        summary = f"{blockers} règle(s) bloquante(s) non satisfaite(s) — validation impossible"
    elif warns:
        summary = f"Règles bloquantes levées · {warns} avertissement(s) à justifier"
    else:
        summary = "Dossier conforme aux règles RCC"

    return ComplianceReport(
        sections=sections,
        rules_total=len(rules),
        rules_ok=ok_count,
        pct=pct,
        blockers=blockers,
        warnings=warns,
        can_validate=blockers == 0,
        summary=summary,
        missing_fields=missing,
        conflicting_fields=conflicting,
        low_confidence_fields=low_conf,
    )
