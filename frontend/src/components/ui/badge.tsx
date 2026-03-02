import { cn } from "@/lib/utils";
import { HTMLAttributes } from "react";

const variants: Record<string, string> = {
  default: "bg-primary text-primary-foreground",
  secondary: "bg-secondary text-secondary-foreground",
  success: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
  warning: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
  destructive: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100",
  outline: "border text-foreground",
};

interface BadgeProps extends HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof variants;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export function StatusBadge({ status }: { status: string }) {
  const variantMap: Record<string, keyof typeof variants> = {
    completed: "success",
    active: "success",
    running: "warning",
    queued: "secondary",
    pending: "secondary",
    failed: "destructive",
    stopped: "destructive",
    cancelled: "outline",
    created: "outline",
  };
  return <Badge variant={variantMap[status] || "outline"}>{status}</Badge>;
}
