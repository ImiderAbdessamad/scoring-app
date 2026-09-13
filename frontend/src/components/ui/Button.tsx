import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'soft' | 'danger'

const variants: Record<Variant, string> = {
  primary:
    'bg-wb-accent text-white shadow-[0_1px_4px_rgba(232,93,12,0.28)] hover:brightness-105 hover:-translate-y-px active:scale-[0.98]',
  secondary:
    'bg-wb-surface text-slate-600 border border-[#E2E5EA] hover:bg-white hover:-translate-y-px active:scale-[0.98]',
  ghost: 'bg-transparent text-wb-muted hover:bg-black/[0.04] active:scale-[0.98]',
  soft: 'bg-wb-accent-soft text-wb-accent border border-wb-accent-border hover:bg-[#FFEBD7] hover:-translate-y-px active:scale-[0.98]',
  danger:
    'bg-[#DC2626] text-white shadow-[0_1px_4px_rgba(220,38,38,0.28)] hover:brightness-105 hover:-translate-y-px active:scale-[0.98]',
}

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  children: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'primary', className = '', children, type = 'button', ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-[9px] px-3.5 py-2 text-[12.5px] font-semibold transition-[filter,background,color,transform] duration-150 cursor-pointer disabled:opacity-50 disabled:pointer-events-none ${variants[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  )
})
