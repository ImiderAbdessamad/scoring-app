from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.analyse import (
    CompanyInfo,
    DocumentSummary,
    ExtractedField,
    ExtractionSummary,
    IdentityInfo,
    ScoringAnalysisResult,
)
from app.schemas.create_dossier import StoredDossierRecord
from app.services.analyse_job_store import job_store
from app.services.rcc_dossier_store import RccDossier, rcc_dossier_store
from app.services.rcc_from_scoring import get_or_import, result_from_workspace
from app.services.rcc_projection import clean_activite, project_rcc_result

client = TestClient(app)


def _result() -> ScoringAnalysisResult:
    return ScoringAnalysisResult(
        document=DocumentSummary(
            filename="liasse.pdf",
            pages_total=2,
            pages_processed=2,
            pages_skipped=0,
            pages_failed=0,
            identity=IdentityInfo(
                identifiant_fiscal="52601461",
                ice="003120883000059",
                raison_sociale="DMT ADVISORY",
                taxe_professionnelle="35100480",
                ville="141.00.00",
                adresse="8 RUE FAKER MOHAMED",
                activite="Activités comptables",
                secteur=None,
                period_start="01/01/2025",
                period_end="31/12/2025",
                declaration_date="30/03/2026",
                declaration_time="15:15:45",
                reference="IS_18b14995e68eb1ba",
            ),
            company=CompanyInfo(raison_sociale="DMT ADVISORY", ice="003120883000059"),
        ),
        extraction=ExtractionSummary(model="v6"),
        fields=[
            ExtractedField(
                number=3,
                code="CHIFFRE_AFFAIRES",
                label="Chiffre d'affaires",
                source="CPC",
                value=1_200_000,
                value_n1=1_000_000,
                status="confirmed",
                confidence=0.92,
            ),
            ExtractedField(
                number=31,
                code="VALEUR_AJOUTEE",
                label="Valeur ajoutée",
                source="ESG",
                value=400_000,
                status="confirmed",
                confidence=0.8,
            ),
        ],
        completeness_pct=40,
    )


def test_rcc_health_and_session():
    assert client.get("/api/v1/rcc/health").json()["status"] == "ok"
    assert client.get("/api/v1/auth/me").json()["role"] == "analyst"
    assert client.get("/api/v1/rcc/system/ocr-health").json()["status"] == "online"


def test_rcc_job_rejects_non_pdf():
    response = client.post("/api/v1/rcc/jobs", files={"file": ("note.txt", b"hello", "text/plain")})
    assert response.status_code == 422


def test_rcc_result_display_and_clean_export():
    job = job_store.create(dossier_id="RCC-test", filename="liasse.pdf", pdf_bytes=b"%PDF-1.4 test")
    job.status = "completed"
    job.result = _result()

    display = client.get(f"/api/v1/rcc/jobs/{job.job_id}/result")
    assert display.status_code == 200
    assert display.json()["identite"]["raison_sociale"] == "DMT ADVISORY"
    assert display.json()["identite"]["identifiant_fiscal"] == "52601461"
    assert display.json()["identite"]["reference"] == "IS_18b14995e68eb1ba"
    codes = [item["code"] for item in display.json()["fields"]]
    assert "CHIFFRE_AFFAIRES" in codes
    assert "VALEUR_AJOUTEE" in codes
    assert "EBE" in codes
    ca = next(item for item in display.json()["fields"] if item["code"] == "CHIFFRE_AFFAIRES")
    assert ca["value"] == 1_200_000
    assert ca["value_n1"] == 1_000_000

    export = client.get(f"/api/v1/rcc/jobs/{job.job_id}/export")
    assert export.status_code == 200
    payload = export.json()
    assert payload["raison_sociale"] == "DMT ADVISORY"
    assert payload["identifiant_fiscal"] == "52601461"
    assert payload["ice"] == "003120883000059"
    assert payload["taxe_professionnelle"] == "35100480"
    assert payload["adresse"] == "8 RUE FAKER MOHAMED"
    assert payload["activite"] == "Activités comptables"
    assert payload["period_start"] == "01/01/2025"
    assert payload["period_end"] == "31/12/2025"
    assert payload["declaration_date"] == "30/03/2026"
    assert payload["declaration_time"] == "15:15:45"
    assert payload["reference"] == "IS_18b14995e68eb1ba"
    assert payload["postes"]["chiffre_affaires"] == {"n": 1_200_000, "n1": 1_000_000}
    assert payload["postes"]["valeur_ajoutee"]["n"] == 400_000
    assert "confidence" not in payload["postes"]["chiffre_affaires"]
    assert "evidence" not in payload

    created = client.post("/api/v1/rcc/dossiers", json={"job_id": job.job_id})
    assert created.status_code == 201
    dossier_id = created.json()["dossier"]["id"]
    shown = client.get(f"/api/v1/rcc/dossiers/{dossier_id}")
    assert shown.status_code == 200
    assert shown.json()["dossier"]["identite"]["ice"] == "003120883000059"
    clean = client.get(f"/api/v1/rcc/dossiers/{dossier_id}/export.json")
    assert clean.status_code == 200
    assert clean.json()["identifiant_fiscal"] == "52601461"
    assert clean.json()["dossier_id"] == dossier_id
    rcc_dossier_store.delete(dossier_id)


def test_rcc_lists_scoring_dossiers(monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.rcc.scoring_list_summaries",
        lambda: [
            {
                "id": "STE-2026-3122",
                "client_name": "DMT ADVISORY",
                "ice": "003120883000059",
                "status": "pending",
                "status_label": "À réviser",
                "updated_at": "2026-09-15T00:00:00+00:00",
                "identifiant_fiscal": "52601461",
            }
        ],
    )
    listed = client.get("/api/v1/rcc/dossiers")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert "STE-2026-3122" in ids


def test_clean_activite_drops_raison_sociale_ocr():
    assert clean_activite("Raison Sociale : STE EUROMEDIA") is None
    assert clean_activite("raison sociale STE EUROMEDIA", "Activités comptables") == "Activités comptables"
    dirty = _result()
    dirty.document.identity.activite = "Raison Sociale : STE EUROMEDIA"
    dirty.document.company.activite = "Raison Sociale : STE EUROMEDIA"
    projected = project_rcc_result(dirty)
    assert projected["identite"]["activite"] in (None, "")
    assert projected["identite"]["secteur"] in (None, "")


def _scoring_record() -> StoredDossierRecord:
    return StoredDossierRecord(
        id="STE-2026-3999",
        name="STE EUROMEDIA",
        sector="Raison Sociale : STE EUROMEDIA",
        amount=100000,
        duration=36,
        analyst="analyst",
        date="15/09/2026",
        ice="003120883000059",
        identifiantFiscal="52601461",
        nature="mobilier",
        valeurBien=120000,
        apport=10,
        fournisseur="Fournisseur",
        proformaReference="PF-1",
        natureBien="Véhicule",
        etat="neuf",
        valeurHt=100000,
        valeurTtc=120000,
        analyse={
            "header": {"companyName": "STE EUROMEDIA"},
            "period": {"start": "01/01/2025", "end": "31/12/2025"},
            "scoring": {"dossierCompletenessPct": 55},
            "financialStatements": {
                "cpc": [
                    {
                        "code": "CHIFFRE_AFFAIRES",
                        "label": "Chiffre d'affaires",
                        "n": 1_200_000,
                        "n1": 1_000_000,
                        "nStatus": "confirmed",
                        "confidence": 0.91,
                        "source": "CPC",
                    }
                ],
                "esg": [
                    {
                        "code": "VALEUR_AJOUTEE",
                        "label": "Valeur ajoutée",
                        "n": 400_000,
                        "nStatus": "confirmed",
                        "confidence": 0.8,
                        "source": "ESG",
                    }
                ],
            },
        },
    )


def test_scoring_workspace_values_display_on_rcc(monkeypatch):
    record = _scoring_record()
    rebuilt = result_from_workspace(record)
    assert rebuilt is not None
    ca = next(item for item in rebuilt.fields if item.code == "CHIFFRE_AFFAIRES")
    assert ca.value == 1_200_000
    assert ca.value_n1 == 1_000_000

    monkeypatch.setattr("app.services.dossier_store.get_by_id", lambda dossier_id: record if dossier_id == record.id else None)
    monkeypatch.setattr("app.services.analyse_job_store.job_store.get_for_dossier", lambda _id: None)
    monkeypatch.setattr("app.services.rcc_from_scoring._load_audit_result", lambda _record: None)
    monkeypatch.setattr("app.services.rcc_from_scoring._pdf_bytes", lambda _record: None)

    rcc_dossier_store.put(
        RccDossier(
            id=record.id,
            job_id=None,
            client_name=record.name,
            ice=record.ice,
            credit_amount=record.amount,
            exercice_date=None,
            status="pending",
            created_at="2026-09-15T00:00:00+00:00",
            updated_at="2026-09-15T00:00:00+00:00",
            sector=record.sector,
            filename=None,
            pdf_path=None,
            completeness_pct=0,
            result={"fields": [], "identite": {"activite": record.sector}},
            scoring_result=_result(),
            identite={"activite": record.sector, "raison_sociale": record.name},
            origin="scoring",
        )
    )
    shown = client.get(f"/api/v1/rcc/dossiers/{record.id}")
    assert shown.status_code == 200
    payload = shown.json()
    assert payload["dossier"]["identite"]["activite"] in (None, "")
    assert payload["dossier"]["activite"] in (None, "")
    ca = next(item for item in payload["dossier"]["result"]["fields"] if item["code"] == "CHIFFRE_AFFAIRES")
    assert ca["value"] == 1_200_000
    assert ca["value_n1"] == 1_000_000
    va = next(item for item in payload["dossier"]["result"]["fields"] if item["code"] == "VALEUR_AJOUTEE")
    assert va["value"] == 400_000
    rcc_dossier_store.delete(record.id)


def test_get_or_import_scoring_without_prior_stub(monkeypatch):
    record = _scoring_record()
    record.id = "STE-2026-4000"
    monkeypatch.setattr("app.services.dossier_store.get_by_id", lambda dossier_id: record if dossier_id == record.id else None)
    monkeypatch.setattr("app.services.analyse_job_store.job_store.get_for_dossier", lambda _id: None)
    monkeypatch.setattr("app.services.rcc_from_scoring._load_audit_result", lambda _record: None)
    monkeypatch.setattr("app.services.rcc_from_scoring._pdf_bytes", lambda _record: None)
    dossier = get_or_import(record.id)
    assert dossier is not None
    ca = next(item for item in dossier.result["fields"] if item["code"] == "CHIFFRE_AFFAIRES")
    assert ca["value"] == 1_200_000
    assert dossier.identite["activite"] in (None, "")
    rcc_dossier_store.delete(record.id)
