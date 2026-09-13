from __future__ import annotations

from app.schemas.analyse import (
    DocumentSummary,
    ExtractionSummary,
    ScoringAnalysisResult,
    YearsBlock,
)
from app.services.synthese_builder import build_synthese


def _result() -> ScoringAnalysisResult:
    return ScoringAnalysisResult(
        document=DocumentSummary(
            filename="liasse.pdf",
            pages_total=10,
            pages_processed=8,
            pages_skipped=2,
            pages_failed=0,
        ),
        extraction=ExtractionSummary(model="test"),
        fields=[],
        completeness_pct=90,
        ratios={
            "croissance_ca": {"value": 0.126, "status": "Conforme"},
            "autonomie_financiere": {"value": 0.25, "status": "Conforme"},
            "tresorerie_jours_ca": {"value": 18.0, "status": "Conforme"},
            "fdr_sur_ca": {"value": 0.08, "status": "Conforme"},
            "rentabilite_commerciale": {"value": 0.0384, "status": "À surveiller"},
            "delais_clients": {"value": 78.0, "status": "À surveiller"},
            "delais_fournisseurs": {"value": 64.0, "status": "Conforme"},
            "ratio_endettement": {"value": 1.61, "status": "Conforme"},
        },
        axes={
            "comportemental": {
                "status": "provided",
                "score": 75,
                "signaux": [
                    "Recours au découvert : 41 j/an en position débitrice",
                    "Écart flux bancaires / CA déclaré de -4.2 % (à justifier)",
                ],
            },
            "sectoriel": {
                "score": 80,
                "indicateurs_compares": 5,
                "comparaisons": [
                    {"indicateur": "croissance_ca", "statut": "Conforme"},
                    {"indicateur": "autonomie_financiere", "statut": "Conforme"},
                    {"indicateur": "ratio_endettement", "statut": "Conforme"},
                    {"indicateur": "capacite_remboursement", "statut": "Conforme"},
                    {"indicateur": "rentabilite_commerciale", "statut": "À surveiller"},
                ],
            },
        },
        decision={
            "score": 83,
            "classe": "A/B+",
            "decision": "Bon",
            "recommandation": "Accord — conditions standards",
            "blocking_status": None,
        },
        ratio_inputs={"fonds_propres": 1_000_000, "dettes_financement": 1_610_000},
        years=YearsBlock(),
    )


def test_synthese_matches_attention_card_shape():
    synthese = build_synthese(_result(), nouveau_financement=1_000_000)
    forts = " ".join(synthese["pointsForts"])
    vigi = " ".join(synthese["pointsVigilance"])

    assert any("Croissance solide" in p for p in synthese["pointsForts"])
    assert "+12,6 %" in forts
    assert "médiane sectorielle" in forts
    assert "autonomie financière à 25 %" in forts
    assert "trésorerie et fonds de roulement positifs" in forts
    assert "aucun incident" in forts
    assert "4 indicateurs sur 5" in forts

    assert any("Rentabilité commerciale" in p for p in synthese["pointsVigilance"])
    assert "3,84 %" in vigi
    assert "78 jours" in vigi
    assert "64 jours" in vigi
    assert "découvert" in vigi.lower()
    assert "2,61x" in vigi

    assert synthese["scoreFinal"].startswith("Score : 83.00 / 100")
    assert "Classe A/B+" in synthese["scoreFinal"]
    assert "Bon" in synthese["scoreFinal"]
    assert "conditions standards" in synthese["scoreFinal"]
    assert "cotation BAM" in synthese["scoreFinal"]


def test_synthese_skips_irréprochable_without_bank_data():
    result = _result()
    result.axes["comportemental"] = {
        "status": "not_provided",
        "score": None,
        "signaux": ["Données comportementales non renseignées."],
    }
    synthese = build_synthese(result)
    forts = " ".join(synthese["pointsForts"]).lower()
    assert "irréprochable" not in forts
    assert any("relevés bancaires" in p.lower() for p in synthese["pointsVigilance"])
