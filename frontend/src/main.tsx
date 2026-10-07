import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AppRouter } from '@/app/router'
import { initAuth } from '@/lib/auth'
import '@/index.css'

const root = document.getElementById('root')!

// Connexion Keycloak avant tout rendu : sans session, initAuth redirige vers la page de login.
initAuth()
  .then((authenticated) => {
    if (!authenticated) return
    createRoot(root).render(
      <StrictMode>
        <AppRouter />
      </StrictMode>,
    )
  })
  .catch((error: unknown) => {
    console.error('Initialisation Keycloak impossible', error)
    root.textContent =
      "Connexion au service d'authentification impossible. Rechargez la page ; si le problème persiste, contactez l'administrateur."
  })
