import type { CSSProperties } from 'react'
import heroBackground from '@/assets/hero-fond.webp'

/** Fond des en-têtes de page : image de la charte assombrie vers la gauche (lisibilité du texte). */
export const HERO_BACKGROUND: CSSProperties = {
  backgroundImage: [
    'linear-gradient(90deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.25) 60%, rgba(0,0,0,0.1) 100%)',
    `url(${heroBackground})`,
  ].join(', '),
  backgroundSize: 'cover',
  backgroundPosition: 'center 35%',
}
