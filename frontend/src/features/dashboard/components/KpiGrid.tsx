import { FolderOpen, Check, X, Clock3, Wallet, TriangleAlert } from 'lucide-react'
import { KpiCard } from '@/components/ui/KpiCard'
import type { DashboardKpis } from '@/types/dossier'

export function KpiGrid({ kpis }: { kpis: DashboardKpis }) {
  return (
    <div className="mb-5 grid grid-cols-2 gap-3.5 xl:grid-cols-6 md:grid-cols-3">
      <KpiCard
        delay={0.05}
        label="En cours"
        value={kpis.inProgress}
        hint={kpis.inProgressDelta}
        icon={<FolderOpen size={15} strokeWidth={1.9} />}
        iconBg="#EFF6FF"
        iconColor="#1D4ED8"
      />
      <KpiCard
        delay={0.1}
        label="À analyser"
        value={kpis.toAnalyze}
        hint={kpis.toAnalyzeHint}
        hintColor="#B45309"
        borderClass="border-[#F7D9B8]"
        valueColor="#E85D0C"
        icon={<Clock3 size={15} strokeWidth={1.9} />}
        iconBg="#FFF6EC"
        iconColor="#E85D0C"
      />
      <KpiCard
        delay={0.12}
        label="À revoir"
        value={kpis.reviewRequired ?? 0}
        hint="Quality gate"
        hintColor="#B45309"
        borderClass="border-[#F7D9B8]"
        valueColor="#B45309"
        icon={<TriangleAlert size={15} strokeWidth={1.9} />}
        iconBg="#FFF8EC"
        iconColor="#B45309"
      />
      <KpiCard
        delay={0.15}
        label={`Approuvés (${kpis.approvedMonth})`}
        value={kpis.approved}
        hint={kpis.approvedDelta}
        valueColor="#16A34A"
        icon={<Check size={15} strokeWidth={2.2} />}
        iconBg="#ECFDF5"
        iconColor="#16A34A"
      />
      <KpiCard
        delay={0.2}
        label={`Rejetés (${kpis.rejectedMonth})`}
        value={kpis.rejected}
        hint={kpis.rejectedDelta}
        valueColor="#DC2626"
        icon={<X size={15} strokeWidth={2.2} />}
        iconBg="#FEF2F2"
        iconColor="#DC2626"
      />
      <KpiCard
        delay={0.25}
        dark
        label="Valeur engagée"
        value={kpis.committedValue}
        hint={kpis.committedHint}
        icon={<Wallet size={15} strokeWidth={1.9} />}
        iconBg="#221d18"
        iconColor="#E85D0C"
        className=""
      />
    </div>
  )
}
