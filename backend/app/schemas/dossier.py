from pydantic import BaseModel


class Dossier(BaseModel):
    id: str
    name: str
    sector: str
    amount: float
    duration: int
    score: int
    status: str
    analyst: str
    receivedDaysAgo: int
    date: str
    urgency: str | None = None
    receivedLabel: str | None = None
    analyseStatus: str | None = None
    analyseProgressPct: int | None = None
    source: str | None = None
    noDemande: str | None = None
    noPv: str | None = None
    classe: str | None = None
    riskLevel: str | None = None


class DossierListResponse(BaseModel):
    items: list[Dossier]
    total: int
