"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatCost } from "@/lib/utils";
import { Activity, DollarSign, Clock, Zap, Star, BarChart3 } from "lucide-react";

export default function MonitoringPage() {
  const [costs, setCosts] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [quality, setQuality] = useState<any>(null);
  const [modelCosts, setModelCosts] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const [c, m, q, mc] = await Promise.allSettled([
        api.getCostSummary(),
        api.getMetrics(),
        api.getQuality(),
        api.getCostByModel(),
      ]);
      if (c.status === "fulfilled") setCosts(c.value);
      if (m.status === "fulfilled") setMetrics(m.value);
      if (q.status === "fulfilled") setQuality(q.value);
      if (mc.status === "fulfilled") setModelCosts(mc.value);
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const latencyChart = metrics
    ? [
        { name: "avg", ms: metrics.avg_latency_ms ?? 0 },
        { name: "p95", ms: metrics.p95_latency_ms ?? 0 },
        { name: "p99", ms: metrics.p99_latency_ms ?? 0 },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Monitoring</h1>
        <p className="text-muted-foreground mt-1">Latency, cost, and quality from request logs</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Cost</CardTitle>
            <DollarSign className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{costs ? formatCost(costs.total_cost_usd) : "—"}</div>
            <div className="text-xs text-muted-foreground mt-1">
              Training: {costs ? formatCost(costs.training_cost_usd) : "—"} | Inference: {costs ? formatCost(costs.inference_cost_usd) : "—"}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">GPU Hours</CardTitle>
            <Zap className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{costs?.total_gpu_hours?.toFixed(1) ?? "—"}</div>
            <div className="text-xs text-muted-foreground mt-1">{costs?.total_tokens?.toLocaleString() ?? 0} total tokens</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Avg Latency</CardTitle>
            <Clock className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics?.avg_latency_ms?.toFixed(0) ?? "—"}ms</div>
            <div className="text-xs text-muted-foreground mt-1">
              p95: {metrics?.p95_latency_ms?.toFixed(0) ?? "—"}ms | p99: {metrics?.p99_latency_ms?.toFixed(0) ?? "—"}ms
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Quality Score</CardTitle>
            <Star className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{quality?.avg_human_score?.toFixed(2) ?? "—"}/5</div>
            <div className="text-xs text-muted-foreground mt-1">{quality?.total_ratings ?? 0} ratings</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <BarChart3 className="h-5 w-5" /> Cost by Model
            </CardTitle>
          </CardHeader>
          <CardContent>
            {modelCosts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No inference data yet.</p>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={modelCosts}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="model_name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number) => formatCost(v)} />
                    <Bar dataKey="total_cost_usd" fill="hsl(221, 83%, 53%)" name="Cost (USD)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="h-5 w-5" /> Request Metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 mb-4">
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm">Total Requests</span>
                <span className="font-medium">{metrics?.total_requests?.toLocaleString() ?? "—"}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm">Error Rate</span>
                <span className="font-medium">{metrics?.error_rate?.toFixed(2) ?? "—"}%</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border p-3">
                <span className="text-sm">Tokens/sec</span>
                <span className="font-medium">{metrics?.tokens_per_second?.toFixed(1) ?? "—"}</span>
              </div>
            </div>
            {latencyChart.some((d) => d.ms > 0) && (
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v: number) => `${v.toFixed(0)}ms`} />
                    <Bar dataKey="ms" fill="hsl(199, 89%, 48%)" name="Latency" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {quality && (quality.score_over_time || []).length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Quality over time</CardTitle></CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={quality.score_over_time}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis domain={[0, 5]} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line type="monotone" dataKey="avg_score" stroke="hsl(271, 81%, 56%)" name="Avg rating" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {quality && Object.keys(quality.score_by_dimension || {}).length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-lg">Quality by Dimension</CardTitle></CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-3">
              {Object.entries(quality.score_by_dimension).map(([dim, score]) => (
                <div key={dim} className="rounded-lg border p-3">
                  <div className="text-sm text-muted-foreground capitalize">{dim}</div>
                  <div className="text-xl font-bold">{(score as number).toFixed(2)}/5</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
