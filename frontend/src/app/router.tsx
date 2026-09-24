import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { DossiersPage } from '@/features/dossiers/DossiersPage'
import { AnalysePage } from '@/features/analyse/AnalysePage'
import { SectorSourcesConfigPage } from '@/features/configuration/SectorSourcesConfigPage'

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="dossiers" element={<DossiersPage />} />
          <Route path="analyse" element={<AnalysePage />} />
          <Route path="analyse/:id" element={<AnalysePage />} />
          <Route path="configuration" element={<SectorSourcesConfigPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
