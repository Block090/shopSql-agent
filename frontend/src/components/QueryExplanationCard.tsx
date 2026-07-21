import { ShieldCheck } from "lucide-react";
import type { QueryExplanationData } from "../types/agent";
import { sanitizeDisplayText } from "../lib/displaySafe";

type QueryExplanationCardProps = {
  explanation: QueryExplanationData;
};

function joinList(values?: string[], fallback = "未明确") {
  return values && values.length > 0
    ? values.map((item) => sanitizeDisplayText(item)).join("、")
    : fallback;
}

export function QueryExplanationCard({ explanation }: QueryExplanationCardProps) {
  const business = explanation.business;
  const technical = explanation.technical;

  return (
    <section className="mt-4 border border-moss/20 bg-moss/5 px-3 py-3">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-moss">
        <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
        查询依据
      </div>

      <div className="grid gap-2 text-sm text-ink/75 sm:grid-cols-2">
        {explanation.risk && (
          <div>
            <div className="text-xs text-ink/45">查询风险</div>
            <div className="mt-0.5 font-medium text-ink">{explanation.risk.label}</div>
          </div>
        )}
        <div>
          <div className="text-xs text-ink/45">指标口径</div>
          <div className="mt-0.5 font-medium text-ink">{joinList(business.metrics)}</div>
        </div>
        <div>
          <div className="text-xs text-ink/45">分析维度</div>
          <div className="mt-0.5 font-medium text-ink">{joinList(business.dimensions)}</div>
        </div>
        <div>
          <div className="text-xs text-ink/45">时间范围</div>
          <div className="mt-0.5 font-medium text-ink">
            {sanitizeDisplayText(business.time_range || "未限定")}
          </div>
        </div>
        <div>
          <div className="text-xs text-ink/45">过滤条件</div>
          <div className="mt-0.5 font-medium text-ink">
            {joinList(business.filters, "无额外过滤条件")}
          </div>
        </div>
      </div>

      {business.result_summary && (
        <div className="mt-3 border-t border-moss/15 pt-3 text-sm text-ink/65">
          {sanitizeDisplayText(business.result_summary)}
        </div>
      )}

      {technical.fields?.length ? (
        <details className="mt-3 border-t border-moss/15 pt-3">
          <summary className="cursor-pointer text-xs font-semibold text-ink/50">
            查看脱敏技术依据
          </summary>
          <div className="mt-2 text-xs leading-6 text-ink/55">底层技术细节已隐藏。</div>
          <div className="mt-1 text-xs leading-6 text-ink/45">
            技术细节仅在后端审计日志中保留，普通视图不直接展示。
          </div>
        </details>
      ) : null}
    </section>
  );
}
