import { useId, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, ChevronDown, Loader2, RefreshCw, TriangleAlert, Zap } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { PipelineData, PipelineTraceLine } from '@/types/analyse'

type PipelineState = {
  running: boolean
  step: number
  trace: PipelineTraceLine[]
  scoreShown: number
}

type Props = {
  pipeline: PipelineData
  state: PipelineState
  onRun: () => void
  runningLabel?: string
  idleLabel?: string
}

const TRACE_STYLE: Record<PipelineTraceLine['type'], { color: string; icon: typeof Check }> = {
  in: { color: '#a3a3a3', icon: Zap },
  ok: { color: '#4ADE80', icon: Check },
  warn: { color: '#FBBF24', icon: TriangleAlert },
  res: { color: '#FF9B26', icon: Check },
}

export function AgentPipeline({ pipeline, state, onRun, runningLabel, idleLabel }: Props) {
  const totalSteps = pipeline.steps.length
  // Accordéon fermé par défaut : seuls le titre et le bouton de lancement restent visibles.
  const [open, setOpen] = useState(false)
  const bodyId = useId()

  return (
    <Card dark className="mx-6 mt-4 overflow-hidden p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={bodyId}
          className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 border-0 bg-transparent p-0 text-left text-white"
        >
          <span className="flex h-9 w-9 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
            <Zap size={15} strokeWidth={2.2} />
          </span>
          <span className="min-w-0">
            <span className="block text-[15px] font-semibold text-white">Pipeline d’analyse IA</span>
          </span>
          <ChevronDown
            size={17}
            strokeWidth={2}
            className={`ml-1 flex-none text-white/70 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
          />
        </button>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onRun}
            disabled={state.running}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-white/30 bg-white/10 px-4 py-2 text-[12px] font-semibold text-white backdrop-blur-[2px] transition-colors hover:bg-white/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {state.running ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <RefreshCw size={13} />
            )}
            {state.running ? (runningLabel ?? 'Analyse en cours') : (idleLabel ?? 'Relancer')}
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={bodyId}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
      <div className="mt-4 flex items-center gap-1 overflow-x-auto pb-1">
        {pipeline.steps.map((step, i) => {
          const done = i < state.step
          const active = i === state.step && state.running
          return (
            <div key={step.label} className="flex flex-1 items-center gap-1">
              <div className="group relative flex flex-1 flex-col items-center gap-1.5">
                <div
                  className={[
                    'flex h-6 w-6 flex-none items-center justify-center rounded-full text-[10px] font-bold transition-colors',
                    done
                      ? 'bg-wb-accent text-white'
                      : active
                        ? 'bg-white/15 text-white ring-2 ring-wb-accent'
                        : 'bg-white/10 text-white/55',
                  ].join(' ')}
                >
                  {done ? <Check size={12} strokeWidth={3} /> : active ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    i + 1
                  )}
                </div>
                <span className="hidden text-center text-[10px] leading-tight text-white/60 sm:block">
                  {step.label}
                </span>
                <div className="pointer-events-none absolute -top-1 left-1/2 z-20 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-[#0D0D0D] px-2 py-1 text-[10.5px] font-semibold text-white shadow-lg ring-1 ring-white/10 group-hover:block">
                  {step.label} · {step.meta}
                </div>
              </div>
              {i < totalSteps - 1 && (
                <div
                  className={[
                    'h-px flex-none w-3 sm:w-5',
                    done ? 'bg-wb-accent' : 'bg-white/10',
                  ].join(' ')}
                />
              )}
            </div>
          )
        })}
      </div>

      <div className="wb-scroll mt-4 max-h-[132px] overflow-y-auto rounded-[14px] bg-[rgba(30,25,22,0.6)] p-3 ring-1 ring-white/10 font-mono text-[11.5px] leading-relaxed">
        <AnimatePresence initial={false}>
          {state.trace.map((line, i) => {
            const style = TRACE_STYLE[line.type]
            const Icon = style.icon
            return (
              <motion.div
                key={`${line.step}-${i}-${line.text}`}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-start gap-2 py-0.5"
              >
                <Icon size={12} className="mt-0.5 flex-none" style={{ color: style.color }} />
                <span style={{ color: style.color }}>{line.text}</span>
              </motion.div>
            )
          })}
        </AnimatePresence>
        {state.trace.length === 0 && (
          <div className="text-white/50">En attente de lancement du pipeline…</div>
        )}
      </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  )
}
