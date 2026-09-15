from __future__ import annotations

import json

from app.db.repositories import sector_benchmark_repository
from app.services.scoring_engine import score_axe3_sectoriel


def resolve_sector_score(ratios: dict, *, benchmark_sector_code: str | None, analysis_year: int | None) -> dict:
    row = sector_benchmark_repository.find(benchmark_sector_code, analysis_year)
    if row is None:
        return {
            "score": None,
            "status": "NO_BENCHMARK",
            "comparaisons": [],
            "indicateurs_compares": 0,
            "note": "Référentiel sectoriel non disponible pour ce secteur.",
            "meta": {
                "sector_code": benchmark_sector_code,
                "year": analysis_year,
            },
        }
    medians = json.loads(row.metrics_json or "{}")
    scored = score_axe3_sectoriel(ratios, sector_medians=medians)
    scored["status"] = "OK"
    scored["meta"] = {
        "sector_code": row.sector_code,
        "sector_label": row.sector_label,
        "year": row.year,
        "source": row.source,
        "sample_size": row.sample_size,
        "version": row.version,
    }
    return scored
