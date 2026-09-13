import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

type Props = {
  children: ReactNode
  className?: string
  dark?: boolean
  delay?: number
}

export function Card({ children, className = '', dark = false, delay = 0 }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      className={`rounded-[14px] border ${
        dark
          ? 'border-transparent bg-wb-ink text-white'
          : 'border-wb-line bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]'
      } ${className}`}
    >
      {children}
    </motion.div>
  )
}
