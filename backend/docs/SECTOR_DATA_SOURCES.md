# Sources sectorielles

Provider CKAN : `HCP_CKAN_BASE_URL=https://data.gov.ma/data/api/3/action`

| Clé | Dataset | Métrique | Fréquence | Prix | Base | Parser | Statut |
|---|---|---|---|---|---|---|---|
| annual_va_current | data_12_29 | VALUE_ADDED | annuelle | courants | 2014 | HcpWorkbookParser | actif |
| annual_va_volume | data_12_28 | VALUE_ADDED | annuelle | volume chaîné | 2014 | idem | actif |
| quarterly_va_current | data_12_41 | VALUE_ADDED | trimestrielle CVS | courants | 2014 | idem | actif |
| quarterly_va_volume | data_12_40 | VALUE_ADDED | trimestrielle CVS | volume | 2014 | idem | actif |
| annual_gdp_current | data_12_26 | GDP | annuelle | courants | 2014 | — | **désactivé** (ne pas mélanger PIB et VA) |

APSF : provider stub, `enabled=false`, métrique `LEASING_MARKET_CONTEXT`.
Wafabail interne : `InternalPortfolioSectorProvider` NotImplemented, pas de taux de défaut.

Unité HCP annuelle observée : millions de DHS → affichée « M MAD » / « Md MAD ». Jamais multipliée arbitrairement.
