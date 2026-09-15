# Mapping activité entreprise → branche HCP

Déterministe uniquement (EXACT, ALIAS, KEYWORD). Qwen ne valide jamais un secteur.

| Statut | Signification |
|---|---|
| MATCHED | confiance ≥ 0,75, branche unique |
| REVIEW_REQUIRED | plusieurs mots-clés ou confiance insuffisante |
| UNMATCHED | aucun rapprochement |

Aucun fallback « Transport ». Aucun fallback vers un autre secteur.

Entrées : `identity.activite` DGI, `sector_raw`, `sector_normalized`.

Le dropdown frontend « Commerce » n’est pas la source unique.

Codes internes : `HCP_CONSTRUCTION`, `HCP_COMMERCE`, `HCP_EQUIPEMENTS_ELECTRIQUES`, etc. — alignés sur les libellés officiels data_12_29.

`benchmark_sector_code` reste null tant qu’un mapping métier Wafabail n’est pas validé (TODO_WAFABAIL_POLICY_VALIDATION).
