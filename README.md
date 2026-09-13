# Wafabail Smart Dashboard

Monorepo de la plateforme intelligente d’automatisation du crédit-bail (Wafabail).

## Prérequis

- Node.js 20+
- Python 3.11+
- Docker Desktop — **optionnel** (MinIO, Kafka)

## Démarrage sans Docker

```bash
# 1. API
cd backend
py -3 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# 2. Frontend (autre terminal)
cd frontend
copy .env.example .env
npm install
npm run dev
```

Ouvre http://localhost:5173 — l’application est ouverte, sans page de connexion.
Les PDF sont stockés dans `backend/data/files/`. Kafka et MinIO sont désactivés.

L’extraction scoring appelle toujours Ollama (URL dans `backend/.env`) : une connexion internet suffit, pas Docker.

## Structure

```
wafabail-platform/
├── docker-compose.yml     # MinIO + Kafka + API + workers
├── frontend/              # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── app/                 # Router
│       ├── components/          # Layout + UI partagés
│       ├── features/            # Pages (dashboard, dossiers, analyse)
│       ├── lib/extraction/      # OCR ICE / RC / raison sociale (Tesseract)
│       ├── services/api/        # Clients API (mock ↔ FastAPI)
│       ├── services/mocks/      # Données de démo
│       └── types/
└── backend/               # FastAPI (dossiers + dashboard + MinIO + Kafka)
    └── worker/            # Consumer Kafka traitement dossiers
```

## Démarrage rapide

```bash
# 1. Infra + API
docker compose up -d

# 2. Frontend
cd frontend
cp .env.example .env   # VITE_USE_MOCK=false pour brancher FastAPI
npm install
npm run dev
```

Ouvre http://localhost:5173.

## Infra locale (Docker)

```bash
docker compose up -d
```

| Service | URL | Identifiants |
|---|---|---|
| MinIO API | http://localhost:9000 | `minioadmin` / `minioadmin` |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| API | http://localhost:8000/docs | — |
| Kafka | localhost:9094 | topic `wafabail.dossiers.created` |

- Bucket MinIO : `wafabail-dossiers` (créé par `minio-init`)
- Worker : `wafabail-dossier-worker` consomme les créations de dossiers

## Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev      # http://localhost:5173
npm test         # Vitest (extraction OCR, etc.)
npm run build
```

Variables utiles (`.env.example`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `VITE_USE_MOCK` | `false` | `true` = données mock locales |
| `VITE_API_BASE_URL` | `/api/v1` | Proxy Vite → FastAPI |

L’OCR (Tesseract) charge les modèles depuis le CDN (`cacheMethod: none`) — aucun fichier `*.traineddata` n’est écrit dans le projet.

À la création d’un dossier, l’upload des pièces entreprise déclenche une extraction progressive (ICE, RC, raison sociale).

## Backend (FastAPI + MinIO + Kafka)

Avec Docker (recommandé) — inclus dans `docker compose up -d` :

- API : http://localhost:8000/docs
- Santé : http://localhost:8000/health
- Worker Kafka : `docker logs -f wafabail-dossier-worker`

En local (Python 3.11+) :

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Le proxy Vite redirige `/api` → `http://127.0.0.1:8000`.

Documentation complète des routes (entrées, sorties, exemples) : [backend/README.md](backend/README.md).  
API partenaire PVC (envoi liasse + GET par `noDemande`) : [backend/README-API-PVC.md](backend/README-API-PVC.md).

### API dossiers

| Méthode | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/dossiers` | Liste (`status`, `q`) |
| `POST` | `/api/v1/dossiers` | Création multipart |
| `GET` | `/api/v1/dossiers/{id}` | Résumé liste |
| `GET` | `/api/v1/dossiers/{id}/detail` | Métadonnées + fichiers MinIO |
| `POST` | `/api/v1/dossiers/{id}/approve` | Approuver |
| `POST` | `/api/v1/dossiers/{id}/reject` | Rejeter |
| `POST` | `/api/v1/dossiers/{id}/reserve` | Sous réserve (`reserved`) |
| `POST` | `/api/v1/dossiers/{id}/cancel` | Annuler la décision → `pending` |
| `POST` | `/api/v1/dossiers/{id}/documents/replace` | Ajouter ou remplacer un document (max 20), puis relancer l’analyse depuis le détail |

**Analyse asynchrone** (file unique, un dossier à la fois) :

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/dossiers` | Crée le dossier **et lance l’analyse** dès qu’une liasse PDF est présente |
| `POST` | `/api/v1/dossiers/{id}/analyse/jobs` | Relancer l’analyse (mise en file si un autre job tourne) |
| `GET` | `/api/v1/dossiers/{id}/analyse` | État du job + workspace UI |
| `GET` | `/api/v1/dossiers/{id}/synthese` | Points forts, points de vigilance, score final |
| `POST` | `/api/v1/dossiers/{id}/copilot` | Copilote Qwen 3.5 (questions sur le dossier) |
| `GET` | `/api/v1/analyse/jobs/{job_id}/stream` | SSE de progression |

**Création** `POST /api/v1/dossiers` (multipart) :

- champ `data` : JSON métadonnées (entreprise, financement, bien)
- champ `documents` : fichiers entreprise → MinIO
- champ `proforma` : pièce proforma → MinIO
- métadonnées persistées dans `backend/data/dossiers.json` (volume Docker `/data`)
- événement publié sur Kafka `wafabail.dossiers.created`

**Dashboard** : `GET /api/v1/dashboard`

### Poste d’analyse

Branché sur le backend via `GET /dossiers/{id}` + `/detail` :

- en-tête : montant financé, durée, apport %, analyste
- onglet Bien financé : nature, valeurs, conditions du contrat
- documents : jusqu’à **9** emplacements ; si statut `pending` (« Docs en attente »), clic pour déposer / remplacer un fichier
- décisions Approuver / Sous réserve / Rejeter / Annuler persistées côté API

Les onglets scores / ratios / pipeline IA restent encore en grande partie mockés à partir des données dossier.

## Écrans

| Route | Contenu | CDC |
|---|---|---|
| `/` | Tableau de bord | F-DASH-001 → 006 |
| `/dossiers` | Liste + création (MinIO + FastAPI + OCR) | F-DOS-001, 003, 004 |
| `/analyse/:id` | Poste d’analyse (données back + docs) | F-ANA-* |
| `/alertes` | Alertes | — |

## Stack

- **Front** : React 19, React Router, Framer Motion, Lucide, Tailwind CSS 4, Tesseract.js, pdfjs, Vitest
- **Back** : FastAPI, Pydantic v2, Uvicorn
- **Fichiers** : MinIO (S3)
- **Events** : Kafka (création dossier → worker)
