# API partenaire PVC → WFB (analyse de liasse)

Cette API permet à la plateforme **PVC / e-bail** d’envoyer un dossier (`PVC_DOSSIER_PV`) **avec le PDF de liasse fiscale**, de lancer **la même analyse** que le poste WFB (OCR v10 + ratios + score), puis de **retrouver le résultat** à tout moment via `noDemande`.

Les dossiers ainsi traités apparaissent aussi dans le **frontend WFB** (`/dossiers`), avec le badge `PVC`.

**Base URL :** `http://127.0.0.1:8000`  
**Swagger :** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (groupe *partenaire PVC*)

---

## Authentification (clé API)

Toutes les routes `/api/v1/partners/pvc/*` exigent une clé.

| | |
|---|---|
| Variable d’environnement | `PVC_API_KEY` |
| Fichier | `WFB/backend/.env` |
| Valeur fournie | `wfb_pvc_8f2c1a9d4e6b70c3a5d18e4f9b2c7a61` |
| En-tête | `X-API-Key: wfb_pvc_8f2c1a9d4e6b70c3a5d18e4f9b2c7a61` |

Équivalent accepté :

```http
Authorization: Bearer wfb_pvc_8f2c1a9d4e6b70c3a5d18e4f9b2c7a61
```

Sans clé → `401`. Clé absente du serveur → `503`.

> Changez cette valeur en production. Ne la commitez pas dans un dépôt public.

---

## Catalogue

| Méthode | URL | Rôle |
|---|---|---|
| `POST` | `/api/v1/partners/pvc/dossiers` | Envoyer le dossier PVC + PDF liasse, lancer l’analyse |
| `GET` | `/api/v1/partners/pvc/dossiers/{noDemande}` | Retrouver l’analyse par `noDemande` |

Identifiant unique PVC : **`noDemande`**. Un second envoi avec le même `noDemande` **met à jour** le dossier et **relance** l’analyse (idempotent).

---

## 1. Envoyer un dossier + liasse

### `POST /api/v1/partners/pvc/dossiers`

**Content-Type :** `multipart/form-data`

| Champ | Type | Obligatoire | Description |
|---|---|---|---|
| `data` | JSON (string) | oui | Objet **DossierPv** — **mêmes noms de colonnes** que la base PVC |
| `liasse` | fichier PDF | oui | Liasse fiscale / bilan |
| `liasses` | fichier(s) PDF | non | Exercices plus anciens (N-1 / N-2) |
| `max_pages` | query int | non | Plafond de pages (défaut 60) |

Réponse **202 Accepted** : le job GPU est **asynchrone** (plusieurs minutes). PVC doit ensuite **poller** le GET.

### JSON `data` — colonnes PVC_DOSSIER_PV

Envoyez un objet plat avec les noms ci-dessous (camelCase identique à votre dataset). Les champs non listés sont acceptés (`extra`) et stockés tels quels.

**Obligatoires :** `noDemande`, `nomClient`.

```json
{
  "id": 4412,
  "noPv": "PV-2026-8891",
  "noDemande": "DEM-2026-00412",
  "noTiers": "T-9981",
  "nomClient": "ADEIS INVEST",
  "typeClient": "PM",
  "montantTotal": 2500000,
  "redevanceTotal": 48000,
  "tauxStandard": 7.5,
  "tauxPropose": 6.9,
  "hasFraisDossier": true,
  "montantFraisDossier": 5000,
  "fournisseur": "Atlas Equipements",
  "dateReceptionEbail": "2026-08-18T10:15:00",
  "commercialNom": "S. El Amrani",
  "statutWorkflow": "EN_SYNTHESE",
  "typeComite": 1,
  "dateSynthese": null,
  "dateFinalisation": null,
  "enRAC": false,
  "racMotif": null,
  "racInitiePar": null,
  "dateInitiationRAC": null,
  "dateCreation": "2026-08-17T09:00:00",
  "rcAnalytique": "12345",
  "villeRC": "CASABLANCA",
  "formeJuridique": "SARL",
  "adresseSociale": "04 Rue Moliere",
  "capital": 100000,
  "telephone": "0522000000",
  "activite": "Immobilier",
  "ribDomiciliation": null,
  "banque": "AWB",
  "segmentMarche": null,
  "segmentationAWB": null,
  "segmentationWafabail": null,
  "noteInterneSysteme": null,
  "noteInterneAgree": null,
  "regionRisque": null,
  "dateEntretienClient": null,
  "garantiesCommercial": null,
  "cycleArbitrage": null,
  "versionNumber": 1,
  "escaladeAnalyste": false,
  "arbitragePresentielDeclenche": false,
  "remarques": null,
  "typeComiteArbitrage": null,
  "actionnaires": [
    {
      "nomPrenom": "Karim Benali",
      "quotePart": 60,
      "cin": "AB123456",
      "dateNaissance": "1980-01-15",
      "adresse": "Casablanca"
    }
  ],
  "mandataires": [
    {
      "nomPrenom": "Karim Benali",
      "qualite": "Gerant",
      "cin": "AB123456",
      "dateNaissance": "1980-01-15",
      "adresse": "Casablanca"
    }
  ],
  "simulations": [
    {
      "duree": 60,
      "redevance": 48000,
      "noContrat": "CB-2026-100",
      "biens": [
        {
          "description": "Engin de chantier",
          "neufOccasion": "neuf",
          "montantHT": 2083333
        }
      ]
    }
  ],
  "votes": [],
  "timeline": []
}
```

| Collection PVC | Colonnes |
|---|---|
| `actionnaires` | `nomPrenom`, `quotePart`, `cin`, `dateNaissance`, `adresse` |
| `mandataires` | `nomPrenom`, `qualite`, `cin`, `dateNaissance`, `adresse` |
| `simulations` | `duree`, `redevance`, `noContrat`, `biens` |
| `biens` | `description`, `neufOccasion`, `montantHT` |
| `votes`, `timeline` | transmises telles quelles |

`noDemande` : 3 à 80 caractères (`A-Z a-z 0-9 . _ : -`). Pas de slash.

### Mapping utilisé pour le scoring WFB

| Colonne PVC | Usage WFB |
|---|---|
| `noDemande` | Identifiant dossier (liste + GET) |
| `nomClient` | Raison sociale affichée |
| `montantTotal` | Montant financé |
| `simulations[0].duree` | Durée (mois) |
| `fournisseur` | Fournisseur |
| `simulations[0].biens[0].description` | Nature du bien |
| `neufOccasion` | `neuf` / `occasion` |
| `rcAnalytique` + `villeRC` | RC |
| `activite` | Secteur |
| `commercialNom` | Analyste / origine |
| `enRAC` | Urgence `haute` si true |
| PDF `liasse` | **Moteur OCR / scoring** |
| ICE | Lu sur la liasse (souvent absent de PVC) |

Le JSON PVC complet est renvoyé dans `dossier` du GET.

### Exemple curl (Windows)

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/partners/pvc/dossiers `
  -H "X-API-Key: wfb_pvc_8f2c1a9d4e6b70c3a5d18e4f9b2c7a61" `
  -F "data=@dossier-pvc.json;type=application/json" `
  -F "liasse=@C:\chemin\liasse-2025.pdf;type=application/pdf"
```

Avec une deuxième liasse (exercice N-2) :

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/v1/partners/pvc/dossiers `
  -H "X-API-Key: wfb_pvc_8f2c1a9d4e6b70c3a5d18e4f9b2c7a61" `
  -F "data=@dossier-pvc.json;type=application/json" `
  -F "liasse=@liasse-2025.pdf;type=application/pdf" `
  -F "liasses=@liasse-2023.pdf;type=application/pdf"
```

### Sortie `202`

```json
{
  "noDemande": "DEM-2026-00412",
  "noPv": "PV-2026-8891",
  "id": "4412",
  "wfb_id": "DEM-2026-00412",
  "nomClient": "ADEIS INVEST",
  "status": "analyzing",
  "message": "Dossier DEM-2026-00412 enregistré — analyse lancée (job …).",
  "job_id": "a1b2c3…",
  "stream_url": "/api/v1/analyse/jobs/a1b2c3…/stream",
  "result_url": "/api/v1/analyse/jobs/a1b2c3…/result",
  "poll_url": "/api/v1/partners/pvc/dossiers/DEM-2026-00412",
  "analyse_url": "/api/v1/partners/pvc/dossiers/DEM-2026-00412",
  "filename": "liasse-Bilan-2025.pdf"
}
```

**Erreurs :** `400` JSON / `noDemande` / fichier manquant · `401` clé · `422` pas un PDF · `503` stockage ou clé serveur.

---

## 2. Retrouver l’analyse par `noDemande`

### `GET /api/v1/partners/pvc/dossiers/{noDemande}`

C’est l’API à appeler **en boucle** (toutes les 10–30 s) jusqu’à `analyseStatus=completed` (ou `failed`).

```powershell
curl.exe http://127.0.0.1:8000/api/v1/partners/pvc/dossiers/DEM-2026-00412 `
  -H "X-API-Key: wfb_pvc_8f2c1a9d4e6b70c3a5d18e4f9b2c7a61"
```

### États (`analyseStatus`)

| Valeur | Signification | Action PVC |
|---|---|---|
| `pending` / `queued` / `processing` | Pas encore fini | Repoller |
| `completed` | Score + ratios + synthèse disponibles | Lire le JSON |
| `failed` | Erreur OCR / GPU | Lire `error`, renvoyer le PDF si besoin |

### Sortie `200` (extrait, une fois terminé)

```json
{
  "noDemande": "DEM-2026-00412",
  "noPv": "PV-2026-8891",
  "id": "4412",
  "wfb_id": "DEM-2026-00412",
  "nomClient": "ADEIS INVEST",
  "status": "ready",
  "analyseStatus": "completed",
  "job_id": "a1b2c3…",
  "progress_pct": 100,
  "score": 72,
  "classe": "B",
  "decision": "Moyen",
  "recommandation": "…",
  "points_forts": ["…"],
  "points_vigilance": ["…"],
  "score_final": "Score 72 — classe B",
  "ice": "001669862000005",
  "rc": "12345/CASABLANCA",
  "exercise": "Du 01/01/2025 au 31/12/2025",
  "year_labels": ["—", "2024", "2025"],
  "completeness_pct": 86.5,
  "ratios": [
    { "label": "Autonomie financière", "value": "32 %", "status": "WARN" }
  ],
  "dossier": { "noDemande": "DEM-2026-00412", "nomClient": "ADEIS INVEST" },
  "stream_url": "/api/v1/analyse/jobs/…/stream",
  "result_url": "/api/v1/analyse/jobs/…/result",
  "error": null
}
```

`dossier` = copie du JSON PVC d’origine (colonnes inchangées).

**Erreurs :** `401` · `404` `noDemande` inconnu.

Progression temps réel (optionnel) : `GET {stream_url}` (SSE), voir [README.md](README.md).

---

## Côté frontend WFB

Après un `POST` partenaire réussi, le dossier est dans `GET /api/v1/dossiers` comme les autres.

- Liste : `/dossiers` — référence = `noDemande`, badge **PVC**
- Fiche analyse : `/analyse/DEM-2026-00412` (même score, ratios, factorielle, documents)

Aucune authentification Keycloak : l’UI WFB continue d’appeler les APIs internes sans `X-API-Key`. **Seule PVC** doit envoyer la clé sur `/partners/pvc`.

---

## Séquence recommandée (PVC)

```
1. POST /api/v1/partners/pvc/dossiers
     X-API-Key + data (DossierPv) + liasse PDF
     → 202 { poll_url, job_id }

2. Répéter GET poll_url  (toutes les 15 s)
     tant que analyseStatus ∈ {queued, processing, pending}

3. Si completed → stocker score, classe, points_forts, ratios
   Si failed    → lire error, alerter, éventuellement renvoyer le PDF
```

L’analyse utilise Ollama (`RCC_OLLAMA_URL`). Un scan multi-pages peut prendre plusieurs minutes. Un seul job GPU à la fois : les dossiers suivants restent en file.

---

## Exemple Java (RestTemplate / WebClient)

En-tête : `X-API-Key`.  
Partie `data` : `application/json` (string du DossierPv).  
Partie `liasse` : `application/pdf`.

Ne pas attendre le score dans le POST : toujours le GET par `noDemande`.
