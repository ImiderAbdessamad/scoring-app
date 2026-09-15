"""Copilote analyste : Qwen (Ollama) répond à partir du dossier analysé."""
from __future__ import annotations

import logging
from typing import Any

import requests

from app import config
from app.schemas.create_dossier import StoredDossierRecord

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es le copilote crédit-bail de Wafabail.
Tu aides l'analyste sur UN dossier précis, en français, de façon concise et professionnelle.

Règles :
- Appuie-toi uniquement sur le CONTEXTE fourni (scoring view, quality, éligibilité, mémo).
- N'invente pas de chiffres, de ratios, de pièces, de cotation BAM ou d'incidents absents du contexte.
- Si BAM est UNKNOWN / non vérifiée, dis « cotation BAM non vérifiée ».
- Si les incidents sont UNKNOWN, dis « incidents bancaires non vérifiés ».
- Si une analyse sectorielle HCP est fournie, utilise uniquement ces chiffres (VA, croissances, fraîcheur).
- N'invente pas de médiane sectorielle, de taux de défaut ou de PIB si la métrique est la valeur ajoutée.
- Si scoring.status = NOT_CALIBRATED, dis que l'analyse sectorielle n'est pas intégrée au score.
- Ne dis jamais que l'entreprise « surperforme en réel » : la VA entreprise est nominale ; la croissance réelle HCP est une conjoncture distincte.
- Si un indicateur sectoriel est absent, dis qu'il n'est pas disponible.
- Une valeur status=suspect n'est pas une valeur confirmée.
- Tu ne modifies jamais le score, la décision, une valeur usable ou le quality gate.
"""


def build_dossier_brief(record: StoredDossierRecord) -> str:
    ws = record.analyse or {}
    scoring = ws.get("scoring") or {}
    ratios = ws.get("ratios") or {}
    attention = scoring.get("attention") or {}
    header = ws.get("header") or {}
    company = header.get("companyName") or record.name
    identity_lines = []
    documents = ws.get("documents") or {}
    for extraction in (documents.get("extractions") or {}).values():
        for field in extraction.get("fields") or []:
            label = (field.get("label") or "").strip()
            value = field.get("value")
            if label in {
                "ICE",
                "Identifiant fiscal",
                "Taxe professionnelle",
                "RC",
                "Adresse",
                "Ville",
                "Activité",
                "Secteur",
                "Période",
                "Date de déclaration",
                "Référence",
            } and value not in (None, "—", ""):
                identity_lines.append(f"{label} : {value}")
        break
    lines = [
        f"Référence : {record.id}",
        f"Entreprise : {company}",
        f"Secteur : {record.sector}",
        *identity_lines,
        f"ICE dossier : {record.ice or '—'}",
        f"RC dossier : {record.rc or '—'}",
        f"Montant demandé : {record.amount} MAD",
        f"Durée : {record.duration} mois",
        f"Apport : {record.apport} %",
        f"Statut dossier : {record.status}",
        f"Score : {scoring.get('score', record.score)} / 100",
        f"Classe : {scoring.get('classe') or '—'}",
        f"Décision moteur : {scoring.get('riskLabel') or '—'}",
        f"Recommandation : {scoring.get('recommendation') or '—'}",
        f"Postes extraits : {scoring.get('dossierCompletenessPct', 0)} %",
        f"Ratios conformes : {scoring.get('ratiosOk', 0)}/{scoring.get('ratiosTotal', 0)}",
    ]
    forts = attention.get("pointsForts") or []
    vigi = attention.get("pointsVigilance") or []
    if forts:
        lines.append("Points forts :")
        lines.extend(f"- {item}" for item in forts[:6])
    if vigi:
        lines.append("Points de vigilance :")
        lines.extend(f"- {item}" for item in vigi[:6])
    if scoring.get("scoreFinal") or attention.get("scoreFinal"):
        lines.append(f"Synthèse score : {attention.get('scoreFinal') or scoring.get('scoreFinal')}")

    items = ratios.get("items") or []
    if items:
        lines.append("Ratios :")
        for item in items[:14]:
            lines.append(
                f"- {item.get('label')}: {item.get('value')} ({item.get('status')})"
            )

    fiscal = ratios.get("fiscal") or []
    if fiscal:
        lines.append("Agrégats :")
        for item in fiscal[:8]:
            lines.append(f"- {item.get('label')}: {item.get('value')}")

    files = [f.name for f in record.files]
    if files:
        lines.append("Documents : " + ", ".join(files[:12]))
    sector = ws.get("sectorAnalysis") or {}
    if sector:
        lines.append("Analyse sectorielle :")
        lines.append(f"- statut : {sector.get('status')}")
        sec = sector.get("sector") or {}
        lines.append(f"- secteur : {sec.get('label') or '—'}")
        fresh = sector.get("dataFreshness") or {}
        lines.append(f"- source : {fresh.get('source')} fraîcheur={fresh.get('status')}")
        head = sector.get("headline") or {}
        lines.append(f"- dernière période VA : {head.get('latestYear')} croissance nominale={head.get('nominalGrowthYoy')} réelle={head.get('realGrowthYoy')}")
        lines.append(f"- scoring sectoriel : {(sector.get('scoring') or {}).get('status')} inclus={ (sector.get('scoring') or {}).get('includedInFinalScore') }")
        if sector.get("summary"):
            lines.append(f"- résumé : {sector.get('summary')}")
        for warn in (sector.get("warnings") or [])[:4]:
            lines.append(f"- avertissement : {warn}")
    if not record.analyse:
        lines.append("Note : l'analyse scoring n'a pas encore été exécutée sur ce dossier.")
    return "\n".join(lines)


def _ollama_chat(messages: list[dict[str, str]]) -> str:
    url = f"{config.RCC_OLLAMA_URL}/api/chat"
    body = {
        "model": config.RCC_COPILOT_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": config.RCC_KEEP_ALIVE,
        "options": {
            "temperature": 0.25,
            "num_ctx": 8192,
            "num_predict": 700,
        },
    }
    try:
        response = requests.post(url, json=body, timeout=120)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise RuntimeError("Qwen n'a pas répondu à temps. Réessayez dans un instant.") from exc
    except requests.RequestException as exc:
        logger.exception("Appel Ollama copilote impossible")
        raise RuntimeError(f"Copilote Qwen indisponible : {exc}") from exc

    payload = response.json()
    content = ((payload.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Qwen a renvoyé une réponse vide.")
    return content


def ask_copilot(
    record: StoredDossierRecord,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    brief = build_dossier_brief(record)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCONTEXTE DU DOSSIER :\n{brief}"},
    ]
    recent = list(history or [])[-8:]
    for item in recent:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content[:2000]})
    messages.append({"role": "user", "content": question.strip()[:2000]})
    reply = _ollama_chat(messages)
    return {"reply": reply, "model": config.RCC_COPILOT_MODEL}
