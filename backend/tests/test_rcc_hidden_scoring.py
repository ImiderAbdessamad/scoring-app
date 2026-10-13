"""Dossiers Étude de risque masqués dans RCC : le choix est enregistré et survit au redémarrage."""
from __future__ import annotations

import uuid

from app.services.rcc_dossier_store import RccDossierStore


def test_hidden_scoring_dossier_is_persisted_and_audited():
    dossier_id = f"TEST-MASQUE-{uuid.uuid4().hex[:6]}"
    store = RccDossierStore()
    assert not store.is_hidden_scoring(dossier_id)

    store.hide_scoring(dossier_id, "STE TEST", "Analyste")
    store.hide_scoring(dossier_id, "STE TEST", "Analyste")  # second appel sans effet
    assert store.is_hidden_scoring(dossier_id)
    events = [e for e in store.audit_all() if e["dossier_id"] == dossier_id]
    assert len(events) == 1

    reloaded = RccDossierStore()
    assert reloaded.is_hidden_scoring(dossier_id)
