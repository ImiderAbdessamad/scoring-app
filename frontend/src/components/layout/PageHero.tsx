import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { HERO_BACKGROUND } from '@/components/layout/heroBackground'

type Props = {
  title: string
  subtitle?: ReactNode
  /** Grand mot en filigrane derrière le titre. */
  watermark?: string
  actions?: ReactNode
}

/** En-tête de page : carte flottante sur l'image de la charte, titre fin et mot en filigrane. */
export function PageHero({ title, subtitle, watermark, actions }: Props) {
  return (
    <header
      className="relative mx-3 mt-3 flex flex-none flex-wrap items-end justify-between gap-4 overflow-hidden rounded-[24px] px-7 py-6 text-white"
      style={HERO_BACKGROUND}
    >
      {watermark && (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-3 right-6 select-none whitespace-nowrap text-[96px] font-semibold leading-none tracking-[-0.04em] text-white/[0.07]"
        >
          {watermark}
        </span>
      )}

      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="relative min-w-0"
      >
        <h1 className="m-0 text-[30px] font-medium leading-tight tracking-[0.01em] text-white">{title}</h1>
        {subtitle && (
          <p className="m-0 mt-3 border-l-2 border-wb-accent pl-3 text-[13px] leading-snug text-white/85">
            {subtitle}
          </p>
        )}
      </motion.div>

      {actions && <div className="relative flex flex-wrap justify-end gap-2">{actions}</div>}
    </header>
  )
}
