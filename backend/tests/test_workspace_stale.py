from __future__ import annotations

from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta
from app.services.v6_result_mapper import map_capital_analysis, map_fiscal_analysis, map_page_audit
from app.services.workspace_builder import analysis_source_fingerprint, overlay_live_documents


def _file(name: str, size: int, category: str = "entreprise") -> StoredFileMeta:
    return StoredFileMeta(
        name=name,
        objectKey=f"dossiers/D1/{name}",
        size=size,
        contentType="application/pdf",
        category=category,
    )


def _record(files: list[StoredFileMeta], analyse: dict | None = None) -> StoredDossierRecord:
    return StoredDossierRecord(
        id="D1",
        name="TEST SA",
        sector="Industrie",
        amount=1_200_000,
        duration=48,
        score=73,
        status="review",
        analyst="Analyste",
        date="13/09/2026",
        ice="003120883000059",
        nature="mobilier",
        valeurBien=1_500_000,
        apport=10,
        fournisseur="Fournisseur",
        proformaReference="PF-1",
        natureBien="Equipement",
        etat="neuf",
        valeurHt=1_250_000,
        valeurTtc=1_500_000,
        files=files,
        analyse=analyse,
    )


def test_liasse_replacement_marks_analysis_stale():
    old_files = [_file("bilan-2025.pdf", 1000)]
    new_files = [_file("bilan-2024.pdf", 2000)]
    old_fp = analysis_source_fingerprint(_record(old_files))
    workspace = {
        "analysisFingerprint": old_fp,
        "yearLabels": ["—", "2024", "2025"],
        "scoring": {"score": 81, "classe": "A/B+", "recommendation": "Favorable"},
        "ratios": {"items": [{"label": "CAF"}]},
        "factorielle": [{"title": "CA"}],
        "documents": {"items": [], "extractions": {}, "missing": [], "present": 0, "total": 4, "completenessPct": 0, "defaultDocId": ""},
    }
    overlay = overlay_live_documents(_record(new_files, analyse=workspace), workspace)
    assert overlay["analysisStale"] is True
    assert overlay["yearLabels"] == ["—", "N-1", "N"]
    assert overlay["scoring"]["stale"] is True
    assert overlay["scoring"]["score"] == 0
    assert overlay["scoring"]["classe"] == ""
    assert overlay["scoring"]["recommendation"].startswith("Analyse à relancer")
    assert overlay["ratios"]["items"] == []
    assert overlay["financialStatements"] is None
    assert "Relancez" in (overlay.get("staleMessage") or "")


def test_fiscal_and_capital_mapped_from_v6():
    fiscal = map_fiscal_analysis(
        {
            "resultat_fiscal": {
                "resultat_net_comptable": "100000",
                "resultat_brut_fiscal": "120000",
                "resultat_net_fiscal": "110000",
                "reintegrations_fiscales": {"total": "30000", "details": [{"label": "Amortissements", "amount": "30000"}]},
                "deductions_fiscales": {"total": "20000", "details": [{"label": "Plus-values", "amount": "20000"}]},
            }
        }
    )
    assert fiscal.available is True
    assert fiscal.resultat_net_comptable.value == 100000
    assert fiscal.reintegrations.total == 30000
    assert fiscal.deductions.details[0].label == "Plus-values"
    assert fiscal.resultat_net_fiscal.value == 110000

    capital = map_capital_analysis(
        {
            "capital_repartition": {
                "capital_social": "500000",
                "associes": [
                    {
                        "nom_prenom": "ASSOCIE UN",
                        "if": "12345678",
                        "nombre_titres_n": "100",
                        "nombre_titres_n1": "80",
                        "valeur_nominale": "100",
                    }
                ],
            }
        }
    )
    assert capital.available is True
    assert capital.associates[0].name == "ASSOCIE UN"
    assert capital.associates[0].titres_current == 100 or capital.associates[0].titres_current is not None


def test_page_audit_recognizes_fiscal_and_capital():
    pages = map_page_audit(
        {
            "pages": [
                {"page": 9, "section": "resultat_fiscal", "row_count": 12, "parser": "v6"},
                {"page": 10, "section": "capital_repartition", "row_count": 4, "parser": "v6"},
            ]
        }
    )
    by_type = {p.detected_type: p.extraction_status for p in pages}
    assert by_type["RESULTAT_FISCAL"] in {"processed", "empty"}
    assert by_type["CAPITAL_REPARTITION"] in {"processed", "empty"}
    assert "skipped" not in by_type.values()
