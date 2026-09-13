from __future__ import annotations

from datetime import date, datetime, timedelta

from app.schemas.create_dossier import StoredDossierRecord
from app.schemas.dashboard import (
    AlertItem,
    AnalystActivity,
    DashboardData,
    DashboardKpis,
    QueueItem,
    RiskBucket,
    SectorStat,
)
from app.services import dossier_store

MONTHS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

OPEN_STATUSES = {
    "pending",
    "ready",
    "analyzing",
    "review",
    "committee",
    "contracting",
}
TO_ANALYZE_STATUSES = {"pending", "ready"}
DECIDED_STATUSES = {"approved", "rejected", "reserved"}
SECTOR_ORDER = ("Transport", "BTP", "Commerce", "Santé", "Industrie", "Autres")
PRESET_SECTORS = {
    "Transport",
    "Immobilier",
    "BTP",
    "Santé",
    "Industrie",
    "Commerce",
    "Agriculture",
    "Tourisme",
    "Tech & Services",
    "Énergie",
    "Automobile",
    "Éducation",
}
QUEUE_LIMIT = 8
ALERT_LIMIT = 8


def get_dashboard() -> DashboardData:
    records = dossier_store.list_created()
    waiting = [r for r in records if r.status in TO_ANALYZE_STATUSES]
    analyst = next((r.analyst for r in records if r.analyst), "Analyste")
    first = analyst.split()[0] if analyst else "Analyste"
    alerts = compute_alerts(records)
    return DashboardData(
        greeting=f"Bienvenue, {first}",
        dateLabel=date.today().strftime("%d/%m/%Y"),
        analystName=analyst,
        kpis=compute_kpis(records),
        queue=compute_queue(waiting),
        queueTotal=len(waiting),
        riskDist=compute_risk_dist(records),
        riskActiveTotal=sum(1 for r in records if r.status in OPEN_STATUSES),
        sectors=compute_sectors(records),
        alerts=alerts,
        unreadAlertCount=sum(1 for a in alerts if not a.read),
        activity=compute_activity(records),
    )


def compute_queue(waiting: list[StoredDossierRecord]) -> list[QueueItem]:
    ranked = sorted(
        waiting,
        key=lambda r: (
            0 if (r.urgency or "").strip().lower() == "haute" else 1,
            _age_days(r),
            r.id,
        ),
    )
    return [
        QueueItem(
            id=record.id,
            name=record.name,
            sector=record.sector or "Autre",
            amountShort=_amount_short(record.amount),
            score=record.score,
            urgency=(record.urgency or "normale").strip().lower() or "normale",
            received=record.receivedLabel or _relative_label(record),
        )
        for record in ranked[:QUEUE_LIMIT]
    ]


def compute_alerts(records: list[StoredDossierRecord]) -> list[AlertItem]:
    items: list[tuple[int, int, AlertItem]] = []
    for record in records:
        alert = _alert_for(record)
        if alert is None:
            continue
        unread_rank = 0 if not alert.read else 1
        items.append((unread_rank, _age_days(record), alert))
    items.sort(key=lambda row: (row[0], row[1], row[2].id))
    return [row[2] for row in items[:ALERT_LIMIT]]


def _alert_for(record: StoredDossierRecord) -> AlertItem | None:
    age = _relative_label(record)
    unread = _age_days(record) <= 2
    name = record.name
    if record.analyseStatus == "failed":
        return AlertItem(
            id=f"al-{record.id}-fail",
            type="Analyse",
            message=f"{name} · l’analyse a échoué, à relancer",
            time=age,
            tone="danger",
            read=False,
        )
    if record.status == "analyzing" or record.analyseStatus == "processing":
        return AlertItem(
            id=f"al-{record.id}-run",
            type="Analyse",
            message=f"{name} · analyse en cours",
            time=age,
            tone="info",
            read=False,
        )
    if record.status == "rejected":
        return AlertItem(
            id=f"al-{record.id}-rej",
            type="Décision",
            message=f"{name} · dossier rejeté",
            time=age,
            tone="danger",
            read=not unread,
        )
    if record.status == "reserved":
        return AlertItem(
            id=f"al-{record.id}-res",
            type="Décision",
            message=f"{name} · décision sous réserve",
            time=age,
            tone="warn",
            read=not unread,
        )
    if record.status == "approved":
        score_bit = f" · score {record.score}/100" if record.score else ""
        return AlertItem(
            id=f"al-{record.id}-ok",
            type="Décision",
            message=f"{name} · approuvé{score_bit}",
            time=age,
            tone="success",
            read=True,
        )
    if record.analyseStatus == "completed" or (record.status == "ready" and record.score):
        return AlertItem(
            id=f"al-{record.id}-score",
            type="Analyse",
            message=f"{name} · scoring {record.score}/100, prêt pour revue",
            time=age,
            tone="success",
            read=not unread,
        )
    if (record.urgency or "").strip().lower() == "haute" and record.status in TO_ANALYZE_STATUSES:
        return AlertItem(
            id=f"al-{record.id}-urg",
            type="Priorité",
            message=f"{name} · urgence haute, en file d’analyse",
            time=age,
            tone="warn",
            read=False,
        )
    if record.status == "pending" and not _has_liasse(record):
        return AlertItem(
            id=f"al-{record.id}-doc",
            type="Documents",
            message=f"{name} · liasse fiscale manquante ou non identifiée",
            time=age,
            tone="warn",
            read=False,
        )
    if record.status in TO_ANALYZE_STATUSES:
        return AlertItem(
            id=f"al-{record.id}-wait",
            type="Dossier",
            message=f"{name} · en attente d’analyse",
            time=age,
            tone="info",
            read=not unread,
        )
    return None


def _has_liasse(record: StoredDossierRecord) -> bool:
    for meta in record.files:
        name = (meta.name or "").lower()
        ctype = (meta.contentType or "").lower()
        if not (name.endswith(".pdf") or "pdf" in ctype):
            continue
        if any(token in name for token in ("liasse", "bilan", "cpc", "fiscal")):
            return True
    return any(
        (f.name or "").lower().endswith(".pdf") or "pdf" in (f.contentType or "").lower()
        for f in record.files
    )


def compute_activity(records: list[StoredDossierRecord]) -> AnalystActivity:
    today = date.today()
    week_start = today - timedelta(days=6)
    today_count = 0
    week_count = 0
    for record in records:
        stamp = _decision_date(record) if record.status in DECIDED_STATUSES else _parse_fr_date(record.date)
        if stamp == today:
            today_count += 1
        if stamp and week_start <= stamp <= today:
            week_count += 1

    decided = [r for r in records if r.status in {"approved", "rejected"}]
    if decided:
        approved = sum(1 for r in decided if r.status == "approved")
        rate = f"{round(100 * approved / len(decided))} %"
    else:
        rate = "—"

    delays: list[int] = []
    for record in records:
        if record.status not in DECIDED_STATUSES:
            continue
        created = _parse_fr_date(record.date)
        decided_on = _parse_fr_date(record.decisionDate) or created
        if created and decided_on:
            delays.append(max(0, (decided_on - created).days))
    if delays:
        avg = sum(delays) / len(delays)
        avg_label = f"{avg:.1f}".replace(".", ",") + " j"
    else:
        avg_label = "—"

    return AnalystActivity(
        today=today_count,
        week=week_count,
        approvalRate=rate,
        avgDelay=avg_label,
    )


def compute_kpis(records: list[StoredDossierRecord]) -> DashboardKpis:
    today = date.today()
    month_label = MONTHS_FR[today.month - 1]
    prev_year, prev_month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    yesterday = today - timedelta(days=1)

    in_progress = sum(1 for r in records if r.status in OPEN_STATUSES)
    to_analyze = sum(1 for r in records if r.status in TO_ANALYZE_STATUSES)

    approved_this = 0
    approved_prev = 0
    rejected_this = 0
    rejected_prev = 0
    created_yesterday = 0
    committed = 0

    for record in records:
        created = _parse_fr_date(record.date)
        if created == yesterday:
            created_yesterday += 1

        decided = _decision_date(record)
        if record.status == "approved":
            committed += record.amount
            if decided and decided.year == today.year and decided.month == today.month:
                approved_this += 1
            elif decided and decided.year == prev_year and decided.month == prev_month:
                approved_prev += 1
        elif record.status == "rejected":
            if decided and decided.year == today.year and decided.month == today.month:
                rejected_this += 1
            elif decided and decided.year == prev_year and decided.month == prev_month:
                rejected_prev += 1
        elif record.status == "active":
            committed += record.amount

    review_required = sum(
        1
        for r in records
        if r.status == "review"
        or ((r.analyse or {}).get("readiness") or {}).get("status") == "review_required"
    )
    failed_analyses = sum(1 for r in records if r.analyseStatus == "failed")
    quality_bad = sum(
        1
        for r in records
        if ((r.analyse or {}).get("readiness") or {}).get("ready_for_automatic_scoring") is False
        and r.analyseStatus == "completed"
    )

    return DashboardKpis(
        inProgress=in_progress,
        inProgressDelta=_created_yesterday_hint(created_yesterday),
        toAnalyze=to_analyze,
        toAnalyzeHint="Priorité · en file" if to_analyze else "Aucun dossier en file",
        approved=approved_this,
        approvedDelta=_month_delta_hint(approved_this, approved_prev),
        approvedMonth=month_label,
        rejected=rejected_this,
        rejectedDelta=_month_delta_hint(rejected_this, rejected_prev),
        rejectedMonth=month_label,
        committedValue=_format_committed(committed),
        committedHint="Portefeuille actif",
        reviewRequired=review_required,
        failedAnalyses=failed_analyses,
        qualityInsufficient=quality_bad,
    )


def _age_days(record: StoredDossierRecord) -> int:
    created = _parse_fr_date(record.date)
    if created is None:
        return max(0, record.receivedDaysAgo)
    return max(0, (date.today() - created).days)


def _relative_label(record: StoredDossierRecord) -> str:
    days = _age_days(record)
    if record.receivedLabel and days <= 0:
        return record.receivedLabel
    if days <= 0:
        return "Aujourd'hui"
    if days == 1:
        return "Hier"
    if days < 7:
        return f"Il y a {days} j"
    return record.date or f"Il y a {days} j"


def _amount_short(amount: float) -> str:
    if amount >= 1_000_000:
        millions = amount / 1_000_000
        text = str(int(millions)) if millions == int(millions) else f"{millions:.1f}".replace(".", ",")
        return f"{text} M"
    return f"{round(amount / 1000)} K"


def _parse_fr_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def _decision_date(record: StoredDossierRecord) -> date | None:
    return _parse_fr_date(record.decisionDate) or _parse_fr_date(record.date)


def _created_yesterday_hint(count: int) -> str:
    if count <= 0:
        return "Aucun nouveau hier"
    if count == 1:
        return "+1 nouveau hier"
    return f"+{count} nouveaux hier"


def _month_delta_hint(current: int, previous: int) -> str:
    diff = current - previous
    if diff > 0:
        return f"+{diff} vs mois précédent"
    if diff < 0:
        return f"−{abs(diff)} vs mois précédent"
    return "Stable vs mois précédent"


def _format_committed(amount: float) -> str:
    if amount >= 1_000_000:
        millions = amount / 1_000_000
        text = str(int(millions)) if millions == int(millions) else f"{millions:.1f}".replace(".", ",")
        return f"{text} M MAD"
    return f"{amount:,} MAD".replace(",", " ")


def _risk_tone(record: StoredDossierRecord) -> str:
    scoring = ((record.analyse or {}).get("scoring") or {})
    level = str(scoring.get("riskLevel") or "").lower()
    classe = str(scoring.get("classe") or "")
    mapped = {"faible": "low", "modere": "mid", "modéré": "mid", "eleve": "high", "élevé": "high", "critique": "critical"}
    if level in mapped:
        return mapped[level]
    if classe in {"A+", "A/B+"}:
        return "low"
    if classe == "B/B-":
        return "mid"
    if classe == "C":
        return "high"
    if classe == "D/F":
        return "critical"
    return "unknown"


def compute_risk_dist(records: list[StoredDossierRecord]) -> list[RiskBucket]:
    total = len(records)
    counts = {"low": 0, "mid": 0, "high": 0, "critical": 0, "unknown": 0}
    for record in records:
        counts[_risk_tone(record)] += 1

    result: list[RiskBucket] = []
    for label, tone in (("Faible", "low"), ("Modéré", "mid"), ("Élevé", "high"), ("Critique", "critical")):
        count = counts[tone]
        pct = round(100 * count / total) if total else 0
        result.append(RiskBucket(label=label, count=count, pct=pct, tone=tone))
    return result


def _dashboard_sector_label(sector: str | None) -> str:
    s = (sector or "").strip()
    if not s or s == "Autre" or s not in PRESET_SECTORS:
        return "Autres"
    return s


def compute_sectors(records: list[StoredDossierRecord]) -> list[SectorStat]:
    counts: dict[str, int] = {}
    for record in records:
        label = _dashboard_sector_label(record.sector)
        counts[label] = counts.get(label, 0) + 1

    ordered: list[SectorStat] = []
    seen: set[str] = set()
    for label in SECTOR_ORDER:
        if counts.get(label):
            ordered.append(SectorStat(label=label, count=counts[label]))
            seen.add(label)
    extras = sorted(
        ((label, count) for label, count in counts.items() if label not in seen and count),
        key=lambda item: (-item[1], item[0]),
    )
    for label, count in extras:
        ordered.append(SectorStat(label=label, count=count))
    return ordered
