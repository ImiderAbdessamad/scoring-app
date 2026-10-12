import type { CSSProperties, ReactNode } from 'react'
import { motion } from 'framer-motion'
import heroBackground from '@/assets/hero-fond.webp'

type Props = {
  children: ReactNode
  className?: string
  dark?: boolean
  delay?: number
}

/* Carte sombre : image de la charte sous un voile, comme le menu latéral. */
const DARK_CARD_STYLE: CSSProperties = {
  backgroundImage: [
    'linear-gradient(160deg, rgba(13,13,13,0.94) 0%, rgba(13,13,13,0.84) 55%, rgba(30,25,22,0.62) 100%)',
    `url(${heroBackground})`,
  ].join(', '),
  backgroundSize: 'cover',
  backgroundPosition: 'center 80%',
}

export function Card({ children, className = '', dark = false, delay = 0 }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      style={dark ? DARK_CARD_STYLE : undefined}
      className={`rounded-[20px] border ${
        dark
          ? 'border-transparent text-white shadow-[0_14px_32px_rgba(13,13,13,0.22)]'
          : 'border-black/[0.12] bg-white shadow-[0_1px_2px_rgba(0,0,0,0.05)]'
      } ${className}`}
    >
      {children}
    </motion.div>
  )
}
