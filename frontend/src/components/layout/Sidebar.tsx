import { NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bell,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  FolderOpen,
  LayoutGrid,
  LineChart,
  LogOut,
  Settings2,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import emblem from '@/assets/icon.png'
import logo from '@/assets/wafabail-logo-blanc.svg'
import heroBackground from '@/assets/hero-fond.webp'
import { currentUser, logout } from '@/lib/auth'
import { fetchDashboard } from '@/services/api/dashboard'
import type { AlertItem } from '@/types/dossier'

type NavItem = {
  to: string
  label: string
  icon: typeof LayoutGrid
  match: (path: string) => boolean
}

const NAV: NavItem[] = [
  { to: '/', label: 'Tableau de bord', icon: LayoutGrid, match: (p) => p === '/' },
  { to: '/dossiers', label: 'Dossiers', icon: FolderOpen, match: (p) => p.startsWith('/dossiers') },
  { to: '/analyse', label: "Poste d'analyse", icon: LineChart, match: (p) => p.startsWith('/analyse') },
  { to: '/configuration', label: 'Configuration', icon: Settings2, match: (p) => p.startsWith('/configuration') },
]

/* Carte flottante de la charte Wafabail : image de fond,
   voile sombre translucide, étiquette claire pour la page active et mini-bouton rond orange. */
const CARD_BACKGROUND = {
  backgroundImage: [
    'linear-gradient(180deg, rgba(13,13,13,0.94) 0%, rgba(13,13,13,0.86) 45%, rgba(30,25,22,0.62) 100%)',
    `url(${heroBackground})`,
  ].join(', '),
  backgroundSize: 'cover',
  backgroundPosition: 'center 85%',
}

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
  const user = currentUser()

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
      animate={{ width: open ? 252 : 76 }}
      transition={{ type: 'spring', stiffness: 320, damping: 32 }}
      style={CARD_BACKGROUND}
      className="relative z-40 m-3 mr-0 flex flex-none flex-col rounded-[24px] py-4 text-white shadow-[0_18px_40px_rgba(13,13,13,0.28)]"
    >
      {/* Marque + repli */}
      <div className={open ? 'flex items-center justify-between gap-2 px-4' : 'flex flex-col items-center gap-3'}>
        {open ? (
          <img src={logo} alt="Wafabail" width={107} height={39} className="block h-[38px] w-auto" />
        ) : (
          <img src={emblem} alt="Wafabail" className="block h-10 w-10 rounded-[12px] object-cover" />
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-label={open ? 'Réduire le menu' : 'Ouvrir le menu'}
          title={open ? 'Réduire' : 'Ouvrir'}
          className="flex h-8 w-8 flex-none cursor-pointer items-center justify-center rounded-full border border-white/15 bg-white/5 text-white/70 transition-colors hover:bg-white/15 hover:text-white"
        >
          {open ? <ChevronsLeft size={15} /> : <ChevronsRight size={15} />}
        </button>
      </div>

      <nav className={open ? 'mt-6 flex flex-1 flex-col gap-1.5 px-3' : 'mt-5 flex flex-1 flex-col items-center gap-1.5'}>
        {NAV.map((item) => (
          <NavItemLink
            key={item.to}
            item={item}
            open={open}
            active={item.match(location.pathname)}
            showTip={!open && hovered === item.to}
            onHover={setHovered}
          />
        ))}

        <div className="relative w-full" onMouseEnter={() => setHovered('alerts')} onMouseLeave={() => setHovered(null)}>
          <button
            type="button"
            aria-label="Alertes"
            aria-expanded={alertsOpen}
            onClick={() => setAlertsOpen((v) => !v)}
            className={[
              'relative flex h-11 cursor-pointer items-center rounded-[12px] border-0 transition-colors',
              open ? 'w-full gap-3 px-3' : 'mx-auto w-11 justify-center',
              alertsOpen ? 'bg-white/12 text-white' : 'bg-transparent text-white/75 hover:bg-white/8 hover:text-white',
            ].join(' ')}
          >
            <span className="relative">
              <Bell size={18} strokeWidth={1.8} />
              {unreadCount > 0 && (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full border-[1.5px] border-wb-ink bg-wb-accent" />
              )}
            </span>
            {open && <span className="text-[14px] font-medium">Alertes</span>}
            {open && unreadCount > 0 && (
              <span className="ml-auto rounded-full bg-wb-accent px-2 py-0.5 text-[11px] font-bold text-white">{unreadCount}</span>
            )}
          </button>
          <Tip show={!open && hovered === 'alerts' && !alertsOpen}>Alertes</Tip>
        </div>
      </nav>

      {/* Carte utilisateur en verre */}
      <div className={open ? 'mx-3 mt-3' : 'mt-3 flex justify-center'}>
        {open ? (
          <div className="flex items-center gap-3 rounded-[16px] bg-[rgba(30,25,22,0.6)] p-3 ring-1 ring-white/10 backdrop-blur-[2px]">
            <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-wb-accent text-[12px] font-bold text-white">
              {user.initials}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-semibold">{user.name}</span>
              <span className="block text-[11px] text-white/55">Analyste scoring</span>
            </span>
            <button
              type="button"
              onClick={() => void logout()}
              aria-label={`Se déconnecter (${user.name})`}
              title="Se déconnecter"
              className="flex h-8 w-8 flex-none cursor-pointer items-center justify-center rounded-full border-0 bg-white/10 text-white/80 transition-colors hover:bg-wb-danger hover:text-white"
            >
              <LogOut size={15} strokeWidth={1.9} />
            </button>
          </div>
        ) : (
          <div className="relative" onMouseEnter={() => setHovered('logout')} onMouseLeave={() => setHovered(null)}>
            <button
              type="button"
              onClick={() => void logout()}
              aria-label={`Se déconnecter (${user.name})`}
              className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border-0 bg-wb-accent text-[12px] font-bold text-white transition-colors hover:bg-wb-danger"
            >
              {user.initials}
            </button>
            <Tip show={hovered === 'logout'}>{user.name} · Se déconnecter</Tip>
          </div>
        )}
      </div>

      <AnimatePresence>
        {alertsOpen && (
          <AlertsPanel
            onClose={() => setAlertsOpen(false)}
            offsetLeft={open ? 264 : 88}
            unreadCount={unreadCount}
            alerts={alerts}
          />
        )}
      </AnimatePresence>
    </motion.aside>
  )
}

/** Lien de navigation : étiquette claire + mini-bouton rond orange quand la page est active. */
function NavItemLink({
  item,
  open,
  active,
  showTip,
  onHover,
}: {
  item: NavItem
  open: boolean
  active: boolean
  showTip: boolean
  onHover: (key: string | null) => void
}) {
  const Icon = item.icon
  return (
    <div className="relative w-full" onMouseEnter={() => onHover(item.to)} onMouseLeave={() => onHover(null)}>
      <NavLink
        to={item.to}
        aria-label={item.label}
        aria-current={active ? 'page' : undefined}
        className={[
          'relative flex h-11 items-center rounded-[12px] no-underline outline-none transition-colors',
          open ? 'gap-3 pl-3 pr-1.5' : 'mx-auto w-11 justify-center',
          active ? 'text-[#171717]' : 'text-white/75 hover:bg-white/8 hover:text-white',
        ].join(' ')}
      >
        {active && (
          <motion.span
            layoutId="sidebar-active"
            className="absolute inset-0 rounded-[12px] bg-[rgba(250,250,250,0.95)]"
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
          />
        )}
        <Icon size={18} strokeWidth={1.8} className="relative z-10 flex-none" />
        {open && (
          <span className={`relative z-10 flex-1 whitespace-nowrap text-[14px] ${active ? 'font-semibold' : 'font-medium'}`}>
            {item.label}
          </span>
        )}
        {open && active && (
          <span className="relative z-10 flex h-7 w-7 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
            <ChevronRight size={15} strokeWidth={2.4} />
          </span>
        )}
        {!open && active && (
          <span className="absolute -right-1 top-1/2 z-10 h-2.5 w-2.5 -translate-y-1/2 rounded-full border-2 border-wb-ink bg-wb-accent" />
        )}
      </NavLink>
      <Tip show={showTip}>{item.label}</Tip>
    </div>
  )
}

function Tip({ show, children }: { show: boolean; children: ReactNode }) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -6 }}
          transition={{ duration: 0.15 }}
          className="pointer-events-none absolute left-[60px] top-1/2 z-50 -translate-y-1/2 whitespace-nowrap rounded-lg bg-[rgba(250,250,250,0.95)] px-2.5 py-1.5 text-[12px] font-semibold text-[#171717] shadow-lg"
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function AlertsPanel({
  onClose,
  offsetLeft,
  unreadCount,
  alerts,
}: {
  onClose: () => void
  offsetLeft: number
  unreadCount: number
  alerts: AlertItem[]
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
        className="fixed bottom-6 z-50 w-[280px] overflow-hidden rounded-2xl border border-wb-line bg-white text-slate-900 shadow-[0_16px_48px_rgba(16,24,40,0.18)]"
      >
        <div className="flex items-center justify-between border-b border-wb-line px-4 py-3">
          <span className="text-[13px] font-bold">Alertes</span>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer border-0 bg-transparent text-[12px] font-semibold text-wb-faint hover:text-slate-700"
          >
            Fermer
          </button>
        </div>
        <div className="px-4 py-3 text-[12.5px] text-wb-muted">
          {unreadCount > 0 ? `${unreadCount} alerte(s) non lue(s)` : 'Aucune alerte non lue.'}
          <ul className="m-0 mt-2 flex list-none flex-col gap-1.5 p-0">
            {alerts.slice(0, 6).map((a) => (
              <li key={a.id} className="text-[12px] text-slate-700">
                {a.message}
              </li>
            ))}
          </ul>
        </div>
      </motion.div>
    </>
  )
}
