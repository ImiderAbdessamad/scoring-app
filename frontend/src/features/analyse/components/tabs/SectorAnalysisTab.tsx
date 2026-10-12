import { useEffect, useMemo, useState } from 'react'
import { Layers, RefreshCw, Settings2 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import {
  CompanyVsSectorNormalizedChart,
  SectorQuarterlyTrendChart,
  SectorRealGrowthChart,
  SectorValueAddedTrendChart,
  VaGrowthBarsChart,
} from '@/features/analyse/components/charts/SectorCharts'
import { formatSectorAmount, formatSectorPeriod, formatSignedPct } from '@/lib/sectorFormat'
import {
  fetchHcpBranches,
  fetchSectorAnalysis,
  fetchSectorSources,
  refreshSectorData,
  saveDossierSectorSource,
  saveSectorMapping,
  type HcpBranch,
  type SectorSourceItem,
} from '@/services/sectors'
import type { SectorAnalysisData } from '@/types/analyse'

type Props = {
  data?: SectorAnalysisData | null
  dossierId?: string
  onSectorUpdated?: (payload: {
    sectorLabel: string
    sectorAnalysis: SectorAnalysisData
  }) => void
}

export function SectorAnalysisTab({ data, dossierId, onSectorUpdated }: Props) {
  const [busy, setBusy] = useState(false)
  const [mappingBusy, setMappingBusy] = useState(false)
  const [sourceBusy, setSourceBusy] = useState(false)
  const [local, setLocal] = useState(data)
  const [branches, setBranches] = useState<HcpBranch[]>([])
  const [sources, setSources] = useState<SectorSourceItem[]>([])
  const [selectedCode, setSelectedCode] = useState('')
  const [selectedSourceId, setSelectedSourceId] = useState('')
  const [notice, setNotice] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [fullHistory, setFullHistory] = useState(false)
  const analysis = local ?? data

  const activeSourceId =
    analysis?.sector?.sourceId ||
    sources.find((s) => s.isDefault)?.id ||
    'hcp'

  useEffect(() => {
    setLocal(data)
  }, [data])

  useEffect(() => {
    if (!dossierId) return
    let cancelled = false
    fetchSectorAnalysis(dossierId, 'auto')
      .then((next) => {
        if (!cancelled) {
          setLocal(next)
          if (next.sector?.sourceId) setSelectedSourceId(next.sector.sourceId)
        }
      })
      .catch(() => {
        /* le workspace reste la source de repli */
      })
    return () => {
      cancelled = true
    }
  }, [dossierId])

  useEffect(() => {
    let cancelled = false
    fetchSectorSources()
      .then((res) => {
        if (cancelled) return
        setSources(res.items || [])
        if (!selectedSourceId) {
          const pinned = analysis?.sector?.sourceId
          const fallback = pinned || res.defaultSourceId || res.items.find((i) => i.isDefault)?.id || 'hcp'
          setSelectedSourceId(fallback)
        }
      })
      .catch(() => {
        if (!cancelled) setSources([])
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dossierId])

  useEffect(() => {
    let cancelled = false
    fetchHcpBranches(activeSourceId)
      .then((res) => {
        if (!cancelled) setBranches(res.items || [])
      })
      .catch(() => {
        if (!cancelled) setBranches([])
      })
    return () => {
      cancelled = true
    }
  }, [activeSourceId])

  useEffect(() => {
    const code = analysis?.sector?.code || ''
    setSelectedCode(code)
  }, [analysis?.sector?.code])

  useEffect(() => {
    if (analysis?.sector?.sourceId) setSelectedSourceId(analysis.sector.sourceId)
  }, [analysis?.sector?.sourceId])

  const currentLabel = useMemo(() => {
    if (selectedCode) {
      return branches.find((b) => b.code === selectedCode)?.label || analysis?.sector?.label || ''
    }
    return analysis?.sector?.label || ''
  }, [selectedCode, branches, analysis?.sector?.label])

  const activeSource = sources.find((s) => s.id === activeSourceId)
  const sourceLabel = analysis?.sector?.sourceLabel || activeSource?.shortLabel || 'HCP'

  async function refresh() {
    if (!dossierId) return
    setBusy(true)
    setNotice(`Vérification des données ${sourceLabel}...`)
    try {
      const result = await refreshSectorData(true, activeSourceId)
      const next = await fetchSectorAnalysis(dossierId, 'false')
      setLocal(next)
      onSectorUpdated?.({
        sectorLabel: next.sector?.label || analysis?.sector?.label || '—',
        sectorAnalysis: next,
      })
      if (result.changed > 0) setNotice(`Nouvelles données ${sourceLabel} importées.`)
      else setNotice('Données déjà à jour.')
    } catch {
      setNotice('Vérification impossible — cache local conservé.')
    } finally {
      setBusy(false)
    }
  }

  async function applySourceChange() {
    if (!dossierId || !selectedSourceId) return
    if (selectedSourceId === analysis?.sector?.sourceId) return
    const confirmed = window.confirm(
      'Changer de source efface le mapping branche actuel (taxonomies isolées) et recalcule l’analyse. Continuer ?',
    )
    if (!confirmed) {
      setSelectedSourceId(analysis?.sector?.sourceId || sources.find((s) => s.isDefault)?.id || 'hcp')
      return
    }
    setSourceBusy(true)
    setNotice(null)
    try {
      const res = await saveDossierSectorSource(dossierId, selectedSourceId)
      setLocal(res.analysis)
      setSelectedCode(res.analysis.sector?.code || '')
      onSectorUpdated?.({
        sectorLabel: res.analysis.sector?.label || analysis?.sector?.label || '—',
        sectorAnalysis: res.analysis,
      })
      setNotice(res.message)
    } catch {
      setNotice('Impossible de changer la source de données.')
      setSelectedSourceId(analysis?.sector?.sourceId || 'hcp')
    } finally {
      setSourceBusy(false)
    }
  }

  async function applySectorChange() {
    if (!dossierId || !selectedCode) return
    setMappingBusy(true)
    setNotice(null)
    try {
      const res = await saveSectorMapping(dossierId, selectedCode)
      const next = res.analysis
      setLocal(next)
      onSectorUpdated?.({
        sectorLabel: res.sector || next.sector?.label || currentLabel,
        sectorAnalysis: next,
      })
      setNotice(`Secteur mis à jour : ${res.sector || next.sector?.label || currentLabel}`)
    } catch {
      setNotice('Impossible d’enregistrer le nouveau secteur.')
    } finally {
      setMappingBusy(false)
    }
  }

  const selectableSources = sources.filter((s) => s.selectable || s.id === activeSourceId)

  const sourceEditor =
    dossierId ? (
      <SectorSourceEditor
        sources={selectableSources.length ? selectableSources : sources}
        selectedSourceId={selectedSourceId || activeSourceId}
        currentSourceId={analysis?.sector?.sourceId || ''}
        onChange={setSelectedSourceId}
        onApply={applySourceChange}
        busy={sourceBusy}
      />
    ) : null

  const mappingEditor =
    dossierId ? (
      <SectorMappingEditor
        branches={branches}
        selectedCode={selectedCode}
        currentCode={analysis?.sector?.code || ''}
        onChange={setSelectedCode}
        onApply={applySectorChange}
        busy={mappingBusy}
        notice={notice}
        rawActivity={analysis?.sector?.rawActivity}
        sourceLabel={sourceLabel}
      />
    ) : null

  // Choix de la source et de la branche : regroupés dans un panneau ouvert à la demande.
  const editors = (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {mappingEditor}
      {sourceEditor}
    </div>
  )

  const refreshButton = dossierId ? (
    <button
      type="button"
      disabled={busy}
      onClick={refresh}
      className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-wb-line bg-white px-4 py-2 text-[12.5px] font-semibold text-slate-700 transition-colors hover:border-wb-accent hover:text-wb-accent-text disabled:cursor-not-allowed disabled:opacity-60"
    >
      <RefreshCw size={13} className={busy ? 'animate-spin' : ''} />
      {busy ? 'Vérification…' : 'Actualiser'}
    </button>
  ) : null

  if (!analysis || analysis.status === 'UNAVAILABLE' || analysis.status === 'NO_DATA' || analysis.status === 'ERROR') {
    return (
      <div className="flex flex-col gap-4">
        <Card className="p-6">
          <SectorTitle label="Analyse sectorielle" />
          <p className="m-0 mt-3 border-l-2 border-wb-accent pl-3 text-[13px] text-slate-600">
            Les données sectorielles publiques ne sont pas disponibles actuellement.
          </p>
          {refreshButton ? <div className="mt-4">{refreshButton}</div> : null}
          {notice ? <p className="m-0 mt-2 text-[12px] text-wb-muted">{notice}</p> : null}
        </Card>
        {editors}
      </div>
    )
  }

  if (analysis.status === 'MAPPING_REVIEW_REQUIRED' || analysis.status === 'UNMAPPED') {
    return (
      <div className="flex flex-col gap-4">
        <Card className="p-6">
          <SectorTitle label="Analyse sectorielle" />
          <p className="m-0 mt-3 border-l-2 border-wb-accent pl-3 text-[13px] text-slate-600">
            Le secteur de l’entreprise n’a pas pu être rapproché d’une branche {sourceLabel} de manière fiable.
            Sélectionnez une branche ci-dessous pour lancer l’analyse sectorielle.
          </p>
          {analysis.sector?.rawActivity ? (
            <p className="m-0 mt-3 text-[12.5px] text-wb-muted">
              Activité détectée : <span className="font-semibold text-[#1C1B1B]">{analysis.sector.rawActivity}</span>
            </p>
          ) : null}
        </Card>
        {editors}
      </div>
    )
  }

  const fresh = analysis.dataFreshness?.status
  const badge =
    fresh === 'FRESH' ? 'Données à jour' : fresh === 'UNAVAILABLE' ? 'Indisponible' : 'Données anciennes'
  const h = analysis.headline || {}
  const companyMissing = (analysis.companyAnnual || []).every((p) => !p.vaUsable)
  const lastAnnual = (analysis.sectorAnnualCurrent || []).at(-1)
  const lastQuarter = (analysis.sectorQuarterly || []).at(-1)
  const latestLabel =
    analysis.dataFreshness?.latestObservationPeriod ||
    h.latestQuarterlyPeriod ||
    (lastQuarter ? formatSectorPeriod(lastQuarter.year, lastQuarter.quarter) : null) ||
    h.latestYear ||
    lastAnnual?.year ||
    '—'
  const companyVaYears = (analysis.companyAnnual || []).filter((p) => p.vaUsable).map((p) => p.year)
  const sectorYears = (analysis.sectorAnnualCurrent || []).map((p) => p.year)
  const commonYears = companyVaYears.filter((year) => sectorYears.includes(year))
  const lastSectorYear = sectorYears.length ? Math.max(...sectorYears) : null
  const comparisonBlocker =
    companyVaYears.length === 0
      ? 'La valeur ajoutée de l’entreprise n’a pas pu être lue dans la liasse : comparaison impossible.'
      : commonYears.length < 2
        ? `Les données du secteur s’arrêtent en ${lastSectorYear ?? '—'} : il faut au moins deux années communes avec la liasse (${companyVaYears.join(', ')}) pour comparer l’évolution.`
        : (analysis.normalizedComparison || []).length === 0
          ? 'Comparaison indisponible pour ce dossier.'
          : null

  // Tableau de croissance : 5 dernières années par défaut, historique complet sur demande.
  const HISTORY_YEARS = 5
  const growthRows = analysis.growthComparison || []
  const visibleGrowthRows = fullHistory ? growthRows : growthRows.slice(-HISTORY_YEARS)
  const hiddenYears = growthRows.length - visibleGrowthRows.length

  const hasReal = (analysis.sectorAnnualReal || []).length > 0
  const hasQuarterly = (analysis.sectorQuarterly || []).length > 0
  const hasInsights = (analysis.insights || []).length > 0

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
              <Layers size={17} strokeWidth={1.8} />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[16px] font-semibold text-[#1C1B1B]">Secteur {analysis.sector?.label || '—'}</span>
                <span
                  className={`rounded-[8px] px-2 py-0.5 text-[11px] font-semibold ${
                    fresh === 'FRESH' ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FFF8EC] text-[#B45309]'
                  }`}
                >
                  {badge}
                </span>
                {!analysis.sector?.validated && analysis.sector?.mappingStatus === 'MATCHED' ? (
                  <span className="rounded-[8px] bg-[#FFF8EC] px-2 py-0.5 text-[11px] font-semibold text-[#B45309]">
                    Correspondance secteur à valider
                  </span>
                ) : null}
              </div>
              <div className="mt-1 text-[12.5px] text-wb-muted">
                Source {sourceLabel} · Comptes nationaux · Dernière donnée {latestLabel}
              </div>
            </div>
          </div>
          {dossierId ? (
            <div className="flex flex-wrap gap-2">
              {refreshButton}
              <button
                type="button"
                onClick={() => setSettingsOpen((v) => !v)}
                aria-expanded={settingsOpen}
                className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full px-4 py-2 text-[12.5px] font-semibold transition-colors ${
                  settingsOpen
                    ? 'border border-wb-ink bg-wb-ink text-white'
                    : 'border border-wb-line bg-white text-slate-700 hover:border-wb-accent hover:text-wb-accent-text'
                }`}
              >
                <Settings2 size={13} />
                Modifier le secteur
              </button>
            </div>
          ) : null}
        </div>
        {notice && !settingsOpen ? <p className="m-0 mt-3 text-[12px] text-wb-muted">{notice}</p> : null}

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-wb-line pt-5 lg:grid-cols-4">
          <KeyFigure
            label="VA sectorielle"
            value={formatSectorAmount(h.latestSectorVa, h.latestUnit)}
            sub={h.latestYear != null ? `Comptes annuels ${h.latestYear}` : undefined}
          />
          <KeyFigure label="Variation nominale N/N-1" value={formatSignedPct(h.nominalGrowthYoy)} sub={h.latestYear ? String(h.latestYear) : undefined} />
          <KeyFigure
            label="Croissance réelle"
            value={formatSignedPct(h.realGrowthYoy)}
            sub={h.latestQuarterlyPeriod && h.latestYear && String(h.latestQuarterlyPeriod).slice(0, 4) > String(h.latestYear) ? h.latestQuarterlyPeriod : h.latestYear ? String(h.latestYear) : undefined}
          />
          <KeyFigure label="Tendance 3 ans" value={h.cagr3y == null ? '—' : `${formatSignedPct(h.cagr3y)}`} sub={h.cagr3y == null ? undefined : 'Croissance annuelle moyenne'} />
        </div>
      </Card>

      {settingsOpen && editors}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card className="p-6">
          <SectionTitle
            title="Valeur ajoutée sectorielle"
            sub={`${analysis.sector?.label || ''} · millions de MAD · prix courants${lastAnnual ? ` · jusqu’à ${lastAnnual.year}` : ''}`}
          />
          <SectorValueAddedTrendChart series={analysis.sectorAnnualCurrent || []} sectorLabel={analysis.sector?.label} />
        </Card>

        <Card className="p-6">
          <SectionTitle title="Entreprise vs secteur — évolution relative" sub="Indice base 100 · valeur ajoutée nominale" />
          {comparisonBlocker ? (
            <EmptyHint text={comparisonBlocker} />
          ) : (
            <CompanyVsSectorNormalizedChart series={analysis.normalizedComparison} />
          )}
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="px-6 pt-5">
          <SectionTitle title="Croissance de la valeur ajoutée" sub="Entreprise et secteur, année par année" />
          <VaGrowthBarsChart rows={analysis.growthComparison || []} />
          {companyMissing && (
            <p className="m-0 mt-2 text-[12.5px] text-wb-muted">
              Valeur ajoutée de l’entreprise non lue dans la liasse : seule la croissance du secteur est affichée.
            </p>
          )}
        </div>
        <div className="wb-scroll mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-[13px]">
            <thead className="bg-[#F8FAFC]">
              <tr className="text-left text-[11px] font-bold uppercase tracking-[0.04em] text-wb-muted">
                <th className="border-y border-wb-line px-6 py-3">Année</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">VA entreprise</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Croissance entreprise</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">VA secteur</th>
                <th className="border-y border-wb-line px-3 py-3 text-right">Croissance secteur</th>
                <th className="border-y border-wb-line px-6 py-3 text-right">Écart</th>
              </tr>
            </thead>
            <tbody>
              {visibleGrowthRows.map((row) => {
                const company = (analysis.companyAnnual || []).find((c) => c.year === row.year)
                const sector = (analysis.sectorAnnualCurrent || []).find((c) => c.year === row.year)
                return (
                  <tr key={row.year} className="border-b border-wb-line transition-colors last:border-b-0 hover:bg-wb-accent-soft/40">
                    <td className="px-6 py-3 font-semibold text-[#1C1B1B]">{row.year}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{company?.vaUsable ? formatSectorAmount(company.va, 'MAD') : '—'}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{formatSignedPct(row.companyGrowth)}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-wb-muted">{formatSectorAmount(sector?.value ?? null, sector?.unit)}</td>
                    <td className="px-3 py-3 text-right tabular-nums text-wb-muted">{formatSignedPct(row.sectorGrowth)}</td>
                    <td className="px-6 py-3 text-right">
                      {row.gapPp == null ? (
                        <span className="text-wb-faint">—</span>
                      ) : (
                        <span
                          className={`rounded-[8px] px-2 py-0.5 text-[11.5px] font-semibold tabular-nums ${
                            row.gapPp >= 0 ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FEF2F2] text-[#B91C1C]'
                          }`}
                        >
                          {`${row.gapPp > 0 ? '+' : ''}${row.gapPp.toFixed(1).replace('.', ',')} pts`}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {growthRows.length > HISTORY_YEARS && (
          <div className="flex justify-center border-t border-wb-line px-6 py-3">
            <button
              type="button"
              onClick={() => setFullHistory((v) => !v)}
              className="cursor-pointer rounded-full border border-wb-line bg-white px-4 py-2 text-[12.5px] font-semibold text-slate-700 transition-colors hover:border-wb-accent hover:text-wb-accent-text"
            >
              {fullHistory
                ? `Afficher les ${HISTORY_YEARS} dernières années`
                : `Voir tout l’historique (${hiddenYears} année(s) de plus)`}
            </button>
          </div>
        )}
      </Card>

      {(hasReal || hasQuarterly) && (
        <div className={`grid grid-cols-1 gap-4 ${hasReal && hasQuarterly ? 'xl:grid-cols-2' : ''}`}>
          {hasReal && (
            <Card className="p-6">
              <SectionTitle title="Conjoncture sectorielle réelle" sub={analysis.realGrowthNote || undefined} />
              <SectorRealGrowthChart series={analysis.sectorAnnualReal} />
            </Card>
          )}
          {hasQuarterly && (
            <Card className="p-6">
              <SectionTitle
                title="Conjoncture — trimestres récents"
                sub={`${sourceLabel} · jusqu’à ${lastQuarter ? formatSectorPeriod(lastQuarter.year, lastQuarter.quarter) : '—'}`}
              />
              <SectorQuarterlyTrendChart series={analysis.sectorQuarterly} />
            </Card>
          )}
        </div>
      )}

      <div className={`grid grid-cols-1 items-start gap-4 ${hasInsights ? 'xl:grid-cols-2' : ''}`}>
        <Card className="p-6">
          <SectionTitle title="Entreprise vs secteur" />
          {(analysis.comparableIndicators || []).length === 0 && <EmptyHint text="Aucun indicateur comparable." />}
          {(analysis.comparableIndicators || []).map((ind) => (
            <div key={ind.code} className="flex items-center justify-between gap-4 border-t border-wb-line py-3 first:border-t-0">
              <span className="min-w-0 text-[13px] font-semibold text-[#1C1B1B]">{ind.label}</span>
              <span className="flex flex-none items-center gap-4 text-right text-[12.5px]">
                <span>
                  <span className="block text-[11px] text-wb-muted">Entreprise</span>
                  <span className="font-bold tabular-nums text-[#1C1B1B]">
                    {ind.companyValue == null ? 'Analyse requise' : formatSignedPct(ind.companyValue)}
                  </span>
                </span>
                <span>
                  <span className="block text-[11px] text-wb-muted">Secteur</span>
                  <span className="font-semibold tabular-nums text-slate-600">{formatSignedPct(ind.sectorValue)}</span>
                </span>
              </span>
            </div>
          ))}
        </Card>

        {hasInsights && (
          <Card className="p-6">
            <SectionTitle title="Lecture de l’analyse" />
            <ul className="m-0 list-none p-0">
              {(analysis.insights || []).map((item) => (
                <li key={item.code} className="flex items-start gap-3 border-t border-wb-line py-3 text-[13px] leading-relaxed text-slate-700 first:border-t-0">
                  <span className="mt-[7px] h-2 w-2 flex-none rounded-full bg-wb-accent" />
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  )
}

function SectorTitle({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
        <Layers size={17} strokeWidth={1.8} />
      </span>
      <span className="text-[16px] font-semibold text-[#1C1B1B]">{label}</span>
    </div>
  )
}

function SectionTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="mb-3">
      <div className="text-[16px] font-semibold text-[#1C1B1B]">{title}</div>
      {sub ? <div className="mt-0.5 text-[12px] text-wb-muted">{sub}</div> : null}
    </div>
  )
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="rounded-[14px] border border-dashed border-wb-line px-4 py-6 text-center text-[13px] text-wb-muted">
      {text}
    </div>
  )
}

function SectorSourceEditor({
  sources,
  selectedSourceId,
  currentSourceId,
  onChange,
  onApply,
  busy,
}: {
  sources: SectorSourceItem[]
  selectedSourceId: string
  currentSourceId: string
  onChange: (id: string) => void
  onApply: () => void
  busy: boolean
}) {
  const unchanged = Boolean(selectedSourceId) && selectedSourceId === currentSourceId
  const canApply = Boolean(selectedSourceId) && !unchanged && !busy

  return (
    <Card className="p-6">
      <div className="text-[16px] font-semibold text-[#1C1B1B]">Source des données</div>
      <p className="m-0 mt-1 text-[12.5px] text-wb-muted">
        Source utilisée pour ce dossier. En changer réinitialise le secteur choisi. La source par défaut se
        règle dans Configuration.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex min-w-0 flex-1 flex-col gap-1.5">
          <span className="text-[12px] font-medium text-wb-muted">Source</span>
          <select
            value={selectedSourceId}
            onChange={(e) => onChange(e.target.value)}
            disabled={busy || sources.length === 0}
            className="h-10 w-full rounded-full border border-wb-line bg-white px-4 text-[13px] text-slate-800 outline-none focus:border-wb-accent"
          >
            {sources.map((source) => (
              <option key={source.id} value={source.id} disabled={!source.selectable && source.id !== currentSourceId}>
                {source.shortLabel} — {source.label}
                {!source.implemented ? ' (bientôt)' : ''}
                {source.isDefault ? ' · défaut' : ''}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!canApply}
          onClick={onApply}
          className="h-10 shrink-0 cursor-pointer rounded-full border border-wb-line bg-white px-4 text-[12.5px] font-semibold text-slate-800 transition-colors hover:border-wb-accent hover:text-wb-accent-text disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? 'Changement…' : 'Appliquer la source'}
        </button>
      </div>
    </Card>
  )
}

function SectorMappingEditor({
  branches,
  selectedCode,
  currentCode,
  onChange,
  onApply,
  busy,
  notice,
  rawActivity,
  sourceLabel,
}: {
  branches: HcpBranch[]
  selectedCode: string
  currentCode: string
  onChange: (code: string) => void
  onApply: () => void
  busy: boolean
  notice: string | null
  rawActivity?: string | null
  sourceLabel: string
}) {
  const unchanged = Boolean(selectedCode) && selectedCode === currentCode
  const canApply = Boolean(selectedCode) && !unchanged && !busy

  return (
    <Card className="p-6">
      <div className="text-[16px] font-semibold text-[#1C1B1B]">Secteur de référence</div>
      <p className="m-0 mt-1 text-[12.5px] text-wb-muted">
        Branche {sourceLabel} à laquelle l’entreprise est comparée. L’analyse sectorielle est recalculée après
        enregistrement.
      </p>
      {rawActivity ? (
        <p className="m-0 mt-2 text-[11.5px] text-wb-faint">
          Activité d’origine : <span className="text-slate-700">{rawActivity}</span>
        </p>
      ) : null}
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <label className="flex min-w-0 flex-1 flex-col gap-1.5">
          <span className="text-[12px] font-medium text-wb-muted">
            Branche {sourceLabel}
          </span>
          <select
            value={selectedCode}
            onChange={(e) => onChange(e.target.value)}
            disabled={busy || branches.length === 0}
            className="h-10 w-full rounded-full border border-wb-line bg-white px-4 text-[13px] text-slate-800 outline-none focus:border-wb-accent"
          >
            <option value="">
              {branches.length ? 'Sélectionner un secteur…' : `Aucune branche pour ${sourceLabel}`}
            </option>
            {branches.map((branch) => (
              <option key={branch.code} value={branch.code}>
                {branch.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!canApply}
          onClick={onApply}
          className="h-10 shrink-0 cursor-pointer rounded-full border-0 bg-wb-accent px-4 text-[12.5px] font-bold text-white transition-[filter] hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? 'Enregistrement…' : 'Enregistrer le secteur'}
        </button>
      </div>
      {notice ? <p className="m-0 mt-2 text-[12px] text-wb-muted">{notice}</p> : null}
    </Card>
  )
}

function KeyFigure({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-[12px] text-wb-muted">{label}</div>
      <div className="mt-1 truncate text-[20px] font-bold tabular-nums tracking-[-0.01em] text-[#1C1B1B]">{value}</div>
      {sub ? <div className="mt-0.5 truncate text-[11.5px] text-wb-faint">{sub}</div> : null}
    </div>
  )
}

export { SectorAnalysisTab as BenchmarkTab }
