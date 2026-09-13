import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2, RefreshCw, TriangleAlert, Zap } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { scoreTone } from '@/lib/format'
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
  in: { color: '#7d756c', icon: Zap },
  ok: { color: '#4ADE80', icon: Check },
  warn: { color: '#FBBF24', icon: TriangleAlert },
  res: { color: '#E85D0C', icon: Check },
}

export function AgentPipeline({ pipeline, state, onRun, runningLabel, idleLabel }: Props) {
  const tone = scoreTone(state.scoreShown)
  const totalSteps = pipeline.steps.length

  return (
    <Card dark className="mx-6 mt-4 overflow-hidden p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-wb-accent/15 text-wb-accent">
            <Zap size={15} strokeWidth={2.2} />
          </span>
          <div>
            <div className="text-[13px] font-bold text-white">Pipeline d’analyse IA</div>
            <div className="text-[11px] text-[#8b8378]">{pipeline.policyVersion}</div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div
              className="font-mono text-[20px] font-extrabold leading-none tabular-nums"
              style={{ color: tone.color }}
            >
              {state.scoreShown}
            </div>
            <div className="text-[10px] uppercase tracking-[0.04em] text-[#6f675e]">Score IA</div>
          </div>
          <button
            type="button"
            onClick={onRun}
            disabled={state.running}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-[9px] border border-white/10 bg-white/5 px-3 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
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
                        : 'bg-white/10 text-[#8b8378]',
                  ].join(' ')}
                >
                  {done ? <Check size={12} strokeWidth={3} /> : active ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    i + 1
                  )}
                </div>
                <span className="hidden text-center text-[9.5px] leading-tight text-[#8b8378] sm:block">
                  {step.label}
                </span>
                <div className="pointer-events-none absolute -top-1 left-1/2 z-20 hidden -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg bg-[#0c0906] px-2 py-1 text-[10.5px] font-semibold text-white shadow-lg ring-1 ring-white/10 group-hover:block">
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

      <div className="wb-scroll mt-3.5 max-h-[132px] overflow-y-auto rounded-[10px] bg-black/25 p-3 font-mono text-[11.5px] leading-relaxed">
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
          <div className="text-[#6f675e]">En attente de lancement du pipeline…</div>
        )}
      </div>
    </Card>
  )
}
