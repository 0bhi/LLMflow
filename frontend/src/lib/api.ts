const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const INFERENCE_URL = process.env.NEXT_PUBLIC_INFERENCE_URL || "http://localhost:8001";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }

  if (res.status === 204) return {} as T;
  return res.json();
}

export const api = {
  // Datasets
  listDatasets: (skip = 0, limit = 20) =>
    request<any[]>(`${API_URL}/api/v1/datasets?skip=${skip}&limit=${limit}`),
  getDataset: (id: number) => request<any>(`${API_URL}/api/v1/datasets/${id}`),
  createDataset: (data: any) =>
    request<any>(`${API_URL}/api/v1/datasets`, { method: "POST", body: JSON.stringify(data) }),
  uploadVersion: (datasetId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${API_URL}/api/v1/datasets/${datasetId}/upload`, {
      method: "POST",
      body: form,
    }).then(async (r) => {
      if (!r.ok) throw new ApiError(r.status, await r.text());
      return r.json();
    });
  },
  listVersions: (datasetId: number) =>
    request<any[]>(`${API_URL}/api/v1/datasets/${datasetId}/versions`),
  createSplits: (datasetId: number, version: number, config: any) =>
    request<any[]>(
      `${API_URL}/api/v1/datasets/${datasetId}/versions/${version}/split`,
      { method: "POST", body: JSON.stringify(config) },
    ),
  getSplits: (datasetId: number, version: number) =>
    request<any[]>(`${API_URL}/api/v1/datasets/${datasetId}/versions/${version}/splits`),

  // Training
  listExperiments: (skip = 0, limit = 20) =>
    request<any[]>(`${API_URL}/api/v1/training/experiments?skip=${skip}&limit=${limit}`),
  createExperiment: (data: any) =>
    request<any>(`${API_URL}/api/v1/training/experiments`, { method: "POST", body: JSON.stringify(data) }),
  getExperiment: (id: number) =>
    request<any>(`${API_URL}/api/v1/training/experiments/${id}`),
  createRun: (experimentId: number, data: any) =>
    request<any>(`${API_URL}/api/v1/training/experiments/${experimentId}/runs`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listRuns: (experimentId: number) =>
    request<any[]>(`${API_URL}/api/v1/training/experiments/${experimentId}/runs`),
  rerunTraining: (runId: number) =>
    request<any>(`${API_URL}/api/v1/training/runs/${runId}/rerun`, { method: "POST" }),
  launchSweep: (experimentId: number, config: any) =>
    request<any[]>(
      `${API_URL}/api/v1/training/sweep?experiment_id=${experimentId}`,
      { method: "POST", body: JSON.stringify(config) },
    ),

  // Evaluations
  listEvaluations: (runId?: number) => {
    const params = runId ? `?training_run_id=${runId}` : "";
    return request<any[]>(`${API_URL}/api/v1/evaluations${params}`);
  },
  createEvaluation: (data: any) =>
    request<any>(`${API_URL}/api/v1/evaluations`, { method: "POST", body: JSON.stringify(data) }),
  getEvaluation: (id: number) => request<any>(`${API_URL}/api/v1/evaluations/${id}`),
  compareModels: (data: any) =>
    request<any>(`${API_URL}/api/v1/evaluations/compare`, { method: "POST", body: JSON.stringify(data) }),
  createRating: (data: any) =>
    request<any>(`${API_URL}/api/v1/evaluations/ratings`, { method: "POST", body: JSON.stringify(data) }),

  // Serving
  listDeployments: () => request<any[]>(`${API_URL}/api/v1/serving/deployments`),
  createDeployment: (data: any) =>
    request<any>(`${API_URL}/api/v1/serving/deployments`, { method: "POST", body: JSON.stringify(data) }),
  updateDeployment: (id: number, data: any) =>
    request<any>(`${API_URL}/api/v1/serving/deployments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteDeployment: (id: number) =>
    request<void>(`${API_URL}/api/v1/serving/deployments/${id}`, { method: "DELETE" }),
  reloadDeployment: (id: number) =>
    request<any>(`${API_URL}/api/v1/serving/deployments/${id}/reload`, { method: "POST" }),
  getLineage: (id: number) => request<any>(`${API_URL}/api/v1/serving/lineage/${id}`),

  // Monitoring
  getCostSummary: (days = 30) =>
    request<any>(`${API_URL}/api/v1/monitoring/costs/summary?days=${days}`),
  getCostByModel: () => request<any[]>(`${API_URL}/api/v1/monitoring/costs/by-model`),
  getTrainingCost: (runId: number) =>
    request<any>(`${API_URL}/api/v1/monitoring/costs/training/${runId}`),
  getMetrics: (hours = 24) =>
    request<any>(`${API_URL}/api/v1/monitoring/metrics/summary?hours=${hours}`),
  getQuality: (days = 30) =>
    request<any>(`${API_URL}/api/v1/monitoring/quality?days=${days}`),

  // Inference
  complete: (data: any) =>
    request<any>(`${INFERENCE_URL}/v1/completions`, { method: "POST", body: JSON.stringify(data) }),
};
