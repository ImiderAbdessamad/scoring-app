import { Link, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { FolderSearch, TriangleAlert } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useAnalyseWorkspace } from '@/features/analyse/hooks/useAnalyseWorkspace'
import { AnalyseHeader } from '@/features/analyse/components/AnalyseHeader'
import { AgentPipeline } from '@/features/analyse/components/AgentPipeline'
import { DocumentsPanel } from '@/features/analyse/components/DocumentsPanel'
import { ExtractionPanel } from '@/features/analyse/components/ExtractionPanel'
import { CopilotPanel } from '@/features/analyse/components/CopilotPanel'
import { SyntheseTab } from '@/features/analyse/components/tabs/SyntheseTab'
import { BienTab } from '@/features/analyse/components/tabs/BienTab'
import { RatiosTab } from '@/features/analyse/components/tabs/RatiosTab'
import { FactorielleTab } from '@/features/analyse/components/tabs/FactorielleTab'
import { ComportementTab } from '@/features/analyse/components/tabs/ComportementTab'
import { BenchmarkTab } from '@/features/analyse/components/tabs/BenchmarkTab'
import { MemoTab } from '@/features/analyse/components/tabs/MemoTab'
import { FiscalTab } from '@/features/analyse/components/tabs/FiscalTab'
import { CapitalTab } from '@/features/analyse/components/tabs/CapitalTab'
import { EtatsTab, QualityTab } from '@/features/analyse/components/tabs/QualityEtatsTabs'

export function AnalysePage() {
  const { id } = useParams()
  const workspace = useAnalyseWorkspace(id)

  if (!id) {
    return <SelectDossierEmptyState />
  }

  return (
    <div className="flex h-full min-h-0">
      <div className="flex min-w-0 flex-1 flex-col">
        {workspace.loading && <AnalysePageSkeleton />}

        {!workspace.loading && workspace.error && <AnalyseErrorState message={workspace.error} />}

        {!workspace.loading && workspace.data && (
          <>
            <AnalyseHeader
              header={workspace.data.header}
              score={workspace.data.scoring.scoreRaw ?? workspace.data.scoring.score}
              classe={workspace.data.scoring.classe}
              provisional={workspace.data.scoring.provisional || workspace.data.analysisStale}
              decision={workspace.decision}
              decisionTime={workspace.decisionTime}
              decisionBusy={workspace.decisionBusy}
              onDecision={workspace.setDecision}
              onClearDecision={workspace.clearDecision}
              copilotOpen={workspace.copilotOpen}
              onToggleCopilot={workspace.toggleCopilot}
              tab={workspace.tab}
              onTabChange={workspace.setTab}
            />

            <div className="wb-scroll flex-1 overflow-y-auto pb-10">
              <AgentPipeline
                pipeline={workspace.data.pipeline}
                state={workspace.pipeline}
                onRun={workspace.runPipeline}
                idleLabel={workspace.data.scoring.score ? 'Relancer l’analyse' : 'Lancer l’analyse'}
                runningLabel={
                  workspace.liveJob
                    ? `${workspace.liveJob.progressPct} % — ${workspace.liveJob.message}`
                    : 'Analyse en cours'
                }
              />
              {workspace.liveJob?.status === 'failed' && (
                <div className="mx-6 mt-3 rounded-[10px] border border-red-200 bg-red-50 px-4 py-2.5 text-[12.5px] text-red-700">
                  {workspace.liveJob.error || 'L’analyse a échoué.'}
                </div>
              )}

              {workspace.data.analysisStale && (
                <div className="mx-6 mt-3 rounded-[10px] border border-amber-200 bg-amber-50 px-4 py-2.5 text-[12.5px] text-amber-900">
                  {workspace.data.staleMessage || 'Le document financier a changé. Relancez l’analyse.'}
                </div>
              )}
              <div className="grid grid-cols-1 gap-4 px-6 py-4 lg:grid-cols-[390px_1fr]">
                <div className="flex flex-col gap-4">
                  <DocumentsPanel
                    documents={workspace.data.documents}
                    selectedDocId={workspace.selectedDocId}
                    onSelect={workspace.selectDoc}
                    uploadable
                    uploadingDocId={workspace.uploadingDocId}
                    onUpload={workspace.uploadDocument}
                  />
                  <ExtractionPanel
                    extraction={workspace.data.documents.extractions[workspace.selectedDocId]}
                    document={workspace.data.documents.items.find((d) => d.id === workspace.selectedDocId)}
                  />
                </div>

                <div className="min-w-0">
                  {workspace.tab === 'synthese' && <SyntheseTab scoring={workspace.data.scoring} />}
                  {workspace.tab === 'etats' && (
                    <EtatsTab
                      statements={workspace.data.financialStatements}
                      yearLabels={workspace.data.yearLabels}
                    />
                  )}
                  {workspace.tab === 'fiscal' && (
                    <FiscalTab fiscal={workspace.data.fiscalAnalysis} />
                  )}
                  {workspace.tab === 'capital' && (
                    <CapitalTab capital={workspace.data.capitalAnalysis} />
                  )}
                  {workspace.tab === 'qualite' && (
                    <QualityTab
                      quality={workspace.data.quality}
                      readiness={workspace.data.readiness}
                      controls={workspace.data.controls}
                    />
                  )}
                  {workspace.tab === 'bien' && <BienTab bien={workspace.data.bien} />}
                  {workspace.tab === 'ratios' && (
                    <RatiosTab
                      ratios={workspace.data.ratios}
                      openIndex={workspace.openKpi}
                      onToggle={workspace.toggleKpi}
                    />
                  )}
                  {workspace.tab === 'factorielle' && (
                    <FactorielleTab
                      axes={workspace.data.factorielle}
                      openAxis={workspace.openAxis}
                      onToggle={workspace.toggleAxis}
                    />
                  )}
                  {workspace.tab === 'comportement' && (
                    <ComportementTab comportement={workspace.data.comportement} />
                  )}
                  {workspace.tab === 'benchmark' && <BenchmarkTab benchmark={workspace.data.benchmark} />}
                  {workspace.tab === 'memo' && (
                    <MemoTab
                      memo={workspace.data.memo}
                      memoSigned={workspace.memoSigned}
                      onToggleSign={workspace.toggleMemoSign}
                    />
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <AnimatePresence>
        {workspace.copilotOpen && workspace.data && (
          <CopilotPanel
            copilot={workspace.data.copilot}
            messages={workspace.messages}
            input={workspace.input}
            thinking={workspace.thinking}
            onChangeInput={workspace.setInput}
            onSend={workspace.sendCopilotMessage}
            onClose={workspace.toggleCopilot}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function SelectDossierEmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md rounded-2xl border border-wb-line bg-white p-8 shadow-[0_1px_2px_rgba(16,24,40,0.04)]"
      >
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-[12px] bg-wb-accent-soft text-wb-accent">
          <FolderSearch size={22} strokeWidth={1.8} />
        </div>
        <h1 className="m-0 text-[19px] font-extrabold text-slate-900">Poste d&apos;analyse</h1>
        <p className="mt-2 text-[13px] leading-relaxed text-wb-muted">
          Sélectionnez un dossier depuis le tableau de bord ou la liste des dossiers pour ouvrir son poste
          d&apos;analyse.
        </p>
        <div className="mt-5 flex justify-center gap-2">
          <Link to="/">
            <Button variant="secondary">Tableau de bord</Button>
          </Link>
          <Link to="/dossiers">
            <Button variant="primary">Voir les dossiers</Button>
          </Link>
        </div>
      </motion.div>
    </div>
  )
}

function AnalyseErrorState({ message }: { message: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-md rounded-2xl border border-wb-line bg-white p-8 shadow-[0_1px_2px_rgba(16,24,40,0.04)]"
      >
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-[12px] bg-[#FEF2F2] text-[#DC2626]">
          <TriangleAlert size={22} strokeWidth={1.8} />
        </div>
        <h1 className="m-0 text-[19px] font-extrabold text-slate-900">Dossier introuvable</h1>
        <p className="mt-2 text-[13px] leading-relaxed text-wb-muted">{message}</p>
        <div className="mt-5 flex justify-center gap-2">
          <Link to="/dossiers">
            <Button variant="primary">Retour aux dossiers</Button>
          </Link>
        </div>
      </motion.div>
    </div>
  )
}

function AnalysePageSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex-none animate-pulse border-b border-wb-line bg-white px-6 py-4">
        <div className="h-4 w-64 rounded bg-wb-surface" />
        <div className="mt-4 h-9 w-96 rounded bg-wb-surface" />
      </div>
      <div className="wb-scroll flex-1 overflow-y-auto px-6 py-5">
        <div className="animate-pulse space-y-4">
          <div className="h-[160px] rounded-[14px] bg-wb-ink-soft/10 border border-wb-line" />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[390px_1fr]">
            <div className="h-[420px] rounded-[14px] bg-white border border-wb-line" />
            <div className="h-[420px] rounded-[14px] bg-white border border-wb-line" />
          </div>
        </div>
      </div>
    </div>
  )
}
