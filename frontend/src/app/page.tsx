"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { formatCost } from "@/lib/utils";
import {
  Database,
  BrainCircuit,
  TestTube,
  Rocket,
  DollarSign,
  Clock,
  Activity,
  Zap,
} from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState({
    datasets: 0,
    experiments: 0,
    deployments: 0,
    totalCost: 0,
    avgLatency: 0,
    totalRequests: 0,
  });
  const [recentDeployments, setRecentDeployments] = useState<any[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [datasets, experiments, deployments, costs, metrics] = await Promise.allSettled([
          api.listDatasets(),
          api.listExperiments(),
          api.listDeployments(),
          api.getCostSummary(),
          api.getMetrics(),
        ]);

        if (deployments.status === "fulfilled") {
          const visible = deployments.value.filter((d: any) => d.status !== "stopped");
          setRecentDeployments(visible.slice(0, 5));
        }

        const visibleCount =
          deployments.status === "fulfilled"
            ? deployments.value.filter((d: any) => d.status !== "stopped").length
            : 0;

        setStats({
          datasets: datasets.status === "fulfilled" ? datasets.value.length : 0,
          experiments: experiments.status === "fulfilled" ? experiments.value.length : 0,
          deployments: visibleCount,
          totalCost: costs.status === "fulfilled" ? costs.value.total_cost_usd : 0,
          avgLatency: metrics.status === "fulfilled" ? metrics.value.avg_latency_ms : 0,
          totalRequests: metrics.status === "fulfilled" ? metrics.value.total_requests : 0,
        });
      } catch {
        // API not available yet
      }
    }
    load();
  }, []);

  const cards = [
    { title: "Datasets", value: stats.datasets, icon: Database, color: "text-blue-500" },
    { title: "Experiments", value: stats.experiments, icon: BrainCircuit, color: "text-purple-500" },
    { title: "Deployments", value: stats.deployments, icon: Rocket, color: "text-green-500" },
    { title: "Total Cost", value: formatCost(stats.totalCost), icon: DollarSign, color: "text-yellow-500" },
    { title: "Avg Latency", value: `${stats.avgLatency.toFixed(0)}ms`, icon: Clock, color: "text-orange-500" },
    { title: "Total Requests", value: stats.totalRequests.toLocaleString(), icon: Activity, color: "text-pink-500" },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Overview of your LLM platform
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {card.title}
              </CardTitle>
              <card.icon className={`h-4 w-4 ${card.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{card.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Deployments</CardTitle>
        </CardHeader>
        <CardContent>
          {recentDeployments.length === 0 ? (
            <p className="text-sm text-muted-foreground">No deployments yet.</p>
          ) : (
            <div className="space-y-3">
              {recentDeployments.map((dep) => (
                <div
                  key={dep.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    <Zap className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <div className="font-medium">{dep.name}</div>
                      <div className="text-xs text-muted-foreground">
                        v{dep.version} &middot; {dep.traffic_pct}% traffic
                      </div>
                    </div>
                  </div>
                  <StatusBadge status={dep.status} />
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
