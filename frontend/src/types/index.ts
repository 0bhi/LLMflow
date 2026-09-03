export interface Dataset {
  id: number;
  name: string;
  description: string | null;
  format: "csv" | "jsonl" | "parquet";
  source_type: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetVersion {
  id: number;
  dataset_id: number;
  version: number;
  storage_path: string;
  content_hash: string;
  row_count: number;
  schema_json: Record<string, any> | null;
  stats_json: Record<string, any> | null;
  created_at: string;
}

export interface DatasetSplit {
  id: number;
  dataset_version_id: number;
  split_type: "train" | "val" | "test";
  row_count: number;
  storage_path: string;
  content_hash: string;
  created_at: string;
}

export interface Experiment {
  id: number;
  name: string;
  base_model: string;
  dataset_version_id: number;
  config_snapshot_json: Record<string, any>;
  status: "created" | "running" | "completed" | "failed";
  mlflow_experiment_id: string | null;
  seed: number;
  created_at: string;
}

export interface TrainingRun {
  id: number;
  experiment_id: number;
  hyperparams: Record<string, any>;
  metrics_json: Record<string, any> | null;
  model_artifact_path: string | null;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  seed: number;
  dataset_hash: string;
  config_hash: string;
  gpu_hours: number | null;
  gpu_cost_usd: number | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Evaluation {
  id: number;
  training_run_id: number;
  eval_type: "perplexity" | "task_accuracy" | "classification" | "self_consistency" | "human";
  dataset_split_id: number;
  results_json: Record<string, any> | null;
  score: number | null;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
}

export interface Deployment {
  id: number;
  name: string;
  training_run_id: number;
  version: string;
  endpoint: string | null;
  status: "pending" | "active" | "stopped" | "failed";
  stage: "staging" | "production" | "archived";
  traffic_pct: number;
  config_json: Record<string, any> | null;
  created_at: string;
}

export interface CostSummary {
  total_cost_usd: number;
  training_cost_usd: number;
  inference_cost_usd: number;
  total_gpu_hours: number;
  total_tokens: number;
  period_start: string;
  period_end: string;
}
