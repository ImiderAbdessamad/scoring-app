import { useCallback, useEffect, useState } from 'react'
import { Database, RefreshCw, ShieldAlert } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { PageHero } from '@/components/layout/PageHero'
import {
  fetchSectorSources,
  refreshSectorData,
  setDefaultSectorSource,
  updateSectorSourceFlags,
  type SectorSourceItem,
  type SectorSourcesConfig,
} from '@/services/sectors'

export function SectorSourcesConfigPage() {
  const [config, setConfig] = useState<SectorSourcesConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [syncBusyId, setSyncBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchSectorSources()
      setConfig(next)
    } catch {
      setError('Impossible de charger la configuration des sources.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function makeDefault(source: SectorSourceItem) {
    setBusyId(source.id)
    setNotice(null)
    setError(null)
    try {
      const next = await setDefaultSectorSource(source.id)
      setConfig(next)
      setNotice(
        `Source par défaut : ${source.shortLabel}. Les dossiers déjà épinglés ne sont pas modifiés.`,
      )
    } catch {
      setError(`Impossible de définir « ${source.shortLabel} » comme défaut.`)
    } finally {
      setBusyId(null)
    }
  }

  async function toggleEnabled(source: SectorSourceItem, enabled: boolean) {
    setBusyId(source.id)
    setNotice(null)
    setError(null)
    try {
      const next = await updateSectorSourceFlags(source.id, {
        enabled,
        selectable: enabled ? source.selectable || source.supportsVaAnalysis : false,
      })
      setConfig(next)
      setNotice(
        enabled
          ? `« ${source.shortLabel} » activée.`
          : `« ${source.shortLabel} » désactivée.`,
      )
    } catch {
      setError(`Modification impossible pour « ${source.shortLabel} ».`)
    } finally {
      setBusyId(null)
    }
  }

  async function toggleSelectable(source: SectorSourceItem, selectable: boolean) {
    setBusyId(source.id)
    setNotice(null)
    setError(null)
    try {
      const next = await updateSectorSourceFlags(source.id, { selectable })
      setConfig(next)
      setNotice(
        selectable
          ? `« ${source.shortLabel} » sélectionnable dans l’analyse.`
          : `« ${source.shortLabel} » retirée du sélecteur d’analyse.`,
      )
    } catch {
      setError(
        `« ${source.shortLabel} » ne peut pas être sélectionnée (source non prête pour l’analyse VA).`,
      )
    } finally {
      setBusyId(null)
    }
  }

  async function syncSource(source: SectorSourceItem) {
    setSyncBusyId(source.id)
    setNotice(null)
    setError(null)
    try {
      const result = await refreshSectorData(true, source.id)
      setNotice(
        result.changed > 0
          ? `Sync ${source.shortLabel} terminée — ${result.updatedObservations} observations mises à jour.`
          : `Sync ${source.shortLabel} terminée — données déjà à jour.`,
      )
      await reload()
    } catch {
      setError(`Synchronisation ${source.shortLabel} impossible.`)
    } finally {
      setSyncBusyId(null)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHero
        title="Sources de données sectorielles"
        watermark="Configuration"
        subtitle="Choisissez la source utilisée pour l’analyse sectorielle. Par défaut : HCP. Les autres sources peuvent être préparées sans écraser les dossiers déjà analysés."
      />
      <div className="wb-scroll flex-1 overflow-y-auto px-6 py-6 pb-10">

      <Card className="mb-5 border-amber-200/80 bg-[#FFFBF5] p-5">
        <div className="flex items-start gap-2.5">
          <ShieldAlert size={16} className="mt-0.5 text-[#B45309]" />
          <div className="text-[12.5px] leading-relaxed text-amber-950">
            <div className="font-bold">Règles anti-conflit</div>
            <ul className="m-0 mt-1.5 list-disc space-y-1 pl-4">
              <li>
                Le <strong>défaut global</strong> s’applique aux nouveaux dossiers uniquement — jamais
                un écrasement silencieux des dossiers déjà épinglés.
              </li>
              <li>
                Changer de source sur un dossier <strong>efface le mapping branche</strong> (taxonomies
                isolées, ex. codes HCP_*).
              </li>
              <li>
                Les caches d’observations coexistent par source : HCP et Banque mondiale (codes WB_*)
                ne s’écrasent jamais.
              </li>
              <li>
                Une source non implémentée peut être listée, mais pas sélectionnée pour l’analyse VA.
              </li>
            </ul>
          </div>
        </div>
      </Card>

      {(error || notice) && (
        <div
          className={`mb-4 rounded-[14px] border px-4 py-3 text-[12.5px] ${
            error
              ? 'border-red-200 bg-red-50 text-red-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          {error || notice}
        </div>
      )}

      {loading && !config ? (
        <Card className="p-5 text-[13px] text-wb-muted">Chargement…</Card>
      ) : (
        <div className="flex flex-col gap-4">
          {(config?.items || []).map((source) => {
            const busy = busyId === source.id
            return (
              <Card
                key={source.id}
                className={`p-6 ${source.isDefault ? 'border-wb-accent shadow-[0_0_0_1px_#FF9B26]' : ''}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full bg-wb-accent text-white">
                      <Database size={18} strokeWidth={1.8} />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-[16px] font-semibold text-[#1C1B1B]">{source.label}</div>
                        {source.isDefault ? (
                          <span className="rounded-[8px] bg-[#ECFDF5] px-2 py-0.5 text-[11px] font-semibold text-[#15803D]">
                            Défaut
                          </span>
                        ) : null}
                        {!source.implemented ? (
                          <span className="rounded-[8px] bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                            Bientôt
                          </span>
                        ) : null}
                      </div>
                      <p className="m-0 mt-1.5 text-[13px] leading-relaxed text-wb-muted">{source.description}</p>
                      {source.notes ? (
                        <p className="m-0 mt-1 text-[11.5px] text-wb-faint">{source.notes}</p>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {source.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="rounded-[8px] bg-wb-surface px-2 py-1 text-[10.5px] font-semibold text-slate-600 ring-1 ring-wb-line"
                          >
                            {cap}
                          </span>
                        ))}
                      </div>
                      <div className="mt-2 text-[11.5px] text-wb-faint">
                        Sync : {source.syncStatus || '—'}
                        {source.lastSyncAt
                          ? ` · ${new Date(source.lastSyncAt).toLocaleString('fr-FR')}`
                          : ''}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col items-stretch gap-3 sm:min-w-[220px]">
                    <Switch
                      label="Activée"
                      checked={source.enabled}
                      disabled={busy || (source.isDefault && source.enabled)}
                      onChange={(checked) => void toggleEnabled(source, checked)}
                    />
                    <Switch
                      label="Sélectionnable (analyse)"
                      checked={source.selectable}
                      disabled={busy || !source.enabled || !source.supportsVaAnalysis}
                      onChange={(checked) => void toggleSelectable(source, checked)}
                    />
                    <button
                      type="button"
                      disabled={busy || source.isDefault || !source.supportsVaAnalysis || !source.enabled}
                      onClick={() => void makeDefault(source)}
                      className="cursor-pointer rounded-full border border-wb-line bg-white px-4 py-2 text-[12.5px] font-semibold text-slate-700 transition-colors hover:border-wb-accent hover:text-wb-accent-text disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {source.isDefault ? 'Source par défaut' : 'Définir comme défaut'}
                    </button>
                    {source.implemented && source.capabilities.includes('OPEN_DATA_SYNC') ? (
                      <button
                        type="button"
                        disabled={syncBusyId !== null}
                        onClick={() => void syncSource(source)}
                        className="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-full border-0 bg-wb-accent px-4 py-2 text-[12.5px] font-bold text-white transition-[filter] hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <RefreshCw size={13} className={syncBusyId === source.id ? 'animate-spin' : ''} />
                        {syncBusyId === source.id ? 'Synchronisation…' : `Synchroniser ${source.shortLabel}`}
                      </button>
                    ) : null}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {config?.updatedAt ? (
        <p className="m-0 mt-4 text-[11.5px] text-wb-faint">
          Dernière mise à jour config : {new Date(config.updatedAt).toLocaleString('fr-FR')}
          {config.updatedBy ? ` · ${config.updatedBy}` : ''}
        </p>
      ) : null}
      </div>
    </div>
  )
}

/** Interrupteur (remplace la case à cocher) : orange quand il est activé. */
function Switch({
  label,
  checked,
  disabled,
  onChange,
}: {
  label: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between gap-3 text-[13px] text-slate-700">
      <span>{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={[
          'relative h-6 w-11 flex-none cursor-pointer rounded-full border-0 p-0 transition-colors disabled:cursor-not-allowed disabled:opacity-50',
          checked ? 'bg-wb-accent' : 'bg-slate-300',
        ].join(' ')}
      >
        <span
          className={[
            'absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-[0_1px_3px_rgba(0,0,0,0.25)] transition-[left]',
            checked ? 'left-[22px]' : 'left-0.5',
          ].join(' ')}
        />
      </button>
    </div>
  )
}
