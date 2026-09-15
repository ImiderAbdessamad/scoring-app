import { useEffect, useState } from 'react'
import { Layers } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import {
  CompanyVsSectorNormalizedChart,
  SectorQuarterlyTrendChart,
  SectorRealGrowthChart,
  SectorValueAddedTrendChart,
  VaGrowthBarsChart,
} from '@/features/analyse/components/charts/SectorCharts'
import { formatSectorAmount, formatSectorPeriod, formatSignedPct } from '@/lib/sectorFormat'
import { fetchSectorAnalysis, refreshSectorData } from '@/services/sectors'
import type { SectorAnalysisData } from '@/types/analyse'

type Props = {
  data?: SectorAnalysisData | null
  dossierId?: string
}

export function SectorAnalysisTab({ data, dossierId }: Props) {
  const [busy, setBusy] = useState(false)
  const [local, setLocal] = useState(data)
  const analysis = local ?? data

  useEffect(() => {
    setLocal(data)
  }, [data])

  useEffect(() => {
    if (!dossierId) return
    let cancelled = false
    fetchSectorAnalysis(dossierId, 'auto')
      .then((next) => {
        if (!cancelled) setLocal(next)
      })
      .catch(() => {
        /* le workspace reste la source de repli */
      })
    return () => {
      cancelled = true
    }
  }, [dossierId])

  const [notice, setNotice] = useState<string | null>(null)

  async function refresh() {
    if (!dossierId) return
    setBusy(true)
    setNotice('Vérification des données HCP...')
    try {
      const result = await refreshSectorData(true)
      const next = await fetchSectorAnalysis(dossierId, 'force')
      setLocal(next)
      if (result.changed > 0) setNotice('Nouvelles données HCP importées.')
      else setNotice('Données déjà à jour.')
    } catch {
      setNotice('Vérification impossible — cache local conservé.')
    } finally {
      setBusy(false)
    }
  }

  if (!analysis || analysis.status === 'UNAVAILABLE' || analysis.status === 'NO_DATA' || analysis.status === 'ERROR') {
    return (
      <Card className="p-5">
        <div className="text-[13px] font-bold text-slate-900">Analyse sectorielle</div>
        <p className="m-0 mt-2 text-[13px] text-wb-muted">
          {analysis?.warnings?.[0] || 'Les données sectorielles publiques ne sont pas disponibles actuellement.'}
        </p>
        {dossierId ? (
          <button type="button" onClick={refresh} className="mt-3 rounded-[8px] border border-wb-line px-3 py-1.5 text-[12px] font-semibold">
            {busy ? 'Vérification des données HCP...' : 'Actualiser'}
          </button>
        ) : null}
      </Card>
    )
  }

  if (analysis.status === 'MAPPING_REVIEW_REQUIRED' || analysis.status === 'UNMAPPED') {
    return (
      <Card className="p-5">
        <div className="text-[13px] font-bold text-slate-900">Analyse sectorielle</div>
        <p className="m-0 mt-2 text-[13px] text-wb-muted">
          Le secteur de l’entreprise n’a pas pu être rapproché d’une branche HCP de manière fiable.
        </p>
        <p className="m-0 mt-1 text-[12px] text-wb-faint">Classification sectorielle à confirmer.</p>
      </Card>
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

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-wb-accent-soft text-wb-accent">
              <Layers size={16} strokeWidth={1.8} />
            </span>
            <div>
              <div className="text-[13px] font-bold text-slate-900">Analyse sectorielle</div>
              <div className="mt-1 text-[12.5px] text-slate-700">Secteur {analysis.sector?.label || '—'}</div>
              {!analysis.sector?.validated && analysis.sector?.mappingStatus === 'MATCHED' ? (
                <div className="mt-1 inline-flex rounded-full bg-[#FFF8EC] px-2 py-0.5 text-[10.5px] font-bold text-[#B45309]">
                  Correspondance secteur à valider
                </div>
              ) : null}
              <div className="mt-0.5 text-[11.5px] text-wb-faint">
                Source HCP — Comptes nationaux Base 2014 · Dernière donnée {latestLabel}
                {analysis.dataFreshness?.lastSyncAt
                  ? ` · Mise à jour locale ${new Date(analysis.dataFreshness.lastSyncAt).toLocaleString('fr-FR')}`
                  : ''}
              </div>
            </div>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-[11.5px] font-bold ${
              fresh === 'FRESH' ? 'bg-[#ECFDF5] text-[#15803D]' : 'bg-[#FFF8EC] text-[#B45309]'
            }`}
          >
            {badge}
          </span>
        </div>
        <p className="m-0 mt-3 border-t border-[#F1F2F4] pt-3 text-[12.5px] text-wb-muted">
          {analysis.scoring?.note || 'Non intégrée au score — politique sectorielle non calibrée.'}
        </p>
        {(analysis.warnings || []).length > 0 ? (
          <ul className="m-0 mt-2 list-none space-y-1 p-0 text-[12px] text-wb-muted">
            {analysis.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        ) : null}
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi
          label="VA sectorielle"
          value={formatSectorAmount(h.latestSectorVa, h.latestUnit)}
          sub={h.latestYear != null ? `Comptes annuels ${h.latestYear}` : '—'}
        />
        <Kpi label="Variation nominale N/N-1" value={formatSignedPct(h.nominalGrowthYoy)} sub={h.latestYear ? String(h.latestYear) : undefined} />
        <Kpi
          label="Croissance réelle"
          value={formatSignedPct(h.realGrowthYoy)}
          sub={h.latestQuarterlyPeriod && h.latestYear && String(h.latestQuarterlyPeriod).slice(0, 4) > String(h.latestYear) ? h.latestQuarterlyPeriod : h.latestYear ? String(h.latestYear) : undefined}
        />
        <Kpi label="Tendance 3 ans" value={h.cagr3y == null ? '—' : `${formatSignedPct(h.cagr3y)} CAGR`} />
      </div>

      <Card className="p-5">
        <div className="text-[13px] font-bold text-slate-900">Valeur ajoutée sectorielle — évolution</div>
        <div className="mb-3 text-[11.5px] text-wb-faint">
          {analysis.sector?.label} · Millions de MAD · prix courants
          {lastAnnual ? ` · jusqu’à ${lastAnnual.year}` : ''}
        </div>
        <SectorValueAddedTrendChart series={analysis.sectorAnnualCurrent || []} sectorLabel={analysis.sector?.label} />
      </Card>

      <Card className="p-5">
        <div className="text-[13px] font-bold text-slate-900">Evolution relative — entreprise vs secteur</div>
        <div className="mb-3 text-[11.5px] text-wb-faint">Indice base 100 · Valeur ajoutée nominale</div>
        {companyMissing || (analysis.normalizedComparison || []).length === 0 ? (
          <p className="m-0 text-[13px] text-wb-muted">Analyse de la liasse requise</p>
        ) : (
          <CompanyVsSectorNormalizedChart series={analysis.normalizedComparison} />
        )}
      </Card>

      <Card className="p-5">
        <div className="text-[13px] font-bold text-slate-900">Croissance de la valeur ajoutée</div>
        <VaGrowthBarsChart rows={analysis.growthComparison || []} />
        {companyMissing && <p className="m-0 mt-2 text-[12px] text-wb-muted">Analyse de la liasse requise</p>}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-left text-[12px]">
            <thead>
              <tr className="text-[10.5px] uppercase tracking-wide text-wb-faint">
                <th className="pb-2 font-semibold">Année</th>
                <th className="pb-2 font-semibold">VA entreprise</th>
                <th className="pb-2 font-semibold">Croissance entreprise</th>
                <th className="pb-2 font-semibold">VA secteur</th>
                <th className="pb-2 font-semibold">Croissance secteur</th>
                <th className="pb-2 font-semibold">Écart</th>
              </tr>
            </thead>
            <tbody>
              {(analysis.growthComparison || []).map((row) => {
                const company = (analysis.companyAnnual || []).find((c) => c.year === row.year)
                const sector = (analysis.sectorAnnualCurrent || []).find((c) => c.year === row.year)
                return (
                  <tr key={row.year} className="border-t border-[#F1F2F4]">
                    <td className="py-2 font-semibold">{row.year}</td>
                    <td>{company?.vaUsable ? formatSectorAmount(company.va, 'MAD') : '—'}</td>
                    <td>{formatSignedPct(row.companyGrowth)}</td>
                    <td>{formatSectorAmount(sector?.value ?? null, sector?.unit)}</td>
                    <td>{formatSignedPct(row.sectorGrowth)}</td>
                    <td>{row.gapPp == null ? '—' : `${row.gapPp > 0 ? '+' : ''}${row.gapPp.toFixed(1).replace('.', ',')} pts`}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {(analysis.sectorAnnualReal || []).length > 0 && (
        <Card className="p-5">
          <div className="text-[13px] font-bold text-slate-900">Conjoncture sectorielle réelle</div>
          <p className="m-0 mb-3 text-[11.5px] text-wb-faint">{analysis.realGrowthNote}</p>
          <SectorRealGrowthChart series={analysis.sectorAnnualReal} />
        </Card>
      )}

      {(analysis.sectorQuarterly || []).length > 0 && (
        <Card className="p-5">
          <div className="text-[13px] font-bold text-slate-900">Conjoncture sectorielle — trimestres récents</div>
          <div className="mb-2 text-[11.5px] text-wb-faint">
            HCP — CVS Base 2014 · jusqu’à {lastQuarter ? formatSectorPeriod(lastQuarter.year, lastQuarter.quarter) : '—'}
          </div>
          <SectorQuarterlyTrendChart series={analysis.sectorQuarterly} />
        </Card>
      )}

      <Card className="p-5">
        <div className="mb-3 text-[13px] font-bold text-slate-900">Entreprise vs secteur</div>
        {(analysis.comparableIndicators || []).map((ind) => (
          <div key={ind.code} className="flex flex-wrap justify-between gap-2 border-t border-[#F1F2F4] py-2 text-[12.5px]">
            <span className="font-semibold text-slate-800">{ind.label}</span>
            <span>Entreprise {ind.companyValue == null ? 'Analyse requise' : formatSignedPct(ind.companyValue)}</span>
            <span>Secteur {formatSignedPct(ind.sectorValue)}</span>
            <span className="text-wb-faint">{ind.source}</span>
          </div>
        ))}
      </Card>

      {(analysis.insights || []).length > 0 && (
        <Card className="p-5">
          <div className="mb-2 text-[13px] font-bold text-slate-900">Lecture déterministe</div>
          <ul className="m-0 list-none space-y-2 p-0">
            {(analysis.insights || []).map((item) => (
              <li key={item.code} className="text-[12.5px] text-wb-muted">
                {item.text}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card className="p-5">
        <div className="text-[13px] font-bold text-slate-900">Qualité et provenance des données</div>
        <ul className="mt-2 list-none space-y-1 p-0 text-[12.5px] text-wb-muted">
          <li>Source : HCP</li>
          <li>Dataset : Valeurs ajoutées à prix courants</li>
          <li>Base : 2014</li>
          <li>Fréquence : annuelle + trimestrielle CVS</li>
          <li>Dernière période : {latestLabel}</li>
          <li>
            Dernier compte annuel : {h.latestYear ?? '—'}
            {h.latestQuarterlyPeriod ? ` · Dernier trimestre : ${h.latestQuarterlyPeriod}` : ''}
          </li>
          <li>Dernière synchronisation : {analysis.dataFreshness?.lastSyncAt || '—'}</li>
          <li>
            Version : {(analysis.dataFreshness?.datasetVersions?.[0]?.sha256 || '').slice(0, 12) || '—'}
          </li>
          <li>État : {badge}</li>
        </ul>
        <button
          type="button"
          disabled={busy}
          onClick={refresh}
          className="mt-3 rounded-[8px] border border-wb-line px-3 py-1.5 text-[12px] font-semibold text-slate-700"
        >
          {busy ? 'Vérification des données HCP...' : 'Actualiser les données'}
        </button>
        {notice ? <p className="m-0 mt-2 text-[12px] text-wb-muted">{notice}</p> : null}
      </Card>
    </div>
  )
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-4">
      <div className="text-[10.5px] uppercase tracking-[0.03em] text-wb-faint">{label}</div>
      <div className="mt-1.5 text-[18px] font-extrabold tabular-nums text-slate-900">{value}</div>
      {sub ? <div className="mt-1 text-[11px] text-wb-faint">{sub}</div> : null}
    </Card>
  )
}

export { SectorAnalysisTab as BenchmarkTab }
