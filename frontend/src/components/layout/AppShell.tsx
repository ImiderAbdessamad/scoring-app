import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { CreateDossierProvider } from '@/features/dossiers/create/CreateDossierProvider'
import { AnalyseJobsProvider } from '@/features/analyse/AnalyseJobsProvider'

const STORAGE_KEY = 'wb-sidebar-open'

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved === 'false') return false
      return true
    } catch {
      return true
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(sidebarOpen))
    } catch {
      
    }
  }, [sidebarOpen])

  return (
    <CreateDossierProvider>
      <AnalyseJobsProvider>
      <div className="flex h-full w-full overflow-hidden bg-wb-canvas">
        <Sidebar
          open={sidebarOpen}
          onToggle={() => setSidebarOpen((v) => !v)}
        />
        <main className="flex min-w-0 flex-1 flex-col bg-wb-surface">
          <Outlet />
        </main>
      </div>
      </AnalyseJobsProvider>
    </CreateDossierProvider>
  )
}
