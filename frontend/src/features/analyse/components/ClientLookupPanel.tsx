import type { ClientLookup } from '@/types/analyse'

const STATUS_STYLE: Record<
  ClientLookup['status'],
  { label: string; className: string }
> = {
  MATCHED: { label: 'Client trouvé', className: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  MULTIPLE: { label: 'Plusieurs correspondances', className: 'bg-amber-50 text-amber-900 ring-amber-200' },
  NOT_FOUND: { label: 'Aucun client', className: 'bg-slate-100 text-slate-700 ring-slate-200' },
  SKIPPED: { label: 'Non recherché', className: 'bg-slate-50 text-slate-500 ring-slate-200' },
  ERROR: { label: 'API indisponible', className: 'bg-rose-50 text-rose-800 ring-rose-200' },
}

type Props = {
  lookup?: ClientLookup | null
}

export function ClientLookupPanel({ lookup }: Props) {
  if (!lookup) return null

  const tone = STATUS_STYLE[lookup.status] || STATUS_STYLE.SKIPPED
  const primary = lookup.primary
  const queryBits = Object.entries(lookup.query || {}).map(([key, value]) => `${key}=${value}`)

  return (
    <section className="rounded-[16px] border border-slate-200/80 bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-[0.08em] text-wb-faint">
            Référentiel clients Wafabail
          </div>
          <h3 className="m-0 mt-1 text-[14px] font-extrabold text-slate-900">N° tiers après OCR</h3>
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ring-1 ${tone.className}`}>
          {tone.label}
        </span>
      </div>

      {lookup.message ? (
        <p className="m-0 mb-3 text-[12.5px] leading-relaxed text-wb-muted">{lookup.message}</p>
      ) : null}

      {primary ? (
        <dl className="mb-3 grid grid-cols-2 gap-x-3 gap-y-2 text-[12.5px]">
          <div>
            <dt className="text-wb-faint">N° tiers</dt>
            <dd className="m-0 font-bold text-slate-900">{primary.tiers || '—'}</dd>
          </div>
          <div>
            <dt className="text-wb-faint">Raison sociale</dt>
            <dd className="m-0 font-semibold text-slate-900">{primary.raison_sociale || '—'}</dd>
          </div>
          <div>
            <dt className="text-wb-faint">ICE</dt>
            <dd className="m-0 font-medium text-slate-800">{primary.ice || '—'}</dd>
          </div>
          <div>
            <dt className="text-wb-faint">RC</dt>
            <dd className="m-0 font-medium text-slate-800">{primary.rc || '—'}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-wb-faint">Identifiant fiscal</dt>
            <dd className="m-0 font-medium text-slate-800">{primary.identifiant_fiscal || '—'}</dd>
          </div>
        </dl>
      ) : null}

      {lookup.matches.length > 1 ? (
        <div className="mb-2 rounded-[12px] bg-slate-50 p-2.5">
          <div className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-wb-faint">
            Autres correspondances
          </div>
          <ul className="m-0 list-none space-y-1 p-0">
            {lookup.matches.slice(1, 4).map((item, index) => (
              <li key={`${item.tiers || item.ice || index}`} className="text-[12px] text-slate-700">
                <span className="font-bold">{item.tiers || '—'}</span>
                {' · '}
                {item.raison_sociale || 'Sans raison sociale'}
                {item.ice ? ` · ICE ${item.ice}` : ''}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {queryBits.length ? (
        <p className="m-0 text-[11px] text-wb-faint">
          Requête : {queryBits.join(' · ')}
        </p>
      ) : null}
    </section>
  )
}
