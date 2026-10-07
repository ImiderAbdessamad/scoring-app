/* Authentification Keycloak (realm SCORING / RCC, client scoring-wb). */

import Keycloak from 'keycloak-js'

/*
 * keycloak-js appelle crypto.randomUUID() à chaque connexion. Le navigateur ne
 * l'expose que sur une page sécurisée (https ou localhost) : sur le serveur dev
 * en http://IP, on le reconstruit à partir de crypto.getRandomValues(), qui
 * reste disponible et offre le même aléa.
 */
if (globalThis.crypto && typeof globalThis.crypto.randomUUID !== 'function') {
  globalThis.crypto.randomUUID = () => {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
    bytes[6] = (bytes[6] & 0x0f) | 0x40 // version 4
    bytes[8] = (bytes[8] & 0x3f) | 0x80 // variante RFC 4122
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}` as `${string}-${string}-${string}-${string}-${string}`
  }
}

export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'https://keycloak.app-dev.wafabail.ma',
  realm: import.meta.env.VITE_KEYCLOAK_REALM || 'scoring-rcc',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'scoring-wb',
})

// Le token est renouvelé en tâche de fond : apiHeaders() le lit de façon synchrone.
const REFRESH_INTERVAL_MS = 30_000
const MIN_VALIDITY_SECONDS = 60

/** Sans session Keycloak, redirige vers la page de connexion (la page est quittée). */
export async function initAuth(): Promise<boolean> {
  const authenticated = await keycloak.init({
    onLoad: 'login-required',
    // PKCE exige crypto.subtle, absent en http://IP : activé seulement sur page sécurisée.
    pkceMethod: window.isSecureContext ? 'S256' : false,
    checkLoginIframe: false,
  })
  if (authenticated) {
    window.setInterval(() => {
      keycloak.updateToken(MIN_VALIDITY_SECONDS).catch(() => login())
    }, REFRESH_INTERVAL_MS)
  }
  return authenticated
}

export function login() {
  return keycloak.login()
}

/** Ferme la session Keycloak (SSO compris, donc RCC aussi) et revient sur l'application. */
export function logout() {
  return keycloak.logout({ redirectUri: `${window.location.origin}/` })
}

export function accessToken(): string | undefined {
  return keycloak.token
}

type ProfileClaims = {
  name?: string
  preferred_username?: string
  given_name?: string
  family_name?: string
}

export function currentUser() {
  const claims = (keycloak.tokenParsed ?? {}) as ProfileClaims
  const name = claims.name || claims.preferred_username || 'Utilisateur'
  const parts = claims.given_name && claims.family_name
    ? [claims.given_name, claims.family_name]
    : name.split(/\s+/)
  const initials = parts.slice(0, 2).map((part) => part[0] ?? '').join('').toUpperCase()
  return { name, initials }
}
