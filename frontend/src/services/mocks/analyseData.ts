import type { Dossier, DossierDetail, StoredFileMeta } from '@/types/dossier'
import { STATUS_META, formatAmountMad, formatAmountShort } from '@/lib/format'
import { getDossierStore } from '@/services/mocks/dossierStore'
import type {
  AnalyseWorkspace,
  BehaviourBlock,
  BenchmarkBlock,
  BienBlock,
  DocumentExtraction,
  DocumentsBlock,
  FactorAxis,
  MemoBlock,
  RatioItem,
  RatioStatus,
  RatiosBlock,
  ScoringBlock,
} from '@/types/analyse'

type Tier = 0 | 1 | 2 

function tierOf(score: number): Tier {
  if (score >= 75) return 2
  if (score >= 55) return 1
  return 0
}

function mockClasse(score: number): string {
  if (score >= 90) return 'A+'
  if (score >= 80) return 'A/B+'
  if (score >= 65) return 'B/B-'
  if (score >= 50) return 'C'
  return 'D/F'
}

function mockGradeLabel(letter: string): string {
  if (letter === 'A+') return 'Excellent'
  if (letter === 'A/B+') return 'Bon'
  if (letter === 'B/B-') return 'Moyen'
  if (letter === 'C') return 'Sensible'
  return 'Risqué'
}

function tierAt(base: Tier, offset: number): Tier {
  return Math.min(2, Math.max(0, base + offset)) as Tier
}

function seedFromId(id: string): number {
  let h = 0
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
  return h
}

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean)
  const letters = parts.slice(0, 3).map((w) => w[0])
  return letters.join('').toUpperCase().slice(0, 3) || 'WB'
}

const SECTOR_LOCATION: Record<string, string> = {
  Transport: 'Casablanca · Zone industrielle Aïn Sebaâ',
  Immobilier: 'Casablanca · Centre-ville',
  Agroalimentaire: 'Agadir · Zone agro-industrielle',
  BTP: 'Rabat · Technopolis',
  Santé: 'Casablanca · Quartier des hôpitaux',
  Industrie: 'Tanger · Zone franche',
  Commerce: 'Casablanca · Sidi Maârouf',
  Agriculture: 'Béni Mellal · Plaine du Tadla',
  Tourisme: 'Marrakech · Hivernage',
  'Tech & Services': 'Casablanca · Technopark',
  Éducation: 'Fès · Ville nouvelle',
  Énergie: 'Ouarzazate · Zone solaire',
  Automobile: 'Rabat · Aéropole',
}

const SECTOR_ASSET: Record<
  string,
  { designation: string; marque: string; modele: string; title: string }
> = {
  Transport: {
    designation: 'Camion porteur 19T',
    marque: 'Mercedes-Benz',
    modele: 'Actros 1935',
    title: 'Flotte de transport routier',
  },
  Immobilier: {
    designation: 'Local commercial R+2',
    marque: '—',
    modele: 'Bien immobilier',
    title: 'Actif immobilier professionnel',
  },
  BTP: {
    designation: 'Pelle hydraulique 20T',
    marque: 'Caterpillar',
    modele: '320 GC',
    title: 'Engin de chantier',
  },
  Agroalimentaire: {
    designation: 'Ligne de conditionnement',
    marque: 'Tetra Pak',
    modele: 'A3 Flex',
    title: 'Équipement de production agroalimentaire',
  },
  Industrie: {
    designation: 'Centre d’usinage CNC',
    marque: 'DMG Mori',
    modele: 'NLX 2500',
    title: 'Équipement industriel de production',
  },
  Santé: {
    designation: 'Scanner médical',
    marque: 'Siemens Healthineers',
    modele: 'Somatom go.Up',
    title: 'Équipement médical d’imagerie',
  },
  Tourisme: {
    designation: 'Mobilier & équipement hôtelier',
    marque: '—',
    modele: 'Lot complet',
    title: 'Équipement hôtelier',
  },
}

function assetFor(sector: string) {
  return (
    SECTOR_ASSET[sector] ?? {
      designation: 'Matériel professionnel',
      marque: '—',
      modele: 'Équipement standard',
      title: 'Équipement professionnel',
    }
  )
}

function pct(base: number, min: number, max: number): number {
  return Math.round(min + (Math.max(0, Math.min(100, base)) / 100) * (max - min))
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toFixed(1).replace('.', ',')} Mo`
  }
  if (bytes >= 1_000) {
    return `${Math.round(bytes / 1_000)} Ko`
  }
  return `${bytes} o`
}

function formatStoredFileMeta(file: StoredFileMeta): string {
  const ext = file.contentType.includes('pdf')
    ? 'PDF'
    : file.contentType.includes('png')
      ? 'PNG'
      : 'JPG'
  return `${ext} · ${formatFileSize(file.size)}`
}


function buildDocumentsFromDetail(d: Dossier, detail: DossierDetail, _tier: Tier): DocumentsBlock {
  const items = detail.files.map((file, index) => ({
    id: `doc-${index}-${file.name}`,
    name: file.name,
    uploadName: file.name,
    meta: formatStoredFileMeta(file),
    confidence: d.status === 'pending' ? 0 : pct(d.score, 76, 99) - (index % 3),
  }))

  const present = items.length
  const extractions: Record<string, DocumentExtraction> = {}
  for (const item of items) {
    extractions[item.id] = {
      title: item.name,
      flag: d.status === 'pending' ? 'Document déposé' : 'Document indexé',
      fields: [],
    }
  }

  return {
    present,
    total: present,
    completenessPct: present ? 100 : 0,
    items,
    missing: [],
    extractions,
    defaultDocId: items[0]?.id ?? '',
  }
}

function buildDocuments(_d: Dossier, _tier: Tier): DocumentsBlock {
  return {
    present: 0,
    total: 0,
    completenessPct: 0,
    items: [],
    missing: [],
    extractions: {},
    defaultDocId: '',
  }
}

type RatioDef = { label: string; formula: string; tiers: [RatioValue, RatioValue, RatioValue] }
type RatioValue = { value: string; interpretation: string; barPct: number }

const RATIO_DEFS: RatioDef[] = [
  {
    label: 'Liquidité générale',
    formula: 'Actif circulant / Passif circulant',
    tiers: [
      { value: '0,78', interpretation: 'Trésorerie tendue, capacité de remboursement à court terme fragile.', barPct: 30 },
      { value: '1,14', interpretation: 'Couverture correcte mais marge de sécurité limitée.', barPct: 56 },
      { value: '1,68', interpretation: 'Bonne capacité à honorer les engagements à court terme.', barPct: 87 },
    ],
  },
  {
    label: 'Autonomie financière',
    formula: 'Capitaux propres / Total bilan',
    tiers: [
      { value: '18%', interpretation: 'Dépendance élevée aux financements externes.', barPct: 22 },
      { value: '31%', interpretation: 'Structure financière acceptable, à renforcer.', barPct: 48 },
      { value: '46%', interpretation: 'Structure financière solide, bon coussin de fonds propres.', barPct: 80 },
    ],
  },
  {
    label: "Taux d'endettement",
    formula: 'Dettes financières / Capitaux propres',
    tiers: [
      { value: '215%', interpretation: 'Endettement élevé, forte sensibilité aux chocs de taux.', barPct: 20 },
      { value: '128%', interpretation: 'Endettement maîtrisé mais à surveiller.', barPct: 50 },
      { value: '74%', interpretation: 'Levier financier raisonnable.', barPct: 82 },
    ],
  },
  {
    label: 'Rentabilité nette',
    formula: 'Résultat net / Chiffre d’affaires',
    tiers: [
      { value: '1,2%', interpretation: 'Marge nette faible, rentabilité fragile.', barPct: 16 },
      { value: '4,6%', interpretation: 'Rentabilité correcte pour le secteur.', barPct: 52 },
      { value: '8,9%', interpretation: 'Bonne rentabilité, au-dessus de la médiane sectorielle.', barPct: 88 },
    ],
  },
  {
    label: 'Couverture du service de la dette (DSCR)',
    formula: 'Cash-flow disponible / Annuités dues',
    tiers: [
      { value: '0,95x', interpretation: 'Cash-flow tout juste suffisant pour couvrir l’échéance.', barPct: 26 },
      { value: '1,25x', interpretation: 'Marge de couverture correcte.', barPct: 55 },
      { value: '1,74x', interpretation: 'Bonne capacité de remboursement des annuités.', barPct: 86 },
    ],
  },
  {
    label: 'Rotation des stocks',
    formula: 'Stock moyen / CA × 365',
    tiers: [
      { value: '112 j', interpretation: 'Rotation lente, immobilisation importante de trésorerie.', barPct: 30 },
      { value: '68 j', interpretation: 'Rotation dans la moyenne du secteur.', barPct: 58 },
      { value: '41 j', interpretation: 'Bonne gestion des stocks.', barPct: 84 },
    ],
  },
  {
    label: 'Délai de recouvrement clients',
    formula: 'Créances clients / CA × 365',
    tiers: [
      { value: '97 j', interpretation: 'Délai de paiement clients élevé, risque de tension de trésorerie.', barPct: 28 },
      { value: '62 j', interpretation: 'Délai correct, cohérent avec le secteur.', barPct: 54 },
      { value: '38 j', interpretation: 'Encaissements rapides, bonne gestion du poste clients.', barPct: 87 },
    ],
  },
  {
    label: 'Marge EBITDA',
    formula: 'EBITDA / Chiffre d’affaires',
    tiers: [
      { value: '6,8%', interpretation: 'Marge opérationnelle sous la moyenne sectorielle.', barPct: 24 },
      { value: '12,4%', interpretation: 'Marge opérationnelle conforme au secteur.', barPct: 56 },
      { value: '18,7%', interpretation: 'Marge opérationnelle solide.', barPct: 89 },
    ],
  },
  {
    label: 'Fonds de roulement / BFR',
    formula: 'Fonds de roulement net / BFR',
    tiers: [
      { value: '−0,4x', interpretation: 'Fonds de roulement insuffisant pour couvrir le BFR.', barPct: 18 },
      { value: '0,9x', interpretation: 'Couverture juste du besoin en fonds de roulement.', barPct: 50 },
      { value: '1,6x', interpretation: 'BFR bien couvert par le fonds de roulement.', barPct: 83 },
    ],
  },
  {
    label: "Capacité d'autofinancement",
    formula: 'CAF / Chiffre d’affaires',
    tiers: [
      { value: '3,1%', interpretation: "CAF limitée, capacité d'investissement réduite.", barPct: 22 },
      { value: '7,4%', interpretation: 'CAF correcte pour soutenir l’activité.', barPct: 53 },
      { value: '13,2%', interpretation: "Bonne capacité d'autofinancement.", barPct: 85 },
    ],
  },
]

const TIER_STATUS: RatioStatus[] = ['BAD', 'WARN', 'GOOD']

function buildRatios(d: Dossier, tier: Tier): RatiosBlock {
  const seed = seedFromId(d.id)
  const items: RatioItem[] = RATIO_DEFS.map((def, i) => {
    const offset = [0, 0, -1, 1, 0, 1, -1, 0, 1, -1][i % 10]
    const t = tierAt(tier, (seed + i) % 3 === 0 ? offset : 0)
    const v = def.tiers[t]
    return {
      label: def.label,
      formula: def.formula,
      value: v.value,
      status: TIER_STATUS[t],
      barPct: v.barPct,
      interpretation: v.interpretation,
    }
  })

  const conformCount = items.filter((r) => r.status === 'GOOD').length
  const watchCount = items.length - conformCount

  const caN = d.amount * 2.6
  const caN1 = caN / (1 + (tier === 2 ? 0.14 : tier === 1 ? 0.05 : -0.06))

  const fiscal: RatiosBlock['fiscal'] = [
    { label: 'CA exercice N', value: formatAmountMad(caN), tone: 'neutral' },
    { label: 'CA exercice N-1', value: formatAmountMad(caN1), tone: 'neutral' },
    {
      label: 'Résultat net',
      value: formatAmountMad(caN * (0.012 + tier * 0.035)),
      tone: tier === 0 ? 'warn' : 'ok',
    },
    { label: 'EBITDA', value: formatAmountMad(caN * (0.07 + tier * 0.06)), tone: tier === 0 ? 'warn' : 'ok' },
    { label: 'Capitaux propres', value: formatAmountMad(d.amount * (0.6 + tier * 0.3)), tone: 'neutral' },
    {
      label: 'Endettement net',
      value: formatAmountMad(d.amount * (1.4 - tier * 0.35)),
      tone: tier === 0 ? 'warn' : 'neutral',
    },
  ]

  return {
    calcTime: '1,8s',
    conformCount,
    watchCount,
    items,
    fiscal,
  }
}



const FACTORS_BY_TIER: Record<Tier, Array<{ label: string; impact: number }>> = {
  2: [
    { label: 'Ancienneté de la relation bancaire', impact: 12 },
    { label: 'Rentabilité nette solide', impact: 9 },
    { label: 'Historique de remboursement', impact: 8 },
    { label: 'Secteur en croissance', impact: 5 },
    { label: 'Endettement résiduel', impact: -4 },
  ],
  1: [
    { label: "Chiffre d'affaires stable", impact: 7 },
    { label: 'Ancienneté de l’entreprise', impact: 5 },
    { label: 'Garanties proposées', impact: 4 },
    { label: "Taux d'endettement élevé", impact: -8 },
    { label: 'Concentration de la clientèle', impact: -6 },
  ],
  0: [
    { label: 'Garantie hypothécaire proposée', impact: 6 },
    { label: 'Rentabilité en baisse', impact: -12 },
    { label: 'Trésorerie tendue', impact: -10 },
    { label: 'Retards de paiement fournisseurs', impact: -7 },
    { label: 'Ancienneté limitée de la relation', impact: -5 },
  ],
}

const RECO_BY_TIER: Record<Tier, string> = {
  2: 'Approbation recommandée',
  1: 'Approbation sous conditions',
  0: 'Rejet recommandé ou complément d’analyse',
}

const RISK_LABEL_BY_TIER: Record<Tier, string> = {
  2: 'Risque faible',
  1: 'Risque modéré',
  0: 'Risque élevé',
}

function buildScoring(d: Dossier, tier: Tier, ratios: RatiosBlock, completenessPct: number): ScoringBlock {
  const growth = tier === 2 ? [0.09, 0.13] : tier === 1 ? [0.03, 0.05] : [-0.04, -0.09]
  const caN2 = d.amount * 2.6
  const caN1 = caN2 / (1 + growth[1])
  const caN0 = caN1 / (1 + growth[0])
  const cas = [caN0, caN1, caN2]
  const maxCa = Math.max(...cas)
  const rns = cas.map((ca) => ca * (0.015 + tier * 0.03))
  const maxRn = Math.max(...rns, 1)

  return {
    score: d.score,
    classe: mockClasse(d.score),
    recommendation: RECO_BY_TIER[tier],
    riskLabel: RISK_LABEL_BY_TIER[tier],
    summary:
      tier === 2
        ? `${d.name} présente un profil financier solide, une structure de bilan équilibrée et un historique de remboursement sans incident. Le dossier est cohérent avec la politique de risque en vigueur pour le secteur ${d.sector.toLowerCase()}.`
        : tier === 1
          ? `${d.name} affiche des fondamentaux corrects mais perfectibles : endettement à surveiller et quelques points de vigilance sur la trésorerie. Une approbation sous conditions (garanties, reporting périodique) est envisageable.`
          : `${d.name} présente plusieurs signaux de fragilité (rentabilité, trésorerie, endettement) qui appellent une analyse complémentaire ou des garanties renforcées avant toute décision d’octroi.`,
    modelConfidencePct: tier === 2 ? 94 : tier === 1 ? 87 : 79,
    ratiosOk: ratios.conformCount,
    ratiosTotal: ratios.items.length,
    dossierCompletenessPct: completenessPct,
    factors: FACTORS_BY_TIER[tier],
    trend: [
      { year: 'N-2', caLabel: formatAmountShort(caN0), caHeightPct: Math.round((caN0 / maxCa) * 100), rnHeightPct: Math.round((rns[0] / maxRn) * 100) },
      { year: 'N-1', caLabel: formatAmountShort(caN1), caHeightPct: Math.round((caN1 / maxCa) * 100), rnHeightPct: Math.round((rns[1] / maxRn) * 100) },
      { year: 'N', caLabel: formatAmountShort(caN2), caHeightPct: Math.round((caN2 / maxCa) * 100), rnHeightPct: Math.round((rns[2] / maxRn) * 100) },
    ],
    trendCaption:
      tier === 2
        ? `Chiffre d’affaires en croissance continue sur 3 exercices (+${Math.round(growth[0] * 100)}% / +${Math.round(growth[1] * 100)}%).`
        : tier === 1
          ? 'Chiffre d’affaires globalement stable sur les 3 derniers exercices.'
          : 'Chiffre d’affaires en repli sur les 2 derniers exercices, à surveiller.',
    attention:
      tier === 2
        ? {
            pointsForts: [
              "Croissance solide du chiffre d'affaires (+12,6 %), largement au-dessus de la médiane sectorielle (+6 %) et de la croissance du secteur au niveau national (+5,9 %).",
              'Structure financière saine : autonomie financière à 25 %, trésorerie et fonds de roulement positifs.',
              'Comportement bancaire irréprochable : aucun incident sur 24 mois, bonne domiciliation du CA (96 %).',
              'Bon positionnement sectoriel : au-dessus de la médiane sur 4 indicateurs sur 5.',
            ],
            pointsVigilance: [
              'Rentabilité commerciale (3,84 %) sous le repère indicatif et sous la médiane sectorielle.',
              'Délais clients élevés (78 jours), supérieurs aux délais fournisseurs (64 jours).',
              "Recours ponctuel au découvert (41 jours/an, 38 % de l'autorisation) et léger écart flux bancaires / CA déclaré (-4,2 %).",
              'Endettement global après la nouvelle opération en hausse à 2,61x les fonds propres.',
            ],
            scoreFinal:
              'Score final : 83 / 100 — Classe A/B+ « Bon » — Accord avec conditions standards recommandé, sous réserve de la confirmation de la cotation BAM (absence de critère bloquant).',
          }
        : {
            pointsForts: [],
            pointsVigilance: [
              'Plusieurs ratios financiers à surveiller (endettement, rentabilité).',
            ],
            scoreFinal: `Score final : ${d.score} / 100 — ${RECO_BY_TIER[tier]}.`,
          },
  }
}



function buildBien(d: Dossier, tier: Tier): BienBlock {
  const asset = assetFor(d.sector)
  const qty = d.amount > 6_000_000 ? 3 : d.amount > 2_500_000 ? 2 : 1
  const unitValue = Math.round(d.amount / qty)
  const durationLabel = `${d.duration} mois`
  const residualPct = 5
  const residual = Math.round(d.amount * (residualPct / 100))
  const apportPct = 20
  const apport = Math.round(d.amount * (apportPct / 100))
  const financed = d.amount - apport

  const totalCost = Math.round(financed * 1.14)
  const creditCost = totalCost - financed
  const monthly = Math.round((financed + creditCost - residual) / d.duration)

  return {
    title: asset.title,
    subtitle: `${d.sector} · ${qty} unité(s) financée(s)`,
    assetValueLabel: formatAmountMad(d.amount),
    financedLabel: formatAmountMad(financed),
    durationLabel,
    residualLabel: formatAmountMad(residual),
    units: Array.from({ length: qty }, (_, i) => ({
      qty: '1',
      designation: asset.designation,
      marque: asset.marque,
      modele: `${asset.modele}${qty > 1 ? ` (unité ${i + 1})` : ''}`,
      annee: '2025',
      valeur: formatAmountMad(unitValue),
    })),
    totalTtcLabel: formatAmountMad(d.amount),
    specs: [
      { key: 'Apport initial', value: `${formatAmountMad(apport)} (${apportPct}%)` },
      { key: 'Montant financé', value: formatAmountMad(financed) },
      { key: 'Valeur résiduelle', value: `${formatAmountMad(residual)} (${residualPct}%)` },
      { key: 'Durée du contrat', value: durationLabel },
      { key: 'Périodicité des loyers', value: 'Mensuelle' },
      { key: 'Taux indicatif', value: tier === 2 ? '5,9%' : tier === 1 ? '6,7%' : '7,8%' },
    ],
    schedule: [
      { label: 'Dépôt de garantie', count: '1', amount: formatAmountMad(Math.round(financed * 0.05)) },
      { label: 'Loyers mensuels', count: `${d.duration}`, amount: formatAmountMad(monthly), highlight: true },
      { label: 'Valeur résiduelle finale', count: '1', amount: formatAmountMad(residual) },
    ],
    totalCostLabel: formatAmountMad(totalCost),
    creditCostLabel: formatAmountMad(creditCost),
    guarantees: [
      { ok: true, title: 'Nantissement du matériel financé', detail: 'Premier rang, au profit de Wafabail' },
      { ok: tier !== 0, title: 'Caution personnelle du gérant', detail: 'Engagement solidaire et indivisible' },
      { ok: true, title: 'Assurance tous risques', detail: 'Couverture valeur à neuf, souscrite à la mise en place' },
      { ok: tier === 2, title: 'Domiciliation des flux d’exploitation', detail: 'Compte d’exploitation principal domicilié' },
    ],
  }
}

function buildBienFromDetail(d: Dossier, detail: DossierDetail, tier: Tier): BienBlock {
  const base = buildBien(d, tier)
  const apportPct =
    detail.valeurBien > 0 ? Math.round((detail.apport / detail.valeurBien) * 100) : 0
  const financed = detail.amount
  const residualPct = 5
  const residual = Math.round(financed * (residualPct / 100))
  const totalCost = Math.round(financed * 1.14)
  const creditCost = totalCost - financed
  const monthly = Math.round((financed + creditCost - residual) / Math.max(detail.duration, 1))

  return {
    ...base,
    title: detail.natureBien || base.title,
    subtitle: `${detail.fournisseur} · ${detail.etat === 'neuf' ? 'Neuf' : 'Occasion'} · Ref. ${detail.proformaReference}`,
    assetValueLabel: formatAmountMad(detail.valeurBien),
    financedLabel: formatAmountMad(financed),
    durationLabel: `${detail.duration} mois`,
    residualLabel: formatAmountMad(residual),
    units: [
      {
        qty: '1',
        designation: detail.natureBien,
        marque: detail.fournisseur,
        modele: detail.proformaReference,
        annee: String(new Date().getFullYear()),
        valeur: formatAmountMad(detail.valeurTtc),
      },
    ],
    totalTtcLabel: formatAmountMad(detail.valeurTtc),
    specs: [
      { key: 'Apport initial', value: `${formatAmountMad(detail.apport)} (${apportPct}%)` },
      { key: 'Montant financé', value: formatAmountMad(financed) },
      { key: 'Valeur résiduelle', value: `${formatAmountMad(residual)} (${residualPct}%)` },
      { key: 'Durée du contrat', value: `${detail.duration} mois` },
      { key: 'Périodicité des loyers', value: 'Mensuelle' },
      { key: 'Taux indicatif', value: tier === 2 ? '5,9%' : tier === 1 ? '6,7%' : '7,8%' },
    ],
    schedule: [
      {
        label: 'Dépôt de garantie',
        count: '1',
        amount: formatAmountMad(Math.round(financed * 0.05)),
      },
      {
        label: 'Loyers mensuels',
        count: `${detail.duration}`,
        amount: formatAmountMad(monthly),
        highlight: true,
      },
      { label: 'Valeur résiduelle finale', count: '1', amount: formatAmountMad(residual) },
    ],
    totalCostLabel: formatAmountMad(totalCost),
    creditCostLabel: formatAmountMad(creditCost),
  }
}



function buildFactorielle(d: Dossier, tier: Tier): FactorAxis[] {
  const growTone = (t: Tier): 'up' | 'flat' | 'down' => (t === 2 ? 'up' : t === 1 ? 'flat' : 'down')
  const axes: Array<Omit<FactorAxis, 'ratios'> & { ratios: Array<{ label: string; tierValue: [string, string, string]; statusTier?: Tier }> }> = [
    {
      num: '01',
      title: 'Structure financière',
      unit: 'MAD',
      rows: [
        { label: 'Capitaux propres', y1: formatAmountShort(d.amount * 0.5), y2: formatAmountShort(d.amount * 0.6), y3: formatAmountShort(d.amount * (0.6 + tier * 0.25)), variation: tier === 2 ? '+18%' : tier === 1 ? '+6%' : '−4%', variationTone: growTone(tier) },
        { label: 'Dettes financières', y1: formatAmountShort(d.amount * 1.6), y2: formatAmountShort(d.amount * 1.4), y3: formatAmountShort(d.amount * (1.4 - tier * 0.3)), variation: tier === 2 ? '−15%' : tier === 1 ? '−5%' : '+9%', variationTone: growTone(2 - tier as Tier) },
        { label: 'Total bilan', y1: formatAmountShort(d.amount * 3.0), y2: formatAmountShort(d.amount * 3.2), y3: formatAmountShort(d.amount * 3.4), variation: '+6%', variationTone: 'up' },
      ],
      ratios: [
        { label: 'Autonomie financière', tierValue: ['18%', '31%', '46%'] },
        { label: "Taux d'endettement", tierValue: ['215%', '128%', '74%'] },
      ],
    },
    {
      num: '02',
      title: 'Rentabilité',
      unit: 'MAD',
      rows: [
        { label: 'Chiffre d’affaires', y1: formatAmountShort(d.amount * 2.3), y2: formatAmountShort(d.amount * 2.45), y3: formatAmountShort(d.amount * 2.6), variation: tier === 2 ? '+13%' : tier === 1 ? '+5%' : '−6%', variationTone: growTone(tier) },
        { label: 'EBITDA', y1: formatAmountShort(d.amount * 0.18), y2: formatAmountShort(d.amount * 0.22), y3: formatAmountShort(d.amount * (0.14 + tier * 0.1)), variation: tier === 2 ? '+21%' : tier === 1 ? '+4%' : '−11%', variationTone: growTone(tier) },
        { label: 'Résultat net', y1: formatAmountShort(d.amount * 0.03), y2: formatAmountShort(d.amount * 0.05), y3: formatAmountShort(d.amount * (0.012 + tier * 0.035)), variation: tier === 2 ? '+24%' : tier === 1 ? '+2%' : '−28%', variationTone: growTone(tier) },
      ],
      ratios: [
        { label: 'Rentabilité nette', tierValue: ['1,2%', '4,6%', '8,9%'] },
        { label: 'Marge EBITDA', tierValue: ['6,8%', '12,4%', '18,7%'] },
      ],
    },
    {
      num: '03',
      title: 'Liquidité & trésorerie',
      unit: 'MAD',
      rows: [
        { label: 'Trésorerie nette', y1: formatAmountShort(d.amount * 0.04), y2: formatAmountShort(d.amount * 0.02), y3: formatAmountShort(d.amount * (tier === 0 ? -0.03 : 0.05 + tier * 0.04)), variation: tier === 2 ? '+140%' : tier === 1 ? '+30%' : '−240%', variationTone: growTone(tier) },
        { label: 'Fonds de roulement', y1: formatAmountShort(d.amount * 0.12), y2: formatAmountShort(d.amount * 0.1), y3: formatAmountShort(d.amount * (0.05 + tier * 0.08)), variation: tier === 2 ? '+22%' : tier === 1 ? '+2%' : '−32%', variationTone: growTone(tier) },
        { label: 'BFR', y1: formatAmountShort(d.amount * 0.18), y2: formatAmountShort(d.amount * 0.2), y3: formatAmountShort(d.amount * 0.22), variation: '+10%', variationTone: 'flat' },
      ],
      ratios: [
        { label: 'Liquidité générale', tierValue: ['0,78', '1,14', '1,68'] },
        { label: 'FR / BFR', tierValue: ['−0,4x', '0,9x', '1,6x'] },
      ],
    },
    {
      num: '04',
      title: 'Exploitation',
      unit: 'jours',
      rows: [
        { label: 'Délai clients', y1: '71 j', y2: '66 j', y3: tier === 2 ? '38 j' : tier === 1 ? '62 j' : '97 j', variation: tier === 2 ? '−46%' : tier === 1 ? '−6%' : '+47%', variationTone: growTone(2 - tier as Tier) },
        { label: 'Délai fournisseurs', y1: '54 j', y2: '58 j', y3: tier === 2 ? '62 j' : tier === 1 ? '55 j' : '38 j', variation: tier === 2 ? '+7%' : tier === 1 ? '−5%' : '−31%', variationTone: growTone(tier) },
        { label: 'Rotation des stocks', y1: '78 j', y2: '70 j', y3: tier === 2 ? '41 j' : tier === 1 ? '68 j' : '112 j', variation: tier === 2 ? '−41%' : tier === 1 ? '−3%' : '+60%', variationTone: growTone(2 - tier as Tier) },
      ],
      ratios: [
        { label: 'Cycle d’exploitation net', tierValue: ['131 j', '95 j', '62 j'] },
        { label: 'Rotation actif', tierValue: ['0,6x', '0,9x', '1,3x'] },
      ],
    },
    {
      num: '05',
      title: 'Levier & endettement',
      unit: 'x',
      rows: [
        { label: 'Dette financière / EBITDA', y1: '4,8x', y2: '4,1x', y3: tier === 2 ? '1,9x' : tier === 1 ? '3,4x' : '6,2x', variation: tier === 2 ? '−54%' : tier === 1 ? '−17%' : '+51%', variationTone: growTone(2 - tier as Tier) },
        { label: 'DSCR', y1: '1,05x', y2: '1,18x', y3: tier === 2 ? '1,74x' : tier === 1 ? '1,25x' : '0,95x', variation: tier === 2 ? '+47%' : tier === 1 ? '+6%' : '−19%', variationTone: growTone(tier) },
        { label: 'Gearing', y1: '158%', y2: '142%', y3: tier === 2 ? '74%' : tier === 1 ? '128%' : '215%', variation: tier === 2 ? '−48%' : tier === 1 ? '−10%' : '+51%', variationTone: growTone(2 - tier as Tier) },
      ],
      ratios: [
        { label: 'Couverture du service de la dette', tierValue: ['0,95x', '1,25x', '1,74x'] },
        { label: "Taux d'endettement", tierValue: ['215%', '128%', '74%'] },
      ],
    },
  ]

  return axes.map((axis) => ({
    num: axis.num,
    title: axis.title,
    unit: axis.unit,
    rows: axis.rows,
    ratios: axis.ratios.map((r) => ({
      label: r.label,
      value: r.tierValue[tier],
      status: TIER_STATUS[r.statusTier ?? tier],
    })),
  }))
}



function buildComportement(d: Dossier, tier: Tier): BehaviourBlock {
  const seed = seedFromId(d.id)
  const baseK = Math.round((d.amount * 0.05) / 1000)
  const months = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']
  const drift = tier === 2 ? 1.06 : tier === 1 ? 1.0 : 0.92

  return {
    score: Math.round(40 + tier * 22 + (seed % 8)),
    profileLabel: tier === 2 ? 'Profil régulier, gestion saine' : tier === 1 ? 'Profil correct, quelques irrégularités' : 'Profil irrégulier, points de vigilance',
    summary:
      tier === 2
        ? 'Les encaissements sont réguliers et cohérents avec le chiffre d’affaires déclaré. Aucun incident de paiement recensé sur la période observée.'
        : tier === 1
          ? 'Les flux bancaires sont globalement cohérents avec l’activité déclarée, avec quelques pics de tension ponctuels sur la trésorerie.'
          : 'Plusieurs incidents et une utilisation fréquente du découvert autorisé traduisent une gestion de trésorerie sous tension.',
    metrics: [
      {
        label: 'Incidents de paiement (6 mois)',
        value: tier === 2 ? '0' : tier === 1 ? '1' : '3',
        tone: tier === 2 ? 'ok' : tier === 1 ? 'neutral' : 'warn',
        sub: 'Rejets de prélèvement / chèques impayés',
      },
      {
        label: 'Utilisation du découvert',
        value: tier === 2 ? '12%' : tier === 1 ? '41%' : '78%',
        tone: tier === 2 ? 'ok' : tier === 1 ? 'neutral' : 'warn',
        sub: 'Moyenne sur 6 mois glissants',
      },
      {
        label: 'Régularité des encaissements',
        value: tier === 2 ? 'Élevée' : tier === 1 ? 'Correcte' : 'Faible',
        tone: tier === 2 ? 'ok' : tier === 1 ? 'neutral' : 'warn',
        sub: 'Écart-type des flux mensuels',
      },
      {
        label: 'Solde moyen mensuel',
        value: formatAmountMad(baseK * 1000 * (0.8 + tier * 0.3)),
        tone: 'neutral',
        sub: 'Compte d’exploitation principal',
      },
    ],
    months: months.map((m, i) => ({
      label: m,
      valueK: Math.round(baseK * drift ** i * (0.9 + ((seed + i) % 5) * 0.04)),
    })),
    signals:
      tier === 2
        ? [
            { tone: 'ok', title: 'Aucun impayé détecté sur 6 mois', detail: 'Historique de remboursement sans incident sur l’ensemble des comptes analysés.' },
            { tone: 'ok', title: 'Encaissements cohérents avec la liasse fiscale', detail: 'Écart inférieur à 5% entre CA déclaré et flux bancaires observés.' },
          ]
        : tier === 1
          ? [
              { tone: 'warn', title: 'Un dépassement ponctuel du découvert autorisé', detail: 'Observé en mars, régularisé sous 5 jours ouvrés.' },
              { tone: 'ok', title: 'Encaissements globalement réguliers', detail: 'Légère saisonnalité cohérente avec le secteur d’activité.' },
            ]
          : [
              { tone: 'warn', title: '3 incidents de paiement sur 6 mois', detail: 'Rejets de prélèvement fournisseurs, dont 1 non régularisé à date.' },
              { tone: 'warn', title: 'Utilisation quasi permanente du découvert', detail: 'Solde négatif sur plus de 60% des jours ouvrés observés.' },
            ],
  }
}



function buildBenchmark(d: Dossier, tier: Tier): BenchmarkBlock {
  const rows: BenchmarkBlock['rows'] = [
    { label: 'Rentabilité nette', client: tier === 2 ? '8,9%' : tier === 1 ? '4,6%' : '1,2%', median: '5,1%', clientPct: tier === 2 ? 89 : tier === 1 ? 46 : 12, medianPct: 51, tone: tier === 0 ? 'bad' : 'ok', percentile: tier === 2 ? 'Top 15%' : tier === 1 ? 'Médiane' : 'Bottom 20%' },
    { label: "Taux d'endettement", client: tier === 2 ? '74%' : tier === 1 ? '128%' : '215%', median: '135%', clientPct: tier === 2 ? 74 : tier === 1 ? 100 : 100, medianPct: 68, tone: tier === 0 ? 'bad' : 'ok', percentile: tier === 2 ? 'Top 20%' : tier === 1 ? 'Médiane' : 'Bottom 15%' },
    { label: 'Liquidité générale', client: tier === 2 ? '1,68' : tier === 1 ? '1,14' : '0,78', median: '1,20', clientPct: tier === 2 ? 84 : tier === 1 ? 57 : 39, medianPct: 60, tone: tier === 0 ? 'bad' : 'ok', percentile: tier === 2 ? 'Top 25%' : tier === 1 ? 'Médiane' : 'Bottom 25%' },
    { label: 'Marge EBITDA', client: tier === 2 ? '18,7%' : tier === 1 ? '12,4%' : '6,8%', median: '11,8%', clientPct: tier === 2 ? 88 : tier === 1 ? 58 : 28, medianPct: 55, tone: tier === 0 ? 'bad' : 'ok', percentile: tier === 2 ? 'Top 18%' : tier === 1 ? 'Médiane' : 'Bottom 30%' },
  ]

  const others = getDossierStore().filter((o) => o.id !== d.id && o.sector === d.sector).slice(0, 3)
  const fallback = getDossierStore().filter((o) => o.id !== d.id).slice(0, 3)
  const comparablesSrc = others.length ? others : fallback

  return {
    sectorLabel: d.sector,
    sampleSize: 42,
    caption: `Comparaison basée sur ${42} dossiers ${d.sector.toLowerCase()} traités sur les 24 derniers mois.`,
    rows,
    aboveMedianLabel: tier === 2 ? 'Au-dessus de la médiane sur 4/4 indicateurs' : tier === 1 ? 'Dans la médiane sur 3/4 indicateurs' : 'Sous la médiane sur 3/4 indicateurs',
    comparables: comparablesSrc.map((o) => ({
      id: o.id,
      name: o.name,
      score: o.score,
      decision: STATUS_META[o.status].label,
      decisionTone: ['approved', 'active', 'contracting'].includes(o.status) ? 'ok' : 'warn',
      date: `${8 + (seedFromId(o.id) % 20)}/0${1 + (seedFromId(o.id) % 8)}/2025`,
    })),
  }
}



function buildMemo(d: Dossier, tier: Tier, scoring: ScoringBlock, ratios: RatiosBlock, comportement: BehaviourBlock): MemoBlock {
  const gradeLetter = mockClasse(d.score)
  const gradeLabel = mockGradeLabel(gradeLetter)
  const seed = seedFromId(d.id)

  return {
    title: `Mémo de crédit — ${d.name}`,
    subtitle: `Crédit-bail ${d.sector.toLowerCase()} · Comité de risque`,
    refLine: `Réf. ${d.id} · Généré le ${new Date().toLocaleDateString('fr-FR')}`,
    recommendation: scoring.recommendation,
    scoreLine: `Score composite ${d.score}/100 · Note ${gradeLetter} (${gradeLabel})`,
    clientGrid: [
      { label: 'Raison sociale', value: d.name },
      { label: 'ICE', value: `00${1000000000000 + seed}`.slice(0, 15) },
      { label: 'RC', value: `RC ${45000 + (seed % 9000)}` },
      { label: 'Secteur', value: d.sector },
      { label: 'Forme juridique', value: 'SARL' },
      { label: 'Montant demandé', value: formatAmountMad(d.amount) },
      { label: 'Durée', value: `${d.duration} mois` },
      { label: 'Analyste en charge', value: d.analyst },
    ],
    sections: [
      {
        title: 'Présentation de l’entreprise',
        paragraphs: [
          `${d.name} est une entreprise du secteur ${d.sector.toLowerCase()}, cliente de longue date sollicitant un financement en crédit-bail d’un montant de ${formatAmountMad(d.amount)} sur ${d.duration} mois.`,
          `Le dossier a été instruit via le pipeline d’analyse automatisée Wafabail (OCR, contrôle anti-fraude, scoring factoriel) avec une confiance modèle de ${scoring.modelConfidencePct}%.`,
        ],
      },
      {
        title: 'Analyse financière',
        table: {
          headers: ['Indicateur', 'N-2', 'N-1', 'N'],
          rows: [
            ['Chiffre d’affaires', scoring.trend[0].caLabel, scoring.trend[1].caLabel, scoring.trend[2].caLabel],
            ['Ratios conformes', '—', '—', `${ratios.conformCount}/${ratios.items.length}`],
          ],
        },
        tableNote: 'Détail complet des ratios disponible dans l’onglet Ratios financiers.',
      },
      {
        title: 'Analyse factorielle & comportementale',
        paragraphs: [scoring.summary, comportement.summary],
        chips: [
          { ok: tier !== 0, label: 'Structure financière', value: tier === 2 ? 'Solide' : tier === 1 ? 'Correcte' : 'Fragile' },
          { ok: tier !== 0, label: 'Comportement bancaire', value: comportement.profileLabel },
          { ok: ratios.conformCount >= ratios.items.length / 2, label: 'Ratios conformes', value: `${ratios.conformCount}/${ratios.items.length}` },
        ],
      },
      {
        title: 'Risques identifiés',
        risks:
          tier === 0
            ? [
                { tone: 'warn', text: 'Rentabilité nette et marge opérationnelle sous la moyenne sectorielle.' },
                { tone: 'warn', text: 'Incidents de paiement recensés sur les relevés bancaires des 6 derniers mois.' },
                { tone: 'info', text: 'Documents fiscaux 2021 manquants — à réclamer avant décision finale.' },
              ]
            : tier === 1
              ? [
                  { tone: 'warn', text: "Taux d'endettement au-dessus de la médiane sectorielle." },
                  { tone: 'info', text: 'Concentration client à surveiller sur les prochains exercices.' },
                ]
              : [{ tone: 'info', text: 'Aucun risque majeur identifié à date sur ce dossier.' }],
      },
      {
        title: 'Conditions suggérées',
        conditions:
          tier === 2
            ? ['Nantissement du matériel financé', 'Assurance tous risques obligatoire', 'Reporting financier annuel']
            : tier === 1
              ? ['Nantissement du matériel financé', 'Caution personnelle du gérant', 'Reporting financier semestriel', 'Domiciliation des flux d’exploitation']
              : ['Garantie hypothécaire complémentaire', 'Caution personnelle solidaire', 'Reporting financier trimestriel', 'Complément d’enquête avant décision finale'],
      },
      {
        title: 'Conclusion',
        conclusionBanner: `${scoring.recommendation} — Score ${d.score}/100 (${mockClasse(d.score)})`,
        paragraphs: [
          tier === 2
            ? 'Le dossier réunit les conditions favorables à une approbation dans les meilleurs délais.'
            : tier === 1
              ? 'Le dossier peut être approuvé sous réserve des conditions et garanties listées ci-dessus.'
              : 'Un complément d’instruction ou un renforcement des garanties est recommandé avant toute décision d’octroi.',
        ],
      },
    ],
    signerName: d.analyst,
    signerRole: 'Analyste risques crédit-bail',
    signedAt: '',
  }
}



function buildPipeline(d: Dossier, tier: Tier, score: number) {
  const steps = [
    { label: 'Réception & indexation du dossier', meta: '0,4s' },
    { label: 'OCR & extraction des documents', meta: '2,1s' },
    { label: 'Vérification identité (ICE / RC)', meta: '0,8s' },
    { label: 'Contrôle anti-fraude', meta: '1,2s' },
    { label: 'Analyse financière & calcul des ratios', meta: '1,6s' },
    { label: 'Analyse factorielle', meta: '1,1s' },
    { label: 'Analyse comportementale bancaire', meta: '1,4s' },
    { label: 'Benchmark sectoriel', meta: '0,9s' },
    { label: 'Génération du score & du mémo', meta: '0,7s' },
  ]

  const fullTrace = [
    { type: 'in' as const, text: `Réception du dossier ${d.id} — ${d.name}`, step: 0 },
    { type: 'ok' as const, text: 'Dossier indexé et mis en file de traitement', step: 0 },
    { type: 'in' as const, text: 'Lancement OCR sur les pièces jointes', step: 1 },
    { type: 'ok' as const, text: 'Extraction terminée — champs financiers structurés', step: 1 },
    { type: 'in' as const, text: 'Contrôle ICE / RC auprès des registres officiels', step: 2 },
    { type: 'ok' as const, text: 'Identité de l’entreprise confirmée', step: 2 },
    { type: 'in' as const, text: 'Analyse anti-fraude (documents, cohérence des montants)', step: 3 },
    {
      type: tier === 0 ? ('warn' as const) : ('ok' as const),
      text: tier === 0 ? 'Anomalie mineure détectée — signalée pour revue humaine' : 'Aucune anomalie détectée',
      step: 3,
    },
    { type: 'in' as const, text: 'Calcul des ratios financiers (liasse fiscale)', step: 4 },
    { type: 'ok' as const, text: `${tier === 2 ? '9' : tier === 1 ? '7' : '4'} ratios sur 10 jugés conformes`, step: 4 },
    { type: 'in' as const, text: 'Analyse factorielle multi-axes', step: 5 },
    { type: 'ok' as const, text: '5 axes analysés (structure, rentabilité, liquidité, exploitation, levier)', step: 5 },
    { type: 'in' as const, text: 'Analyse comportementale des relevés bancaires', step: 6 },
    {
      type: tier === 0 ? ('warn' as const) : ('ok' as const),
      text: tier === 0 ? 'Incidents de paiement détectés sur 6 mois' : 'Comportement bancaire jugé sain',
      step: 6,
    },
    { type: 'in' as const, text: 'Comparaison au benchmark sectoriel', step: 7 },
    { type: 'ok' as const, text: `Positionnement établi vs ${42} dossiers ${d.sector.toLowerCase()}`, step: 7 },
    { type: 'in' as const, text: 'Consolidation du score composite & rédaction du mémo', step: 8 },
    { type: 'res' as const, text: `Score final : ${score}/100 — ${RECO_BY_TIER[tier]}`, step: 8 },
  ]

  return {
    policyVersion: 'Politique de risque v3.2 — crédit-bail PME',
    steps,
    fullTrace,
    initialStep: steps.length,
    initialScore: score,
  }
}



function buildCopilot(d: Dossier, tier: Tier, scoring: ScoringBlock, ratios: RatiosBlock) {
  return {
    welcomeMessage: `Bonjour, je suis le copilote d’analyse pour le dossier ${d.name}. Posez-moi une question sur le score, les risques ou le secteur.`,
    chips: [
      { label: 'Pourquoi ce score ?', intent: 'pourquoi' as const },
      { label: 'Quel est le principal risque ?', intent: 'risque' as const },
      { label: 'Le dossier est-il complet ?', intent: 'complet' as const },
      { label: 'Comment se compare-t-il au secteur ?', intent: 'secteur' as const },
    ],
    qa: {
      pourquoi: `Le score de ${d.score}/100 s’explique principalement par : ${scoring.factors
        .slice(0, 3)
        .map((f) => `${f.label} (${f.impact > 0 ? '+' : ''}${f.impact} %)`)
        .join(', ')}. ${scoring.summary}`,
      risque: tier === 0
        ? 'Le principal risque identifié concerne la trésorerie tendue et les incidents de paiement détectés sur les relevés bancaires des 6 derniers mois.'
        : tier === 1
          ? "Le principal point de vigilance est le taux d'endettement, au-dessus de la médiane sectorielle."
          : 'Aucun risque majeur identifié — le principal point d’attention reste l’endettement résiduel, à un niveau maîtrisé.',
      complet: `Le dossier est complet à ${scoring.dossierCompletenessPct}%. ${
        scoring.dossierCompletenessPct >= 90
          ? 'Toutes les pièces essentielles ont été reçues et vérifiées.'
          : 'Certaines pièces restent à réclamer avant la décision finale (voir panneau Documents).'
      }`,
      secteur: `Sur les ${ratios.items.length} ratios analysés, ${ratios.conformCount} sont jugés conformes. Comparé aux dossiers similaires du secteur ${d.sector.toLowerCase()}, ce client se positionne ${
        tier === 2 ? 'au-dessus de la médiane' : tier === 1 ? 'dans la médiane' : 'en-dessous de la médiane'
      } sur la majorité des indicateurs.`,
      fallback:
        "Je n'ai pas assez d'éléments pour répondre précisément à cette question sur ce dossier. Essayez de reformuler ou consultez les onglets Ratios, Facteurs ou Comportement pour plus de détails.",
    },
  }
}



function buildHeader(d: Dossier) {
  const meta = STATUS_META[d.status]
  return {
    id: d.id,
    shortCode: initials(d.name),
    companyName: d.name,
    subtitle: `${d.sector} · SARL · ${SECTOR_LOCATION[d.sector] ?? 'Casablanca, Maroc'}`,
    status: d.status,
    statusLabel: meta.label,
    analyst: d.analyst,
    amountFinanced: d.amount,
    assetValue: d.amount,
    durationMonths: d.duration,
    apportPct: 20,
    location: SECTOR_LOCATION[d.sector] ?? 'Casablanca, Maroc',
  }
}

function buildHeaderFromDetail(d: Dossier, detail: DossierDetail) {
  const meta = STATUS_META[d.status]
  const apportPct =
    detail.valeurBien > 0 ? Math.round((detail.apport / detail.valeurBien) * 100) : 0
  const natureLabel = detail.nature === 'immobilier' ? 'Immobilier' : 'Mobilier'
  return {
    id: d.id,
    shortCode: initials(detail.name),
    companyName: detail.name,
    subtitle: `${detail.sector} · ${natureLabel}${detail.ice ? ` · ICE ${detail.ice}` : ''}`,
    status: d.status,
    statusLabel: meta.label,
    analyst: detail.analyst,
    amountFinanced: detail.amount,
    assetValue: detail.valeurBien,
    durationMonths: detail.duration,
    apportPct,
    location: SECTOR_LOCATION[detail.sector] ?? 'Casablanca, Maroc',
  }
}



export function buildAnalyseWorkspace(d: Dossier, detail?: DossierDetail | null): AnalyseWorkspace {
  const tier = tierOf(d.score)
  const useDetailDocs = Boolean(detail && (d.status === 'pending' || detail.files.length > 0))
  const documents =
    detail && useDetailDocs
      ? buildDocumentsFromDetail(d, detail, tier)
      : buildDocuments(d, tier)
  const ratios = buildRatios(d, tier)
  const scoring = buildScoring(d, tier, ratios, documents.completenessPct)
  const bien = detail ? buildBienFromDetail(d, detail, tier) : buildBien(d, tier)
  const factorielle = buildFactorielle(d, tier)
  const comportement = buildComportement(d, tier)
  const benchmark = buildBenchmark(d, tier)
  const memo = buildMemo(d, tier, scoring, ratios, comportement)
  const pipeline = buildPipeline(d, tier, d.score)
  const copilot = buildCopilot(d, tier, scoring, ratios)

  return {
    header: detail ? buildHeaderFromDetail(d, detail) : buildHeader(d),
    pipeline,
    documents,
    scoring,
    ratios,
    bien,
    factorielle,
    comportement,
    sectorAnalysis: {
      status: 'UNAVAILABLE',
      sector: { mappingStatus: 'UNMATCHED' },
      dataFreshness: { status: 'UNAVAILABLE', source: 'HCP' },
      headline: { latestSectorVa: null, latestYear: null, nominalGrowthYoy: null, realGrowthYoy: null, cagr3y: null },
      sectorAnnualCurrent: [],
      sectorAnnualReal: [],
      sectorQuarterly: [],
      companyAnnual: [],
      normalizedComparison: [],
      growthComparison: [],
      comparableIndicators: [],
      warnings: ['Données HCP non synchronisées en mode démo.'],
      scoring: { status: 'NOT_CALIBRATED', includedInFinalScore: false, score: null },
    },
    benchmark,
    memo,
    copilot,
  }
}

export function getMockAnalyseWorkspace(
  id: string,
  dossierOverride?: Dossier | null,
  detail?: DossierDetail | null,
): AnalyseWorkspace | null {
  const dossier =
    dossierOverride ?? getDossierStore().find((d) => d.id === id) ?? null
  if (!dossier) return null
  return buildAnalyseWorkspace(dossier, detail)
}
