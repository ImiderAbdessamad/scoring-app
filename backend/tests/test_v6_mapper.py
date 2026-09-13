from __future__ import annotations

from app.services.scoring_lab_pipeline import _derived_fields, build_result_from_v6
from app.services.v6_result_mapper import identity_from_v6, map_fields


def test_identity_from_bilan_header():
    identity = identity_from_v6(
        {
            "identifiant_fiscal": "52601461",
            "ice": "003120883000059",
            "raison_sociale": "DMT ADVISORY",
            "taxe_professionnelle": "35100480",
            "ville": "141.00.00",
            "adresse": "8 RUE FAKER MOHAMED",
            "activite": "Activités comptables",
            "secteur": None,
            "period_start": "01/01/2025",
            "period_end": "31/12/2025",
            "declaration_date": "30/03/2026",
            "declaration_time": "15:15:45",
            "reference": "IS_18b14995e68eb1ba",
        }
    )
    assert identity.ice == "003120883000059"
    assert identity.identifiant_fiscal == "52601461"
    assert identity.raison_sociale == "DMT ADVISORY"
    assert identity.taxe_professionnelle == "35100480"
    assert identity.ville == "141.00.00"
    assert identity.reference == "IS_18b14995e68eb1ba"


def test_caf_and_identity_in_api_result():
    v6 = {
        "identity": {
            "identifiant_fiscal": "52601461",
            "ice": "003120883000059",
            "raison_sociale": "DMT ADVISORY",
            "taxe_professionnelle": "35100480",
            "ville": "141.00.00",
            "adresse": "8 RUE FAKER MOHAMED",
            "activite": "Activités comptables",
            "secteur": None,
            "period_start": "01/01/2025",
            "period_end": "31/12/2025",
            "declaration_date": "30/03/2026",
            "declaration_time": "15:15:45",
            "reference": "IS_18b14995e68eb1ba",
        },
        "canonical": {
            "caf": {
                "current": "120000",
                "previous": "110000",
                "usable_current": "120000",
                "usable_previous": "110000",
                "period_status": {"current": "observed", "previous": "observed"},
                "value_status": {"current": "high_confidence", "previous": "high_confidence"},
                "label": "I - Capacité d'autofinancement (C.A.F.)",
                "section": "esg",
                "page": 8,
                "confidence": 0.92,
                "evidence": {"current": {"page": 8, "label": "C.A.F.", "raw": "120 000", "section": "esg"}},
            },
            "chiffre_affaires": {
                "current": "1000000",
                "previous": "900000",
                "period_status": {"current": "observed", "previous": "observed"},
                "section": "cpc",
                "label": "Chiffre d'affaires",
                "page": 5,
            },
            "resultat_net": {
                "current": "80000",
                "previous": "70000",
                "period_status": {"current": "observed", "previous": "observed"},
                "section": "cpc",
                "page": 5,
            },
            "total_actif": {
                "current": "2000000",
                "previous": "1800000",
                "period_status": {"current": "observed", "previous": "observed"},
                "section": "bilan_actif",
                "page": 2,
            },
            "fonds_propres": {
                "current": "500000",
                "previous": "420000",
                "period_status": {"current": "observed", "previous": "observed"},
                "section": "bilan_passif",
                "page": 3,
            },
        },
        "pages": [{"page": 1, "section": "generic", "parser": "pymupdf", "errors": []}],
        "validations": [],
        "source": {"pages": 12},
        "_pages_total": 12,
        "_source_filename": "bilan.pdf",
    }
    result = build_result_from_v6(v6, "bilan.pdf")
    assert result.document.identity.ice == "003120883000059"
    assert result.document.company.identifiant_fiscal == "52601461"
    assert result.document.exercise.debut == "01/01/2025"
    caf = next(f for f in result.fields if f.code == "CAF")
    assert caf.value == 120000.0
    assert caf.value_n1 == 110000.0
    assert caf.status == "confirmed"
    assert result.ratio_inputs["caf"] == 120000.0


def test_caf_proxy_when_esg_missing():
    fields = map_fields(
        {
            "resultat_net": {
                "current": "80",
                "usable_current": "80",
                "period_status": {"current": "observed"},
                "value_status": {"current": "high_confidence"},
            },
            "dotations_exploitation": {
                "current": "20",
                "usable_current": "20",
                "period_status": {"current": "observed"},
                "value_status": {"current": "high_confidence"},
            },
        }
    )
    fields.extend(_derived_fields(fields))
    caf = next(f for f in fields if f.code == "CAF")
    assert caf.value == 100.0
    assert caf.status == "derived"
    assert len([f for f in fields if f.code == "CAF"]) == 1
