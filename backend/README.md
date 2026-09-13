# API backend WFB (Wafabail Smart Dashboard)

Documentation de **toutes les routes** du backend FastAPI : rôle, entrée, sortie, erreurs, exemples.

- **Base URL** : `http://127.0.0.1:8000`
- **Préfixe métier** : `/api/v1`
- **Swagger** : [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc** : [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Auth** : aucune sur les routes UI. Les routes **partenaire PVC** exigent `X-API-Key` — voir [README-API-PVC.md](README-API-PVC.md).

## Démarrer l’API

```powershell
cd WFB\backend
.\.venv\Scripts\activate
copy .env.example .env   # une seule fois
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Sans Docker : `STORAGE_BACKEND=local`, `KAFKA_ENABLED=false`. Les PDF sont dans `data/files/`, les dossiers dans `data/dossiers.json`.

L’extraction scoring et le copilote appellent **Ollama** (`RCC_OLLAMA_URL` dans `.env`).

---

## Catalogue

| Méthode | URL | Rôle |
|---|---|---|
| `GET` | `/health` | Santé du serveur |
| `GET` | `/api/v1/dashboard` | KPIs + file d’attente + alertes |
| `GET` | `/api/v1/dossiers` | Liste des dossiers |
| `POST` | `/api/v1/dossiers` | Créer un dossier **et lancer l’analyse** |
| `GET` | `/api/v1/dossiers/{id}` | Résumé liste (carte dossier) |
| `GET` | `/api/v1/dossiers/{id}/detail` | Dossier complet + fichiers |
| `POST` | `/api/v1/dossiers/{id}/approve` | Décision : approuver |
| `POST` | `/api/v1/dossiers/{id}/reject` | Décision : rejeter |
| `POST` | `/api/v1/dossiers/{id}/reserve` | Décision : sous réserve |
| `POST` | `/api/v1/dossiers/{id}/cancel` | Annuler la décision → `pending` |
| `POST` | `/api/v1/dossiers/{id}/documents/replace` | Ajouter / remplacer un fichier |
| `POST` | `/api/v1/dossiers/{id}/analyse/jobs` | Relancer l’analyse scoring |
| `GET` | `/api/v1/dossiers/{id}/analyse` | État du job + workspace UI |
| `GET` | `/api/v1/dossiers/{id}/synthese` | Points forts / vigilance / score |
| `POST` | `/api/v1/dossiers/{id}/copilot` | Question au copilote Qwen |
| `GET` | `/api/v1/analyse/jobs/{job_id}` | Progression d’un job |
| `GET` | `/api/v1/analyse/jobs/{job_id}/stream` | SSE de progression |
| `GET` | `/api/v1/analyse/jobs/{job_id}/result` | Résultat brut d’extraction + ratios |

Identifiant dossier : `XXX-YYYY-NNNN` (3 lettres de la raison sociale + année + 4 chiffres), ex. `ADE-2026-8502`.

Statuts dossier : `pending` · `analyzing` · `ready` · `reserved` · `approved` · `rejected`.

Statuts job d’analyse : `queued` · `processing` · `completed` · `failed`.

---

## Parcours type

```
1. POST /api/v1/dossiers          → id + job_id (analyse en file unique)
2. GET  .../analyse/jobs/{job}/stream   → suivre la progression (SSE)
3. GET  /api/v1/dossiers/{id}/analyse   → workspace (scores, ratios, factorielle)
4. GET  /api/v1/dossiers/{id}/synthese  → points d’attention
5. POST /api/v1/dossiers/{id}/copilot   → questions analyste
6. POST /api/v1/dossiers/{id}/approve   → décision
```

Un seul job GPU à la fois (`_PIPELINE_LOCK`). Les dossiers suivants restent en `queued` jusqu’à leur tour.

Les années des colonnes bilan (N / N-1 / N-2) viennent de la **période de la liasse** (page 1), pas du nom de fichier. N-2 n’apparaît que si une autre liasse plus ancienne est jointe.

---

## Santé

### `GET /health`

Vérifie que l’API tourne et quel mode de stockage / Kafka est actif.

**Entrée** : aucune.

**Sortie `200`**

```json
{
  "status": "ok",
  "storage": "local",
  "kafka": false
}
```

```bash
curl http://127.0.0.1:8000/health
```

---

## Dashboard

### `GET /api/v1/dashboard`

Alimente le tableau de bord : KPIs du jour, file à analyser, répartition de risque, secteurs, alertes, activité analyste. Calculé à partir des dossiers persistés.

**Entrée** : aucune.

**Sortie `200` — `DashboardData`**

| Champ | Type | Sens |
|---|---|---|
| `greeting` | string | Ex. `Bienvenue, K.` |
| `dateLabel` | string | Date du jour `dd/MM/yyyy` |
| `analystName` | string | Nom affiché |
| `kpis` | object | Compteurs (en cours, à analyser, approuvés, rejetés, encours) |
| `queue` | array | Jusqu’à 8 dossiers `pending` / `ready` |
| `queueTotal` | int | Nombre total en file |
| `riskDist` | array | Buckets `{ label, count, pct, tone }` (`mid` / `high`) |
| `riskActiveTotal` | int | Dossiers encore ouverts |
| `sectors` | array | `{ label, count }` |
| `alerts` | array | `{ id, type, message, time, tone, read }` |
| `activity` | object | `today`, `week`, `approvalRate`, `avgDelay` |

**KPIs (`kpis`)** : `inProgress`, `inProgressDelta`, `toAnalyze`, `toAnalyzeHint`, `approved`, `approvedDelta`, `approvedMonth`, `rejected`, `rejectedDelta`, `rejectedMonth`, `committedValue`, `committedHint`.

```bash
curl http://127.0.0.1:8000/api/v1/dashboard
```

---

## Dossiers

### `GET /api/v1/dossiers`

Liste filtrable pour l’écran « Dossiers ».

**Query**

| Paramètre | Type | Défaut | Sens |
|---|---|---|---|
| `status` | string | tous | `pending`, `analyzing`, `ready`, `reserved`, `approved`, `rejected`, ou `all` |
| `q` | string | — | Recherche dans id, nom, secteur, analyste (insensible à la casse) |

**Sortie `200`**

```json
{
  "items": [
    {
      "id": "ADE-2026-8502",
      "name": "ADEIS INVEST",
      "sector": "Immobilier",
      "amount": 2500000,
      "duration": 60,
      "score": 72,
      "status": "ready",
      "analyst": "K. Benali",
      "receivedDaysAgo": 0,
      "date": "18/08/2026",
      "urgency": "normale",
      "receivedLabel": "Auj. 14:02",
      "analyseStatus": "completed",
      "analyseProgressPct": null
    }
  ],
  "total": 1
}
```

```bash
curl "http://127.0.0.1:8000/api/v1/dossiers?status=ready&q=ADEIS"
```

---

### `POST /api/v1/dossiers`

Crée un dossier crédit-bail, enregistre les fichiers, publie un événement Kafka (si activé), puis **met l’analyse scoring en file** dès qu’une liasse PDF est présente.

**Content-Type** : `multipart/form-data`

| Champ | Type | Obligatoire | Sens |
|---|---|---|---|
| `data` | string JSON | oui | Métadonnées (voir ci-dessous) |
| `documents` | fichier(s) | oui (≥ 1) | Pièces entreprise (liasse, RC, CIN…). PDF / PNG / JPG, max **15 Mo** chacun |
| `proforma` | fichier | oui | Facture / proforma |

**JSON `data`**

```json
{
  "entreprise": {
    "ice": "001669862000005",
    "raisonSociale": "ADEIS INVEST",
    "rc": "12345/CASABLANCA",
    "secteur": "Immobilier",
    "documentNames": ["bilan.pdf"]
  },
  "financement": {
    "nature": "mobilier",
    "montantDemande": 2500000,
    "valeurBien": 3125000,
    "dureeMois": 60,
    "apport": 20,
    "urgence": "normale"
  },
  "fournisseurBien": {
    "fournisseur": "Atlas Equipements",
    "proformaReference": "PRO-2026-001",
    "proformaFileName": "proforma.pdf",
    "natureBien": "Engin de chantier",
    "etat": "neuf",
    "valeurHt": 2604167,
    "valeurTtc": 3125000
  }
}
```

`secteur` connu : Transport, Immobilier, BTP, Santé, Industrie, Commerce, Agriculture, Tourisme, Tech & Services, Énergie, Automobile, Éducation. Sinon → `Autre`.

`nature` : `mobilier` ou `immobilier`.  
`urgence` : typiquement `normale` ou `haute`.  
`etat` : typiquement `neuf` ou `occasion`.

**Sortie `201`**

Si une liasse PDF est détectée, l’analyse démarre (ou s’ajoute à la file) :

```json
{
  "id": "ADE-2026-8502",
  "status": "analyzing",
  "message": "Dossier ADE-2026-8502 créé — analyse lancée en file d'attente (job …).",
  "job_id": "a1b2c3d4…",
  "stream_url": "/api/v1/analyse/jobs/a1b2c3d4…/stream",
  "result_url": "/api/v1/analyse/jobs/a1b2c3d4…/result",
  "synthese_url": "/api/v1/dossiers/ADE-2026-8502/synthese",
  "filename": "ADEISINVEST-BILAN-2025.pdf"
}
```

Sans liasse PDF exploitable, le dossier est tout de même créé (`status: pending`, pas de `job_id`).

**Erreurs** : `400` payload / fichier manquant / type interdit / trop volumineux · `503` stockage indisponible.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dossiers ^
  -F "data=@payload.json;type=application/json" ^
  -F "documents=@liasse.pdf;type=application/pdf" ^
  -F "proforma=@facture.pdf;type=application/pdf"
```

Sous PowerShell, le JSON peut être passé en ligne :

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/dossiers `
  -F "data={\"entreprise\":{\"ice\":\"001669862000005\",\"raisonSociale\":\"ADEIS INVEST\",\"rc\":\"\",\"secteur\":\"Immobilier\",\"documentNames\":[]},\"financement\":{\"nature\":\"mobilier\",\"montantDemande\":2500000,\"valeurBien\":3125000,\"dureeMois\":60,\"apport\":20,\"urgence\":\"normale\"},\"fournisseurBien\":{\"fournisseur\":\"Atlas\",\"proformaReference\":\"PRO-1\",\"proformaFileName\":null,\"natureBien\":\"Engin\",\"etat\":\"neuf\",\"valeurHt\":2604167,\"valeurTtc\":3125000}}" `
  -F "documents=@C:\chemin\liasse.pdf" `
  -F "proforma=@C:\chemin\proforma.pdf"
```

---

### `GET /api/v1/dossiers/{id}`

Résumé pour les listes / en-tête (même schéma qu’un item de `GET /dossiers`).

**Erreurs** : `404` dossier introuvable.

```bash
curl http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502
```

---

### `GET /api/v1/dossiers/{id}/detail`

Dossier **complet** : identité, financement, bien, fichiers stockés, éventuellement le workspace d’analyse persisté.

**Sortie `200` — `StoredDossierRecord`**

Champs principaux en plus du résumé :

| Champ | Sens |
|---|---|
| `ice`, `rc` | Identifiants (complétés par l’OCR liasse s’ils étaient vides) |
| `nature`, `valeurBien`, `apport` | Contrat |
| `fournisseur`, `proformaReference`, `natureBien`, `etat`, `valeurHt`, `valeurTtc` | Bien |
| `files[]` | `{ name, objectKey, size, contentType, category }` (`entreprise` ou `proforma`) |
| `decisionDate` | Date de décision si approuvé / rejeté / réservé |
| `analyseJobId`, `analyseStatus` | Dernier job |
| `analyse` | Workspace UI (objet large, voir section Analyse) |

**Erreurs** : `404`.

```bash
curl http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/detail
```

---

### Décisions

Toutes **sans body**. Réponse = résumé `Dossier` avec le nouveau `status`.

| Route | Nouveau statut |
|---|---|
| `POST /api/v1/dossiers/{id}/approve` | `approved` |
| `POST /api/v1/dossiers/{id}/reject` | `rejected` |
| `POST /api/v1/dossiers/{id}/reserve` | `reserved` |
| `POST /api/v1/dossiers/{id}/cancel` | `pending` (annule la décision) |

**Erreurs** : `404`.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/approve
```

---

### `POST /api/v1/dossiers/{id}/documents/replace`

Ajoute un document **ou** remplace un fichier existant du même `name`. Maximum **20** fichiers. Autorisé quel que soit le statut du dossier.

**Content-Type** : `multipart/form-data`

| Champ | Type | Sens |
|---|---|---|
| `name` | string | Nom logique (ex. `liasse-2024.pdf`). S’il existe déjà → remplacement |
| `file` | fichier | PDF / PNG / JPG, max 15 Mo |

Si `name` contient `proforma` ou `facture`, la catégorie devient `proforma`, sinon `entreprise`.

**Sortie `200`** : `StoredDossierRecord` à jour (liste `files` rafraîchie dans le workspace).

**Erreurs** : `400` nom vide / trop de fichiers / type interdit · `404` · `503` stockage.

Après un ajout de liasse, relancer `POST .../analyse/jobs` pour ré-extraire.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/documents/replace ^
  -F "name=Bilan-2024.pdf" ^
  -F "file=@Bilan-2024.pdf;type=application/pdf"
```

---

## Analyse scoring (moteur RCC v10)

Pipeline : PDF liasse → OCR / vision Ollama → 20 postes RCC + agrégats scoring → ratios → score → workspace UI.

Choix de la liasse : parmi les PDF du dossier, priorité aux noms contenant `liasse`, `bilan` ou `cpc`, puis à l’année dans le nom. Jusqu’à **2 PDF extra** (années plus anciennes) pour remplir N-2.

### `POST /api/v1/dossiers/{id}/analyse/jobs`

Relance (ou reprend) l’analyse. Si un job `queued` / `processing` existe déjà pour ce dossier, il est **réutilisé** (pas de doublon).

**Query optionnelle**

| Paramètre | Type | Sens |
|---|---|---|
| `max_pages` | int | Limite de pages (1 … `RCC_MAX_PAGES`, défaut 60) |

**Sortie `200` — `AnalyseJobCreateResponse`**

```json
{
  "job_id": "a1b2c3d4…",
  "dossier_id": "ADE-2026-8502",
  "status": "queued",
  "stream_url": "/api/v1/analyse/jobs/a1b2c3d4…/stream",
  "result_url": "/api/v1/analyse/jobs/a1b2c3d4…/result",
  "filename": "ADEISINVEST-BILAN-2025.pdf"
}
```

**Erreurs** : `404` · `422` pas de liasse PDF / `max_pages` invalide / PDF corrompu · `503` lecture fichier.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/analyse/jobs?max_pages=20"
```

---

### `GET /api/v1/dossiers/{id}/analyse`

État **pour l’UI** : job en cours + workspace (scores, ratios, factorielle, documents, copilote, etc.).

**Sortie `200` — `AnalyseStateResponse`**

```json
{
  "dossier_id": "ADE-2026-8502",
  "job": {
    "job_id": "…",
    "dossier_id": "ADE-2026-8502",
    "status": "processing",
    "progress_pct": 42,
    "current_step": "extracting_page",
    "current_page": 3,
    "pages_total": 12,
    "pages_financial": 5,
    "pages_skipped": 2,
    "pages_failed": 0,
    "message": "Extraction page 3",
    "error": null,
    "stream_url": "/api/v1/analyse/jobs/…/stream",
    "result_url": "/api/v1/analyse/jobs/…/result",
    "filename": "…pdf"
  },
  "workspace": { },
  "error": null
}
```

`workspace` (clés principales) :

| Clé | Contenu UI |
|---|---|
| `header` | Entreprise, montant, durée, statut |
| `pipeline` | Étapes agent OCR / scoring |
| `documents` | Liste des pièces + champs extraits (ICE, RC, exercice, postes) |
| `scoring` | Score, classe, facteurs, tendance CA/RN, synthèse attention |
| `ratios` | Grille ratios + agrégats fiscaux |
| `bien` | Bien financé |
| `factorielle` | 3 axes, colonnes d’années, variations |
| `yearLabels` | Ex. `["—", "2024", "2025"]` (dates de liasse) |
| `comportement` | Axe comportemental (si calculé) |
| `benchmark` | Comparaison sectorielle |
| `memo` | Mémo d’analyse |
| `copilot` | Message d’accueil + puces |

**Erreurs** : `404`.

```bash
curl http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/analyse
```

---

### `GET /api/v1/dossiers/{id}/synthese`

Vue courte pour la carte « Synthèse et points d’attention » (sans tout le workspace).

**Sortie `200` — `DossierSyntheseResponse`**

| Champ | Sens |
|---|---|
| `status` | Statut du job (`pending` / `queued` / `processing` / `completed` / `failed`) |
| `job_id` | Dernier job |
| `points_forts` | Liste de phrases |
| `points_vigilance` | Liste de phrases |
| `score_final` | Texte de synthèse du score |
| `score` | 0–100 |
| `classe` | Ex. `A`, `B`, `C` |
| `decision` | Libellé risque |
| `recommandation` | Texte moteur |
| `message` | Info si l’analyse n’est pas encore prête |

```bash
curl http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/synthese
```

---

### `POST /api/v1/dossiers/{id}/copilot`

Pose une question à **Qwen 3.5** (`RCC_COPILOT_MODEL`). Le modèle ne voit que le contexte du dossier (score, ratios, synthèse, pièces). Il n’invente pas de chiffres absents.

**Body JSON — `CopilotChatRequest`**

| Champ | Type | Contrainte |
|---|---|---|
| `message` | string | 1–2000 caractères |
| `history` | array | Derniers tours `{ "role": "user" \| "assistant", "content": "…" }` (max 4000 car. / message) |

**Sortie `200`**

```json
{
  "reply": "Le score 72 classé B s’explique surtout par…",
  "model": "qwen3.5:9b"
}
```

**Erreurs** : `404` · `422` body invalide · `503` Ollama / modèle indisponible.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/dossiers/ADE-2026-8502/copilot ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Pourquoi ce score ?\",\"history\":[]}"
```

---

### `GET /api/v1/analyse/jobs/{job_id}`

Progression d’un job (même objet `job` que dans `/analyse`). Jobs expirés après `ANALYSE_JOB_TTL_MINUTES` (défaut 180 min) → `404`.

```bash
curl http://127.0.0.1:8000/api/v1/analyse/jobs/JOB_ID
```

---

### `GET /api/v1/analyse/jobs/{job_id}/stream`

**Server-Sent Events** (pas de JSON unique : flux `text/event-stream`). À utiliser pour une barre de progression.

Premier événement : `job_status`. Keepalive toutes les 25 s. Fin sur `result_ready` ou `job_failed`.

| Event SSE | Sens |
|---|---|
| `job_status` | Instantané initial |
| `job_started` | Traitement commencé |
| `pdf_validated` | PDF OK |
| `pages_rendered` | Pages prêtes |
| `page_classified` | Type de page (bilan, CPC, …) |
| `page_extracted` | Page extraite |
| `page_skipped` | Page ignorée |
| `page_failed` | Échec page |
| `resolving_fields` | Mapping des postes |
| `running_controls` | Contrôles comptables |
| `calculating_ratios` | Ratios |
| `scoring_computed` | Score calculé |
| `result_ready` | Terminé |
| `job_failed` | Erreur |

Chaque `data:` contient `job_id`, `status`, `progress_pct`, `current_step`, `current_page`, `pages_total`, `message`, `error`, etc.

```bash
curl -N http://127.0.0.1:8000/api/v1/analyse/jobs/JOB_ID/stream
```

---

### `GET /api/v1/analyse/jobs/{job_id}/result`

Résultat **technique** (extraction + ratios), pas le workspace UI.

**Sortie `200` — `ScoringAnalysisResult`**

| Champ | Sens |
|---|---|
| `document` | Fichier, pages, `company` (ICE, RC, raison sociale…), `exercise` (`debut` / `fin` / `label`) |
| `extraction` | Modèle, audit par page, warnings |
| `fields` | Postes 1–30 : `code`, `value`, `value_n1`, `status`, `evidence` |
| `completeness_pct` | % de postes renseignés |
| `controls` | Identités comptables (OK / écart) |
| `ratio_inputs` | Agrégats utilisés |
| `ratios` | Chaque ratio : `value`, `status` (`Conforme` / `À surveiller` / `Non conforme` / `Non calculable`) |
| `axes` | Notes par axe |
| `decision` | `score`, `classe`, `decision`, `recommandation` |
| `years` | `labels` (ex. `["—","2024","2025"]`), `series` (CA, RN, CAF… par colonne) |

**Erreurs** : `404` job expiré · `409` pas encore prêt · `422` job en échec.

```bash
curl http://127.0.0.1:8000/api/v1/analyse/jobs/JOB_ID/result
```

---

## Codes HTTP récurrents

| Code | Cas |
|---|---|
| `200` / `201` | OK |
| `400` | Fichier / JSON / nom de document invalide |
| `404` | Dossier ou job introuvable (ou job expiré) |
| `409` | Résultat d’analyse pas encore disponible |
| `422` | Pas de liasse, PDF invalide, job failed, validation Pydantic |
| `503` | Disque / MinIO / Ollama (copilote ou lecture PDF) |

Le `detail` FastAPI est une string ou un tableau de validation.

---

## Fichiers extraits (rappel)

Les **20 postes RCC** (EKIP) + **10 agrégats scoring** (fonds propres, stocks, CAF, FDR, BFR, etc.) sont dans `fields` du résultat et dans l’onglet documents du workspace.

ICE : souvent le bloc de **15 chiffres** en tête de page 1, même si la ligne `ICE :` est vide.

Exercice : `période du jj/mm/aaaa au jj/mm/aaaa` sur la page d’identification.
