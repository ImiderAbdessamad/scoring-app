"""Payloads partenaire PVC — mêmes noms de colonnes que DossierPv / Simulation / Bien."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PvcActionnaire(BaseModel):
    model_config = ConfigDict(extra="allow")

    nomPrenom: str | None = None
    quotePart: float | None = None
    cin: str | None = None
    dateNaissance: str | None = None
    adresse: str | None = None


class PvcMandataire(BaseModel):
    model_config = ConfigDict(extra="allow")

    nomPrenom: str | None = None
    qualite: str | None = None
    cin: str | None = None
    dateNaissance: str | None = None
    adresse: str | None = None


class PvcBien(BaseModel):
    model_config = ConfigDict(extra="allow")

    description: str | None = None
    neufOccasion: str | None = None
    montantHT: float | None = None
    simulation: str | int | None = None
    dossier: str | int | None = None


class PvcSimulation(BaseModel):
    model_config = ConfigDict(extra="allow")

    duree: int | float | None = None
    redevance: float | None = None
    noContrat: str | None = None
    biens: list[PvcBien] = Field(default_factory=list)
    dossier: str | int | None = None


class PvcDossierPv(BaseModel):
    """Table principale PVC_DOSSIER_PV + collections."""

    model_config = ConfigDict(extra="allow")

    id: str | int | None = None
    noPv: str | None = None
    noDemande: str
    noTiers: str | None = None
    nomClient: str
    typeClient: str | None = None
    montantTotal: float | None = None
    redevanceTotal: float | None = None
    tauxStandard: float | None = None
    tauxPropose: float | None = None
    hasFraisDossier: bool | None = None
    montantFraisDossier: float | None = None
    fournisseur: str | None = None
    dateReceptionEbail: str | None = None
    commercialNom: str | None = None
    statutWorkflow: str | None = None
    typeComite: str | int | None = None
    dateSynthese: str | None = None
    dateFinalisation: str | None = None
    enRAC: bool | None = None
    racMotif: str | None = None
    racInitiePar: str | None = None
    dateInitiationRAC: str | None = None
    dateCreation: str | None = None
    rcAnalytique: str | None = None
    villeRC: str | None = None
    formeJuridique: str | None = None
    adresseSociale: str | None = None
    capital: float | None = None
    telephone: str | None = None
    activite: str | None = None
    ribDomiciliation: str | None = None
    banque: str | None = None
    segmentMarche: str | None = None
    segmentationAWB: str | None = None
    segmentationWafabail: str | None = None
    noteInterneSysteme: str | None = None
    noteInterneAgree: str | None = None
    regionRisque: str | None = None
    dateEntretienClient: str | None = None
    garantiesCommercial: str | None = None
    cycleArbitrage: str | None = None
    versionNumber: int | None = None
    escaladeAnalyste: bool | None = None
    arbitragePresentielDeclenche: bool | None = None
    remarques: str | None = None
    typeComiteArbitrage: str | int | None = None
    actionnaires: list[PvcActionnaire] = Field(default_factory=list)
    mandataires: list[PvcMandataire] = Field(default_factory=list)
    simulations: list[PvcSimulation] = Field(default_factory=list)
    votes: list[Any] = Field(default_factory=list)
    timeline: list[Any] = Field(default_factory=list)


class PartnerIngestResponse(BaseModel):
    noDemande: str
    noPv: str | None = None
    id: str | int | None = None
    wfb_id: str
    nomClient: str
    status: str
    message: str
    job_id: str | None = None
    stream_url: str | None = None
    result_url: str | None = None
    poll_url: str
    analyse_url: str
    filename: str | None = None


class PartnerRatioItem(BaseModel):
    label: str
    value: str | None = None
    status: str | None = None


class PartnerAnalyseResponse(BaseModel):
    noDemande: str
    noPv: str | None = None
    id: str | int | None = None
    wfb_id: str
    nomClient: str
    status: str
    analyseStatus: str | None = None
    job_id: str | None = None
    progress_pct: int | None = None
    message: str | None = None
    score: int | None = None
    classe: str | None = None
    decision: str | None = None
    recommandation: str | None = None
    points_forts: list[str] = Field(default_factory=list)
    points_vigilance: list[str] = Field(default_factory=list)
    score_final: str | None = None
    ice: str | None = None
    rc: str | None = None
    exercise: str | None = None
    year_labels: list[str] = Field(default_factory=list)
    completeness_pct: float | None = None
    ratios: list[PartnerRatioItem] = Field(default_factory=list)
    dossier: dict[str, Any] = Field(default_factory=dict)
    stream_url: str | None = None
    result_url: str | None = None
    error: str | None = None
