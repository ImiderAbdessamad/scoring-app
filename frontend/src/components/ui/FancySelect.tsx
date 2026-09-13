import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronDown, Search } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

export type SelectOption = {
  value: string
  label: string
  description?: string
}

type Props = {
  value: string
  options: SelectOption[]
  onChange: (value: string, meta?: { query: string }) => void
  placeholder?: string
  error?: boolean
  disabled?: boolean
  searchable?: boolean
  searchPlaceholder?: string
  emptyLabel?: string
}

type MenuPos = {
  top: number
  left: number
  width: number
  maxHeight: number
  openUp: boolean
}

export function FancySelect({
  value,
  options,
  onChange,
  placeholder = 'Sélectionner…',
  error = false,
  disabled = false,
  searchable = false,
  searchPlaceholder = 'Rechercher…',
  emptyLabel = 'Aucun résultat',
}: Props) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [pos, setPos] = useState<MenuPos | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const listId = useId()
  const selected = options.find((o) => o.value === value)

  const filtered = useMemo(() => {
    if (!searchable) return options
    const q = query.trim().toLowerCase()
    if (!q) return options
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        (o.description?.toLowerCase().includes(q) ?? false),
    )
  }, [options, query, searchable])

  function updatePosition() {
    const el = triggerRef.current
    if (!el) return
    const rect = el.getBoundingClientRect()
    const gap = 6
    const spaceBelow = window.innerHeight - rect.bottom - gap - 12
    const spaceAbove = rect.top - gap - 12
    const openUp = spaceBelow < 220 && spaceAbove > spaceBelow
    const available = openUp ? spaceAbove : spaceBelow
    const maxHeight = Math.min(360, Math.max(160, available))
    setPos({
      top: openUp ? rect.top - gap : rect.bottom + gap,
      left: rect.left,
      width: rect.width,
      maxHeight,
      openUp,
    })
  }

  useLayoutEffect(() => {
    if (!open) return
    updatePosition()
    const onScroll = () => updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  useEffect(() => {
    if (!open) {
      setQuery('')
      return
    }
    const t = searchable
      ? window.setTimeout(() => searchRef.current?.focus(), 30)
      : undefined
    const onDoc = (e: MouseEvent) => {
      const target = e.target as Node
      if (rootRef.current?.contains(target)) return
      const menu = document.getElementById(listId)
      if (menu?.contains(target)) return
      setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    window.addEventListener('keydown', onKey)
    return () => {
      if (t) window.clearTimeout(t)
      document.removeEventListener('mousedown', onDoc)
      window.removeEventListener('keydown', onKey)
    }
  }, [open, listId, searchable])

  const menu =
    open &&
    pos &&
    createPortal(
      <AnimatePresence>
        <motion.div
          id={listId}
          role="listbox"
          initial={{ opacity: 0, y: pos.openUp ? 6 : -6, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: pos.openUp ? 4 : -4, scale: 0.98 }}
          transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
          style={{
            position: 'fixed',
            top: pos.openUp ? undefined : pos.top,
            bottom: pos.openUp ? window.innerHeight - pos.top : undefined,
            left: pos.left,
            width: pos.width,
            maxHeight: pos.maxHeight,
            zIndex: 200,
          }}
          className="flex flex-col overflow-hidden rounded-[14px] border border-wb-line bg-white shadow-[0_16px_48px_rgba(16,24,40,0.18)]"
        >
          {searchable && (
            <div className="flex flex-none items-center gap-2 border-b border-wb-line px-3 py-2.5">
              <Search size={14} className="text-wb-faint" />
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={searchPlaceholder}
                className="w-full border-0 bg-transparent text-[13px] text-slate-900 outline-none placeholder:text-wb-faint"
              />
            </div>
          )}
          <ul
            className="m-0 min-h-0 flex-1 list-none overflow-y-auto p-1.5"
            style={{ maxHeight: pos.maxHeight - (searchable ? 48 : 0) }}
          >
            {filtered.length === 0 && (
              <li className="px-3 py-4 text-center text-[12.5px] text-wb-faint">
                {emptyLabel}
              </li>
            )}
            {filtered.map((opt) => {
              const active = opt.value === value
              return (
                <li key={opt.value} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(opt.value, { query })
                      setOpen(false)
                    }}
                    className={[
                      'flex w-full cursor-pointer items-center gap-2.5 rounded-[10px] border-0 px-3 py-2.5 text-left transition-colors',
                      active
                        ? 'bg-wb-accent-soft text-wb-accent'
                        : 'bg-transparent text-slate-800 hover:bg-wb-surface',
                    ].join(' ')}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] font-semibold">{opt.label}</span>
                      {opt.description && (
                        <span
                          className={[
                            'mt-0.5 block text-[11px]',
                            active ? 'text-wb-accent/80' : 'text-wb-faint',
                          ].join(' ')}
                        >
                          {opt.description}
                        </span>
                      )}
                    </span>
                    {active && <Check size={15} strokeWidth={2.4} className="flex-none" />}
                  </button>
                </li>
              )
            })}
          </ul>
        </motion.div>
      </AnimatePresence>,
      document.body,
    )

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
        className={[
          'flex h-11 w-full cursor-pointer items-center gap-2 rounded-[12px] border bg-white px-3.5 text-left transition-all',
          open
            ? 'border-wb-accent ring-2 ring-wb-accent/15'
            : error
              ? 'border-red-300'
              : 'border-[#E2E5EA] hover:border-wb-accent-border',
          disabled ? 'cursor-not-allowed opacity-60' : '',
        ].join(' ')}
      >
        <span className="min-w-0 flex-1">
          {selected ? (
            <span className="block truncate text-[13px] font-semibold text-slate-900">
              {selected.label}
            </span>
          ) : (
            <span className="block truncate text-[13px] text-wb-faint">{placeholder}</span>
          )}
        </span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.18 }}
          className="flex h-7 w-7 flex-none items-center justify-center rounded-lg bg-wb-surface text-wb-muted"
        >
          <ChevronDown size={15} strokeWidth={2.2} />
        </motion.span>
      </button>
      {menu}
    </div>
  )
}
