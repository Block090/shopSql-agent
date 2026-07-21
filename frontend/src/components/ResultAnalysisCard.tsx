/**
 * 查询结果分析卡片
 * 展示 LLM 生成的摘要、洞察和图表。
 */
import { BrainCircuit, Lightbulb } from "lucide-react";
import type { ResultAnalysisData } from "../types/agent";
import { sanitizeDisplayText } from "../lib/displaySafe";
import { ResultChart } from "./ResultChart";

export function ResultAnalysisCard({
  analysis,
  data,
}: {
  analysis: ResultAnalysisData;
  data: unknown;
}) {
  if (!analysis.summary && (!analysis.insights || analysis.insights.length === 0)) {
    return null;
  }

  return (
    <section className="mt-4 border border-moss/20 bg-moss/5 px-4 py-4 shadow-line">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-moss">
        <BrainCircuit className="h-4 w-4" aria-hidden="true" />
        智能分析
      </div>

      {analysis.summary && (
        <p className="text-sm leading-7 text-ink/80">{sanitizeDisplayText(analysis.summary)}</p>
      )}

      {analysis.insights?.length > 0 && (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink/50">
            <Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />
            关键洞察
          </div>
          <ul className="space-y-2 text-sm text-ink/80">
            {analysis.insights.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-moss" />
                <span>{sanitizeDisplayText(item)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ResultChart data={data} analysis={analysis} />
    </section>
  );
}
