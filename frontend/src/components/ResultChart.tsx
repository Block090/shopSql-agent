/**
 * 简易结果图表
 * 第一版不引入额外依赖，使用 SVG 渲染柱状图和折线图。
 */
import type { ResultAnalysisData } from "../types/agent";
import { safeLabel, sanitizeDisplayText, sanitizeDisplayValue } from "../lib/displaySafe";

function normalizeRows(data: unknown): Array<Record<string, unknown>> {
  if (!Array.isArray(data)) return [];
  return data.filter(
    (item): item is Record<string, unknown> =>
      Boolean(item) && typeof item === "object" && !Array.isArray(item),
  );
}

function toNumber(value: unknown) {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value.replace(/,/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function ResultChart({
  data,
  analysis,
}: {
  data: unknown;
  analysis: ResultAnalysisData;
}) {
  const chart = analysis.chart_recommendation;
  const rows = normalizeRows(data);

  if (!chart?.type || !chart.x || !chart.y || rows.length === 0) return null;

  const points = rows
    .map((row) => ({
      label: sanitizeDisplayValue(getChartValue(row, chart.x!)),
      value: toNumber(getChartValue(row, chart.y!)),
    }))
    .filter((item): item is { label: string; value: number } => item.value !== null)
    .slice(0, 10);

  if (points.length === 0) return null;

  const maxValue = Math.max(...points.map((item) => item.value), 1);

  return (
    <section className="mt-4 border border-ink/10 bg-white/70 px-4 py-4 shadow-line">
      <div className="mb-3">
        <div className="text-sm font-semibold text-ink">结果图表</div>
        <div className="text-xs text-ink/45">
          {chart.type === "line" ? "折线图" : "柱状图"}：{safeLabel(chart.x)} / {safeLabel(chart.y)}
        </div>
      </div>

      {chart.type === "line" ? (
        <LineChart points={points} maxValue={maxValue} />
      ) : (
        <BarChart points={points} maxValue={maxValue} />
      )}

      {chart.reason && (
        <div className="mt-3 text-xs text-ink/55">{sanitizeDisplayText(chart.reason)}</div>
      )}
    </section>
  );
}

function getChartValue(row: Record<string, unknown>, field: string) {
  if (field in row) return row[field];
  const matchedKey = Object.keys(row).find((key) => safeLabel(key) === safeLabel(field));
  return matchedKey ? row[matchedKey] : undefined;
}

function BarChart({
  points,
  maxValue,
}: {
  points: Array<{ label: string; value: number }>;
  maxValue: number;
}) {
  return (
    <div className="space-y-3">
      {points.map((point) => (
        <div key={point.label} className="grid gap-2 sm:grid-cols-[180px_minmax(0,1fr)_72px] sm:items-center">
          <div className="truncate text-sm text-ink/75">{point.label}</div>
          <div className="h-3 overflow-hidden bg-[#efe6d8]">
            <div
              className="h-full bg-moss"
              style={{ width: `${Math.max((point.value / maxValue) * 100, 4)}%` }}
            />
          </div>
          <div className="text-right text-sm font-semibold text-ink">{point.value}</div>
        </div>
      ))}
    </div>
  );
}

function LineChart({
  points,
  maxValue,
}: {
  points: Array<{ label: string; value: number }>;
  maxValue: number;
}) {
  const width = 560;
  const height = 220;
  const padding = 24;
  const stepX = points.length > 1 ? (width - padding * 2) / (points.length - 1) : 0;
  const coordinates = points.map((point, index) => {
    const x = padding + index * stepX;
    const y = height - padding - (point.value / maxValue) * (height - padding * 2);
    return { ...point, x, y };
  });
  const path = coordinates.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-[220px] min-w-[560px]">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#b2aa9f" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#b2aa9f" />
        <path d={path} fill="none" stroke="#2f6b4f" strokeWidth="3" />
        {coordinates.map((point) => (
          <g key={point.label}>
            <circle cx={point.x} cy={point.y} r="4" fill="#2f6b4f" />
            <text x={point.x} y={height - 8} textAnchor="middle" fontSize="10" fill="#6d675f">
              {point.label}
            </text>
            <text x={point.x} y={point.y - 10} textAnchor="middle" fontSize="10" fill="#20201d">
              {point.value}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
