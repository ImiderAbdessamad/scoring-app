from pydantic import BaseModel, Field, field_validator, model_validator
import re


class EntreprisePayload(BaseModel):
    ice: str
    raisonSociale: str
    rc: str = ""
    identifiantFiscal: str = ""
    secteur: str = ""
    secteurRaw: str = ""
    documentNames: list[str] = Field(default_factory=list)

    @field_validator("raisonSociale")
    @classmethod
    def _raison(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("Raison sociale obligatoire")
        return text

    @field_validator("ice")
    @classmethod
    def _ice(cls, value: str) -> str:
        text = (value or "").replace(" ", "")
        if text and not re.fullmatch(r"\d{15}", text):
            raise ValueError("ICE : 15 chiffres requis")
        return text


class FinancementPayload(BaseModel):
    nature: str
    montantDemande: float
    valeurBien: float
    dureeMois: int
    apport: float
    urgence: str

    @model_validator(mode="after")
    def _bounds(self) -> "FinancementPayload":
        if self.nature not in {"mobilier", "immobilier"}:
            raise ValueError("Nature de financement invalide")
        if not (self.montantDemande > 0):
            raise ValueError("Montant demandé doit être > 0")
        if not (self.valeurBien > 0):
            raise ValueError("Valeur du bien doit être > 0")
        if not (self.dureeMois > 0):
            raise ValueError("Durée doit être > 0")
        if not (0 <= self.apport <= 100):
            raise ValueError("Apport entre 0 et 100")
        if self.urgence not in {"haute", "normale", "basse"}:
            raise ValueError("Urgence invalide")
        return self


class FournisseurBienPayload(BaseModel):
    fournisseur: str
    proformaReference: str
    proformaFileName: str | None = None
    natureBien: str
    etat: str
    valeurHt: float
    valeurTtc: float

    @field_validator("etat")
    @classmethod
    def _etat(cls, value: str) -> str:
        if value not in {"neuf", "occasion"}:
            raise ValueError("État du bien invalide")
        return value


class CreateDossierPayload(BaseModel):
    entreprise: EntreprisePayload
    financement: FinancementPayload
    fournisseurBien: FournisseurBienPayload


class CreateDossierResponse(BaseModel):
    id: str
    status: str
    message: str
    job_id: str | None = None
    stream_url: str | None = None
    result_url: str | None = None
    synthese_url: str | None = None
    filename: str | None = None


class StoredFileMeta(BaseModel):
    name: str
    objectKey: str
    size: int
    contentType: str
    category: str
    sha256: str | None = None
    version: int = 1


class StoredDossierRecord(BaseModel):
    id: str
    name: str
    sector: str
    amount: float
    duration: int
    score: int = 0
    status: str = "pending"
    analyst: str
    receivedDaysAgo: int = 0
    date: str
    urgency: str | None = None
    receivedLabel: str | None = None
    ice: str
    identifiantFiscal: str = ""
    rc: str = ""
    sectorRaw: str | None = None
    sectorNormalized: str | None = None
    benchmarkSectorCode: str | None = None
    nature: str
    valeurBien: float
    apport: float
    fournisseur: str
    proformaReference: str
    natureBien: str
    etat: str
    valeurHt: float
    valeurTtc: float
    files: list[StoredFileMeta] = Field(default_factory=list)
    decisionDate: str | None = None
    analyseJobId: str | None = None
    analyseStatus: str | None = None
    analyse: dict | None = None
    source: str = "wfb"
    noDemande: str | None = None
    noPv: str | None = None
    pvcId: str | None = None
    pvc: dict | None = None
