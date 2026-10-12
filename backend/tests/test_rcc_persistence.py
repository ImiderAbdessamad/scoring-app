"""Les dossiers RCC sont enregistrés en base et rechargés après un redémarrage de l'API."""
from __future__ import annotations

import uuid

import pytest

from app.schemas.analyse import DocumentSummary, ExtractionSummary, ScoringAnalysisResult, YearsBlock
from app.services.rcc_dossier_store import (
    RccDossier,
    RccDossierStore,
    dossier_from_payload,
    dossier_to_payload,
)


def _scoring_result() -> ScoringAnalysisResult:
    return ScoringAnalysisResult(
        document=DocumentSummary(filename="liasse.pdf", pages_total=4, pages_processed=4, pages_skipped=0, pages_failed=0),
        extraction=ExtractionSummary(model="test"),
        fields=[],
        completeness_pct=72,
        years=YearsBlock(),
    )


def _dossier(dossier_id: str, **changes) -> RccDossier:
    values = dict(
        id=dossier_id, job_id=f"job-{dossier_id}", client_name="STE EUROMEDIA", ice="001531725000054",
        credit_amount=250000.0, exercice_date="31/12/2025", status="pending",
        created_at="2026-10-12T08:00:00+00:00", updated_at="2026-10-12T08:00:00+00:00",
        sector="Médias", filename="liasse.pdf", pdf_path=None, completeness_pct=72,
        result={"fields": [{"code": "CHIFFRE_AFFAIRES", "value": 1200.0}]},
        scoring_result=_scoring_result(),
        identite={"period_end": "31/12/2025", "raison_sociale": "STE EUROMEDIA"},
    )
    values.update(changes)
    return RccDossier(**values)


@pytest.fixture
def dossier_id():
    # Numéro du même format que les vrais dossiers, très haut pour ne pas croiser ceux du poste.
    value = f"RCC-2026-{9000 + uuid.uuid4().int % 900}"
    yield value
    RccDossierStore().delete(value)


def test_payload_round_trip_keeps_everything():
    dossier = _dossier("RCC-2026-0001", bilans_push={"status": "sent", "noRcTiers": "022654"})
    restored = dossier_from_payload(dossier_to_payload(dossier))

    assert restored.client_name == "STE EUROMEDIA"
    assert restored.bilans_push == {"status": "sent", "noRcTiers": "022654"}
    assert isinstance(restored.scoring_result, ScoringAnalysisResult)
    assert restored.scoring_result.completeness_pct == 72


def test_dossier_survives_restart(dossier_id):
    before = RccDossierStore()
    before.put(_dossier(dossier_id))
    before.set_tiers(dossier_id, "022654", "manual", "Analyste A")
    before.save_overrides(dossier_id, [{"field_code": "CHIFFRE_AFFAIRES", "corrected_value": 1300.0, "verified": True}], "Analyste A")
    before.patch(dossier_id, {"status": "validated", "comment": "OK"}, "Analyste A")

    # Nouveau store = API redémarrée : tout est relu depuis la base.
    after = RccDossierStore()
    dossier = after.get(dossier_id)

    assert dossier is not None
    assert dossier.identite["tiers"] == "022654"
    assert dossier.identite["tiers_source"] == "manual"
    assert [(o.field_code, o.corrected_value, o.verified) for o in dossier.overrides] == [("CHIFFRE_AFFAIRES", 1300.0, True)]
    assert dossier.status == "validated"
    assert dossier.comment == "OK"
    assert isinstance(dossier.scoring_result, ScoringAnalysisResult)
    assert after.find_by_job(f"job-{dossier_id}") is dossier

    actions = [event["action"] for event in after.audit_for(dossier_id)]
    assert "N° tiers saisi" in actions
    assert "Vérification" in actions


def test_numbering_continues_after_restart(dossier_id):
    RccDossierStore().put(_dossier(dossier_id))
    after = RccDossierStore()
    after.get(dossier_id)  # premier accès : recharge la base

    # Le compteur reprend après le plus grand numéro enregistré (pas de doublon RCC-…-0001).
    next_number = int(after._next_id().rsplit("-", 1)[1])
    assert next_number > int(dossier_id.rsplit("-", 1)[1])


def test_deleted_dossier_stays_deleted(dossier_id):
    store = RccDossierStore()
    store.put(_dossier(dossier_id))
    assert store.delete(dossier_id) is True

    assert RccDossierStore().get(dossier_id) is None
