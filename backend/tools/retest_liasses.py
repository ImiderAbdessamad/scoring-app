"""Retest native des liasses ADEISINVEST / FDINVEST (sans GPU)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import ocr_lab_core_v10 as engine
from app.services.scoring_lab_pipeline import build_result

PDFS = [
    Path(r"c:\Users\Dell\OneDrive\Documents\ocr-cin\documentation-wafabail\use-case-RCC\data\ADEISINVEST-BILAN-2025.pdf"),
    Path(r"c:\Users\Dell\OneDrive\Documents\ocr-cin\documentation-wafabail\use-case-RCC\data\FDINVEST -Bilan 2025.pdf"),
]


def run_one(path: Path) -> dict:
    client = engine.OllamaClient(base_url="http://127.0.0.1:9")
    audit, _rows, rcc, controls, evidence = engine.analyze_pdf(
        path,
        client=client,
        use_glm_verification=False,
        use_reasoning_mapper=False,
        use_adjudicator=False,
    )
    result = build_result(
        filename=path.name,
        audit_frame=audit,
        rcc_frame=rcc,
        controls_frame=controls,
        evidence=evidence,
        pages_total=int(audit["page"].max()) if not audit.empty else 0,
    )
    by_code = {f.code: f for f in result.fields}
    ident = {
        row.field_code: row.cells.get("TEXT")
        for row in evidence
        if row.page_type == "IDENTIFICATION"
    }
    summary = {
        "file": path.name,
        "ice": result.document.company.ice,
        "rc": result.document.company.rc,
        "raison_sociale": result.document.company.raison_sociale,
        "exercice": result.document.exercise.label,
        "years": result.years.labels,
        "available": result.years.available_count,
        "ca": by_code.get("CHIFFRE_AFFAIRES") and by_code["CHIFFRE_AFFAIRES"].value,
        "ca_n1": by_code.get("CHIFFRE_AFFAIRES") and by_code["CHIFFRE_AFFAIRES"].value_n1,
        "rn": by_code.get("RESULTAT_NET") and by_code["RESULTAT_NET"].value,
        "rn_n1": by_code.get("RESULTAT_NET") and by_code["RESULTAT_NET"].value_n1,
        "dap": by_code.get("DOTATIONS_EXPLOITATION") and by_code["DOTATIONS_EXPLOITATION"].value,
        "caf": by_code.get("CAF") and by_code["CAF"].value,
        "fp": by_code.get("FONDS_PROPRES") and by_code["FONDS_PROPRES"].value,
        "score": result.decision.get("score"),
        "ident_raw": ident,
        "ratios": {
            key: {"value": val.get("value"), "status": val.get("status")}
            for key, val in result.ratios.items()
            if key in {
                "ratio_endettement",
                "capacite_remboursement",
                "caf_sur_ca",
                "delais_stocks",
                "croissance_ca",
            }
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return summary


if __name__ == "__main__":
    for pdf in PDFS:
        print("=" * 80)
        run_one(pdf)
