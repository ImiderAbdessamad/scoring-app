import { describe, expect, it } from 'vitest'
import { detectCandidates, extractFromOcrResult, extractFromText } from '@/lib/extraction/detectors'
import { mergeCandidates, mergeField, stateFromForm } from '@/lib/extraction/merge'
import {
  normalizeOcrLabels,
  normalizeRcAnalytique,
  prepareTextForExtraction,
} from '@/lib/extraction/normalize'
import { scoreCandidate } from '@/lib/extraction/scoring'
import { ExtractionWorkspace, withExtractionWorkspace } from '@/lib/extraction/workspace'
import type { ExtractionCandidate } from '@/lib/extraction/types'
import { CONFIDENCE_MEDIUM } from '@/lib/extraction/types'

const ICE_CERT = `
CERTIFICAT DE L'IDENTIFIANT COMMUN DE L'ENTREPRISE
IDENTIFIANT COMMUN DE L'ENTREPRISE
001535820000069
Dénomination
CANALISATIONS ET MATERIAUX PREFABRIQUES DU MAROC
Numéro RC
1107/AGADIR
`

const RC_REGISTER = `
Registre du Commerce (N° I.C.E):
Copie des Inscriptions Portées au registre analytique N°: 29951
Dénomination
RAYAN INVESTISSEMENT SARL
N° Chronologique: 1050
CODE DEMANDE: 403032127121
`

const RC_REGISTER_OCR = `
sire du Commerce
(N° LCE):
Cape 08 Inscaptiors Pardes au again arulyique N° 294951
Dénomination (ead): RAYAN INVESTISSEMENT SARL
N°Chronologique: 1050
CODE DEMAMDE 40308212711
`

const INVOICE = `
Facture N° : 202600123
Montant : 50 000 MAD
Téléphone : 0612345678
`

const RC_MULTILINE = `
Registre de
Commerce :
Casablanca 123456
`

const ICE_MULTILINE = `
I.C.E
:
001234567890123
`

function iceCandidate(value: string, confidence: number, sourceFile = 'doc.pdf'): ExtractionCandidate {
  return {
    fieldType: 'ICE',
    value,
    confidence,
    sourceFile,
    context: `ICE : ${value}`,
    label: 'ICE',
    matchedLabel: 'ICE',
  }
}

describe('normalizeOcrLabels', () => {
  it('corrige les labels OCR courants', () => {
    const text = normalizeOcrLabels('sire du Commerce\nRegistre de\nCommerce')
    expect(text).toContain('Registre du Commerce')
    expect(text).toContain('Registre de Commerce')
  })

  it('corrige registre analytique OCR', () => {
    const text = prepareTextForExtraction(
      "Inscaptiors Pardes au 'again arulyique N° 294951",
    )
    expect(text).toMatch(/registre analytique/i)
  })
})

describe('normalizeRcAnalytique', () => {
  it('corrige 294951 → 29951', () => {
    expect(normalizeRcAnalytique('294951')).toBe('29951')
  })

  it('corrige 29551 → 29951', () => {
    expect(normalizeRcAnalytique('29551')).toBe('29951')
  })
})

describe('scoring', () => {
  it('rejette un ICE associé à une facture', () => {
    const { confidence } = scoreCandidate({
      fieldType: 'ICE',
      rawValue: '202600123456789',
      normalizedValue: '202600123456789',
      matchedLabel: 'N° facture',
      context: 'Facture N° 202600123456789',
    })
    expect(confidence).toBeLessThan(CONFIDENCE_MEDIUM)
  })

  it('accepte un RC avec label registre analytique', () => {
    const { confidence } = scoreCandidate({
      fieldType: 'RC',
      rawValue: '29951',
      normalizedValue: '29951',
      matchedLabel: 'registre analytique',
      context: 'Copie des Inscriptions Portées au registre analytique N°: 29951',
      labelProximity: 'adjacent',
    })
    expect(confidence).toBeLessThan(0.5)
  })

  it('accepte un RC avec label N° Chronologique', () => {
    const { confidence } = scoreCandidate({
      fieldType: 'RC',
      rawValue: '905',
      normalizedValue: '905',
      matchedLabel: 'N° Chronologique',
      context: 'N° Chronologique: 905',
      labelProximity: 'adjacent',
    })
    expect(confidence).toBeGreaterThanOrEqual(0.8)
  })
})

describe('detectCandidates', () => {
  it('1 — extrait un ICE valide depuis certificat ICE', () => {
    const c = extractFromText(ICE_CERT, 'ice.png')
    expect(c.find((x) => x.fieldType === 'ICE')?.value).toBe('001535820000069')
    expect(c.find((x) => x.fieldType === 'RAISON_SOCIALE')?.value).toContain('CANALISATIONS')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('1107/AGADIR')
  })

  it('2 — ignore les nombres sans label ICE', () => {
    const c = extractFromText(INVOICE, 'facture.pdf')
    expect(c.find((x) => x.fieldType === 'ICE')).toBeUndefined()
  })

  it('6 — rejette un numéro de facture comme ICE', () => {
    const c = detectCandidates('Facture N° 202600123 Montant 12500', 'f.pdf')
    expect(c.some((x) => x.fieldType === 'ICE')).toBe(false)
  })

  it('7 — extrait un RC labellisé (certificat ICE)', () => {
    const c = extractFromText(ICE_CERT, 'ice.png')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('1107/AGADIR')
  })

  it('8 — extrait le RC depuis N° Chronologique (pas le N° analytique)', () => {
    const c = extractFromText(RC_REGISTER, 'rc.pdf')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('1050')
    const analytic = c.find((x) => x.fieldType === 'RC' && x.value === '29951')
    if (analytic) expect(analytic.confidence).toBeLessThan(0.5)
  })

  it('extrait aussi le N° Chronologique comme RC', () => {
    const c = extractFromText('N° Chronologique: 1050\nDénomination RAYAN INVESTISSEMENT SARL', 'rc.pdf')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('1050')
    expect(c.find((x) => x.fieldType === 'RC')?.matchedLabel).toMatch(/Chronologique/i)
  })

  it('N* Chronologique (variante OCR) → RC', () => {
    const c = extractFromText('N* Chronologique : 29951', 'rc.png')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('29951')
  })

  it('OCR rc.png Eljadida : N°*Chronologique → 905 (pas 18399)', () => {
    const ocr = `
Registre du Commerce
(N*LC.E):
Cople des Inscriptions Portées au registre anatySque N:18399
Date immatriculation rue cold: 12/07/2021 N°*Chronologique (d= sj): 905
Dénomination (++): FROMAGERIE ATLANTIQUE Sigle:
`
    const c = extractFromText(ocr, 'rc.png')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('905')
    const analytic = c.find((x) => x.value === '18399')
    if (analytic) expect(analytic.confidence).toBeLessThan(0.5)
    expect(c.find((x) => x.fieldType === 'RAISON_SOCIALE')?.value).toBe('FROMAGERIE ATLANTIQUE')
  })

  it('N° Chronologique seul candidat RC sur extrait analytique', () => {
    const c = extractFromText(RC_REGISTER, 'rc.pdf')
    const rcs = c.filter((x) => x.fieldType === 'RC')
    expect(rcs[0].value).toBe('1050')
    expect(rcs.filter((x) => x.value === '1050').length).toBeGreaterThan(0)
  })

  it('8b — extrait RC depuis texte OCR dégradé (image.png simulé)', () => {
    const c = extractFromText(RC_REGISTER_OCR, 'image.png')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('1050')
  })

  it('9 — extrait la raison sociale labellisée', () => {
    const c = extractFromText(RC_REGISTER, 'rc.pdf')
    expect(c.find((x) => x.fieldType === 'RAISON_SOCIALE')?.value).toBe('RAYAN INVESTISSEMENT SARL')
  })

  it('10 — document sans info ne produit aucun candidat', () => {
    const c = extractFromText('Lorem ipsum document interne', 'vide.pdf')
    expect(c).toHaveLength(0)
  })

  it('RC multiligne — Registre de / Commerce', () => {
    const c = extractFromText(RC_MULTILINE, 'rc.pdf')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toMatch(/123456/)
  })

  it('ICE multiligne', () => {
    const c = extractFromText(ICE_MULTILINE, 'ice.pdf')
    expect(c.find((x) => x.fieldType === 'ICE')?.value).toBe('001234567890123')
  })

  it('RC : 123456', () => {
    const c = extractFromText('RC : 123456', 'doc.pdf')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('123456')
  })

  it('R.C : 123456', () => {
    const c = extractFromText('R.C : 123456', 'doc.pdf')
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('123456')
  })

  it('ne prend pas le CODE DEMANDE comme RC', () => {
    const c = extractFromText('CODE DEMANDE: 403032127121', 'doc.pdf')
    expect(c.find((x) => x.fieldType === 'RC')).toBeUndefined()
  })

  it('ne prend pas Client comme raison sociale', () => {
    const c = extractFromText('Client : ATLAS SERVICES SARL', 'doc.pdf')
    expect(c.find((x) => x.fieldType === 'RAISON_SOCIALE')).toBeUndefined()
  })

  it('OCR boxes : Chronologique à gauche → chiffre à droite (905 pas 505)', () => {
    const words = [
      { text: 'N°Chronotogique', confidence: 57, x: 618, y: 325, width: 200, height: 20 },
      { text: '505', confidence: 40, x: 100, y: 325, width: 40, height: 20 }, // à gauche = date parasite
      { text: '905', confidence: 81, x: 945, y: 325, width: 40, height: 20 },
    ]
    const c = extractFromOcrResult({
      text: 'N°Chronotogique 505 905',
      words,
      avgConfidence: 70,
      sourceFile: 'rc.png',
    })
    expect(c.find((x) => x.fieldType === 'RC')?.value).toBe('905')
  })
})

describe('mergeCandidates', () => {
  it('3 — conserve le premier ICE si le second fichier n’en a pas', () => {
    let state = mergeCandidates({ conflicts: [] }, extractFromText(ICE_CERT, 'ice.png'))
    const before = state.ice?.value
    state = mergeCandidates(state, extractFromText(INVOICE, 'facture.pdf'))
    expect(state.ice?.value).toBe(before)
  })

  it('4 — deux fichiers avec le même ICE → pas de conflit', () => {
    let state = mergeCandidates({ conflicts: [] }, extractFromText(ICE_CERT, 'a.pdf'))
    state = mergeCandidates(state, extractFromText(ICE_CERT, 'b.pdf'))
    expect(state.conflicts).toHaveLength(0)
    expect(state.ice?.value).toBe('001535820000069')
  })

  it('5 — deux ICE différents → conflit sans écrasement silencieux', () => {
    let state = mergeCandidates({ conflicts: [] }, [
      iceCandidate('001234567890123', 0.97, 'a.pdf'),
    ])
    const result = mergeField(state.ice, iceCandidate('001234567890999', 0.94, 'b.pdf'))
    expect(result.decision).toBe('CONFLICT')
    expect(result.next?.value).toBe('001234567890123')
  })

  it('11 — ordre des fichiers : valeur fiable conservée', () => {
    const first = mergeCandidates({ conflicts: [] }, extractFromText(ICE_CERT, '1.pdf'))
    const second = mergeCandidates(first, extractFromText(INVOICE, '2.pdf'))
    const reversedBase = mergeCandidates({ conflicts: [] }, extractFromText(INVOICE, '2.pdf'))
    const reversed = mergeCandidates(reversedBase, extractFromText(ICE_CERT, '1.pdf'))
    expect(second.ice?.value).toBe('001535820000069')
    expect(reversed.ice?.value).toBe('001535820000069')
  })

  it('ne remplace pas une valeur form existante par une moins fiable', () => {
    let state = stateFromForm({ ice: '001234567890123' })
    state = mergeCandidates(state, [iceCandidate('202600123', 0.32, 'facture.pdf')])
    expect(state.ice?.value).toBe('001234567890123')
  })

  it('fichier 2 avec faux RC ne remplace pas RC fiable', () => {
    let state = mergeCandidates({ conflicts: [] }, extractFromText(RC_REGISTER, 'rc.pdf'))
    expect(state.rc?.value).toBe('1050')
    state = mergeCandidates(state, extractFromText(INVOICE, 'facture.pdf'))
    expect(state.rc?.value).toBe('1050')
  })
})

describe('ExtractionWorkspace', () => {
  it('cleanup supprime les entrées même après erreur', async () => {
    const ws = new ExtractionWorkspace()
    ws.add('test.png', new Blob(['x'], { type: 'image/png' }))
    await expect(
      withExtractionWorkspace(async (workspace) => {
        workspace.add('fail.png', new Blob(['y'], { type: 'image/png' }))
        throw new Error('simulated failure')
      }),
    ).rejects.toThrow('simulated failure')
  })
})

describe('liasse DGI', () => {
  it('extrait l’ICE en tête de liasse DGI (Identification du contribuable)', () => {
    const page1 = `
001669862000005
Identification du contribuable
Raison Sociale :
Adresse :
Ville :
Identifiant fiscal
ADEIS INVEST
ICE :
`
    const c = extractFromText(page1, 'ADEISINVEST-BILAN-2025.pdf')
    expect(c.find((x) => x.fieldType === 'ICE')?.value).toBe('001669862000005')
  })
})
