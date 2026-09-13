"""Projection extracteur V6 → contrat API Scoring (champs RCC + identity + CAF)."""
from __future__ import annotations

from typing import Any

from app.schemas.analyse import (
    RCC_ELEMENTS,
    SCORING_EXTRA_ELEMENTS,
    AccountingControlView,
    AmountQuality,
    AssociateRow,
    CapitalAnalysis,
    CompanyInfo,
    DocumentSummary,
    ExerciseInfo,
    ExtractedField,
    ExtractionSummary,
    FieldEvidence,
    FieldQualityStatus,
    FinancialPageAudit,
    FiscalAnalysis,
    FiscalBlock,
    FiscalLine,
    IdentityInfo,
    PeriodFieldValue,
)

PIPELINE_MODEL = "financial-extractor-v6"

_IDENTITY_KEYS = (
    "identifiant_fiscal",
    "ice",
    "raison_sociale",
    "taxe_professionnelle",
    "ville",
    "adresse",
    "activite",
    "secteur",
    "period_start",
    "period_end",
    "declaration_date",
    "declaration_time",
    "reference",
)

# Poste API ← clés canoniques V6 (ordre = priorité).
_CANONICAL_KEYS: dict[str, list[str]] = {
    "ACTIFS_IMMOBILISES": ["total_immobilise"],
    "TOTAL_BILAN": ["total_actif", "total_passif"],
    "CHIFFRE_AFFAIRES": ["chiffre_affaires"],
    "CA_EXPORT": ["chiffre_affaires_export"],
    "DETTES_BANCAIRES_MLT": ["dettes_financement"],
    "DETTES_BANCAIRES_CT": ["credits_tresorerie", "credits_escompte"],
    "PASSIF_CIRCULANT": ["total_passif_circulant"],
    "DETTES_FOURNISSEURS": ["fournisseurs"],
    "COMPTE_COURANT_ASSOCIES": ["comptes_associes_passif"],
    "TRESORERIE_PASSIF": ["tresorerie_passif", "banques_passif"],
    "ACTIF_CIRCULANT": ["total_actif_circulant"],
    "CREANCES_CLIENTS": ["clients"],
    "TRESORERIE_ACTIF": ["tresorerie_actif", "banques_actif"],
    "CAISSE": ["caisse"],
    "ACHATS_REVENDUS": ["achats_rev_marchandises"],
    "ACHATS_CONSOMMES": ["achats_consommes"],
    "AUTRES_CHARGES_EXTERNES": ["autres_charges_externes"],
    "CHARGES_INTERETS": ["charges_interets", "charges_financieres"],
    "RESULTAT_NET": ["resultat_net"],
    "FONDS_PROPRES": ["fonds_propres"],
    "STOCKS": ["stocks"],
    "RESULTAT_EXPLOITATION": ["resultat_exploitation"],
    "DOTATIONS_EXPLOITATION": ["dotations_exploitation"],
    "CAF": ["caf"],
}

_CONTROL_MAP: list[tuple[str, str, str, list[str]]] = [
    ("total_actif_equals_total_passif", "bilan_equilibre", "Total Actif = Total Passif", ["TOTAL_BILAN"]),
    ("actif_components", "bilan_actif_totaux", "Bilan actif : immobilisé + circulant + trésorerie = total actif", ["ACTIFS_IMMOBILISES", "ACTIF_CIRCULANT", "TRESORERIE_ACTIF"]),
    ("passif_components", "bilan_passif_totaux", "Bilan passif : permanent + circulant + trésorerie = total passif", ["PASSIF_CIRCULANT", "TRESORERIE_PASSIF"]),
    ("chiffre_affaires", "cpc_ventes_chiffre_affaires", "CPC : ventes marchandises + ventes biens et services = chiffre d'affaires", ["CHIFFRE_AFFAIRES"]),
    ("resultat_net", "resultat_net", "Résultat net CPC / passif", ["RESULTAT_NET"]),
    ("row_net_equals_brut_minus_amort", "actif_brut_amort_net", "Bilan actif : Brut − Amortissements = Net", ["ACTIFS_IMMOBILISES"]),
    ("row_cpc_operations_sum", "cpc_operations_total", "CPC : opérations de l'exercice + exercices antérieurs = total", ["CHIFFRE_AFFAIRES"]),
    ("caf_esg_complete", "caf_esg", "ESG : capacité d'autofinancement", ["CAF"]),
]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def identity_from_v6(raw: dict[str, Any] | None) -> IdentityInfo:
    data = raw or {}
    payload = {key: _clean_text(data.get(key)) for key in _IDENTITY_KEYS}
    return IdentityInfo(**payload)


def company_from_identity(identity: IdentityInfo) -> CompanyInfo:
    return CompanyInfo(
        raison_sociale=identity.raison_sociale,
        identifiant_fiscal=identity.identifiant_fiscal,
        ice=identity.ice,
        rc=None,
        taxe_professionnelle=identity.taxe_professionnelle,
        adresse=identity.adresse,
        ville=identity.ville,
        activite=identity.activite,
        secteur=identity.secteur,
        period_start=identity.period_start,
        period_end=identity.period_end,
        declaration_date=identity.declaration_date,
        declaration_time=identity.declaration_time,
        reference=identity.reference,
    )


def exercise_from_identity(identity: IdentityInfo) -> ExerciseInfo:
    debut = identity.period_start
    fin = identity.period_end
    label = None
    if debut and fin:
        label = f"Du {debut} au {fin}"
    elif fin:
        label = f"Clôture au {fin}"
    return ExerciseInfo(debut=debut, fin=fin, label=label)


def _to_float(value: Any) -> float | None:
    if value is None or value is True or value is False:
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


def _period_field(entry: dict[str, Any] | None, period: str) -> PeriodFieldValue:
    """N et N-1 : observed ≠ usable. Le scoring n'utilise que usable_value."""
    if not entry:
        return PeriodFieldValue(status="missing", usable=False)
    observed = _to_float(entry.get(period))
    usable_raw = _to_float(entry.get(f"usable_{period}"))
    period_status = str((entry.get("period_status") or {}).get(period) or "")
    value_status = str((entry.get("value_status") or {}).get(period) or "")
    fused = ((entry.get("confidence_components") or {}).get(period) or {}).get("fused_score")
    confidence = float(fused) if fused is not None else _to_float(entry.get("confidence"))
    if confidence is not None and confidence > 1:
        confidence = min(1.0, confidence / 100.0)
    evidence = _evidence_for(entry, period)
    warnings: list[str] = []

    if period_status in {"blank", "explicit_blank"}:
        return PeriodFieldValue(
            status="blank_on_form",
            usable=False,
            period_status=period_status,
            confidence=confidence,
            evidence=evidence,
        )
    if observed is None and usable_raw is None:
        return PeriodFieldValue(
            status="missing",
            usable=False,
            period_status=period_status or "missing",
            confidence=confidence,
            evidence=evidence,
        )

    status: FieldQualityStatus = "ambiguous"
    usable = False
    usable_value = None
    if period_status == "conflict":
        status = "conflicting"
        warnings.append("Conflit de sources pour cette période.")
    elif value_status == "suspect":
        status = "suspect"
        warnings.append("Valeur marquée suspecte par l'extracteur.")
    elif value_status in {"cross_checked"} or period_status == "reconstructed_cross_checked":
        status = "cross_checked"
        usable = usable_raw is not None
        usable_value = usable_raw if usable else None
    elif value_status in {"high_confidence", "validated_by_equation"}:
        status = "confirmed" if value_status == "high_confidence" else "validated_by_equation"
        usable = usable_raw is not None
        usable_value = usable_raw if usable else None
    elif usable_raw is not None:
        status = "confirmed"
        usable = True
        usable_value = usable_raw
    else:
        status = "ambiguous"
        warnings.append("Valeur observée mais non autorisée pour le scoring.")

    return PeriodFieldValue(
        observed_value=observed if observed is not None else usable_raw,
        usable_value=usable_value,
        status=status,
        usable=usable,
        confidence=confidence,
        period_status=period_status or None,
        accounting_status=value_status or None,
        evidence=evidence,
        warnings=warnings,
    )


def _period_amount(entry: dict[str, Any] | None, period: str) -> tuple[float | None, str, float]:
    """Projection affichage : observed. Ne pas utiliser pour les ratios."""
    field = _period_field(entry, period)
    conf = float(field.confidence or 0.0)
    return field.observed_value, field.status, conf


def _evidence_for(entry: dict[str, Any] | None, period: str) -> list[FieldEvidence]:
    if not entry:
        return []
    proof = (entry.get("evidence") or {}).get(period) or {}
    if not proof and not entry.get("label"):
        return []
    return [
        FieldEvidence(
            page_number=proof.get("page") or entry.get("page"),
            raw_label=proof.get("label") or entry.get("label"),
            raw_value=str(proof.get("raw") or entry.get(period) or ""),
            column_name=period,
            page_type=str(proof.get("section") or entry.get("section") or ""),
            confidence=_to_float(proof.get("fused_confidence") or proof.get("confidence")),
            source_excerpt=str(proof.get("parser") or entry.get("source_parser") or "v6"),
            period=period,
        )
    ]


def _lookup_entry(canonical: dict[str, Any], keys: list[str]) -> tuple[str | None, dict[str, Any] | None]:
    for key in keys:
        entry = canonical.get(key)
        if entry:
            value = _period_field(entry, "current").usable_value
            if value is not None:
                return key, entry
    for key in keys:
        if key in canonical:
            return key, canonical[key]
    return None, None


def _chiffre_affaires(canonical: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    key, entry = _lookup_entry(canonical, ["chiffre_affaires"])
    if entry:
        value = _period_field(entry, "current").usable_value
        if value is not None:
            return entry, "chiffre_affaires"
    ventes_m = _period_field(canonical.get("ventes_marchandises"), "current")
    ventes_s = _period_field(canonical.get("ventes_biens_services"), "current")
    if ventes_m.usable_value is None and ventes_s.usable_value is None:
        return entry, key or "chiffre_affaires"
    current = None
    if ventes_m.usable_value is not None or ventes_s.usable_value is not None:
        current = (ventes_m.usable_value or 0.0) + (ventes_s.usable_value or 0.0)
    prev_m = _period_field(canonical.get("ventes_marchandises"), "previous")
    prev_s = _period_field(canonical.get("ventes_biens_services"), "previous")
    previous = None
    if prev_m.usable_value is not None or prev_s.usable_value is not None:
        previous = (prev_m.usable_value or 0.0) + (prev_s.usable_value or 0.0)
    fake = dict(canonical.get("chiffre_affaires") or {})
    fake["current"] = current
    fake["previous"] = previous
    fake["usable_current"] = current
    fake["usable_previous"] = previous
    fake["period_status"] = {"current": "observed", "previous": "observed" if previous is not None else "missing"}
    fake["label"] = "Ventes marchandises + ventes biens et services"
    fake["section"] = "cpc"
    return fake, "ventes_sum"


def map_fields(canonical: dict[str, Any]) -> list[ExtractedField]:
    fields: list[ExtractedField] = []
    labels = {code: label for _, code, label, _ in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)}
    sources = {code: source for _, code, label, source in (*RCC_ELEMENTS, *SCORING_EXTRA_ELEMENTS)}

    for number, code, label, source in RCC_ELEMENTS:
        if code == "TYPE_RESULTAT":
            continue
        if code == "CHIFFRE_AFFAIRES":
            entry, used = _chiffre_affaires(canonical)
            note = "Somme des lignes de ventes" if used == "ventes_sum" else None
        else:
            _, entry = _lookup_entry(canonical, _CANONICAL_KEYS.get(code, []))
            note = None
        current = _period_field(entry, "current")
        previous = _period_field(entry, "previous")
        fields.append(
            ExtractedField(
                number=number,
                code=code,
                label=label,
                source=source,
                current=current,
                previous=previous,
                note=note,
            )
        )

    rn = next((f for f in fields if f.code == "RESULTAT_NET"), None)
    type_note = None
    type_status = "missing"
    if rn is not None and rn.value is not None:
        type_status = "derived"
        if rn.value > 0:
            type_note = "Bénéficiaire"
        elif rn.value < 0:
            type_note = "Déficitaire"
        else:
            type_note = "Nul"
    fields.append(
        ExtractedField(
            number=20,
            code="TYPE_RESULTAT",
            label=labels["TYPE_RESULTAT"],
            source=sources["TYPE_RESULTAT"],
            value=None,
            status=type_status,
            note=type_note,
            confidence=0.9 if type_note else 0.0,
        )
    )

    for number, code, label, source in SCORING_EXTRA_ELEMENTS:
        if code in {"DETTES_FINANCIERES", "ENDETTEMENT_TERME", "TRESORERIE_NETTE", "FDR", "BFR"}:
            continue
        if code == "CAF":
            source = "ESG"
        _, entry = _lookup_entry(canonical, _CANONICAL_KEYS.get(code, []))
        current = _period_field(entry, "current")
        previous = _period_field(entry, "previous")
        fields.append(
            ExtractedField(
                number=number,
                code=code,
                label=label,
                source=source,
                current=current,
                previous=previous,
            )
        )
    return fields


def map_page_audit(v6: dict[str, Any]) -> list[FinancialPageAudit]:
    pages: list[FinancialPageAudit] = []
    financial = {
        "bilan_actif",
        "bilan_passif",
        "cpc",
        "esg",
        "detail_cpc",
        "resultat_fiscal",
        "capital_repartition",
    }
    for page in v6.get("pages") or []:
        section = str(page.get("section") or "generic")
        errors = page.get("errors") or []
        rows = int(page.get("row_count") or 0)
        if not rows:
            # pages[] is stripped of rows; count from all_rows
            rows = sum(1 for row in v6.get("all_rows") or [] if row.get("page") == page.get("page"))
        if errors:
            status = "failed"
        elif section in financial and rows:
            status = "processed"
        elif section in financial:
            status = "empty"
        else:
            status = "skipped"
        rotation = page.get("rotation_clockwise") or 0
        try:
            orientation = int(rotation) % 360
        except (TypeError, ValueError):
            orientation = 0
        pages.append(
            FinancialPageAudit(
                page_number=int(page.get("page") or 0),
                detected_type=section.upper() if section != "generic" else "AUTRE",
                orientation=orientation if orientation in {0, 90, 180, 270} else 0,
                extraction_status=status,
                extraction_strategy=str(page.get("parser") or page.get("kind") or "v6"),
                candidates_count=rows,
                error="; ".join(str(e) for e in errors) if errors else None,
            )
        )
    return pages


def map_controls(
    validations: list[dict[str, Any]],
    *,
    year_n: int | None = None,
) -> list[AccountingControlView]:
    known = {item[0]: item for item in _CONTROL_MAP}
    controls: list[AccountingControlView] = []
    for row in validations or []:
        name = str(row.get("check") or "")
        period: str | None = None
        base = name
        if name.endswith("_current"):
            period = "current"
            base = name[: -len("_current")]
        elif name.endswith("_previous"):
            period = "previous"
            base = name[: -len("_previous")]
        elif row.get("period") in {"current", "previous"}:
            period = str(row.get("period"))
        meta = known.get(base)
        if meta is None:
            continue
        _, code, label, affected = meta
        status_raw = str(row.get("status") or "not_evaluable")
        if status_raw not in {"passed", "failed", "not_evaluable"}:
            status_raw = "failed" if status_raw not in {"ok", "passed"} else "passed"
        if status_raw == "not_evaluable":
            mapped_status = "not_evaluable"
        elif status_raw == "passed":
            mapped_status = "passed"
        else:
            mapped_status = "failed"
        difference = _to_float(row.get("difference"))
        period_label = None
        if period == "current" and year_n:
            period_label = str(year_n)
        elif period == "previous" and year_n:
            period_label = str(year_n - 1)
        suffix = f" ({period_label})" if period_label else (" N" if period == "current" else " N-1" if period == "previous" else "")
        controls.append(
            AccountingControlView(
                code=f"{code}/{period}" if period else code,
                label=f"{label}{suffix}",
                period=period if period in {"current", "previous"} else None,
                period_label=period_label,
                status=mapped_status,
                expected=_to_float((row.get("inputs") or {}).get("expected")),
                observed=_to_float(row.get("observed")),
                difference=difference,
                tolerance=0.02,
                affected_fields=affected,
                message=(
                    "Contrôle non évaluable."
                    if mapped_status == "not_evaluable"
                    else "Contrôle vérifié."
                    if mapped_status == "passed"
                    else f"Écart {difference} (tolérance 0,02)."
                ),
            )
        )
    controls.sort(key=lambda c: (c.period != "current", c.status != "failed", c.label))
    return controls


def document_from_v6(v6: dict[str, Any], filename: str, identity: IdentityInfo) -> DocumentSummary:
    pages = map_page_audit(v6)
    source_pages = (v6.get("source") or {}).get("pages") or len(pages)
    return DocumentSummary(
        filename=filename,
        pages_total=int(v6.get("_pages_total") or source_pages or len(pages)),
        pages_processed=sum(1 for p in pages if p.extraction_status == "processed"),
        pages_skipped=sum(1 for p in pages if p.extraction_status in {"skipped", "empty"}),
        pages_failed=sum(1 for p in pages if p.extraction_status == "failed"),
        company=company_from_identity(identity),
        identity=identity,
        exercise=exercise_from_identity(identity),
    )


def extraction_summary(pages: list[FinancialPageAudit], warnings: list[str]) -> ExtractionSummary:
    return ExtractionSummary(model=PIPELINE_MODEL, page_audit=pages, warnings=warnings)


def identity_warnings(v6: dict[str, Any], identity: IdentityInfo) -> list[str]:
    warnings: list[str] = []
    for conflict in v6.get("identity_conflicts") or []:
        warnings.append(
            f"Identité divergente ({conflict.get('field')}) page {conflict.get('page')} : "
            f"{conflict.get('value')} (retenu {conflict.get('selected')})."
        )
    missing = [
        label
        for key, label in (
            ("ice", "ICE"),
            ("identifiant_fiscal", "identifiant fiscal"),
            ("raison_sociale", "raison sociale"),
            ("period_start", "début d'exercice"),
            ("period_end", "fin d'exercice"),
        )
        if not getattr(identity, key, None)
    ]
    if missing:
        warnings.append("Identité incomplète sur le bilan : " + ", ".join(missing) + ".")
    return warnings


def _amount_quality(raw: Any, *, flags: list[str] | None = None, evidence: list[FieldEvidence] | None = None) -> AmountQuality:
    value = _to_float(raw)
    if value is None:
        return AmountQuality(status="missing", usable=False, evidence=evidence or [])
    suspect = any("suspect" in str(flag).lower() for flag in (flags or []))
    return AmountQuality(
        value=value,
        status="suspect" if suspect else "confirmed",
        usable=not suspect,
        evidence=evidence or [],
    )


def _fiscal_evidence(blob: Any) -> list[FieldEvidence]:
    items = blob if isinstance(blob, list) else [blob] if blob else []
    out: list[FieldEvidence] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            FieldEvidence(
                page_number=item.get("page"),
                raw_label=item.get("label"),
                raw_value=str(item.get("raw") or item.get("value") or ""),
                page_type="resultat_fiscal",
                source_excerpt=str(item.get("parser") or "v6"),
            )
        )
    return out


def map_fiscal_analysis(v6: dict[str, Any]) -> FiscalAnalysis:
    raw = v6.get("resultat_fiscal") or {}
    if not raw:
        return FiscalAnalysis(available=False)
    flags = list(raw.get("quality_flags") or [])
    evidence = raw.get("evidence") or {}
    reint = raw.get("reintegrations_fiscales") or {}
    ded = raw.get("deductions_fiscales") or {}
    details_reint = [
        FiscalLine(
            label=str(item.get("label") or ""),
            amount=_to_float(item.get("amount")),
            evidence=_fiscal_evidence(item.get("evidence")),
        )
        for item in (reint.get("details") or [])
        if isinstance(item, dict)
    ]
    details_ded = [
        FiscalLine(
            label=str(item.get("label") or ""),
            amount=_to_float(item.get("amount")),
            evidence=_fiscal_evidence(item.get("evidence")),
        )
        for item in (ded.get("details") or [])
        if isinstance(item, dict)
    ]
    rn = _amount_quality(raw.get("resultat_net_comptable"), flags=flags, evidence=_fiscal_evidence(evidence.get("resultat_net_comptable")))
    brut = _amount_quality(raw.get("resultat_brut_fiscal"), flags=flags, evidence=_fiscal_evidence(evidence.get("resultat_brut_fiscal")))
    net = _amount_quality(raw.get("resultat_net_fiscal"), flags=flags, evidence=_fiscal_evidence(evidence.get("resultat_net_fiscal")))
    deficit = _amount_quality(raw.get("deficit_net_fiscal"), flags=flags, evidence=_fiscal_evidence(evidence.get("deficit_net_fiscal")))
    available = any(
        item.value is not None
        for item in (rn, brut, net, deficit)
    ) or bool(details_reint) or bool(details_ded) or reint.get("total") is not None or ded.get("total") is not None
    warnings = [str(flag) for flag in flags]
    validation = "a_verifier" if flags or not available else "coherent"
    return FiscalAnalysis(
        available=available,
        resultat_net_comptable=rn,
        reintegrations=FiscalBlock(total=_to_float(reint.get("total")), details=details_reint),
        deductions=FiscalBlock(total=_to_float(ded.get("total")), details=details_ded),
        resultat_brut_fiscal=brut,
        reports_deficitaires=deficit,
        resultat_net_fiscal=net,
        validation_status=validation if available else None,
        warnings=warnings,
    )


def map_capital_analysis(v6: dict[str, Any]) -> CapitalAnalysis:
    raw = v6.get("capital_repartition") or {}
    if not raw:
        return CapitalAnalysis(available=False)
    flags = list(raw.get("quality_flags") or [])
    capital = _amount_quality(raw.get("capital_social"), flags=flags, evidence=_fiscal_evidence((raw.get("evidence") or {}).get("capital_social")))
    associates: list[AssociateRow] = []
    for person in raw.get("associes") or []:
        if not isinstance(person, dict):
            continue
        name = person.get("nom_prenom") or person.get("raison_sociale")
        identifier = person.get("if") or person.get("cni") or person.get("carte_etranger")
        identifier_type = "IF" if person.get("if") else "CNI" if person.get("cni") else "CE" if person.get("carte_etranger") else None
        pflags = list(person.get("quality_flags") or [])
        status: FieldQualityStatus = "suspect" if pflags else "confirmed"
        if not name and identifier is None:
            continue
        associates.append(
            AssociateRow(
                name=_clean_text(name),
                identifier=_clean_text(identifier),
                identifier_type=identifier_type,
                titres_previous=_to_float(person.get("titres_previous") or person.get("nombre_titres_n1")),
                titres_current=_to_float(person.get("titres_current") or person.get("nombre_titres_n")),
                nominal_value=_to_float(person.get("valeur_nominale")),
                capital_souscrit=_to_float(person.get("capital_souscrit")),
                capital_appele=_to_float(person.get("capital_appele")),
                capital_libere=_to_float(person.get("capital_libere")),
                status=status,
                evidence=_fiscal_evidence((person.get("evidence") or {}).get("nom_prenom") or (person.get("evidence") or {}).get("raison_sociale")),
            )
        )
    available = capital.value is not None or bool(associates)
    return CapitalAnalysis(
        available=available,
        capital_social=capital,
        validation_status="a_verifier" if flags else ("valide" if available else None),
        warnings=[str(flag) for flag in flags],
        associates=associates,
    )

