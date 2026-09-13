import { motion } from 'framer-motion'
import { Card } from '@/components/ui/Card'
import type { AnalystActivity, AlertItem, RiskBucket, SectorStat } from '@/types/dossier'

const RISK_COLOR: Record<RiskBucket['tone'], string> = {
  low: '#16A34A',
  mid: '#B45309',
  high: '#DC2626',
  critical: '#7F1D1D',
  unknown: '#64748B',
}

const ALERT_TONE = {
  danger: { color: '#DC2626', bg: '#FEF2F2' },
  warn: { color: '#B45309', bg: '#FFF8EC' },
  info: { color: '#7C3AED', bg: '#F5F3FF' },
  success: { color: '#15803D', bg: '#ECFDF5' },
} as const

type Props = {
  riskDist: RiskBucket[]
  riskActiveTotal: number
  sectors: SectorStat[]
  alerts: AlertItem[]
  activity: AnalystActivity
}

export function DashboardSidePanels({
  riskDist,
  riskActiveTotal,
  sectors,
  alerts,
  activity,
}: Props) {
  const unread = alerts.filter((a) => !a.read).length

  return (
    <div className="flex flex-col gap-3.5">
      <Card delay={0.32} className="p-4">
        <div className="mb-3.5 text-[13px] font-bold text-slate-900">
          Distribution des risques · {riskActiveTotal} actifs
        </div>
        <div className="flex flex-col gap-2.5">
          {riskDist.map((rd, i) => (
            <div key={rd.label} className="flex items-center gap-2.5">
              <div
                className="w-[50px] flex-none text-[12px] font-semibold"
                style={{ color: RISK_COLOR[rd.tone] }}
              >
                {rd.label}
              </div>
              <div className="h-2 flex-1 overflow-hidden rounded-md bg-[#EEF0F3]">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${rd.pct}%` }}
                  transition={{ delay: 0.4 + i * 0.08, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                  className="h-full rounded-md"
                  style={{ background: RISK_COLOR[rd.tone] }}
                />
              </div>
              <div className="w-[18px] flex-none text-right text-[13px] font-bold tabular-nums text-slate-700">
                {rd.count}
              </div>
              <div className="w-[34px] flex-none text-right text-[11px] text-wb-faint">
                {rd.pct}%
              </div>
            </div>
          ))}
        </div>
        {sectors.length > 0 && (
          <div className="mt-3.5 flex flex-wrap gap-3 border-t border-[#F1F2F4] pt-3">
            {sectors.map((sd) => (
              <div key={sd.label} className="min-w-[52px] text-center">
                <div className="text-[14px] font-bold tabular-nums text-slate-700">
                  {sd.count}
                </div>
                <div className="text-[10px] text-wb-faint">{sd.label}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card delay={0.38} className="overflow-hidden p-0">
        <div className="flex items-center justify-between px-4 pt-4">
          <div className="text-[13px] font-bold text-slate-900">Alertes récentes</div>
          <span className="rounded-full bg-wb-accent px-2 py-0.5 text-[10px] font-bold text-white">
            {unread || alerts.length}
          </span>
        </div>
        <ul className="m-0 list-none p-2">
          {alerts.length === 0 && (
            <li className="px-2.5 py-8 text-center text-[12.5px] text-wb-muted">
              Aucune alerte : les événements des dossiers s’afficheront ici.
            </li>
          )}
          {alerts.map((a, i) => {
            const tone = ALERT_TONE[a.tone]
            return (
              <motion.li
                key={a.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.42 + i * 0.05 }}
                className="flex items-start gap-2 rounded-xl px-2.5 py-2.5 hover:bg-wb-surface"
              >
                <div className="min-w-0 flex-1">
                  <div className="text-[12.5px] font-semibold leading-snug text-slate-800">
                    {a.message}
                  </div>
                  <div className="mt-1 text-[10.5px] text-wb-faint">{a.time}</div>
                </div>
                <span
                  className="rounded-md px-1.5 py-0.5 text-[10px] font-bold"
                  style={{ color: tone.color, background: tone.bg }}
                >
                  {a.type}
                </span>
              </motion.li>
            )
          })}
        </ul>
      </Card>

      <Card delay={0.44} dark className="p-4">
        <div className="mb-3 text-[12px] font-bold uppercase tracking-[0.04em] text-[#6f675e]">
          Mon activité
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          {[
            { v: activity.today, l: "Aujourd'hui" },
            { v: activity.week, l: 'Cette semaine' },
            { v: activity.approvalRate, l: 'Taux appro.', accent: true },
            { v: activity.avgDelay, l: 'Délai moyen' },
          ].map((cell) => (
            <div
              key={cell.l}
              className="rounded-[9px] bg-[#1d1813] p-2.5 text-center"
            >
              <div
                className={`text-[22px] font-extrabold tabular-nums ${
                  cell.accent ? 'text-wb-accent' : 'text-white'
                }`}
              >
                {cell.v}
              </div>
              <div className="mt-0.5 text-[10.5px] text-[#6f675e]">{cell.l}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
