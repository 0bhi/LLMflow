#!/usr/bin/env python3
"""
LLMflow end-to-end demo.

Usage:
    python demo/run_demo.py [--api-url http://localhost:8000]

Walks through the full pipeline:
  1. Create dataset + upload demo JSONL
  2. Create train/val/test splits
  3. Create experiment + launch training run (real LoRA fine-tune of GPT-2)
  4. Wait for training to complete
  5. Run perplexity evaluation on test split
  6. Wait for eval to complete
  7. Print results summary
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

DEMO_DATASET = Path(__file__).parent / "alpaca_demo.jsonl"
POLL_INTERVAL = 5
MAX_WAIT = 600


def api(base: str, method: str, path: str, **kwargs):
    url = f"{base}{path}"
    resp = getattr(requests, method)(url, **kwargs)
    if resp.status_code >= 400:
        print(f"  ERROR {resp.status_code}: {resp.text}")
        sys.exit(1)
    return resp.json() if resp.content else {}


def main():
    parser = argparse.ArgumentParser(description="LLMflow end-to-end demo")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--inference-url", default="http://localhost:8001")
    args = parser.parse_args()
    base = args.api_url.rstrip("/")
    inference_base = args.inference_url.rstrip("/")

    print("=" * 60)
    print("  LLMflow End-to-End Demo")
    print("=" * 60)

    # ------------------------------------------------------------------ #
    # 1. Create dataset
    # ------------------------------------------------------------------ #
    print("\n[1/7] Creating dataset...")
    ds = api(base, "post", "/api/v1/datasets", json={
        "name": f"alpaca-demo-{int(time.time())}",
        "description": "Small instruction-following demo dataset",
        "format": "jsonl",
    })
    ds_id = ds["id"]
    print(f"  Dataset created: id={ds_id}")

    # ------------------------------------------------------------------ #
    # 2. Upload version
    # ------------------------------------------------------------------ #
    print("\n[2/7] Uploading dataset version...")
    with open(DEMO_DATASET, "rb") as f:
        ver = api(base, "post", f"/api/v1/datasets/{ds_id}/upload",
                  files={"file": ("alpaca_demo.jsonl", f, "application/json")})
    ver_id = ver["id"]
    print(f"  Version uploaded: v{ver['version']}, rows={ver['row_count']}, "
          f"hash={ver['content_hash'][:12]}...")

    # ------------------------------------------------------------------ #
    # 3. Create splits
    # ------------------------------------------------------------------ #
    print("\n[3/7] Creating train/val/test splits...")
    splits = api(base, "post",
                 f"/api/v1/datasets/{ds_id}/versions/{ver['version']}/split",
                 json={"train_ratio": 0.7, "val_ratio": 0.15, "test_ratio": 0.15, "seed": 42})
    for s in splits:
        print(f"  {s['split_type']:5s}: {s['row_count']} rows  hash={s['content_hash'][:12]}...")

    train_split = next(s for s in splits if s["split_type"] == "train")
    test_split = next(s for s in splits if s["split_type"] == "test")

    # ------------------------------------------------------------------ #
    # 4. Create experiment + training run
    # ------------------------------------------------------------------ #
    print("\n[4/7] Creating experiment and launching training...")
    exp = api(base, "post", "/api/v1/training/experiments", json={
        "name": f"demo-finetune-{int(time.time())}",
        "base_model": "gpt2",
        "dataset_version_id": ver_id,
        "config_snapshot_json": {
            "epochs": 1,
            "batch_size": 2,
            "gradient_accumulation_steps": 2,
            "learning_rate": 5e-4,
            "lora_r": 8,
            "lora_alpha": 16,
            "max_seq_length": 128,
            "warmup_steps": 5,
        },
        "seed": 42,
    })
    exp_id = exp["id"]
    print(f"  Experiment created: id={exp_id}")

    run = api(base, "post", f"/api/v1/training/experiments/{exp_id}/runs", json={
        "hyperparams": {},
    })
    run_id = run["id"]
    print(f"  Training run queued: id={run_id}")

    # ------------------------------------------------------------------ #
    # 5. Wait for training
    # ------------------------------------------------------------------ #
    print("\n[5/7] Waiting for training to complete...")
    elapsed = 0
    while elapsed < MAX_WAIT:
        r = api(base, "get", f"/api/v1/training/experiments/{exp_id}")
        runs = api(base, "get", f"/api/v1/training/experiments/{exp_id}/runs")
        current_run = next((rn for rn in runs if rn["id"] == run_id), None)
        status = current_run["status"] if current_run else "unknown"
        print(f"  Status: {status} ({elapsed}s elapsed)", end="\r")

        if status == "completed":
            print(f"\n  Training completed in {elapsed}s")
            metrics = current_run.get("metrics_json", {})
            print(f"  Train loss:  {metrics.get('final_train_loss', 'N/A')}")
            print(f"  Eval loss:   {metrics.get('final_eval_loss', 'N/A')}")
            print(f"  Perplexity:  {metrics.get('perplexity', 'N/A')}")
            print(f"  GPU hours:   {current_run.get('gpu_hours', 'N/A')}")
            print(f"  GPU cost:    ${current_run.get('gpu_cost_usd', 'N/A')}")
            break
        elif status == "failed":
            print(f"\n  Training FAILED.")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    else:
        print(f"\n  Timed out after {MAX_WAIT}s")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # 6. Run perplexity evaluation
    # ------------------------------------------------------------------ #
    print("\n[6/7] Running perplexity evaluation on test split...")
    ev = api(base, "post", "/api/v1/evaluations", json={
        "training_run_id": run_id,
        "eval_type": "perplexity",
        "dataset_split_id": test_split["id"],
    })
    eval_id = ev["id"]
    print(f"  Evaluation queued: id={eval_id}")

    elapsed = 0
    while elapsed < MAX_WAIT:
        ev = api(base, "get", f"/api/v1/evaluations/{eval_id}")
        status = ev["status"]
        print(f"  Status: {status} ({elapsed}s elapsed)", end="\r")

        if status == "completed":
            print(f"\n  Evaluation completed!")
            results = ev.get("results_json", {})
            print(f"  Perplexity: {results.get('perplexity', 'N/A')}")
            print(f"  Avg loss:   {results.get('avg_loss', 'N/A')}")
            print(f"  Samples:    {results.get('n_samples', 'N/A')}")
            print(f"  Tokens:     {results.get('total_tokens', 'N/A')}")
            break
        elif status == "failed":
            print(f"\n  Evaluation FAILED.")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    else:
        print(f"\n  Timed out after {MAX_WAIT}s")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # 7. Query the inference server
    # ------------------------------------------------------------------ #
    print("\n[7/7] Querying inference server...")
    try:
        inf_resp = requests.post(f"{inference_base}/v1/completions", json={
            "prompt": "### Instruction:\nExplain what machine learning is.\n### Response:\n",
            "max_tokens": 100,
            "temperature": 0.7,
        }, timeout=30)
        if inf_resp.status_code == 200:
            data = inf_resp.json()
            print(f"  Model: {data.get('model', 'N/A')}")
            print(f"  Completion: {data.get('completion', 'N/A')[:200]}")
            print(f"  Latency: {data.get('latency_ms', 'N/A')}ms")
        else:
            print(f"  Inference server returned {inf_resp.status_code} (model may not be loaded)")
    except requests.exceptions.ConnectionError:
        print("  Inference server not reachable (skipping — deploy a model first)")

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)
    print(f"""
  Dataset:    {ds['name']} (id={ds_id})
  Experiment: id={exp_id}, model=gpt2
  Run:        id={run_id}, status=completed
  Eval:       id={eval_id}, type=perplexity

  Dashboards:
    Frontend:   http://localhost:3000
    API docs:   http://localhost:8000/docs
    MLflow:     http://localhost:5000
    MinIO:      http://localhost:9001
    Grafana:    http://localhost:3001
""")


if __name__ == "__main__":
    main()
