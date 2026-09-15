from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

ScoreStatus = Literal["NOT_CALCULABLE", "PARTIAL", "FINAL"]


class DecisionBand(BaseModel):
    min_score: float
    classe: str
    decision: str
    recommandation: str


class RatioThreshold(BaseModel):
    # TODO_WAFABAIL_POLICY_VALIDATION — recopié de l'existant, non recalibré.
    key: str
    meta: dict[str, Any] = Field(default_factory=dict)


class ScoringPolicy(BaseModel):
    version: str = "WFB-CREDIT-V1"
    name: str = "Wafabail crédit-bail V1"
    effective_from: date | None = None
    validation_status: str = "PENDING_WAFABAIL_BUSINESS_VALIDATION"
    financial_weight: Decimal = Decimal("0.75")
    behavioral_weight: Decimal = Decimal("0.15")
    sector_weight: Decimal = Decimal("0.10")
    decision_grid: list[DecisionBand] = Field(default_factory=list)
    financial_ratio_thresholds: dict[str, RatioThreshold] = Field(default_factory=dict)
    minimum_sector_coverage: int = 1
    minimum_behavioral_coverage: int = 1
    require_bam_for_final_decision: bool = True
    require_incidents_check_for_final_decision: bool = True
    allow_reject_without_full_eligibility: bool = True
    axe1_penalty_surveiller: float = 7.5
    axe1_penalty_non_conforme: float = 20.0


def default_policy() -> ScoringPolicy:
    # TODO_WAFABAIL_POLICY_VALIDATION
    return ScoringPolicy(
        decision_grid=[
            DecisionBand(min_score=90.0, classe="A+", decision="Excellent", recommandation="Accord sans condition"),
            DecisionBand(min_score=80.0, classe="A/B+", decision="Bon", recommandation="Accord — conditions standards"),
            DecisionBand(min_score=65.0, classe="B/B-", decision="Moyen", recommandation="Accord avec garanties complémentaires"),
            DecisionBand(min_score=50.0, classe="C", decision="Sensible", recommandation="Accord conditionné ou refus partiel"),
            DecisionBand(min_score=0.0, classe="D/F", decision="Risqué", recommandation="Refus recommandé / systématique"),
        ]
    )


@dataclass
class ScoreComputation:
    score_status: ScoreStatus
    financial_score: float | None
    behavioral_score: float | None
    sector_score: float | None
    partial_score: float | None
    final_score: float | None
    available_weight: float
    missing_axes: list[str]
    classe: str | None = None
    algorithmic_recommendation: str | None = None
    decision_label: str | None = None


def policy_as_dict(policy: ScoringPolicy) -> dict[str, Any]:
    return policy.model_dump(mode="json")
