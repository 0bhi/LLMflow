"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { Rocket, Send, Undo2, Network, Copy, Check, RefreshCw } from "lucide-react";

function alpacaPrompt(instruction: string, input = "") {
  let text = `### Instruction:\n${instruction}`;
  if (input) text += `\n### Input:\n${input}`;
  text += `\n### Response:\n`;
  return text;
}

const PLAYGROUND_EXAMPLES = [
  {
    label: "Primary colors",
    instruction: "What are the three primary colors?",
    gold: "The three primary colors are red, blue, and yellow.",
  },
  {
    label: "What is an API?",
    instruction: "Explain what an API is.",
    gold: "An API (Application Programming Interface) is a set of rules that lets programs talk to each other.",
  },
  {
    label: "Healthy tips",
    instruction: "Give three tips for staying healthy.",
    gold: "Eat a balanced diet, exercise regularly, and get enough sleep.",
  },
  {
    label: "Atom structure",
    instruction: "Describe the structure of an atom.",
    gold: "A nucleus of protons and neutrons with electrons in surrounding shells.",
  },
  {
    label: "Summarize ML",
    instruction: "Summarize the given text in one sentence.",
    input:
      "Machine learning is a subset of artificial intelligence that involves training algorithms on data to make predictions or decisions without being explicitly programmed. It has applications in image recognition, natural language processing, recommendation systems, and many other fields.",
    gold: "Machine learning trains algorithms on data to make predictions, used in vision, NLP, and recommendations.",
  },
  {
    label: "C to F",
    instruction: "Convert the temperature from Celsius to Fahrenheit.",
    input: "25°C",
    gold: "25°C is 77°F.",
  },
  {
    label: "Odd one out",
    instruction: "Identify the odd one out.",
    input: "Twitter, Instagram, Telegram",
    gold: "Telegram — it is a messenger, the others are public social networks.",
  },
];

export default function ServingPage() {
  const [deployments, setDeployments] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [lineage, setLineage] = useState<any | null>(null);
  const [form, setForm] = useState({ name: "", training_run_id: 1, version: "1.0.0", traffic_pct: 100 });
  const [playground, setPlayground] = useState({
    prompt: "",
    response: "",
    loading: false,
    model: "",
    gold: "",
    meta: null as null | {
      latency_ms: number;
      tokens_in: number;
      tokens_out: number;
      cached: boolean;
      placeholder: boolean;
    },
  });
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [reloading, setReloading] = useState<number | null>(null);
  const [sanity, setSanity] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    try {
      const list = (await api.listDeployments()).filter((d: any) => d.status !== "stopped");
      setDeployments(list);
      setPlayground((p) => {
        const stillVisible = list.some((d: any) => d.name === p.model);
        const active = list.find((d: any) => d.status === "active");
        return {
          ...p,
          model: stillVisible ? p.model : active?.name || "",
        };
      });
      setLineage((prev) => {
        if (!prev?.deployment?.id) return prev;
        return list.some((d: any) => d.id === prev.deployment.id) ? prev : null;
      });
    } catch {}
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    setError(null);
    try {
      const dep = await api.createDeployment(form);
      setShowCreate(false);
      setPlayground((p) => ({ ...p, model: dep.name }));
      load();
    } catch (e: any) {
      setError(e.message || "Deploy failed");
    }
  };

  const handleDelete = async (id: number) => {
    await api.deleteDeployment(id);
    load();
  };

  const handleReload = async (id: number) => {
    setError(null);
    setReloading(id);
    try {
      await api.reloadDeployment(id);
      load();
    } catch (e: any) {
      setError(e.message || "Failed to load model into inference");
    } finally {
      setReloading(null);
    }
  };

  const handleLineage = async (id: number) => {
    const data = await api.getLineage(id);
    setLineage(data);
  };

  const handleSanity = async (dep: any) => {
    setSanity((s) => ({ ...s, [dep.id]: "checking" }));
    try {
      const result = await api.complete({
        prompt: alpacaPrompt("What are the three primary colors?"),
        max_tokens: 64,
        temperature: 0.2,
        model: dep.name,
      });
      const placeholder = String(result.completion || "").includes("not loaded. This is a placeholder");
      const ok = !placeholder && (result.tokens_out ?? 0) >= 1;
      setSanity((s) => ({
        ...s,
        [dep.id]: ok
          ? `ok · ${result.latency_ms}ms · ${result.tokens_out} tokens`
          : "fail · model not loaded in inference — use Load weights",
      }));
    } catch (e: any) {
      setSanity((s) => ({ ...s, [dep.id]: `fail · ${e.message || "request error"}` }));
    }
  };

  const handleInfer = async () => {
    setPlayground({ ...playground, loading: true, response: "", meta: null });
    try {
      const result = await api.complete({
        prompt: playground.prompt,
        max_tokens: 64,
        temperature: 0.2,
        model: playground.model || undefined,
      });
      const placeholder = String(result.completion || "").includes("not loaded. This is a placeholder");
      setPlayground({
        ...playground,
        loading: false,
        response: placeholder ? "" : result.completion,
        meta: {
          latency_ms: result.latency_ms,
          tokens_in: result.tokens_in,
          tokens_out: result.tokens_out,
          cached: !!result.cached,
          placeholder,
        },
      });
    } catch (e: any) {
      setPlayground({
        ...playground,
        loading: false,
        response: "",
        meta: { latency_ms: 0, tokens_in: 0, tokens_out: 0, cached: false, placeholder: true },
      });
      setError(e.message || "Generate failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Serving</h1>
          <p className="text-muted-foreground mt-1">
            Deploy a trained run, split traffic, and query the loaded model
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Rocket className="mr-2 h-4 w-4" /> New Deployment
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {showCreate && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Deploy Model</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <input
                className="rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <input
                type="number"
                className="rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Training Run ID"
                value={form.training_run_id}
                onChange={(e) => setForm({ ...form, training_run_id: parseInt(e.target.value) })}
              />
              <input
                className="rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Version"
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
              />
              <input
                type="number"
                className="rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Traffic %"
                value={form.traffic_pct}
                onChange={(e) => setForm({ ...form, traffic_pct: parseFloat(e.target.value) })}
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} disabled={!form.name}>
                Deploy
              </Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
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
              <CardDescription>
                v{dep.version} &middot; {dep.traffic_pct}% traffic &middot; {dep.stage}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => handleLineage(dep.id)}>
                  <Network className="mr-1 h-3 w-3" /> Lineage
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={reloading === dep.id}
                  onClick={() => handleReload(dep.id)}
                >
                  <RefreshCw className="mr-1 h-3 w-3" />
                  {reloading === dep.id ? "Loading…" : "Load weights"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={sanity[dep.id] === "checking"}
                  onClick={() => handleSanity(dep)}
                >
                  Sanity check
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setPlayground({ ...playground, model: dep.name })}
                >
                  Use in playground
                </Button>
                <Button size="sm" variant="destructive" onClick={() => handleDelete(dep.id)}>
                  <Undo2 className="mr-1 h-3 w-3" /> Stop
                </Button>
              </div>
              {sanity[dep.id] && (
                <p className={`mt-2 text-xs ${sanity[dep.id].startsWith("ok") ? "text-green-600" : sanity[dep.id] === "checking" ? "text-muted-foreground" : "text-destructive"}`}>
                  {sanity[dep.id] === "checking" ? "Running generate…" : sanity[dep.id]}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
        {deployments.length === 0 && (
          <div className="col-span-full text-center py-12 text-muted-foreground">No deployments yet.</div>
        )}
      </div>

      {lineage && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Network className="h-5 w-5" /> Model Lineage
            </CardTitle>
          </CardHeader>
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
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Send className="h-5 w-5" /> Playground
          </CardTitle>
          <CardDescription>
            {playground.model
              ? `Model: ${playground.model} · GPT-2 LoRA demo — compare to the gold line, not ChatGPT quality.`
              : "Deploy a model first, then generate."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-xs text-muted-foreground mb-2">
              Use an instruction chip (same format as training). Success is: not a placeholder, tokens out, latency. The gold line is from the dataset.
            </p>
            <div className="flex flex-wrap gap-2">
              {PLAYGROUND_EXAMPLES.map((ex) => {
                const prompt = alpacaPrompt(ex.instruction, ex.input);
                return (
                  <div key={ex.label} className="inline-flex items-center rounded-md border bg-muted/40">
                    <button
                      type="button"
                      className="px-2.5 py-1 text-xs font-medium hover:bg-accent"
                      onClick={() =>
                        setPlayground({ ...playground, prompt, gold: ex.gold, response: "", meta: null })
                      }
                    >
                      {ex.label}
                    </button>
                    <button
                      type="button"
                      className="border-l px-1.5 py-1 text-muted-foreground hover:text-foreground"
                      title="Copy prompt"
                      onClick={async () => {
                        await navigator.clipboard.writeText(prompt);
                        setCopied(ex.label);
                        setTimeout(() => setCopied(null), 1500);
                      }}
                    >
                      {copied === ex.label ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          <textarea
            className="w-full rounded-md border bg-background px-3 py-2 text-sm h-36 font-mono"
            placeholder={alpacaPrompt("What are the three primary colors?")}
            value={playground.prompt}
            onChange={(e) => setPlayground({ ...playground, prompt: e.target.value })}
          />
          <Button onClick={handleInfer} disabled={playground.loading || !playground.prompt || !playground.model}>
            {playground.loading ? "Generating..." : "Generate"}
          </Button>
          {playground.meta?.placeholder && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              Inference returned a placeholder — weights are not in memory. Click Load weights, then Sanity check.
            </div>
          )}
          {playground.meta && !playground.meta.placeholder && (
            <div className="text-xs text-muted-foreground font-mono">
              {playground.model} · {playground.meta.latency_ms}ms · {playground.meta.tokens_in} in /{" "}
              {playground.meta.tokens_out} out · {playground.meta.cached ? "cached" : "live"}
            </div>
          )}
          {playground.response && (
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">Model completion (clipped at ###)</div>
              <div className="rounded-lg bg-muted/50 p-4 text-sm whitespace-pre-wrap">{playground.response}</div>
            </div>
          )}
          {playground.gold && (
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-1">Gold (from demo dataset)</div>
              <div className="rounded-lg border p-4 text-sm text-muted-foreground">{playground.gold}</div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
