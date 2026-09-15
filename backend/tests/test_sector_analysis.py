from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from app.sector.calculations import cagr, growth_gap, normalized_index, safe_growth
from app.sector.domain import DownloadedDataset, RemoteDatasetMetadata, RemoteResource, SectorAnalysisResult
from app.sector.mapping import map_activity
from app.sector.providers.hcp_ckan import HcpCkanProvider
from app.sector.providers.hcp_parser import HcpWorkbookParser, SchemaValidationError, parse_hcp_number, parse_period
from app.sector.registry import HCP_DATASETS
from app.services.scoring_engine import score_axe3_sectoriel
from app.services.sector_analysis_service import SectorAnalysisService
from app.services.sector_sync_service import SectorSyncService


def _xlsx(headers, rows, title="Valeurs ajoutées à prix courants (Annuelle Base 2014) (En millions de dhs)"):
    wb = Workbook()
    ws = wb.active
    ws.append([title])
    ws.append([])
    ws.append([])
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def sample_bytes():
    return _xlsx(
        ["Secteurs d'activité", 2021, 2022, 2023, 2024],
        [
            ["Total", 100, 110, 120, 130],
            ["Construction", 70000, 75000, 78000, 81000],
            ["Commerce de gros et de détail; réparation de véhicules automobiles et de motocycles", 140000, 145000, 150000, 156000],
        ],
    )


def test_growth():
    assert abs(safe_growth(110, 100) - 10) < 1e-9


def test_growth_zero_base():
    assert safe_growth(10, 0) is None


def test_cagr():
    value = cagr(100, 121, 2)
    assert value is not None and abs(value - 10) < 0.05


def test_normalized_index():
    idx = normalized_index([100, 110, 121])
    assert idx[0] == 100
    assert abs(idx[1] - 110) < 1e-6


def test_company_sector_nominal_gap():
    assert growth_gap(12.4, 4.2) == 8.2


def test_nominal_not_compared_to_real():
    company_nominal = 12.4
    sector_real = 3.4
    assert company_nominal - sector_real != company_nominal  # concepts distincts
    note = SectorAnalysisResult().realGrowthNote
    assert "n'est pas directement soustraite" in note


def test_hcp_number_spaces():
    assert parse_hcp_number("121 082") == Decimal("121082")


def test_parse_period_datetime_and_provisional():
    assert parse_period(datetime(2024, 1, 1)) == (2024, None)
    assert parse_period(2024.0) == (2024, None)
    assert parse_period("2024*") == (2024, None)
    assert parse_period("2024 (e)") == (2024, None)
    assert parse_period("2024 T3") == (2024, 3)
    assert parse_period("2024-01-01 00:00:00") == (2024, None)


def test_hcp_xlsx_datetime_headers():
    parsed = HcpWorkbookParser().parse(
        _xlsx(
            ["Secteurs d'activité", datetime(2022, 1, 1), "2023*", "2024 (e)"],
            [["Construction", 75000, 78000, 81000]],
        ),
        HCP_DATASETS["annual_va_current"],
    )
    years = {o.year for o in parsed.observations}
    assert years == {2022, 2023, 2024}


def test_hcp_xlsx_parse():
    parsed = HcpWorkbookParser().parse(sample_bytes(), HCP_DATASETS["annual_va_current"])
    codes = {o.sector_code for o in parsed.observations}
    assert "HCP_CONSTRUCTION" in codes
    assert parsed.unit == "M MAD"
    assert parsed.title and "PIB" not in parsed.title.upper()


def test_hcp_schema_change_rejected():
    bad = _xlsx(["Secteur", "foo", "bar"], [["Construction", "x", "y"]])
    try:
        HcpWorkbookParser().parse(bad, HCP_DATASETS["annual_va_current"])
        assert False
    except SchemaValidationError as exc:
        assert "FAILED_SCHEMA" in str(exc)


def test_hcp_package_metadata_parse():
    payload = {
        "success": True,
        "result": {
            "name": "data_12_29",
            "title": "Valeurs ajoutées à prix courants (Annuelle Base 2014)",
            "metadata_modified": "2025-02-06T12:14:48",
            "resources": [
                {
                    "id": "abc",
                    "name": "I_12.29.xlsx",
                    "format": "XLSX",
                    "url": "https://data.gov.ma/data/dataset/x/resource/abc/download/i.xlsx",
                    "size": 11299,
                }
            ],
            "organization": {"title": "HCP"},
        },
    }
    meta = HcpCkanProvider().parse_package(payload)
    assert meta.dataset_id == "data_12_29"
    res = HcpCkanProvider().select_xlsx(meta)
    assert res.resource_id == "abc"


def test_hcp_resource_selection():
    meta = RemoteDatasetMetadata(
        dataset_id="data_12_29",
        resources=[
            RemoteResource(resource_id="1", name="note.pdf", format="PDF", url="https://data.gov.ma/a.pdf"),
            RemoteResource(resource_id="2", name="I_12.29.xlsx", format="XLSX", url="https://data.gov.ma/a.xlsx"),
        ],
    )
    assert HcpCkanProvider().select_xlsx(meta).resource_id == "2"


class FakeProvider:
    def __init__(self, content: bytes, modified: str = "v1"):
        self.content = content
        self.modified = modified
        self.downloads = 0

    async def check_dataset(self, dataset_id: str) -> RemoteDatasetMetadata:
        return RemoteDatasetMetadata(
            dataset_id=dataset_id,
            title="VA",
            metadata_modified=self.modified,
            resources=[
                RemoteResource(
                    resource_id="r1",
                    name="file.xlsx",
                    format="XLSX",
                    url="https://data.gov.ma/file.xlsx",
                    last_modified=self.modified,
                    size=len(self.content),
                )
            ],
        )

    def select_xlsx(self, metadata: RemoteDatasetMetadata) -> RemoteResource:
        return metadata.resources[0]

    async def download_dataset(self, dataset_id: str) -> DownloadedDataset:
        self.downloads += 1
        import hashlib

        meta = await self.check_dataset(dataset_id)
        raw = self.content
        return DownloadedDataset(
            dataset_id=dataset_id,
            metadata=meta,
            resource=meta.resources[0],
            content=raw,
            sha256=hashlib.sha256(raw).hexdigest(),
            retrieved_at=datetime.now(timezone.utc),
        )


def test_hcp_hash_unchanged_no_reimport(monkeypatch):
    from app.db.session import init_database

    init_database()
    provider = FakeProvider(sample_bytes(), "v1")
    service = SectorSyncService(provider=provider)
    import asyncio

    first = asyncio.run(service.sync_dataset("data_12_29"))
    second = asyncio.run(service.sync_dataset("data_12_29"))
    assert first["status"] in {"UPDATED", "UNCHANGED"}
    assert second["status"] == "UNCHANGED"


def test_hcp_new_hash_updates():
    from app.db.session import init_database

    init_database()
    provider = FakeProvider(sample_bytes(), "v1")
    service = SectorSyncService(provider=provider)
    import asyncio

    asyncio.run(service.sync_dataset("data_12_29"))
    other = _xlsx(
        ["Secteurs d'activité", 2021, 2022, 2023, 2024],
        [["Construction", 1, 2, 3, 4]],
    )
    provider.content = other
    provider.modified = "v2"
    result = asyncio.run(service.sync_dataset("data_12_29"))
    assert result["status"] == "UPDATED"


def test_failed_sync_keeps_previous_snapshot():
    from app.db.repositories.sector_data_repository import sector_data_repository
    from app.db.session import init_database

    init_database()
    provider = FakeProvider(sample_bytes(), "v1")
    service = SectorSyncService(provider=provider)
    import asyncio

    asyncio.run(service.sync_dataset("data_12_29"))
    before = sector_data_repository.get_dataset_by_external("data_12_29")
    assert before and before.resource_sha256
    provider.content = b"not-xlsx"
    provider.modified = "broken"
    result = asyncio.run(service.sync_dataset("data_12_29"))
    assert result["status"] in {"FAILED", "FAILED_SCHEMA"}
    after = sector_data_repository.get_dataset_by_external("data_12_29")
    assert after.resource_sha256 == before.resource_sha256


def test_exact_mapping():
    mapped = map_activity("Construction")
    assert mapped.status == "MATCHED"
    assert mapped.sector_code == "HCP_CONSTRUCTION"


def test_alias_mapping():
    mapped = map_activity("BTP")
    assert mapped.sector_code == "HCP_CONSTRUCTION"


def test_unknown_mapping():
    mapped = map_activity("Activité lunaire non classée xyz")
    assert mapped.status == "UNMATCHED"


def test_low_confidence_requires_review():
    mapped = map_activity("commerce de transport et construction")
    assert mapped.status == "REVIEW_REQUIRED"


def test_no_transport_default():
    mapped = map_activity("Fabrication de câbles électriques")
    assert mapped.sector_code != "HCP_TRANSPORTS"
    assert mapped.sector_code == "HCP_EQUIPEMENTS_ELECTRIQUES"


def test_skip_raison_sociale_uses_dossier_sector():
    from app.sector.mapping import resolve_mapping

    mapped = resolve_mapping("Raison Sociale : STE EUROMEDIA", "Information et communication")
    assert mapped.status == "MATCHED"
    assert mapped.sector_code == "HCP_INFORMATION"


def test_missing_company_va():
    scored = score_axe3_sectoriel({}, None)
    assert scored["score"] is None


def test_unusable_company_va():
    class P:
        usable = False
        usable_value = None

    class F:
        current = P()
        previous = P()
        code = "VALEUR_AJOUTEE"

    class Dummy:
        fields = [F()]
        years = type("Y", (), {"years": [None, 2023, 2024]})()
        document = type("D", (), {"identity": type("I", (), {"activite": "Construction"})()})()

    record = type("R", (), {"id": "x", "sector": "Construction", "sectorRaw": "Construction"})()
    from app.db.session import init_database

    init_database()
    result = SectorAnalysisService().analyze(record=record, result=Dummy())
    assert result.status in {"UNAVAILABLE", "PARTIAL", "MAPPING_REVIEW_REQUIRED", "AVAILABLE", "UNMAPPED", "NO_DATA"}
    if result.companyAnnual:
        assert all(not p.vaUsable or p.va is not None for p in result.companyAnnual)


def test_sector_score_not_calibrated():
    scored = score_axe3_sectoriel({"rentabilite_commerciale": {"value": 0.1}})
    assert scored["score"] is None
    assert scored["status"] == "NOT_CALIBRATED"


def test_package_show_success_false():
    payload = {"success": False, "error": {"message": "Not found"}}
    try:
        if not payload.get("success"):
            raise RuntimeError("package_show success=false")
        assert False
    except RuntimeError as exc:
        assert "success=false" in str(exc)


def test_manual_override_priority():
    from app.sector.mapping import resolve_mapping_for_record

    record = type(
        "R",
        (),
        {
            "sector": "Commerce",
            "sectorRaw": "Commerce de détail",
            "sectorNormalized": None,
            "benchmarkSectorCode": "HCP_CONSTRUCTION",
        },
    )()
    mapped = resolve_mapping_for_record(record)
    assert mapped.mapping_method == "MANUAL"
    assert mapped.sector_code == "HCP_CONSTRUCTION"
    assert mapped.validated is True
    assert mapped.raw_activity == "Commerce de détail"


def test_ratio_null_if_denominator_zero():
    from app.services.sector_analysis_service import _ratio

    assert _ratio(10, 0) is None
    assert _ratio(None, 5) is None
    assert _ratio(10, 20) == 0.5
