import { NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bell,
  ChevronsLeft,
  ChevronsRight,
  FolderOpen,
  LayoutGrid,
  LineChart,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import icon from '@/assets/icon.png'
import { fetchDashboard } from '@/services/api/dashboard'
import type { AlertItem } from '@/types/dossier'

type NavItem = {
  to: string
  label: string
  icon: typeof LayoutGrid
  match?: (path: string) => boolean
}

const NAV: NavItem[] = [
  {
    to: '/',
    label: 'Tableau de bord',
    icon: LayoutGrid,
    match: (p) => p === '/',
  },
  {
    to: '/dossiers',
    label: 'Dossiers',
    icon: FolderOpen,
    match: (p) => p.startsWith('/dossiers'),
  },
  {
    to: '/analyse',
    label: "Poste d'analyse",
    icon: LineChart,
    match: (p) => p.startsWith('/analyse'),
  },
]

type Props = {
  open: boolean
  onToggle: () => void
}

export function Sidebar({ open, onToggle }: Props) {
  const location = useLocation()
  const [hovered, setHovered] = useState<string | null>(null)
  const [alertsOpen, setAlertsOpen] = useState(false)
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchDashboard()
      .then((d) => {
        if (cancelled) return
        setAlerts(d.alerts || [])
        setUnreadCount(d.unreadAlertCount ?? (d.alerts || []).filter((a) => !a.read).length)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <motion.aside
      initial={false}
      animate={{ width: open ? 240 : 64 }}
      transition={{ type: 'spring', stiffness: 320, damping: 32 }}
      className="relative z-40 flex h-full flex-none flex-col overflow-hidden bg-wb-ink py-3.5"
    >
      <div
        className={
          open
            ? 'flex items-center gap-3 px-3.5'
            : 'flex flex-col items-center gap-2'
        }
      >
        <button
          type="button"
          onClick={onToggle}
          className="relative flex-none cursor-pointer border-0 bg-transparent p-0"
          aria-label={open ? 'Réduire le menu' : 'Ouvrir le menu'}
          title={open ? 'Réduire le menu' : 'Ouvrir le menu'}
        >
          <img
            src={icon}
            alt="Wafabail"
            className="block h-10 w-10 rounded-[11px] object-cover shadow-[0_4px_12px_rgba(232,93,12,0.35)]"
          />
          <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-wb-ink bg-wb-accent" />
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.18 }}
              className="min-w-0 flex-1"
            >
              <div className="truncate text-[13px] font-extrabold tracking-tight text-white">
                Wafabail
              </div>
              <div className="truncate text-[10.5px] font-medium text-wb-rail">
                Smart Dashboard
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <button
          type="button"
          onClick={onToggle}
          aria-label={open ? 'Réduire le menu' : 'Ouvrir le menu'}
          title={open ? 'Réduire' : 'Ouvrir'}
          className="flex h-8 w-8 flex-none cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-wb-rail transition-colors hover:bg-wb-ink-soft hover:text-white"
        >
          {open ? <ChevronsLeft size={16} /> : <ChevronsRight size={16} />}
        </button>
      </div>

      <div
        className={
          open ? 'mx-3.5 my-2.5 h-px bg-wb-ink-muted' : 'mx-auto my-2.5 h-px w-6 bg-wb-ink-muted'
        }
      />

      <nav
        className={
          open
            ? 'flex flex-1 flex-col gap-1.5 px-2.5'
            : 'flex flex-1 flex-col items-center gap-1.5'
        }
      >
        {NAV.map((item, i) => {
          const active = item.match?.(location.pathname) ?? false
          const Icon = item.icon
          const showTip = !open && hovered === item.to

          return (
            <div
              key={item.to}
              className="relative w-full"
              onMouseEnter={() => setHovered(item.to)}
              onMouseLeave={() => setHovered(null)}
            >
              <NavLink
                to={item.to}
                aria-label={item.label}
                className={[
                  'relative flex h-[42px] items-center rounded-[11px] outline-none no-underline transition-colors',
                  open ? 'gap-3 px-3' : 'mx-auto w-[42px] justify-center',
                  active ? '' : 'hover:bg-wb-ink-soft',
                ].join(' ')}
              >
                {active && (
                  <motion.span
                    layoutId="rail-active"
                    className="absolute inset-0 rounded-[11px] bg-wb-ink-soft"
                    transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                  />
                )}
                <motion.span
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 * i }}
                  className="relative z-10 flex items-center gap-3"
                >
                  <Icon
                    size={18}
                    strokeWidth={1.8}
                    className={active ? 'text-white' : 'text-wb-rail'}
                  />
                  <AnimatePresence>
                    {open && (
                      <motion.span
                        initial={{ opacity: 0, x: -6 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -6 }}
                        className={[
                          'whitespace-nowrap text-[13px] font-semibold',
                          active ? 'text-white' : 'text-wb-rail',
                        ].join(' ')}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </motion.span>
              </NavLink>

              <AnimatePresence>
                {showTip && (
                  <motion.div
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -6 }}
                    transition={{ duration: 0.15 }}
                    className="pointer-events-none absolute left-[52px] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-lg bg-wb-ink-soft px-2.5 py-1.5 text-[12px] font-semibold text-white shadow-lg ring-1 ring-white/10"
                  >
                    {item.label}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )
        })}

        <div
          className="relative w-full"
          onMouseEnter={() => setHovered('alerts')}
          onMouseLeave={() => setHovered(null)}
        >
          <button
            type="button"
            aria-label="Alertes"
            onClick={() => {
              setAlertsOpen((v) => !v)
            }}
            className={[
              'relative flex h-[42px] cursor-pointer items-center rounded-[11px] border-0 transition-colors',
              open ? 'w-full gap-3 px-3' : 'mx-auto w-[42px] justify-center',
              alertsOpen
                ? 'bg-wb-ink-soft text-white'
                : 'bg-transparent text-wb-rail hover:bg-wb-ink-soft hover:text-white',
            ].join(' ')}
          >
            <span className="relative">
              <Bell size={18} strokeWidth={1.8} />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 rounded-full border-[1.5px] border-wb-ink bg-wb-accent" />
              )}
            </span>
            <AnimatePresence>
              {open && (
                <motion.span
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -6 }}
                  className="text-[13px] font-semibold"
                >
                  Alertes
                </motion.span>
              )}
            </AnimatePresence>
          </button>
          <AnimatePresence>
            {!open && hovered === 'alerts' && !alertsOpen && (
              <motion.div
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -6 }}
                className="pointer-events-none absolute left-[52px] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-lg bg-wb-ink-soft px-2.5 py-1.5 text-[12px] font-semibold text-white shadow-lg ring-1 ring-white/10"
              >
                Alertes
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="mt-auto" />
      </nav>

      <AnimatePresence>
        {alertsOpen && (
          <RailPanel
            onClose={() => setAlertsOpen(false)}
            title="Alertes"
            offsetLeft={open ? 248 : 72}
          >
            <div className="px-4 py-3 text-[12.5px] text-wb-muted">
              {unreadCount > 0
                ? `${unreadCount} alerte(s) non lue(s)`
                : 'Aucune alerte non lue.'}
              <ul className="mt-2 flex flex-col gap-1.5">
                {alerts.slice(0, 6).map((a) => (
                  <li key={a.id} className="text-[12px] text-slate-700">
                    {a.message}
                  </li>
                ))}
              </ul>
            </div>
          </RailPanel>
        )}
      </AnimatePresence>
    </motion.aside>
  )
}

function RailPanel({
  title,
  children,
  onClose,
  offsetLeft,
}: {
  title: string
  children: ReactNode
  onClose: () => void
  offsetLeft: number
}) {
  return (
    <>
      <motion.button
        type="button"
        aria-label="Fermer"
        className="fixed inset-0 z-40 cursor-default border-0 bg-black/20"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, x: -12, scale: 0.98 }}
        animate={{ opacity: 1, x: 0, scale: 1 }}
        exit={{ opacity: 0, x: -12, scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 380, damping: 28 }}
        style={{ left: offsetLeft }}
        className="absolute bottom-4 z-50 w-[280px] overflow-hidden rounded-2xl border border-wb-line bg-white shadow-[0_16px_48px_rgba(16,24,40,0.18)]"
      >
        <div className="flex items-center justify-between border-b border-wb-line px-4 py-3">
          <span className="text-[13px] font-bold text-slate-900">{title}</span>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer border-0 bg-transparent text-[12px] font-semibold text-wb-faint hover:text-slate-700"
          >
            Fermer
          </button>
        </div>
        {children}
      </motion.div>
    </>
  )
}
