"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatDate, formatCost } from "@/lib/utils";
import { Rocket, Send, Undo2, Network, DollarSign } from "lucide-react";

export default function ServingPage() {
  const [deployments, setDeployments] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [lineage, setLineage] = useState<any | null>(null);
  const [form, setForm] = useState({ name: "", training_run_id: 1, version: "1.0.0", traffic_pct: 100 });
  const [playground, setPlayground] = useState({ prompt: "", response: "", loading: false });

  const load = useCallback(async () => {
    try { setDeployments(await api.listDeployments()); } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    await api.createDeployment(form);
    setShowCreate(false);
    load();
  };

  const handleDelete = async (id: number) => {
    await api.deleteDeployment(id);
    load();
  };

  const handleLineage = async (id: number) => {
    const data = await api.getLineage(id);
    setLineage(data);
  };

  const handleInfer = async () => {
    setPlayground({ ...playground, loading: true, response: "" });
    try {
      const result = await api.complete({ prompt: playground.prompt, max_tokens: 256, temperature: 0.7 });
      setPlayground({ ...playground, response: result.completion, loading: false });
    } catch (e: any) {
      setPlayground({ ...playground, response: `Error: ${e.message}`, loading: false });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Serving</h1>
          <p className="text-muted-foreground mt-1">Deploy models, A/B testing, and model lineage</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Rocket className="mr-2 h-4 w-4" /> New Deployment
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Deploy Model</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Training Run ID" value={form.training_run_id} onChange={(e) => setForm({ ...form, training_run_id: parseInt(e.target.value) })} />
              <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Version" value={form.version} onChange={(e) => setForm({ ...form, version: e.target.value })} />
              <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Traffic %" value={form.traffic_pct} onChange={(e) => setForm({ ...form, traffic_pct: parseFloat(e.target.value) })} />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate}>Deploy</Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {deployments.map((dep) => (
          <Card key={dep.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{dep.name}</CardTitle>
                <StatusBadge status={dep.status} />
              </div>
              <CardDescription>v{dep.version} &middot; {dep.traffic_pct}% traffic &middot; {dep.stage}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => handleLineage(dep.id)}>
                  <Network className="mr-1 h-3 w-3" /> Lineage
                </Button>
                <Button size="sm" variant="destructive" onClick={() => handleDelete(dep.id)}>
                  <Undo2 className="mr-1 h-3 w-3" /> Rollback
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {deployments.length === 0 && (
          <div className="col-span-full text-center py-12 text-muted-foreground">No deployments yet.</div>
        )}
      </div>

      {lineage && (
        <Card>
          <CardHeader><CardTitle className="text-lg flex items-center gap-2"><Network className="h-5 w-5" /> Model Lineage</CardTitle></CardHeader>
          <CardContent>
            <div className="flex items-center gap-3 overflow-x-auto py-4">
              {[
                { label: "Dataset", data: lineage.dataset_version, fields: ["id", "version", "content_hash", "row_count"] },
                { label: "Experiment", data: lineage.experiment, fields: ["id", "name", "base_model"] },
                { label: "Training Run", data: lineage.training_run, fields: ["id", "status", "seed", "gpu_hours", "gpu_cost_usd"] },
                { label: "Model Artifact", data: lineage.model_artifact, fields: ["path", "config_hash", "dataset_hash"] },
                { label: "Deployment", data: lineage.deployment, fields: ["id", "name", "version", "status"] },
              ].map((node, i) => (
                <div key={node.label} className="flex items-center gap-3">
                  <div className="rounded-lg border bg-muted/50 p-3 min-w-[180px]">
                    <div className="font-medium text-sm mb-2">{node.label}</div>
                    {node.fields.map((f) => (
                      <div key={f} className="text-xs text-muted-foreground">
                        {f}: <span className="font-mono">{String(node.data?.[f] ?? "—").slice(0, 20)}</span>
                      </div>
                    ))}
                  </div>
                  {i < 4 && <span className="text-muted-foreground text-lg">&rarr;</span>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-lg flex items-center gap-2"><Send className="h-5 w-5" /> Playground</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm h-24" placeholder="Enter your prompt..." value={playground.prompt} onChange={(e) => setPlayground({ ...playground, prompt: e.target.value })} />
          <Button onClick={handleInfer} disabled={playground.loading || !playground.prompt}>
            {playground.loading ? "Generating..." : "Generate"}
          </Button>
          {playground.response && (
            <div className="rounded-lg bg-muted/50 p-4 text-sm whitespace-pre-wrap">{playground.response}</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
