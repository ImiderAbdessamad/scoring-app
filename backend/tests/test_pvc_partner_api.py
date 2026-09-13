from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient

from app.core.config import settings
from app.schemas.analyse import AnalyseJobCreateResponse
from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta
from app.services import dossier_store
from app.services.pvc_partner import parse_pvc_payload, pvc_to_record

TEST_KEY = "wfb_test_pvc_key_00000000000001"
MIN_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

PVC_PAYLOAD = {
    "id": 4412,
    "noPv": "PV-2026-8891",
    "noDemande": "DEM-2026-00412",
    "noTiers": "T-9981",
    "nomClient": "ADEIS INVEST",
    "typeClient": "PM",
    "montantTotal": 2500000,
    "redevanceTotal": 48000,
    "tauxStandard": 7.5,
    "tauxPropose": 6.9,
    "hasFraisDossier": True,
    "montantFraisDossier": 5000,
    "fournisseur": "Atlas Equipements",
    "dateReceptionEbail": "2026-08-18T10:15:00",
    "commercialNom": "S. El Amrani",
    "statutWorkflow": "EN_SYNTHESE",
    "rcAnalytique": "12345",
    "villeRC": "CASABLANCA",
    "formeJuridique": "SARL",
    "adresseSociale": "04 Rue Moliere",
    "activite": "Immobilier",
    "enRAC": False,
    "actionnaires": [
        {
            "nomPrenom": "Karim Benali",
            "quotePart": 60,
            "cin": "AB123456",
            "dateNaissance": "1980-01-15",
            "adresse": "Casablanca",
        }
    ],
    "mandataires": [
        {
            "nomPrenom": "Karim Benali",
            "qualite": "Gerant",
            "cin": "AB123456",
            "dateNaissance": "1980-01-15",
            "adresse": "Casablanca",
        }
    ],
    "simulations": [
        {
            "duree": 60,
            "redevance": 48000,
            "noContrat": "CB-2026-100",
            "biens": [
                {
                    "description": "Engin de chantier",
                    "neufOccasion": "neuf",
                    "montantHT": 2083333,
                }
            ],
        }
    ],
    "votes": [],
    "timeline": [],
}


async def _fake_start(dossier_id, background_tasks, max_pages=None):
    return AnalyseJobCreateResponse(
        job_id="job-pvc-test",
        dossier_id=dossier_id,
        status="queued",
        stream_url="/api/v1/analyse/jobs/job-pvc-test/stream",
        result_url="/api/v1/analyse/jobs/job-pvc-test/result",
        filename="liasse-bilan.pdf",
    )


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "pvc_api_key", TEST_KEY)
    monkeypatch.setattr(settings, "dossiers_store_path", tmp_path / "dossiers.json")
    monkeypatch.setattr(settings, "files_dir", tmp_path / "files")
    monkeypatch.setattr(settings, "storage_backend", "local")
    dossier_store._records = None
    monkeypatch.setattr("app.api.v1.partners.start_analyse_job", _fake_start)
    from app.main import app

    return TestClient(app)


def test_parse_pvc_keeps_column_names():
    payload = parse_pvc_payload(json.dumps(PVC_PAYLOAD))
    assert payload.noDemande == "DEM-2026-00412"
    assert payload.nomClient == "ADEIS INVEST"
    assert payload.rcAnalytique == "12345"
    assert payload.simulations[0].duree == 60
    assert payload.simulations[0].biens[0].neufOccasion == "neuf"
    assert payload.actionnaires[0].nomPrenom == "Karim Benali"


def test_pvc_to_record_maps_financement_and_bien():
    payload = parse_pvc_payload(json.dumps(PVC_PAYLOAD))
    record = pvc_to_record(payload, [])
    assert record.id == "DEM-2026-00412"
    assert record.noDemande == "DEM-2026-00412"
    assert record.source == "pvc"
    assert record.amount == 2500000
    assert record.duration == 60
    assert record.natureBien == "Engin de chantier"
    assert record.etat == "neuf"
    assert record.fournisseur == "Atlas Equipements"
    assert "12345" in record.rc
    assert record.pvc["noPv"] == "PV-2026-8891"


def test_partner_api_requires_key(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get("/api/v1/partners/pvc/dossiers/DEM-2026-00412")
    assert response.status_code == 401


def test_partner_post_and_get_by_no_demande(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    files = {
        "liasse": ("Bilan-2025.pdf", io.BytesIO(MIN_PDF), "application/pdf"),
    }
    created = client.post(
        "/api/v1/partners/pvc/dossiers",
        data={"data": json.dumps(PVC_PAYLOAD)},
        files=files,
        headers={"X-API-Key": TEST_KEY},
    )
    assert created.status_code == 202, created.text
    body = created.json()
    assert body["noDemande"] == "DEM-2026-00412"
    assert body["noPv"] == "PV-2026-8891"
    assert body["status"] == "analyzing"
    assert body["job_id"] == "job-pvc-test"
    assert "DEM-2026-00412" in body["poll_url"]

    fetched = client.get(
        "/api/v1/partners/pvc/dossiers/DEM-2026-00412",
        headers={"X-API-Key": TEST_KEY},
    )
    assert fetched.status_code == 200, fetched.text
    detail = fetched.json()
    assert detail["noDemande"] == "DEM-2026-00412"
    assert detail["nomClient"] == "ADEIS INVEST"
    assert detail["dossier"]["rcAnalytique"] == "12345"
    assert detail["dossier"]["simulations"][0]["duree"] == 60

    listed = client.get("/api/v1/dossiers?q=DEM-2026-00412")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    item = listed.json()["items"][0]
    assert item["noDemande"] == "DEM-2026-00412"
    assert item["source"] == "pvc"


def test_partner_get_unknown_demande(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    response = client.get(
        "/api/v1/partners/pvc/dossiers/UNKNOWN-1",
        headers={"Authorization": f"Bearer {TEST_KEY}"},
    )
    assert response.status_code == 404


def test_partner_get_completed_analysis(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    record = StoredDossierRecord(
        id="DEM-2026-00999",
        name="FDI INVEST",
        sector="Immobilier",
        amount=1_000_000,
        duration=36,
        score=72,
        status="ready",
        analyst="PVC",
        date="18/08/2026",
        ice="001669786000020",
        rc="1050",
        nature="mobilier",
        valeurBien=1_200_000,
        apport=0,
        fournisseur="X",
        proformaReference="",
        natureBien="Engin",
        etat="neuf",
        valeurHt=1_000_000,
        valeurTtc=1_200_000,
        files=[
            StoredFileMeta(
                name="liasse.pdf",
                objectKey="k",
                size=10,
                contentType="application/pdf",
                category="entreprise",
            )
        ],
        source="pvc",
        noDemande="DEM-2026-00999",
        noPv="PV-99",
        pvc={"noDemande": "DEM-2026-00999", "nomClient": "FDI INVEST"},
        analyseStatus="completed",
        analyse={
            "yearLabels": ["—", "2024", "2025"],
            "scoring": {
                "score": 72,
                "classe": "B",
                "riskLabel": "Moyen",
                "recommendation": "Etudier avec garanties.",
                "dossierCompletenessPct": 88,
                "attention": {
                    "pointsForts": ["Fonds propres positifs"],
                    "pointsVigilance": ["Rentabilite faible"],
                    "scoreFinal": "Score 72 — classe B",
                },
            },
            "ratios": {
                "items": [
                    {"label": "Autonomie financiere", "value": "32 %", "status": "WARN"}
                ]
            },
        },
    )
    dossier_store.prepend(record)
    response = client.get(
        "/api/v1/partners/pvc/dossiers/DEM-2026-00999",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["score"] == 72
    assert body["classe"] == "B"
    assert body["points_forts"] == ["Fonds propres positifs"]
    assert body["year_labels"] == ["—", "2024", "2025"]
    assert body["ratios"][0]["label"] == "Autonomie financiere"
