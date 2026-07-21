import { ListChecks } from "lucide-react";
import type { FollowupSuggestionsData } from "../types/agent";
import { sanitizeDisplayText } from "../lib/displaySafe";

export function FollowupSuggestionsCard({
  suggestions,
}: {
  suggestions: FollowupSuggestionsData;
}) {
  if (!suggestions.suggestions.length) return null;

  return (
    <section className="mt-4 border border-ink/10 bg-white/38 px-4 py-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink/70">
        <ListChecks className="h-4 w-4" aria-hidden="true" />
        后续分析建议
      </div>
      <p className="text-sm leading-7 text-ink/65">{sanitizeDisplayText(suggestions.summary)}</p>
      <ul className="mt-3 space-y-2 text-sm text-ink/75">
        {suggestions.suggestions.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-moss" />
            <span>{sanitizeDisplayText(item)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
