import { useMemo, useState } from 'react'
import { formatSectorAmount, formatSectorPeriod, formatSignedPct } from '@/lib/sectorFormat'
import type { GrowthComparisonPoint, NormalizedSectorPoint, SectorSeriesPoint } from '@/types/analyse'

const ORANGE = '#e85d0c'
const INK = '#111827'
const MUTED = '#94a3b8'

function scale(values: Array<number | null | undefined>, height: number) {
  const nums = values.filter((v): v is number => v != null)
  const min = nums.length ? Math.min(...nums, 0) : 0
  const max = nums.length ? Math.max(...nums) : 1
  const span = max - min || 1
  return {
    y: (v: number) => height - ((v - min) / span) * (height - 8) - 4,
    min,
    max,
  }
}

export function SectorValueAddedTrendChart({
  series,
  sectorLabel,
}: {
  series: SectorSeriesPoint[]
  sectorLabel?: string | null
}) {
  const shown = series.slice(-12)
  const [active, setActive] = useState(Math.max(shown.length - 1, 0))
  const point = shown[active]
  const w = 640
  const h = 180
  const ys = scale(shown.map((s) => s.value), h)
  const pts = shown.map((s, i) => {
    const x = 24 + (i * (w - 48)) / Math.max(shown.length - 1, 1)
    const y = s.value == null ? h / 2 : ys.y(s.value)
    return { x, y, s, i }
  })
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ')
  const area = `${path} L${pts.at(-1)?.x ?? 0},${h} L${pts[0]?.x ?? 0},${h} Z`
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h + 28}`} className="h-[210px] w-full" role="img" aria-label="Valeur ajoutée sectorielle">
        <path d={area} fill={ORANGE} opacity="0.08" />
        <path d={path} fill="none" stroke={ORANGE} strokeWidth="2.2" />
        {pts.map((p) => (
          <g key={p.s.year}>
            <circle
              cx={p.x}
              cy={p.y}
              r={p.i === active ? 5 : 3.5}
              fill={ORANGE}
              className="cursor-pointer"
              onClick={() => setActive(p.i)}
            />
            <text x={p.x} y={h + 18} textAnchor="middle" fontSize="11" fill={MUTED}>
              {p.s.year}
            </text>
          </g>
        ))}
      </svg>
      {point && (
        <div className="mt-2 rounded-[10px] border border-wb-line bg-wb-surface px-3 py-2 text-[12.5px]">
          <span className="font-bold text-slate-800">Point sélectionné {point.year}</span>
          <span className="ml-2 text-wb-muted">
            {formatSectorAmount(point.value, point.unit)} · {formatSignedPct(point.growthYoy)} vs N-1
          </span>
        </div>
      )}
      <div className="mt-1 text-[11px] text-wb-faint">
        {sectorLabel} · {series[0]?.unit || 'Millions de MAD'} · prix courants
      </div>
    </div>
  )
}

export function CompanyVsSectorNormalizedChart({ series }: { series: NormalizedSectorPoint[] }) {
  const w = 640
  const h = 180
  const values = series.flatMap((s) => [s.companyIndex, s.sectorIndex])
  const ys = scale(values, h)
  const xs = series.map((_, i) => 24 + (i * (w - 48)) / Math.max(series.length - 1, 1))
  const line = (key: 'companyIndex' | 'sectorIndex') =>
    series
      .map((s, i) => {
        const v = s[key]
        if (v == null) return null
        return `${xs[i]},${ys.y(v)}`
      })
      .filter(Boolean)
      .join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h + 28}`} className="h-[210px] w-full" role="img">
      <polyline points={line('sectorIndex')} fill="none" stroke={ORANGE} strokeWidth="2.2" />
      <polyline points={line('companyIndex')} fill="none" stroke={INK} strokeWidth="2.2" />
      {series.map((s, i) => (
        <text key={s.year} x={xs[i]} y={h + 18} textAnchor="middle" fontSize="11" fill={MUTED}>
          {s.year}
        </text>
      ))}
    </svg>
  )
}

export function VaGrowthBarsChart({ rows }: { rows: GrowthComparisonPoint[] }) {
  const shown = rows.slice(-12)
  const max = Math.max(
    1,
    ...shown.flatMap((r) => [Math.abs(r.companyGrowth || 0), Math.abs(r.sectorGrowth || 0)]),
  )
  return (
    <div className="flex items-end gap-4" style={{ height: 180 }}>
      {shown.map((row) => (
        <div key={row.year} className="flex flex-1 flex-col items-center gap-1">
          <div className="flex h-[150px] w-full items-end justify-center gap-1">
            <Bar value={row.companyGrowth} max={max} color={INK} ghost={!row.companyAvailable} />
            <Bar value={row.sectorGrowth} max={max} color={ORANGE} ghost={row.sectorGrowth == null} />
          </div>
          <div className="text-[10.5px] text-wb-faint">{row.year}</div>
        </div>
      ))}
    </div>
  )
}

function Bar({
  value,
  max,
  color,
  ghost,
}: {
  value: number | null
  max: number
  color: string
  ghost?: boolean
}) {
  const h = value == null ? 8 : Math.max(8, (Math.abs(value) / max) * 140)
  return (
    <div
      className="w-[14px] rounded-t-[3px]"
      style={{
        height: h,
        background: ghost ? '#E5E7EB' : color,
        opacity: ghost ? 0.7 : 1,
      }}
      title={value == null ? 'Analyse de la liasse requise' : formatSignedPct(value)}
    />
  )
}

export function SectorRealGrowthChart({ series }: { series: SectorSeriesPoint[] }) {
  const shown = series.slice(-8)
  const max = Math.max(1, ...shown.map((s) => Math.abs(s.growthYoy || 0)))
  return (
    <div className="flex items-end gap-3" style={{ height: 160 }}>
      {shown.map((s) => {
        const positive = (s.growthYoy || 0) >= 0
        return (
          <div key={`${s.year}-${s.quarter}`} className="flex flex-1 flex-col items-center gap-1">
            <div className="flex h-[130px] w-full items-end justify-center">
              <div
                className="w-full max-w-[28px] rounded-t-[4px]"
                style={{
                  height: Math.max(6, ((Math.abs(s.growthYoy || 0) / max) * 120)),
                  background: s.growthYoy == null ? '#E5E7EB' : positive ? ORANGE : '#DC2626',
                }}
              />
            </div>
            <div className="text-[10px] text-wb-faint">{formatSectorPeriod(s.year, s.quarter, true)}</div>
            <div className="text-[10px] font-semibold text-slate-700">{formatSignedPct(s.growthYoy)}</div>
          </div>
        )
      })}
    </div>
  )
}

export function SectorQuarterlyTrendChart({ series }: { series: SectorSeriesPoint[] }) {
  const [mode, setMode] = useState<'value' | 'growth'>('value')
  const shown = useMemo(() => series.slice(-16), [series])
  const values = shown.map((s) => (mode === 'value' ? s.value : s.growthYoy))
  const w = 640
  const h = 160
  const ys = scale(values, h)
  const pts = shown.map((s, i) => {
    const x = 20 + (i * (w - 40)) / Math.max(shown.length - 1, 1)
    const v = values[i]
    return { x, y: v == null ? h / 2 : ys.y(v), s }
  })
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ')
  return (
    <div>
      <div className="mb-2 flex gap-2">
        {(['value', 'growth'] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded-full border px-3 py-1 text-[11px] font-semibold ${
              mode === m ? 'border-wb-accent bg-wb-accent-soft text-wb-accent' : 'border-wb-line text-wb-muted'
            }`}
          >
            {m === 'value' ? 'Valeur' : 'Croissance YoY'}
          </button>
        ))}
      </div>
      <svg viewBox={`0 0 ${w} ${h + 24}`} className="h-[190px] w-full">
        <path d={d} fill="none" stroke={ORANGE} strokeWidth="2" />
        {pts.map((p) => (
          <text key={`${p.s.year}${p.s.quarter}`} x={p.x} y={h + 16} textAnchor="middle" fontSize="9" fill={MUTED}>
            {formatSectorPeriod(p.s.year, p.s.quarter, true)}
          </text>
        ))}
      </svg>
    </div>
  )
}
