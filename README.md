# LLMflow

Internal LLM ops platform: versioned datasets with leakage-safe splits, LoRA fine-tuning with reproducibility (seed, config hash, re-run), held-out eval, deploy a run to an inference process with traffic split and Redis cache, then cost and latency from real request logs.

Docker Compose demo trains GPT-2 end-to-end, deploys the adapter, and queries it.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Next.js Frontend                           │
│  Dashboard │ Data │ Training │ Evaluation │ Serving │ Monitoring│
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    FastAPI Backend (API v1)                      │
│  Datasets │ Training │ Evaluation │ Serving │ Monitoring │ Cost │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
       │          │          │          │          │
┌──────▼──┐ ┌────▼────┐ ┌───▼───┐ ┌───▼────┐ ┌───▼──────┐
│ Celery  │ │ MLflow  │ │ MinIO │ │ Redis  │ │PostgreSQL│
│ Workers │ │Tracking │ │  S3   │ │ Cache  │ │ Metadata │
└─────────┘ └─────────┘ └───────┘ └────┬───┘ └──────────┘
                                       │
                              ┌────────▼────────┐
                              │ Inference Server │
                              │ load │ A/B │ $  │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │   Prometheus +   │
                              │     Grafana      │
                              └─────────────────┘
```

## What works

### Data
- **Upload JSONL or CSV** — SHA-256 content hashing and immutable versions
- **Split discipline** — Enforced train/val/test splits, row-hash leakage checks
- **Data page** — List, create, upload, split, inspect hashes and row counts

### Training
- **LoRA fine-tuning** — PEFT + Transformers (optional 4-bit QLoRA on GPU)
- **Reproducibility** — Seed locking, config snapshots, dataset hash check, re-run
- **Hyperparameter sweep** — Grid or random over a param JSON, capped by max runs
- **Experiment tracking** — MLflow params and metrics; model weights stored in MinIO
- **Cost tracking** — GPU hours × rate per training run

### Evaluation
- **Perplexity** on held-out test sets
- **QA exact-match** and **classification F1** (macro)
- **Self-consistency**
- **Human ratings** from the playground (stars + dimension on a real inference log)
- **Split enforcement** — API rejects evals on train splits; hash mismatch blocks leakage

### Serving
- **Deploy a completed run** — Inference downloads the MinIO artifact and loads the PEFT model
- **A/B traffic %** — Registered on the inference router when you deploy
- **Redis response cache**
- **Playground** — Prompts the loaded model; rate the completion afterward
- **Registry stages** — Staging / Production / Archived
- **Stop** — Unloads the model and zeros traffic
- **Lineage chain** — Dataset → Experiment → Run → Artifact → Deployment
- **Inference logs + cost** — Each completion writes a log and tokens × rate

### Monitoring
- Prometheus scrapes backend and inference `/metrics`
- Grafana provisions a Prometheus datasource and the bundled dashboard
- Cost APIs aggregate training GPU cost and inference token cost from logs
- Monitoring page charts cost and latency (Recharts); error rate is placeholders / total logs

### Infra
- Docker Compose, GitHub Actions (lint/test/build), in-memory rate limiter, JSON logs via structlog

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Celery, Pydantic v2 |
| ML | PyTorch, HuggingFace Transformers, PEFT |
| Tracking | MLflow (experiments), MinIO (weights) |
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Lucide Icons, Recharts |
| Database | PostgreSQL 16, Redis 7, MinIO (S3-compatible) |
| Monitoring | Prometheus, Grafana |
| Infra | Docker Compose, GitHub Actions |

## One-Command Demo

```bash
make demo
```

This will:
1. Start Compose services (Postgres, Redis, MinIO, MLflow, Backend, Worker, Inference, Frontend, Prometheus, Grafana)
2. Run database migrations
3. Upload a 40-row instruction-following dataset
4. Create train/val/test splits with leakage verification
5. Fine-tune GPT-2 with LoRA for 1 epoch
6. Run perplexity evaluation on the held-out test split
7. Deploy the run and load the adapter on the inference server
8. Query the loaded model

You'll see real training metrics, artifacts in MinIO, a live completion, and experiment tracking in MLflow.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for the demo script)
- Make (optional)

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/LLMflow.git
cd LLMflow
cp .env.example .env
```

### 2. Start all services

```bash
make up-build
# or: docker compose up -d --build
```

### 3. Run database migrations

```bash
make migrate
# or: docker compose exec backend alembic upgrade head
```

### 4. Access the platform

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000/docs |
| **Inference API** | http://localhost:8001/docs |
| **MLflow** | http://localhost:5000 |
| **MinIO Console** | http://localhost:9001 |
| **Grafana** | http://localhost:3001 (admin/admin) |
| **Prometheus** | http://localhost:9090 |

## Project Structure

```
LLMflow/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/v1/         # REST endpoints
│   │   ├── core/           # Config, DB, Redis, MinIO, middleware
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic (data, training, eval, serving, cost)
│   │   ├── ml/             # ML code (LoRA trainer, evaluators)
│   │   └── workers/        # Celery tasks
│   └── tests/
├── inference/               # Separate inference server
│   └── app/
│       ├── engine/         # Caching
│       ├── router/         # A/B traffic routing
│       └── models/         # Model loading (MinIO + PEFT)
├── frontend/                # Next.js dashboard
│   └── src/
│       ├── app/            # Pages (dashboard, data, training, eval, serving, monitoring)
│       ├── components/     # UI components
│       ├── lib/            # API client, utilities
│       └── types/          # TypeScript interfaces
├── demo/                    # One-command demo
│   ├── alpaca_demo.jsonl
│   └── run_demo.py
├── infra/                   # Prometheus, Grafana configs
├── docker-compose.yml
├── Makefile
└── README.md
```

## API Endpoints

### Datasets
- `POST /api/v1/datasets` — Create dataset
- `POST /api/v1/datasets/{id}/upload` — Upload version
- `POST /api/v1/datasets/{id}/versions/{v}/split` — Create train/val/test splits

### Training
- `POST /api/v1/training/experiments` — Create experiment
- `POST /api/v1/training/experiments/{id}/runs` — Launch training run
- `POST /api/v1/training/runs/{id}/rerun` — Re-run with same config
- `POST /api/v1/training/sweep` — Launch hyperparameter sweep

### Evaluation
- `POST /api/v1/evaluations` — Run evaluation (split-enforced)
- `POST /api/v1/evaluations/compare` — Side-by-side comparison
- `POST /api/v1/evaluations/ratings` — Submit human rating

### Serving
- `POST /api/v1/serving/deployments` — Deploy a completed run (loads the model)
- `POST /api/v1/serving/inference-logs` — Record a completion (used by inference)
- `GET /api/v1/serving/lineage/{id}` — Lineage chain
- `POST /v1/completions` — Inference (on inference server)
- `POST /admin/models/load` — Load artifact (inference server)
- `POST /admin/models/unload` — Unload model (inference server)
- `PATCH /api/v1/serving/deployments/{id}` — Traffic, status, or stage

### Monitoring
- `GET /api/v1/monitoring/costs/summary` — Cost breakdown
- `GET /api/v1/monitoring/costs/by-model` — Cost per model
- `GET /api/v1/monitoring/metrics/summary` — Latency & throughput
- `GET /api/v1/monitoring/quality` — Human rating aggregates

## Development

```bash
make up          # Start services
make down        # Stop services
make logs        # View logs
make test        # Run backend tests
make lint        # Run linters
make migrate     # Run DB migrations
make shell-backend  # Shell into backend container
make shell-db    # PostgreSQL shell
```

## License

MIT
