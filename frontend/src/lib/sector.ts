import { SECTEURS } from '@/types/create-dossier'

const PRESET_SECTORS = new Set(
  SECTEURS.filter((s) => s !== 'Autre') as readonly string[],
)

export function isPresetSector(sector: string): boolean {
  return PRESET_SECTORS.has(sector.trim())
}

export function displaySector(sector: string): string {
  const s = sector.trim()
  if (!s || s === 'Autre' || !isPresetSector(s)) return 'Autre'
  return s
}

export function dashboardSectorLabel(sector: string): string {
  const s = sector.trim()
  if (!s || s === 'Autre' || !isPresetSector(s)) return 'Autres'
  return s
}
