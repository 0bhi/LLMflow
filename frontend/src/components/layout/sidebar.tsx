"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Database,
  BrainCircuit,
  TestTube,
  Rocket,
  Activity,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Data", href: "/data", icon: Database },
  { name: "Training", href: "/training", icon: BrainCircuit },
  { name: "Evaluation", href: "/evaluation", icon: TestTube },
  { name: "Serving", href: "/serving", icon: Rocket },
  { name: "Monitoring", href: "/monitoring", icon: Activity },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-50 w-64 border-r bg-card">
      <div className="flex h-16 items-center gap-2 border-b px-6">
        <BrainCircuit className="h-7 w-7 text-primary" />
        <span className="text-xl font-bold tracking-tight">LLMflow</span>
      </div>
      <nav className="flex flex-col gap-1 p-4">
        {navigation.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.name}
            </Link>
          );
        })}
      </nav>
      <div className="absolute bottom-4 left-4 right-4">
        <div className="rounded-lg border bg-muted/50 p-3 text-xs text-muted-foreground">
          <div className="font-medium">LLMflow v0.1.0</div>
          <div>ML Platform</div>
        </div>
      </div>
    </aside>
  );
}
