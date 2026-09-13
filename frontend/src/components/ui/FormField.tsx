import {
  useId,
  type ChangeEvent,
  type InputHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react'

type FieldProps = {
  label: string
  error?: string
  hint?: string
  children: ReactNode
  required?: boolean
}

export function Field({ label, error, hint, children, required }: FieldProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[12px] font-semibold text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-wb-accent">*</span>}
      </span>
      {children}
      {hint && !error && (
        <span className="text-[11px] text-wb-faint">{hint}</span>
      )}
      {error && (
        <span className="text-[11.5px] font-medium text-wb-danger">{error}</span>
      )}
    </div>
  )
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: boolean
}

export function sanitizeInteger(raw: string): string {
  return raw.replace(/\D/g, '')
}

export function sanitizeDecimal(raw: string): string {
  const normalized = raw.replace(/,/g, '.').replace(/[^\d.]/g, '')
  const firstDot = normalized.indexOf('.')
  if (firstDot === -1) return normalized
  return (
    normalized.slice(0, firstDot + 1) +
    normalized.slice(firstDot + 1).replace(/\./g, '')
  )
}

type NumericInputProps = Omit<InputProps, 'inputMode' | 'type'> & {
  decimal?: boolean
}

function isNumericKeyAllowed(e: KeyboardEvent<HTMLInputElement>, decimal: boolean) {
  if (e.ctrlKey || e.metaKey || e.altKey) return true
  const nav = [
    'Backspace',
    'Delete',
    'Tab',
    'Escape',
    'Enter',
    'ArrowLeft',
    'ArrowRight',
    'ArrowUp',
    'ArrowDown',
    'Home',
    'End',
  ]
  if (nav.includes(e.key)) return true
  if (/^\d$/.test(e.key)) return true
  if (decimal && (e.key === '.' || e.key === ',')) return true
  return false
}

export function NumericInput({
  decimal = false,
  error,
  className = '',
  onChange,
  onKeyDown,
  onPaste,
  ...rest
}: NumericInputProps) {
  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const cleaned = decimal
      ? sanitizeDecimal(e.target.value)
      : sanitizeInteger(e.target.value)
    if (cleaned === e.target.value) {
      onChange?.(e)
      return
    }
    const next = {
      ...e,
      target: { ...e.target, value: cleaned },
      currentTarget: { ...e.currentTarget, value: cleaned },
    } as ChangeEvent<HTMLInputElement>
    onChange?.(next)
  }

  return (
    <input
      type="text"
      inputMode={decimal ? 'decimal' : 'numeric'}
      pattern={decimal ? '[0-9]*[.,]?[0-9]*' : '[0-9]*'}
      className={[
        'h-10 w-full rounded-[10px] border bg-white px-3 text-[13px] text-slate-900 outline-none transition-shadow placeholder:text-wb-faint',
        error
          ? 'border-red-300 focus:ring-2 focus:ring-red-200'
          : 'border-[#E2E5EA] focus:border-wb-accent focus:ring-2 focus:ring-wb-accent/15',
        className,
      ].join(' ')}
      onKeyDown={(e) => {
        if (!isNumericKeyAllowed(e, decimal)) {
          e.preventDefault()
          return
        }
        onKeyDown?.(e)
      }}
      onPaste={(e) => {
        e.preventDefault()
        const text = e.clipboardData.getData('text')
        const cleaned = decimal ? sanitizeDecimal(text) : sanitizeInteger(text)
        const target = e.currentTarget
        const start = target.selectionStart ?? target.value.length
        const end = target.selectionEnd ?? target.value.length
        const merged = target.value.slice(0, start) + cleaned + target.value.slice(end)
        const value = decimal ? sanitizeDecimal(merged) : sanitizeInteger(merged)
        const next = {
          ...e,
          target: { ...target, value },
          currentTarget: { ...target, value },
        } as unknown as ChangeEvent<HTMLInputElement>
        onChange?.(next)
        onPaste?.(e)
      }}
      onChange={handleChange}
      {...rest}
    />
  )
}

export function TextInput({ error, className = '', ...rest }: InputProps) {
  return (
    <input
      className={[
        'h-10 w-full rounded-[10px] border bg-white px-3 text-[13px] text-slate-900 outline-none transition-shadow placeholder:text-wb-faint',
        error
          ? 'border-red-300 focus:ring-2 focus:ring-red-200'
          : 'border-[#E2E5EA] focus:border-wb-accent focus:ring-2 focus:ring-wb-accent/15',
        className,
      ].join(' ')}
      {...rest}
    />
  )
}

export function SelectInput({
  error,
  className = '',
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { error?: boolean }) {
  return (
    <select
      className={[
        'h-10 w-full cursor-pointer rounded-[10px] border bg-white px-3 text-[13px] text-slate-900 outline-none transition-shadow',
        error
          ? 'border-red-300 focus:ring-2 focus:ring-red-200'
          : 'border-[#E2E5EA] focus:border-wb-accent focus:ring-2 focus:ring-wb-accent/15',
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </select>
  )
}

type ChoiceProps = {
  label: string
  description?: string
  selected: boolean
  onSelect: () => void
  error?: boolean
}

export function ChoiceCard({ label, description, selected, onSelect, error }: ChoiceProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        'flex flex-1 cursor-pointer flex-col items-start rounded-[12px] border px-4 py-3.5 text-left transition-all',
        selected
          ? 'border-wb-accent bg-wb-accent-soft shadow-[0_0_0_1px_rgba(232,93,12,0.25)]'
          : error
            ? 'border-red-300 bg-white hover:border-red-400'
            : 'border-[#E2E5EA] bg-white hover:border-wb-accent-border hover:bg-[#FFFCFA]',
      ].join(' ')}
    >
      <span
        className={[
          'text-[13px] font-bold',
          selected ? 'text-wb-accent' : 'text-slate-800',
        ].join(' ')}
      >
        {label}
      </span>
      {description && (
        <span className="mt-0.5 text-[11.5px] text-wb-muted">{description}</span>
      )}
    </button>
  )
}

export function useFieldId(prefix: string) {
  return useId() + prefix
}
