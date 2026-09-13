export function normalizeText(raw: string): string {
  return raw
    .replace(/\u0000/g, ' ')
    .replace(/[ \t]+/g, ' ')
    .replace(/\r/g, '\n')
}


export function normalizeOcrLabels(raw: string): string {
  let text = raw
    .replace(/\r/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n+/g, '\n')

  const labelFixes: Array<[RegExp, string]> = [
    [/\bsire\s+du\s+Commerce\b/gi, 'Registre du Commerce'],
    [/\bReg(?:a|e)ire\s+du\s+Com(?:r)?merce\b/gi, 'Registre du Commerce'],
    [/\bRegistre\s+de\s+Com(?:r)?merce\b/gi, 'Registre de Commerce'],
    [/\bRegistre\s+du\s+Com(?:r)?merce\b/gi, 'Registre du Commerce'],
    [/\bregistre\s+arnaiy[eé]que\b/gi, 'registre analytique'],
    [/\bregistre\s+anulyique\b/gi, 'registre analytique'],
    [/\bregistre\s+arulyique\b/gi, 'registre analytique'],
    [/\bregistre\s+anatysque\b/gi, 'registre analytique'],
    [/\bregistre\s+anaty[sS]que\b/gi, 'registre analytique'],
    [/\bregistre\s+an[a-z]{3,12}(?:ique|que)\b/gi, 'registre analytique'],
    [/\bagain\s+arulyique\b/gi, 'registre analytique'],
    [/\barnaiy[eé]que\b/gi, 'analytique'],
    [/\barulyique\b/gi, 'analytique'],
    [/\banaty[sS]que\b/gi, 'analytique'],
    [/\bCople\s+des\s+Inscriptions/gi, 'Copie des Inscriptions'],
    [/\bInscapti\w*\s+Pardes\s+au\s+(?:['']?again\s+)?arulyique/gi, 'Inscriptions Portées au registre analytique'],
    [/\bInscaptions?\s+Pardes?\b/gi, 'Inscriptions Portées'],
    [/\bCape\s+0?8\s+Inscapti/gi, 'Copie des Inscriptions'],
    [/\bN[°ºo]\s*LCE\b/gi, 'N° ICE'],
    [/\bN\*\s*I\.?\s*C\.?\s*E\b/gi, 'N° ICE'],
    [/\b\(N\*LC\.E\)/gi, '(N° ICE)'],
    [/\bI\.?\s*C\.?\s*E\b/gi, 'ICE'],
    [/\blCE\b/g, 'ICE'],
    [/\bD[eé]nominati(?:on|o)\b/gi, 'Dénomination'],
    [/\bN[°ºo*.*]+\s*Chronotogique\b/gi, 'N° Chronologique'],
    [/\bN[°ºo*.*]+\s*Chronologique\b/gi, 'N° Chronologique'],
    [/\bN[°ºo*.]*Chron[oa]log\w*/gi, 'N° Chronologique'],
    [/\bChronotogique\b/gi, 'Chronologique'],
    [/\bChronalogique\b/gi, 'Chronologique'],
    [/\bNum[eé]ro\s*R\.?\s*C\b/gi, 'Numéro RC'],
    [/\bNun[eé]ro\s*R\.?\s*C\b/gi, 'Numéro RC'],
    [/\bNum[eé]ro\s*RG\b/gi, 'Numéro RC'],
  ]

  for (const [pattern, replacement] of labelFixes) {
    text = text.replace(pattern, replacement)
  }


  text = text
    .replace(/Registre\s+de\s*\n\s*Commerce/gi, 'Registre de Commerce')
    .replace(/Registre\s+du\s*\n\s*Commerce/gi, 'Registre du Commerce')
    .replace(/Raison\s*\n\s*sociale/gi, 'Raison sociale')
    .replace(/Identifiant\s*\n\s*Commun/gi, 'Identifiant Commun')

  return text
}

export function digitsOnly(s: string): string {
  return s.replace(/\D/g, '')
}


export function fixOcrDigits(s: string): string {
  return s.replace(/[Oo]/g, '0').replace(/[Il|]/g, '1')
}

export function normalizeIce(value: string): string {
  return digitsOnly(fixOcrDigits(value)).slice(0, 15)
}

export function normalizeRc(value: string): string {
  return value
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\s+/g, '')
    .replace('%', '/')
    .replace(/([0-9])([A-Za-zÀ-ÿ])/g, '$1/$2')
}


export function normalizeRcAnalytique(raw: string): string {
  let digits = digitsOnly(fixOcrDigits(raw))

  if (digits.length === 6 && /^2\d{5}$/.test(digits) && digits.endsWith('9951')) {
    digits = digits.slice(1)
  }

  if (digits === '29551') digits = '29951'

  if (digits === '294951') digits = '29951'

  return digits
}

export function normalizeRaison(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

export function isValidIce(digits: string): boolean {
  return /^\d{15}$/.test(digits)
}

export function isValidRc(value: string): boolean {
  const v = normalizeRc(value)
  if (v.length < 2 || v.length > 32) return false
  if (/^\d{15}$/.test(v)) return false
  if (/^(facture|ref|reference)/i.test(v)) return false
  if (/^\d{4,8}$/.test(v)) return true
  return (
    /^\d{1,8}(\/[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-]{2,20})?$/.test(v) ||
    /^[A-Za-zÀ-ÿ]{3,20}\s*\d{1,8}$/i.test(v) ||
    /^[A-Za-zÀ-ÿ]{3,20}\d{1,8}$/i.test(v)
  )
}

const RAISON_LABEL_WORDS =
  /^(identifiant|fiscal|num[eé]ro|certificat|d[eé]nomination|raison|sociale|registre|commerce|entreprise|soci[eé]t[eé]|cnss|ice|rc)$/i

export function isValidRaison(value: string): boolean {
  const v = normalizeRaison(value)
  if (v.length < 4 || v.length > 160) return false
  if (/^(client|fournisseur|g[eé]rant|gerant)\s*:/i.test(v)) return false
  if (/certificat|identifiant commun|royaume du maroc|minist[eè]re de la justice/i.test(v)) {
    return false
  }

  if (RAISON_LABEL_WORDS.test(v)) return false
  const words = v.split(/\s+/).filter(Boolean)
  if (words.length === 1 && words[0].length < 8) return false
  return /[A-Za-zÀ-ÿ]{3,}/.test(v)
}

const NEGATIVE_ICE =
  /facture|r[eé]f[ée]rence|montant|t[eé]l[eé]phone|cnss|identifiant\s+fiscal|code\s+demande|capital|chronologique|n[°ºo]?\s*facture|demande\s+n/i

const NEGATIVE_RC =
  /facture|r[eé]f[ée]rence|code\s+demande|capital\s+social|identifiant\s+fiscal|cnss|demande\s+n|t[eé]l[eé]phone|montant/i

const NEGATIVE_RAISON = /\b(client|fournisseur|g[eé]rant|dirigeant)\s*:/i

export function isNegativeIceContext(context: string): boolean {
  return NEGATIVE_ICE.test(context)
}

export function isNegativeRcContext(context: string): boolean {
  return NEGATIVE_RC.test(context)
}

export function isNegativeRaisonContext(context: string): boolean {
  return NEGATIVE_RAISON.test(context)
}

export function snippet(text: string, index: number, radius = 70): string {
  const start = Math.max(0, index - radius)
  const end = Math.min(text.length, index + radius)
  return text.slice(start, end).replace(/\s+/g, ' ').trim()
}

export function prepareTextForExtraction(raw: string): string {
  return normalizeText(normalizeOcrLabels(raw))
}
