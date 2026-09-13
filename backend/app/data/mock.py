from datetime import date, timedelta

from app.schemas.dashboard import (
    AlertItem,
    AnalystActivity,
    DashboardData,
    DashboardKpis,
    QueueItem,
    RiskBucket,
    SectorStat,
)


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _days_ago(n: int) -> str:
    return _fmt(date.today() - timedelta(days=n))


def _relative(days: int, time: str) -> str:
    if days <= 0:
        return f"Auj. {time}"
    if days == 1:
        return f"Hier {time}"
    return _days_ago(days)


def build_dashboard() -> DashboardData:
    queue = [
        QueueItem(
            id="MED-2025-0432",
            name="Clinique Privée Méditerranée",
            sector="Santé",
            amountShort="8,5 M",
            score=91,
            urgency="haute",
            received=_relative(1, "16:42"),
        ),
        QueueItem(
            id="HOT-2025-0436",
            name="Hôtel Riad Luxe SA",
            sector="Tourisme",
            amountShort="12 M",
            score=88,
            urgency="haute",
            received=_relative(0, "08:15"),
        ),
        QueueItem(
            id="ENE-2025-0443",
            name="Énergies Vertes Maroc",
            sector="Énergie",
            amountShort="11,5 M",
            score=86,
            urgency="haute",
            received=_relative(1, "07:45"),
        ),
        QueueItem(
            id="BTP-2025-0431",
            name="Atlas Construction SA",
            sector="BTP",
            amountShort="3,2 M",
            score=72,
            urgency="normale",
            received=_relative(1, "11:30"),
        ),
        QueueItem(
            id="LOG-2025-0438",
            name="Logistique Express Sud",
            sector="Transport",
            amountShort="3,4 M",
            score=74,
            urgency="normale",
            received=_relative(2, "14:20"),
        ),
    ]
    return DashboardData(
        greeting="Bienvenue, Karim Benali",
        dateLabel=_fmt(date.today()),
        analystName="Karim Benali",
        kpis=DashboardKpis(
            inProgress=24,
            inProgressDelta="+2 nouveaux hier",
            toAnalyze=7,
            toAnalyzeHint="Priorité · en file",
            approved=18,
            approvedDelta="+5 vs mois précédent",
            approvedMonth="juin",
            rejected=4,
            rejectedDelta="−1 vs mois précédent",
            rejectedMonth="juin",
            committedValue="487 M MAD",
            committedHint="Portefeuille actif",
        ),
        queue=queue,
        queueTotal=7,
        riskDist=[
            RiskBucket(label="Faible", count=9, pct=37, tone="low"),
            RiskBucket(label="Moyen", count=9, pct=38, tone="mid"),
            RiskBucket(label="Élevé", count=6, pct=25, tone="high"),
        ],
        riskActiveTotal=24,
        sectors=[
            SectorStat(label="Transport", count=4),
            SectorStat(label="BTP", count=5),
            SectorStat(label="Commerce", count=6),
            SectorStat(label="Santé", count=3),
            SectorStat(label="Industrie", count=3),
            SectorStat(label="Autres", count=3),
        ],
        alerts=[
            AlertItem(
                id="a1",
                type="Fraude",
                message="Industrie Plastique Nord · score anti-fraude 67/100",
                time="Il y a 2h",
                tone="danger",
                read=False,
            ),
            AlertItem(
                id="a2",
                type="Documents",
                message="Coopérative Agricole Tadla · liasse 2023 expirante",
                time="Il y a 4h",
                tone="warn",
                read=False,
            ),
            AlertItem(
                id="a3",
                type="Escalade",
                message="Distribution Centrale · demande comité d’octroi",
                time="Il y a 6h",
                tone="info",
                read=True,
            ),
            AlertItem(
                id="a4",
                type="Analyse",
                message="Hôtel Riad Luxe · pipeline terminé, prêt revue",
                time="Il y a 8h",
                tone="success",
                read=True,
            ),
        ],
        activity=AnalystActivity(
            today=3, week=11, approvalRate="74%", avgDelay="3,2j"
        ),
    )
