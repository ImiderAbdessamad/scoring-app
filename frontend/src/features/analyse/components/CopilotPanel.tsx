import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Bot, Send, Sparkles, X } from 'lucide-react'
import type { CopilotBlock, CopilotQa } from '@/types/analyse'

type Message = { role: 'ai' | 'user'; text: string }

type Props = {
  copilot: CopilotBlock
  messages: Message[]
  input: string
  thinking: boolean
  onChangeInput: (value: string) => void
  onSend: (text?: string, intent?: keyof Omit<CopilotQa, 'fallback'>) => void
  onClose: () => void
}

export function CopilotPanel({ copilot, messages, input, thinking, onChangeInput, onSend, onClose }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, thinking])

  return (
    <motion.aside
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 24 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="flex w-[380px] flex-none flex-col border-l border-wb-line bg-white"
    >
      <div className="flex flex-none items-center justify-between gap-2 border-b border-wb-line px-4 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-wb-ink text-wb-accent">
            <Bot size={15} strokeWidth={1.9} />
          </span>
          <div>
            <div className="text-[13px] font-bold text-slate-900">Copilote IA</div>
            <div className="text-[10.5px] text-wb-faint">Qwen 3.5 · questions sur ce dossier</div>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fermer le copilote"
          className="flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg border-0 bg-transparent text-wb-faint hover:bg-wb-surface hover:text-slate-700"
        >
          <X size={15} />
        </button>
      </div>

      <div ref={scrollRef} className="wb-scroll flex-1 overflow-y-auto px-4 py-4">
        <div className="flex flex-col gap-3">
          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={[
                  'max-w-[86%] rounded-[12px] px-3 py-2 text-[12.5px] leading-relaxed',
                  m.role === 'user'
                    ? 'bg-wb-accent text-white'
                    : 'whitespace-pre-wrap bg-wb-surface text-slate-700',
                ].join(' ')}
              >
                {m.text}
              </div>
            </motion.div>
          ))}

          {thinking && (
            <div className="flex justify-start">
              <div className="flex items-center gap-1.5 rounded-[12px] bg-wb-surface px-3 py-2.5">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-wb-faint"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex-none border-t border-wb-line px-4 py-3">
        <div className="mb-2.5 flex flex-wrap gap-1.5">
          {copilot.chips.map((chip) => (
            <button
              key={chip.label}
              type="button"
              onClick={() => onSend(chip.label, chip.intent)}
              disabled={thinking}
              className="inline-flex cursor-pointer items-center gap-1 rounded-full border border-wb-accent-border bg-wb-accent-soft px-2.5 py-1 text-[11px] font-semibold text-wb-accent transition-colors hover:bg-[#FFEBD7] disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Sparkles size={10} />
              {chip.label}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            onSend()
          }}
          className="flex items-center gap-2 rounded-[10px] border border-[#E2E5EA] bg-wb-surface px-3 py-2 focus-within:border-wb-accent focus-within:bg-white focus-within:ring-2 focus-within:ring-wb-accent/15"
        >
          <input
            value={input}
            onChange={(e) => onChangeInput(e.target.value)}
            placeholder="Posez une question sur ce dossier…"
            className="w-full border-0 bg-transparent text-[12.5px] text-slate-900 outline-none placeholder:text-wb-faint"
          />
          <button
            type="submit"
            disabled={!input.trim() || thinking}
            aria-label="Envoyer"
            className="flex h-7 w-7 flex-none cursor-pointer items-center justify-center rounded-[8px] border-0 bg-wb-accent text-white transition-[filter] hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send size={13} />
          </button>
        </form>
      </div>
    </motion.aside>
  )
}
