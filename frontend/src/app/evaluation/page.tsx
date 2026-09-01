"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { TestTube, Star, GitCompare } from "lucide-react";

export default function EvaluationPage() {
  const [evaluations, setEvaluations] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ training_run_id: 1, eval_type: "perplexity", dataset_split_id: 1 });
  const [compareForm, setCompareForm] = useState({ run_id_a: 1, run_id_b: 2, eval_type: "perplexity", dataset_split_id: 1 });
  const [comparison, setComparison] = useState<any | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [ratingForm, setRatingForm] = useState({ inference_log_id: 1, rater_id: "reviewer-1", score: 4, feedback: "", dimension: "overall" });

  const load = useCallback(async () => {
    try { setEvaluations(await api.listEvaluations()); } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    await api.createEvaluation(form);
    setShowCreate(false);
    load();
  };

  const handleCompare = async () => {
    const result = await api.compareModels(compareForm);
    setComparison(result);
  };

  const handleRate = async () => {
    await api.createRating(ratingForm);
    setRatingForm({ ...ratingForm, feedback: "", score: 4 });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Evaluation</h1>
          <p className="text-muted-foreground mt-1">Automated and human evaluation with split discipline</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowCompare(!showCompare)}>
            <GitCompare className="mr-2 h-4 w-4" /> Compare
          </Button>
          <Button onClick={() => setShowCreate(true)}>
            <TestTube className="mr-2 h-4 w-4" /> New Evaluation
          </Button>
        </div>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Run Evaluation</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="text-xs text-muted-foreground">Training Run ID</label>
                <input type="number" className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.training_run_id} onChange={(e) => setForm({ ...form, training_run_id: parseInt(e.target.value) })} />
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Eval Type</label>
                <select className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.eval_type} onChange={(e) => setForm({ ...form, eval_type: e.target.value })}>
                  <option value="perplexity">Perplexity</option>
                  <option value="task_accuracy">Task Accuracy</option>
                  <option value="self_consistency">Self-Consistency</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-muted-foreground">Dataset Split ID (val/test id from Data)</label>
                <input type="number" className="w-full rounded-md border bg-background px-3 py-2 text-sm" value={form.dataset_split_id} onChange={(e) => setForm({ ...form, dataset_split_id: parseInt(e.target.value) })} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate}>Run Evaluation</Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {showCompare && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Compare Models</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-4 gap-4">
              <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Run A" value={compareForm.run_id_a} onChange={(e) => setCompareForm({ ...compareForm, run_id_a: parseInt(e.target.value) })} />
              <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Run B" value={compareForm.run_id_b} onChange={(e) => setCompareForm({ ...compareForm, run_id_b: parseInt(e.target.value) })} />
              <select className="rounded-md border bg-background px-3 py-2 text-sm" value={compareForm.eval_type} onChange={(e) => setCompareForm({ ...compareForm, eval_type: e.target.value })}>
                <option value="perplexity">Perplexity</option>
                <option value="task_accuracy">Task Accuracy</option>
              </select>
              <Button onClick={handleCompare}>Compare</Button>
            </div>
            {comparison && (
              <div className="grid grid-cols-2 gap-4">
                {["run_a", "run_b"].map((key) => (
                  <div key={key} className="rounded-lg border p-4">
                    <h4 className="font-medium">Run #{comparison[key].run_id}</h4>
                    <div className="mt-2 text-2xl font-bold">{comparison[key].score?.toFixed(4) ?? "N/A"}</div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="rounded-lg border">
        <div className="grid grid-cols-6 gap-4 p-3 border-b text-xs font-medium text-muted-foreground">
          <div>ID</div><div>Run</div><div>Type</div><div>Score</div><div>Status</div><div>Date</div>
        </div>
        {evaluations.map((ev) => (
          <div key={ev.id} className="grid grid-cols-6 gap-4 p-3 text-sm items-center">
            <div>#{ev.id}</div>
            <div>Run #{ev.training_run_id}</div>
            <div>{ev.eval_type}</div>
            <div className="font-medium">{ev.score?.toFixed(4) ?? "—"}</div>
            <div><StatusBadge status={ev.status} /></div>
            <div className="text-xs text-muted-foreground">{formatDate(ev.created_at)}</div>
          </div>
        ))}
        {evaluations.length === 0 && (
          <div className="p-8 text-center text-sm text-muted-foreground">No evaluations yet.</div>
        )}
      </div>

      <Card>
        <CardHeader><CardTitle className="text-lg flex items-center gap-2"><Star className="h-5 w-5" /> Human Rating</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-5 gap-3">
            <input type="number" className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Log ID" value={ratingForm.inference_log_id} onChange={(e) => setRatingForm({ ...ratingForm, inference_log_id: parseInt(e.target.value) })} />
            <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Rater ID" value={ratingForm.rater_id} onChange={(e) => setRatingForm({ ...ratingForm, rater_id: e.target.value })} />
            <input type="number" step="0.5" min="1" max="5" className="rounded-md border bg-background px-3 py-2 text-sm" value={ratingForm.score} onChange={(e) => setRatingForm({ ...ratingForm, score: parseFloat(e.target.value) })} />
            <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="Feedback" value={ratingForm.feedback} onChange={(e) => setRatingForm({ ...ratingForm, feedback: e.target.value })} />
            <Button onClick={handleRate}>Submit Rating</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
