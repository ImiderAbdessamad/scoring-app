# UI Analyse sectorielle

Onglet interne `benchmark` (compat navigation), **label** : Analyse sectorielle.

Onglet `comportement`, **label** : Comportement bancaire.

Composants : `SectorAnalysisTab`, `BankingBehaviorTab`, graphiques SVG dans `SectorCharts.tsx`.

Pas de Recharts (cohérent avec les barres existantes). Pas de PIB si métrique VA.

KPI, tendance VA, indice 100 entreprise vs secteur, barres de croissance %, conjoncture réelle, trimestriel, provenance + bouton sync.

États vides : Analyse requise / mapping à confirmer / cache / indisponible.

Score : jamais 0 fictif — `NOT_CALIBRATED`, non intégré à la note.
