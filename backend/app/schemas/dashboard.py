from pydantic import BaseModel


class QueueItem(BaseModel):
    id: str
    name: str
    sector: str
    amountShort: str
    score: int
    urgency: str
    received: str


class RiskBucket(BaseModel):
    label: str
    count: int
    pct: int
    tone: str


class SectorStat(BaseModel):
    label: str
    count: int


class AlertItem(BaseModel):
    id: str
    type: str
    message: str
    time: str
    tone: str
    read: bool


class DashboardKpis(BaseModel):
    inProgress: int
    inProgressDelta: str
    toAnalyze: int
    toAnalyzeHint: str
    approved: int
    approvedDelta: str
    approvedMonth: str
    rejected: int
    rejectedDelta: str
    rejectedMonth: str
    committedValue: str
    committedHint: str
    reviewRequired: int = 0
    failedAnalyses: int = 0
    qualityInsufficient: int = 0


class AnalystActivity(BaseModel):
    today: int
    week: int
    approvalRate: str
    avgDelay: str


class DashboardData(BaseModel):
    greeting: str
    dateLabel: str
    analystName: str
    kpis: DashboardKpis
    queue: list[QueueItem]
    queueTotal: int
    riskDist: list[RiskBucket]
    riskActiveTotal: int
    sectors: list[SectorStat]
    alerts: list[AlertItem]
    unreadAlertCount: int = 0
    activity: AnalystActivity
