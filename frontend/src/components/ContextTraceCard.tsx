/**
 * 上下文理解展示卡片
 * 用于解释多轮追问时系统实际继承了哪些条件、覆盖了哪些条件。
 */
import type { ContextTraceData } from "../types/agent";
import { safeLabel, sanitizeDisplayText, sanitizeDisplayValue } from "../lib/displaySafe";

type ContextTraceCardProps = {
  trace: ContextTraceData;
};

export function ContextTraceCard({ trace }: ContextTraceCardProps) {
  if (!trace.is_follow_up) return null;

  return (
    <div className="mt-4 border border-moss/20 bg-moss/5 px-3 py-3 text-sm">
      <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-moss">
        系统理解
      </div>
      <div className="space-y-2 text-ink/75">
        <ContextLine label="原问题" value={sanitizeDisplayText(trace.original_query)} />
        <ContextLine label="实际查询" value={sanitizeDisplayText(trace.resolved_query)} strong />
        <ContextLine label="继承" value={formatContext(trace.inherited_context)} />
        <ContextLine label="变更" value={formatContext(trace.overwritten_context)} />
        <ContextLine label="方式" value={formatRewriteMethod(trace.rewrite_method)} />
        <ContextLine label="置信度" value={formatConfidence(trace.confidence)} />
      </div>
    </div>
  );
}

function ContextLine({
  label,
  value,
  strong = false,
}: {
  label: string;
  value?: string;
  strong?: boolean;
}) {
  if (!value) return null;

  return (
    <div className="grid gap-1 sm:grid-cols-[72px_minmax(0,1fr)]">
      <span className="text-ink/45">{label}</span>
      <span className={strong ? "font-semibold text-ink" : "text-ink/70"}>{value}</span>
    </div>
  );
}

function formatContext(context: Record<string, unknown>) {
  const entries = Object.entries(context);
  if (entries.length === 0) return "";

  return entries
    .map(([key, value]) => `${labelFor(key)}=${formatValue(value)}`)
    .join("，");
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeDisplayValue(item)).join("、");
  }
  if (value && typeof value === "object") {
    return formatObjectValue(value as Record<string, unknown>);
  }
  return sanitizeDisplayValue(value);
}

function formatObjectValue(value: Record<string, unknown>): string {
  const sortField = value.field ?? value.metric;
  const sortOrder = value.order ?? value.direction;
  if (typeof sortField === "string") {
    return `按 ${safeLabel(sortField)} ${formatSortOrder(sortOrder)}排序`;
  }

  return Object.entries(value)
    .map(([key, entryValue]) => `${labelFor(key)}=${formatValue(entryValue)}`)
    .join("，");
}

function formatSortOrder(order: unknown): string {
  if (order === "asc") return "从低到高";
  return "从高到低";
}

function formatConfidence(confidence?: number) {
  if (typeof confidence !== "number") return "";
  return `${Math.round(confidence * 100)}%`;
}

function formatRewriteMethod(method?: string) {
  if (method === "llm") return "大模型结构化理解";
  if (method === "rule") return "规则改写";
  if (method === "confirmation") return "用户确认后执行";
  return "";
}

function labelFor(key: string) {
  const labels: Record<string, string> = {
    time_range: "时间",
    metrics: "指标",
    metric: "指标",
    dimensions: "维度",
    dimension: "维度",
    sort: "排序",
    region: "地区",
  };
  return labels[key] ?? safeLabel(key);
}
