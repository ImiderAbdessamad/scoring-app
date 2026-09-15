"""Synthèse lisible : points forts, points de vigilance, score final."""
from __future__ import annotations

from typing import Any

from app.services.ratio_engine import RATIO_METADATA

_NATIONAL_CA_GROWTH = 0.059  # croissance nationale de référence (docx scoring)


def _pct(value: float, *, signed: bool = False, digits: int = 2) -> str:
    pct = value * 100
    body = f"{pct:.{digits}f}".rstrip("0").rstrip(".").replace(".", ",")
    if signed and value > 0:
        return f"+{body} %"
    if signed and value < 0:
        return f"{body} %"
    return f"{body} %"


def _days(value: float) -> str:
    return f"{int(round(value))} jours"


def _mult(value: float) -> str:
    body = f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{body}x"


def _ratio(result: dict[str, Any], key: str) -> dict[str, Any] | None:
    raw = (result.ratios or {}).get(key)
    if not isinstance(raw, dict):
        return None
    return raw


def _value(raw: dict[str, Any] | None) -> float | None:
    if not raw:
        return None
    value = raw.get("value")
    if value is None:
        return None
    return float(value)


def _status(raw: dict[str, Any] | None) -> str:
    if not raw:
        return "Non calculable"
    return str(raw.get("status") or "Non calculable")


def _fmt_ratio(key: str, value: float) -> str:
    unit = RATIO_METADATA.get(key, {}).get("unit", "")
    if unit == "%":
        return _pct(value)
    if unit == "j":
        return _days(value)
    if unit in {"x", "ans"}:
        return _mult(value) if unit == "x" else f"{value:.1f}".replace(".", ",") + " ans"
    return f"{value:.2f}".replace(".", ",")


def _axe2(result) -> dict[str, Any]:
    return (result.axes or {}).get("comportemental") or {}


def _axe3(result) -> dict[str, Any]:
    return (result.axes or {}).get("sectoriel") or {}


def _points_forts(result) -> list[str]:
    forts: list[str] = []
    croissance = _ratio(result, "croissance_ca")
    croissance_v = _value(croissance)
    if croissance_v is not None and croissance_v >= 0.05:
        forts.append(
            f"Croissance solide du chiffre d'affaires ({_pct(croissance_v, signed=True)})."
        )

    autonomie = _ratio(result, "autonomie_financiere")
    treso = _ratio(result, "tresorerie_jours_ca")
    fdr = _ratio(result, "fdr_sur_ca")
    auto_ok = _status(autonomie) == "Conforme" and _value(autonomie) is not None
    treso_ok = _status(treso) == "Conforme"
    fdr_ok = _status(fdr) == "Conforme"
    if auto_ok:
        bits = [f"autonomie financière à {_pct(_value(autonomie) or 0)}"]
        if treso_ok and fdr_ok:
            bits.append("trésorerie et fonds de roulement positifs")
        elif treso_ok:
            bits.append("trésorerie positive")
        elif fdr_ok:
            bits.append("fonds de roulement positif")
        forts.append("Structure financière saine : " + ", ".join(bits) + ".")
    elif treso_ok and fdr_ok:
        forts.append("Trésorerie nette et fonds de roulement positifs.")

    axe2 = _axe2(result)
    signals = [s for s in (axe2.get("signaux") or []) if "Couverture comportementale" not in str(s)]
    incident_like = any(
        any(token in str(s).lower() for token in ("incident", "rejet", "impayé", "impaye", "retards"))
        for s in signals
    )
    if axe2.get("status") not in {None, "not_provided"} and not incident_like:
        forts.append(
            "Comportement bancaire déclaré sans signal d'incident dans les métriques fournies."
        )

    axe3 = _axe3(result)
    if axe3.get("status") == "OK" and axe3.get("score") is not None:
        comparisons = axe3.get("comparaisons") or []
        n_comp = int(axe3.get("indicateurs_compares") or 0) or len(
            [c for c in comparisons if c.get("statut") != "Non calculable"]
        )
        n_above = sum(1 for c in comparisons if c.get("statut") == "Conforme")
        if n_comp and n_above / n_comp >= 0.6:
            forts.append(
                f"Bon positionnement sectoriel : au-dessus de la médiane sur {n_above} indicateur{'s' if n_above > 1 else ''} sur {n_comp}."
            )
    return forts


def _points_vigilance(result, *, nouveau_financement: float | None) -> list[str]:
    vigilance: list[str] = []
    covered: set[str] = set()

    rentab = _ratio(result, "rentabilite_commerciale")
    rentab_v = _value(rentab)
    if rentab_v is not None and _status(rentab) in {"À surveiller", "Non conforme"}:
        extra = "sous le repère indicatif"
        vigilance.append(f"Rentabilité commerciale ({_pct(rentab_v)}) {extra}.")
        covered.add("rentabilite_commerciale")

    clients = _ratio(result, "delais_clients")
    fournisseurs = _ratio(result, "delais_fournisseurs")
    clients_v = _value(clients)
    fourn_v = _value(fournisseurs)
    if clients_v is not None and _status(clients) in {"À surveiller", "Non conforme"}:
        if fourn_v is not None and clients_v > fourn_v:
            vigilance.append(
                f"Délais clients élevés ({_days(clients_v)}), supérieurs aux délais fournisseurs ({_days(fourn_v)})."
            )
        else:
            vigilance.append(f"Délais clients élevés ({_days(clients_v)}).")
        covered.add("delais_clients")

    inputs = result.ratio_inputs or {}
    fp = inputs.get("fonds_propres")
    debt = inputs.get("dettes_financement")
    if debt is None:
        debt = inputs.get("dettes_financieres")
    after_op = None
    if fp and float(fp) > 0 and nouveau_financement:
        after_op = (float(debt or 0) + float(nouveau_financement)) / float(fp)
    endet = _ratio(result, "ratio_endettement")
    endet_v = after_op if after_op is not None else _value(endet)
    if endet_v is not None and endet_v > 2.0:
        vigilance.append(
            f"Endettement global après la nouvelle opération en hausse à {_mult(endet_v)} les fonds propres."
        )
        covered.add("ratio_endettement")
        covered.add("endettement_global_apres_operation")

    axe2 = _axe2(result)
    if axe2.get("status") == "not_provided":
        vigilance.append("Données comportementales (relevés bancaires) non encore intégrées.")
    else:
        for signal in axe2.get("signaux") or []:
            text = str(signal).strip()
            if not text or "Couverture comportementale" in text:
                continue
            if any(token in text.lower() for token in ("découvert", "decouvert", "écart flux", "ecart flux")):
                vigilance.append(text if text.endswith(".") else f"{text}.")
            elif any(token in text.lower() for token in ("incident", "rejet", "impayé", "impaye", "retards", "domiciliation")):
                vigilance.append(text if text.endswith(".") else f"{text}.")

    for key, raw in (result.ratios or {}).items():
        if key in covered:
            continue
        if not isinstance(raw, dict):
            continue
        status = _status(raw)
        value = _value(raw)
        if status not in {"À surveiller", "Non conforme"} or value is None:
            continue
        label = RATIO_METADATA.get(key, {}).get("label", key)
        qualifier = "non conforme" if status == "Non conforme" else "à surveiller"
        vigilance.append(f"{label} {qualifier} ({_fmt_ratio(key, value)}).")

    if getattr(result, "readiness", None) and result.readiness.blocking_reasons:
        for reason in result.readiness.blocking_reasons[:8]:
            vigilance.append(reason)
    for control in getattr(result, "controls", []) or []:
        if getattr(control, "status", None) == "failed":
            vigilance.append(f"Contrôle comptable en écart — {control.label}.")
    fiscal = getattr(result, "fiscal_analysis", None)
    if fiscal and fiscal.warnings:
        vigilance.extend(str(w) for w in fiscal.warnings[:4])
    capital = getattr(result, "capital_analysis", None)
    if capital and capital.warnings:
        vigilance.extend(str(w) for w in capital.warnings[:4])

    return vigilance


_RECO_PHRASE = {
    "Accord sans condition": "Accord sans condition recommandé",
    "Accord — conditions standards": "Accord avec conditions standards recommandé",
    "Accord avec garanties complémentaires": "Accord avec garanties complémentaires recommandé",
    "Accord conditionné ou refus partiel": "Accord conditionné ou refus partiel recommandé",
    "Refus recommandé / systématique": "Refus recommandé",
}


def _score_final(result) -> str:
    decision = result.decision or {}
    score = decision.get("score")
    if score is None:
        return "Score final non calculable — données insuffisantes."
    score_f = float(score)
    classe = decision.get("classe") or "—"
    label = decision.get("decision") or ""
    reco = _RECO_PHRASE.get(decision.get("recommandation") or "", decision.get("recommandation") or "").rstrip(".")
    blocking = decision.get("blocking_status")
    classe_bit = f"Classe {classe}" if classe and classe != "—" else "Classe non attribuée (score non final)"
    if label:
        classe_bit += f" « {label} »"
    parts = [f"Score : {score_f:.2f} / 100", classe_bit]
    if decision.get("score_status") == "PARTIAL" or decision.get("provisional"):
        parts.append("score provisoire (revue manuelle)")
    if reco:
        parts.append(reco)
    if blocking in {None, "NOT_CHECKED"}:
        parts.append("cotation BAM non vérifiée")
        parts.append("incidents bancaires non vérifiés")
    elif blocking == "NO_GO":
        parts.append("critère bloquant cotation BAM")
    elif blocking == "MANUAL_REVIEW":
        parts.append("revue manuelle requise (incidents non résolus)")
    return " — ".join(parts) + "."


def empty_synthese() -> dict[str, Any]:
    return {
        "pointsForts": [],
        "pointsVigilance": [],
        "scoreFinal": "",
    }


def build_synthese(result, *, nouveau_financement: float | None = None) -> dict[str, Any]:
    return {
        "pointsForts": _points_forts(result),
        "pointsVigilance": _points_vigilance(result, nouveau_financement=nouveau_financement),
        "scoreFinal": _score_final(result),
    }
