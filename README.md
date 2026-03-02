# LLMflow

**A production-grade LLM platform for the full ML lifecycle: Train → Evaluate → Deploy → Monitor → Improve**

LLMflow is an internal ML platform that manages the complete lifecycle of large language models — from dataset ingestion and LoRA fine-tuning, through automated evaluation with split discipline, to production serving with A/B testing and cost accounting.

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
                              │ A/B │ Batch │ $  │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │   Prometheus +   │
                              │     Grafana      │
                              └─────────────────┘
```

## Key Features

### Data Pipeline
- **Dataset ingestion** — Upload CSV, JSONL, Parquet; auto-versioning with SHA-256 content hashing
- **Split discipline** — Enforced train/val/test splits with holdout protection and leakage prevention
- **Labeling UI** — Built-in annotation interface

### Training
- **LoRA fine-tuning** — PEFT + Transformers with 4-bit QLoRA support
- **Reproducibility controls** — Seed locking, config snapshots, dataset hash verification, library version logging, "re-run" button
- **Experiment tracking** — MLflow integration with auto-logged params, metrics, and artifacts
- **Hyperparameter sweeps** — Grid and random search
- **Cost tracking** — GPU hours × rate per training run

### Evaluation
- **Perplexity** on held-out test sets
- **Task-specific metrics** — Classification F1, QA exact-match
- **Self-consistency check** — N-sample generation to detect hallucinations
- **Human evaluation** — Side-by-side blind comparison with Likert scales
- **Split enforcement** — API rejects evals on train splits; cross-checks hashes for leakage

### Serving
- **Inference server** — Request batching, response caching (Redis), SSE streaming
- **A/B testing** — Traffic splitting by percentage across model versions
- **Model registry** — Version, stage (staging/production/archived), lineage tracking
- **Model lineage graph** — Visual DAG: Dataset → Experiment → Run → Model → Deployment
- **Playground** — Interactive chat with deployed models

### Monitoring
- **Prometheus + Grafana** — Request latency (p50/p95/p99), throughput, tokens/sec
- **Cost dashboard** — Token usage per model, GPU hours, cost per 1k requests
- **Quality metrics** — Aggregated human ratings over time

### Production
- **CI/CD** — GitHub Actions for lint, test, build, push
- **Kubernetes manifests** — Deployments, Services, Ingress, ConfigMaps, Secrets
- **Rate limiting** — Sliding-window in-memory rate limiter
- **API key auth** — Header-based authentication
- **Structured logging** — JSON logs via structlog

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Celery, Pydantic v2 |
| ML | PyTorch, HuggingFace Transformers, PEFT, bitsandbytes, scikit-learn |
| Tracking | MLflow |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Recharts, Lucide Icons |
| Database | PostgreSQL 16, Redis 7, MinIO (S3-compatible) |
| Monitoring | Prometheus, Grafana |
| Infra | Docker Compose, Kubernetes, GitHub Actions |

## One-Command Demo

Run the full pipeline end-to-end with a single command:

```bash
make demo
```

This will:
1. Start all 10 services (Postgres, Redis, MinIO, MLflow, Backend, Worker, Inference, Frontend, Prometheus, Grafana)
2. Run database migrations
3. Upload a 40-row instruction-following dataset
4. Create train/val/test splits with leakage verification
5. Fine-tune GPT-2 with LoRA for 1 epoch (real training, real loss curves)
6. Run perplexity evaluation on the held-out test split
7. Query the inference server

You'll see real training metrics, model artifacts in MinIO, and experiment tracking in MLflow.

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

This starts: PostgreSQL, Redis, MinIO, MLflow, Backend API, Celery Worker, Inference Server, Frontend, Prometheus, Grafana.

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
│       ├── engine/         # Batching, caching
│       ├── router/         # A/B traffic routing
│       └── models/         # Model loading
├── frontend/                # Next.js dashboard
│   └── src/
│       ├── app/            # Pages (dashboard, data, training, eval, serving, monitoring)
│       ├── components/     # UI components
│       ├── lib/            # API client, utilities
│       └── types/          # TypeScript interfaces
├── demo/                    # One-command demo
│   ├── alpaca_demo.jsonl   # 40-row instruction-following dataset
│   └── run_demo.py         # Drives full pipeline via API
├── infra/                   # Prometheus, Grafana configs
├── k8s/                     # Kubernetes manifests
├── .github/workflows/       # CI/CD pipelines
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
- `POST /api/v1/serving/deployments` — Deploy model
- `GET /api/v1/serving/lineage/{id}` — Model lineage graph
- `POST /v1/completions` — Inference (on inference server)

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
