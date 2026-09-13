import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { CreateDossierWizard } from '@/features/dossiers/create/CreateDossierWizard'

type Ctx = {
  openCreateDossier: () => void
  closeCreateDossier: () => void
}

const CreateDossierContext = createContext<Ctx | null>(null)

export function CreateDossierProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)

  const openCreateDossier = useCallback(() => setOpen(true), [])
  const closeCreateDossier = useCallback(() => setOpen(false), [])

  const value = useMemo(
    () => ({ openCreateDossier, closeCreateDossier }),
    [openCreateDossier, closeCreateDossier],
  )

  return (
    <CreateDossierContext.Provider value={value}>
      {children}
      <CreateDossierWizard open={open} onClose={closeCreateDossier} />
    </CreateDossierContext.Provider>
  )
}

export function useCreateDossier() {
  const ctx = useContext(CreateDossierContext)
  if (!ctx) {
    throw new Error('useCreateDossier must be used within CreateDossierProvider')
  }
  return ctx
}
