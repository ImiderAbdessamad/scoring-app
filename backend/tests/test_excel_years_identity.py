from __future__ import annotations

from app.services.ocr_lab_core_v10 import extract_native_identification
from app.services.scoring_lab_pipeline import _build_years, _derived_fields, merge_liasse_years
from app.schemas.analyse import ExtractedField, ExerciseInfo, ScoringAnalysisResult, YearsBlock


ADEIS_PAGE1 = """
001669862000005
Identification du contribuable
Raison Sociale :
Adresse :
Ville :
Identifiant fiscal
Activité	 :
ADEIS INVEST
04, RUE MOLIERE, 1ER ETAGE, C/O STE SIHAMRI
141.00.00
15301043
Autres activités des
Art. Taxe professionnelle
35623299
Etat de synthèse conforme à la déclaration souscrite
le 27/03/2026 17:23:38 au titre de la période du 01/01/2025 au
31/12/2025
ICE :
"""

FDI_PAGE1 = """
001669786000020
Identification du contribuable
Raison Sociale :
Adresse :
Ville :
Identifiant fiscal
Activité	 :
FDI INVEST
4 RUE MOLIERE, 1ER ETAGE
141.00.00
18718360
Autres activités des
Art. Taxe professionnelle
35623559
Etat de synthèse conforme à la déclaration souscrite
le 27/03/2026 18:40:25 au titre de la période du 01/01/2025 au
31/12/2025
ICE :
"""


def _by_code(rows):
    return {row.field_code: row.cells.get("TEXT") for row in rows}


def test_ice_and_dates_adeis():
    fields = _by_code(extract_native_identification(ADEIS_PAGE1, 1))
    assert fields["ICE"] == "001669862000005"
    assert fields["RAISON_SOCIALE"] == "ADEIS INVEST"
    assert fields["EXERCICE_DEBUT"] == "01/01/2025"
    assert fields["EXERCICE_FIN"] == "31/12/2025"
    assert "RC" not in fields or not fields["RC"]


def test_ice_fdi():
    fields = _by_code(extract_native_identification(FDI_PAGE1, 1))
    assert fields["ICE"] == "001669786000020"
    assert "FDI" in (fields.get("RAISON_SOCIALE") or "")


def test_rc_when_printed():
    text = ADEIS_PAGE1 + "\nR.C. : 12345/CASABLANCA\n"
    fields = _by_code(extract_native_identification(text, 1))
    assert "12345" in fields["RC"]


def test_caf_proxy_and_three_year_columns():
    fields = [
        ExtractedField(number=19, code="RESULTAT_NET", label="RN", source="CPC", value=-203619.12, status="confirmed", value_n1=20635.96),
        ExtractedField(number=24, code="DOTATIONS_EXPLOITATION", label="DAP", source="CPC", value=36746.74, status="confirmed", value_n1=0.0),
        ExtractedField(number=3, code="CHIFFRE_AFFAIRES", label="CA", source="CPC", value=0.0, status="confirmed", value_n1=0.0),
        ExtractedField(number=5, code="DETTES_BANCAIRES_MLT", label="MLT", source="Passif", value=0.0, status="confirmed", value_n1=0.0),
        ExtractedField(number=6, code="DETTES_BANCAIRES_CT", label="CT", source="Passif", value=0.0, status="confirmed", value_n1=0.0),
    ]
    derived = {item.code: item for item in _derived_fields(fields)}
    assert round(derived["CAF"].value, 2) == round(-203619.12 + 36746.74, 2)
    assert derived["CAF"].value_n1 == 20635.96
    years = _build_years(fields + list(derived.values()), ExerciseInfo(fin="31/12/2025"), "FDINVEST -Bilan 2025.pdf")
    assert years.labels == ["—", "2024", "2025"]
    assert years.years == [None, 2024, 2025]
    assert years.series["caf"][2] == derived["CAF"].value
    assert years.series["caf"][1] == derived["CAF"].value_n1
    assert years.series["caf"][0] is None
    assert years.available_count == 2


def test_years_follow_liasse_period_not_filename():
    years = _build_years(
        [ExtractedField(number=3, code="CHIFFRE_AFFAIRES", label="CA", source="CPC", value=10.0, status="confirmed", value_n1=8.0)],
        ExerciseInfo(debut="01/01/2022", fin="31/12/2022", label="Du 01/01/2022 au 31/12/2022"),
        "ADEISINVEST-BILAN-2025.pdf",
    )
    assert years.labels == ["—", "2021", "2022"]
    assert years.years == [None, 2021, 2022]


def test_years_without_liasse_dates_stay_generic():
    years = _build_years(
        [ExtractedField(number=3, code="CHIFFRE_AFFAIRES", label="CA", source="CPC", value=10.0, status="confirmed")],
        ExerciseInfo(),
        "Bilan 2025.pdf",
    )
    assert years.labels == ["—", "N-1", "N"]
    assert years.years == [None, None, None]


def test_merge_adds_n2_from_older_liasse_period():
    primary = ScoringAnalysisResult.model_construct(
        years=YearsBlock(
            labels=["—", "2024", "2025"],
            years=[None, 2024, 2025],
            available_count=2,
            series={"chiffre_affaires": [None, 80.0, 100.0]},
        )
    )
    extra = ScoringAnalysisResult.model_construct(
        years=YearsBlock(
            labels=["—", "2022", "2023"],
            years=[None, 2022, 2023],
            available_count=2,
            series={"chiffre_affaires": [None, 50.0, 60.0]},
        )
    )
    merged = merge_liasse_years(primary, [extra])
    assert merged.years.labels == ["2023", "2024", "2025"]
    assert merged.years.years == [2023, 2024, 2025]
    assert merged.years.series["chiffre_affaires"] == [60.0, 80.0, 100.0]
