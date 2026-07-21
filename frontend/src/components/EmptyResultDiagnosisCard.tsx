import { SearchX } from "lucide-react";
import type { EmptyResultDiagnosisData } from "../types/agent";
import { sanitizeDisplayText } from "../lib/displaySafe";

export function EmptyResultDiagnosisCard({
  diagnosis,
}: {
  diagnosis: EmptyResultDiagnosisData;
}) {
  return (
    <section className="mt-4 border border-tomato/20 bg-tomato/5 px-4 py-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-tomato">
        <SearchX className="h-4 w-4" aria-hidden="true" />
        空结果诊断
      </div>
      <p className="text-sm leading-7 text-ink/75">{sanitizeDisplayText(diagnosis.summary)}</p>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">
            可能原因
          </div>
          <ul className="space-y-2 text-sm text-ink/70">
            {diagnosis.possible_reasons.map((item) => (
              <li key={item}>- {sanitizeDisplayText(item)}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-ink/45">
            建议尝试
          </div>
          <ul className="space-y-2 text-sm text-ink/70">
            {diagnosis.suggestions.map((item) => (
              <li key={item}>- {sanitizeDisplayText(item)}</li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
