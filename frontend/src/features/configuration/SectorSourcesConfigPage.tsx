import { useCallback, useEffect, useState } from 'react'
import { Database, RefreshCw, ShieldAlert } from 'lucide-react'
import { Card } from '@/components/ui/Card'
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
  const [syncBusy, setSyncBusy] = useState(false)
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

  async function syncHcp() {
    setSyncBusy(true)
    setNotice(null)
    setError(null)
    try {
      const result = await refreshSectorData(true)
      setNotice(
        result.changed > 0
          ? `Sync HCP terminée — ${result.updatedObservations} observations mises à jour.`
          : 'Sync HCP terminée — données déjà à jour.',
      )
      await reload()
    } catch {
      setError('Synchronisation HCP impossible.')
    } finally {
      setSyncBusy(false)
    }
  }

  return (
    <div className="wb-scroll flex-1 overflow-y-auto px-6 py-5">
      <div className="mb-5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.04em] text-wb-faint">
          Configuration
        </div>
        <h1 className="m-0 mt-1 text-[22px] font-extrabold tracking-tight text-slate-900">
          Sources de données sectorielles
        </h1>
        <p className="m-0 mt-2 max-w-3xl text-[13.5px] leading-relaxed text-wb-muted">
          Choisissez la source utilisée pour l’analyse sectorielle. Par défaut : HCP. Les autres
          sources peuvent être préparées sans écraser les dossiers déjà analysés.
        </p>
      </div>

      <Card className="mb-4 border-amber-200/80 bg-[#FFFBF5] p-4">
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
                Les caches d’observations coexistent par source : HCP n’est pas écrasé par une future
                source APSF / interne.
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
          className={`mb-4 rounded-[10px] border px-4 py-2.5 text-[12.5px] ${
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
        <div className="flex flex-col gap-3">
          {(config?.items || []).map((source) => {
            const busy = busyId === source.id
            return (
              <Card key={source.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-wb-accent-soft text-wb-accent">
                      <Database size={18} strokeWidth={1.8} />
                    </span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-[14px] font-bold text-slate-900">{source.label}</div>
                        {source.isDefault ? (
                          <span className="rounded-full bg-[#ECFDF5] px-2 py-0.5 text-[10.5px] font-bold text-[#15803D]">
                            Défaut
                          </span>
                        ) : null}
                        {!source.implemented ? (
                          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10.5px] font-bold text-slate-600">
                            Bientôt
                          </span>
                        ) : null}
                      </div>
                      <p className="m-0 mt-1 text-[12.5px] text-wb-muted">{source.description}</p>
                      {source.notes ? (
                        <p className="m-0 mt-1 text-[11.5px] text-wb-faint">{source.notes}</p>
                      ) : null}
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {source.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600"
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

                  <div className="flex flex-col items-stretch gap-2 sm:min-w-[200px]">
                    <label className="flex items-center justify-between gap-3 text-[12.5px] text-slate-700">
                      <span>Activée</span>
                      <input
                        type="checkbox"
                        checked={source.enabled}
                        disabled={busy || (source.isDefault && source.enabled)}
                        onChange={(e) => void toggleEnabled(source, e.target.checked)}
                      />
                    </label>
                    <label className="flex items-center justify-between gap-3 text-[12.5px] text-slate-700">
                      <span>Sélectionnable (analyse)</span>
                      <input
                        type="checkbox"
                        checked={source.selectable}
                        disabled={busy || !source.enabled || !source.supportsVaAnalysis}
                        onChange={(e) => void toggleSelectable(source, e.target.checked)}
                      />
                    </label>
                    <button
                      type="button"
                      disabled={busy || source.isDefault || !source.supportsVaAnalysis || !source.enabled}
                      onClick={() => void makeDefault(source)}
                      className="rounded-[8px] border border-wb-line px-3 py-1.5 text-[12px] font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {source.isDefault ? 'Source par défaut' : 'Définir comme défaut'}
                    </button>
                    {source.id === 'hcp' ? (
                      <button
                        type="button"
                        disabled={syncBusy}
                        onClick={() => void syncHcp()}
                        className="inline-flex items-center justify-center gap-1.5 rounded-[8px] bg-wb-accent px-3 py-1.5 text-[12px] font-bold text-white disabled:opacity-60"
                      >
                        <RefreshCw size={13} className={syncBusy ? 'animate-spin' : ''} />
                        {syncBusy ? 'Synchronisation…' : 'Synchroniser HCP'}
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
  )
}
