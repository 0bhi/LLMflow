"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatDate, formatCost } from "@/lib/utils";
import { BrainCircuit, Play, RefreshCw, Hash, Fingerprint, DollarSign } from "lucide-react";

export default function TrainingPage() {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [selectedExp, setSelectedExp] = useState<any | null>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "", base_model: "gpt2", dataset_version_id: 1, seed: 42,
    config_snapshot_json: `{
  "epochs": 1,
  "batch_size": 2,
  "gradient_accumulation_steps": 2,
  "learning_rate": 5e-4,
  "lora_r": 8,
  "lora_alpha": 16,
  "max_seq_length": 128,
  "warmup_steps": 5
}`,
  });

  const loadExperiments = useCallback(async () => {
    try { setExperiments(await api.listExperiments()); } catch {}
  }, []);

  useEffect(() => { loadExperiments(); }, [loadExperiments]);

  const loadRuns = async (expId: number) => {
    setRuns(await api.listRuns(expId));
  };

  const handleCreate = async () => {
    await api.createExperiment({
      ...form,
      config_snapshot_json: JSON.parse(form.config_snapshot_json),
    });
    setShowCreate(false);
    loadExperiments();
  };

  const handleLaunchRun = async (expId: number) => {
    await api.createRun(expId, { hyperparams: {} });
    loadRuns(expId);
  };

  const handleRerun = async (runId: number) => {
    await api.rerunTraining(runId);
    if (selectedExp) loadRuns(selectedExp.id);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Training</h1>
          <p className="text-muted-foreground mt-1">LoRA fine-tuning with reproducibility controls</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <BrainCircuit className="mr-2 h-4 w-4" /> New Experiment
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Create Experiment</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Experiment name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Base model (e.g. gpt2)" value={form.base_model} onChange={(e) => setForm({ ...form, base_model: e.target.value })} />
              <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Dataset version ID (from Data → version id)" value={form.dataset_version_id} onChange={(e) => setForm({ ...form, dataset_version_id: parseInt(e.target.value) })} />
              <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Seed" value={form.seed} onChange={(e) => setForm({ ...form, seed: parseInt(e.target.value) })} />
            </div>
            <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono h-32" placeholder="Config JSON" value={form.config_snapshot_json} onChange={(e) => setForm({ ...form, config_snapshot_json: e.target.value })} />
            <div className="flex gap-2">
              <Button onClick={handleCreate}>Create</Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {experiments.map((exp) => (
          <Card key={exp.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => { setSelectedExp(exp); loadRuns(exp.id); }}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{exp.name}</CardTitle>
                <StatusBadge status={exp.status} />
              </div>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">Model</span><span>{exp.base_model}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">Seed</span><span>{exp.seed}</span></div>
              <div className="text-xs text-muted-foreground mt-2">{formatDate(exp.created_at)}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {selectedExp && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">{selectedExp.name} — Runs</CardTitle>
              <Button size="sm" onClick={() => handleLaunchRun(selectedExp.id)}>
                <Play className="mr-1 h-3 w-3" /> Launch Run
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No runs yet.</p>
            ) : (
              <div className="rounded-lg border">
                <div className="grid grid-cols-7 gap-2 p-3 border-b text-xs font-medium text-muted-foreground">
                  <div>Run</div><div>Status</div><div>Seed</div><div>Config Hash</div><div>GPU Hours</div><div>Cost</div><div>Actions</div>
                </div>
                {runs.map((run) => (
                  <div key={run.id} className="grid grid-cols-7 gap-2 p-3 text-sm items-center">
                    <div className="font-medium">#{run.id}</div>
                    <div><StatusBadge status={run.status} /></div>
                    <div className="flex items-center gap-1"><Fingerprint className="h-3 w-3 text-muted-foreground" />{run.seed}</div>
                    <div className="font-mono text-xs flex items-center gap-1"><Hash className="h-3 w-3 text-muted-foreground" />{run.config_hash.slice(0, 10)}...</div>
                    <div>{run.gpu_hours?.toFixed(2) ?? "—"}</div>
                    <div className="flex items-center gap-1">{run.gpu_cost_usd ? <><DollarSign className="h-3 w-3" />{formatCost(run.gpu_cost_usd)}</> : "—"}</div>
                    <div>
                      <Button size="sm" variant="ghost" onClick={() => handleRerun(run.id)} title="Re-run with same config">
                        <RefreshCw className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-4 rounded-lg bg-muted/50 p-4">
              <h4 className="font-medium text-sm mb-2">Reproducibility Info</h4>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>Seed: {selectedExp.seed}</div>
                <div>Dataset Version: #{selectedExp.dataset_version_id}</div>
                <div className="col-span-2 font-mono break-all">Config: {JSON.stringify(selectedExp.config_snapshot_json).slice(0, 100)}...</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
