# Resume-readiness roadmap

Goal: make LLMflow something you can demo and defend in an interview. Prefer a smaller **complete** Train → Evaluate → Deploy → Monitor loop over a wide README that does not match the code.

Principle: keep one honest lifecycle, finish the easy gaps in that loop, and drop claims you cannot explain in 30 seconds.

---

## What is already defensible (keep)

These match the README closely enough to talk about. Do not dilute them.

| Area | What actually works |
|------|---------------------|
| Data | Upload, SHA-256 versions, train/val/test, immutable splits, row-hash leakage checks |
| Training | Real LoRA on GPT-2 via Celery, seed, config hash, dataset-hash check, MLflow params/metrics, MinIO artifacts, GPU-hour cost, re-run |
| Eval | Perplexity, self-consistency, QA exact-match, reject eval on train split |
| Infra | Docker Compose, CI (lint/test/build), structured logs, in-memory rate limiter |
| Tests | Split math, leakage, eval enforcement, re-run clone, config dedup |

That is the interview spine.

---

## Implement (easy / high interview value)

### 1. Data page (must)

Sidebar links to `/data`. There is no `frontend/src/app/data/page.tsx`. The dataset API already exists (`create`, `upload`, `versions`, `split`).

Build a page: list datasets → create → upload file → create splits → show hashes and row counts.

Without this, “Data pipeline” is a broken nav item.

### 2. Close the Deploy → Serve → Monitor loop (must)

This is the biggest mismatch with the README.

- Creating a deployment only inserts a row with `status=pending`. Nothing talks to the inference server.
- Inference returns a placeholder when the model is not loaded. `load_model` is never called.
- `ABRouter.set_route` is never called, so A/B traffic % on the form does nothing.
- `InferenceLog` is never written, so monitoring latency/cost/quality stay empty. Human ratings require an `inference_log_id` that never exists.
- Playground and `make demo` step 7 hit the placeholder.

Minimum complete version (still interview-honest):

1. On deploy: set status `active`, tell inference to load the run’s MinIO artifact, register `traffic_pct`.
2. On each completion: write `InferenceLog` + a cost row (tokens × rate).
3. Optional: an admin/routes endpoint on inference that the backend calls.

Without this you cannot claim serving, A/B, playground, or monitoring.

### 3. Hyperparameter sweep UI

Backend grid/random sweep exists (`ExperimentService.launch_sweep`). Frontend has `api.launchSweep` and no UI.

Add a small form: strategy, param JSON, max runs.

### 4. Wire classification F1 or stop claiming it

`TaskEvaluator.evaluate_classification` exists. The worker always calls `evaluate_qa_exact_match`. Either add a subtype (`qa` vs `classification`) or drop F1 from the README.

### 5. Fix eval routing + ratings

`GET /api/v1/evaluations/{evaluation_id}` is registered before list/static paths and will treat `/evaluations/ratings` as `evaluation_id="ratings"`. Move static paths first.

After inference logs exist, rate from the playground (stars + dimension) instead of a raw Log ID field. That is enough for “human eval”; do not build a blind lab.

### 6. Monitoring that actually shows numbers

- Add Grafana Prometheus datasource provisioning. Dashboards exist; the datasource is not provisioned, so Grafana is empty.
- Prometheus scrapes `backend:8000` but the backend has no `/metrics`. Add a tiny `/metrics` or scrape only inference.
- Use Recharts on the monitoring page (it is in `package.json` and unused). README already claims it.
- `error_rate` is hardcoded `0.0` — compute it from logs or remove the metric.

### 7. Small polish interviewers notice

- Deployment “Rollback” currently only sets `stopped`; it does not unload the model. Either unload + zero traffic, or rename the button to “Stop”.
- Model registry: `GET /serving/registry` and `stage` exist; UI never changes stage. Add Staging / Production / Archived.
- Lineage is already a linear Dataset → … → Deployment strip. Keep it. Change README to “lineage chain”, not “visual DAG”.
- Apply `verify_api_key` on mutating routes when `DEBUG=false`, or drop “API key auth” from the README (`verify_api_key` is unused).
- Delete unused `clean_dataset` Celery task.
- Align README versions (frontend is Next 16, not 14).

---

## Remove (hard, fake, or not worth defending)

Do not implement these. Cut them from README, UI copy, and architecture diagram.

| Claim | Reality | Why drop |
|-------|---------|----------|
| **Labeling UI** | Zero code | Real annotation product. Interviewers will ask to see it. |
| **SSE streaming** | `stream: bool` ignored | Token streaming + HF generate is extra surface. |
| **Request batching** | `RequestBatcher` is a lock around one generate; queue unused | Fake batching is worse than “synchronous inference with Redis cache”. |
| **Blind side-by-side human eval** | Form posts a Likert to a log ID | Real blinding is extra product. Simple ratings after logs are enough. |
| **Parquet** | Enum only; `_count_rows` returns 0; splits treat bytes as text | Broken binary path. Support JSONL + CSV only. |
| **Full Kubernetes** | App Deployments + Ingress only; no Postgres/Redis/MinIO/MLflow/PVC; `OWNER` image; secrets in git | Compose is the real deploy story. Keep manifests as app-service sketches or delete `k8s/`. |
| **QLoRA as a demo feature** | Flag exists; CPU Compose demo will not use bitsandbytes | Keep `load_in_4bit` in config; README: “optional on GPU”. |
| **MLflow model artifacts** | Params/metrics/text logged; weights go to MinIO | Say “MLflow for experiments, MinIO for weights”. |
| **Quality over time charts** | One aggregate, no series | Skip until you have ratings; then one Recharts line is enough. |

CD (GHCR push) is real enough to keep if the repo is on GitHub. Do not claim “production Kubernetes CI/CD”.

---

## Target README story after cleanup

Something you can say without hedging:

> Internal LLM ops platform: versioned datasets with leakage-safe splits, LoRA fine-tuning with reproducibility (seed, config hash, re-run), held-out eval, deploy a run to an inference process with traffic split and Redis cache, then cost and latency from real request logs. Docker Compose demo trains GPT-2 end-to-end.

Drop: labeling, streaming, batching, parquet, k8s-as-production, blind eval, “visual DAG”.

---

## Order of work

### Phase A — demo does not embarrass you (done)

1. Data page
2. Deploy loads model + A/B routes + inference logs + cost
3. Playground uses that model; demo script deploys then queries
4. README + nav copy match reality

### Phase B — features that are already ~80% done

5. Sweep UI
6. Classification F1 wire-up **or** README cut
7. Registry stages + stop/unload
8. Grafana datasource + Recharts + backend metrics scrape fix
9. Eval route bug + in-app ratings

### Phase C — delete

10. Labeling, stream flag, batcher class (or rename to “serialized generate”), parquet, unused tasks
11. Shrink or remove `k8s/`
12. README architecture diagram: Compose is the system; Prometheus scrapes inference

---

## What to practice for interviews

After this, you should be able to:

1. Draw Compose boxes and the data flow: MinIO hashes → Celery LoRA → MLflow → eval on test split only.
2. Explain leakage: row SHA overlap + “no eval on train” + hash mismatch.
3. Explain re-run vs duplicate-config rejection.
4. Explain deploy: artifact path → load PEFT model → traffic % → Redis cache key.
5. Explain cost: `gpu_hours × rate` for training; tokens × rate for inference logs.

Do **not** claim you built a labeling tool, a batching engine, or a production cluster unless those are real.
