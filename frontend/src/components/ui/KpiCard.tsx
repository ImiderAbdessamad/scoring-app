import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { Card } from '@/components/ui/Card'

type Props = {
  label: string
  value: string | number
  hint: string
  icon: ReactNode
  iconBg: string
  iconColor: string
  dark?: boolean
  delay?: number
  valueColor?: string
  hintColor?: string
  borderClass?: string
  className?: string
}

export function KpiCard({
  label,
  value,
  hint,
  icon,
  iconBg,
  iconColor,
  dark = false,
  delay = 0,
  valueColor,
  hintColor,
  borderClass,
  className = '',
}: Props) {
  return (
    <Card
      dark={dark}
      delay={delay}
      className={`p-4 ${borderClass ?? ''} ${dark ? '' : 'hover:-translate-y-0.5 transition-transform duration-200'} ${className}`}
    >
      <div className="mb-3 flex items-center justify-between">
        <span
          className={`text-[10.5px] font-bold uppercase tracking-[0.04em] ${
            dark ? 'text-[#6f675e]' : 'text-wb-faint'
          }`}
          style={!dark && label.includes('À') ? { color: '#B45309' } : undefined}
        >
          {label}
        </span>
        <div
          className="flex h-8 w-8 items-center justify-center rounded-[9px]"
          style={{ background: iconBg, color: iconColor }}
        >
          {icon}
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: delay + 0.12, duration: 0.4 }}
        className={`font-extrabold tracking-tight tabular-nums leading-none ${
          dark ? 'text-[26px] text-white' : 'text-[34px]'
        }`}
        style={{ color: valueColor ?? (dark ? undefined : '#111827'), letterSpacing: dark ? '-1px' : '-1.5px' }}
      >
        {value}
      </motion.div>
      <div
        className={`mt-1.5 text-[11.5px] ${dark ? 'text-[#6f675e]' : 'text-wb-faint'}`}
        style={hintColor ? { color: hintColor, fontWeight: 600 } : undefined}
      >
        {hint}
      </div>
    </Card>
  )
}
