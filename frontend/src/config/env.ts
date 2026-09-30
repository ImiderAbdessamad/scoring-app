export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export const USE_MOCK =
  (import.meta.env.VITE_USE_MOCK ?? 'false').toLowerCase() === 'true'

export const SHOW_SCORE =
  (import.meta.env.VITE_SHOW_SCORE ?? 'false').toLowerCase() === 'true'
