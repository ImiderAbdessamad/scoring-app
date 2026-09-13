from __future__ import annotations

from app.schemas.create_dossier import StoredDossierRecord, StoredFileMeta
from app.services.copilot_service import build_dossier_brief


def test_copilot_brief_includes_score_and_files():
    record = StoredDossierRecord(
        id="ABC-2026-1111",
        name="ADEIS INVEST",
        sector="Immobilier",
        amount=1_200_000,
        duration=48,
        score=70,
        status="ready",
        analyst="K. Benali",
        date="17/08/2026",
        ice="001669862000005",
        rc="",
        nature="Crédit-bail mobilier",
        valeurBien=1_500_000,
        apport=20,
        fournisseur="X",
        proformaReference="PF-1",
        natureBien="Engins",
        etat="neuf",
        valeurHt=1_200_000,
        valeurTtc=1_440_000,
        files=[
            StoredFileMeta(
                name="bilan.pdf",
                objectKey="k",
                size=10,
                contentType="application/pdf",
                category="entreprise",
            )
        ],
        analyse={
            "scoring": {
                "score": 70,
                "classe": "B/B-",
                "riskLabel": "Moyen",
                "recommendation": "Accord avec garanties complémentaires",
                "dossierCompletenessPct": 70,
                "ratiosOk": 4,
                "ratiosTotal": 11,
                "attention": {
                    "pointsForts": ["Structure financière saine."],
                    "pointsVigilance": ["Rentabilité commerciale à surveiller."],
                    "scoreFinal": "Score final : 70 / 100 — Classe B/B- « Moyen ».",
                },
            },
            "ratios": {
                "items": [
                    {"label": "Autonomie financière", "value": "25 %", "status": "GOOD"},
                ],
                "fiscal": [{"label": "CAF", "value": "676 839 MAD"}],
            },
        },
    )
    brief = build_dossier_brief(record)
    assert "ADEIS INVEST" in brief
    assert "70 / 100" in brief
    assert "B/B-" in brief
    assert "bilan.pdf" in brief
    assert "Rentabilité commerciale" in brief


def _sample_record() -> StoredDossierRecord:
    return StoredDossierRecord(
        id="ABC-2026-1111",
        name="ADEIS INVEST",
        sector="Immobilier",
        amount=1_200_000,
        duration=48,
        score=70,
        status="ready",
        analyst="K. Benali",
        date="17/08/2026",
        ice="001669862000005",
        nature="Crédit-bail mobilier",
        valeurBien=1_500_000,
        apport=20,
        fournisseur="X",
        proformaReference="PF-1",
        natureBien="Engins",
        etat="neuf",
        valeurHt=1_200_000,
        valeurTtc=1_440_000,
    )


def test_ask_copilot_accepts_empty_history(monkeypatch):
    from app.services import copilot_service

    captured: dict = {}

    def fake_chat(messages):
        captured["messages"] = messages
        return "Score 70, classe B/B-."

    monkeypatch.setattr(copilot_service, "_ollama_chat", fake_chat)
    result = copilot_service.ask_copilot(_sample_record(), "Pourquoi ce score ?", [])
    assert result["reply"] == "Score 70, classe B/B-."
    assert captured["messages"][-1]["content"] == "Pourquoi ce score ?"


def test_ask_copilot_keeps_last_eight_turns(monkeypatch):
    from app.services import copilot_service

    captured: dict = {}

    def fake_chat(messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(copilot_service, "_ollama_chat", fake_chat)
    history = [{"role": "user", "content": f"q{i}"} for i in range(12)]
    copilot_service.ask_copilot(_sample_record(), "suite ?", history)
    user_turns = [m for m in captured["messages"] if m["role"] == "user"]
    assert user_turns[0]["content"] == "q4"
    assert user_turns[-1]["content"] == "suite ?"
    assert len(user_turns) == 9

