/**
 * 聊天消息气泡组件
 * 组合展示用户问题、智能体回复、执行流程和结果表格
 */
import { Bot, Copy, UserRound } from "lucide-react";
import { ContextTraceCard } from "./ContextTraceCard";
import { EmptyResultDiagnosisCard } from "./EmptyResultDiagnosisCard";
import { FollowupSuggestionsCard } from "./FollowupSuggestionsCard";
import { OperationPlanCard } from "./OperationPlanCard";
import { QueryExplanationCard } from "./QueryExplanationCard";
import { ResultAnalysisCard } from "./ResultAnalysisCard";
import { ResultTable } from "./ResultTable";
import { StepRail } from "./StepRail";
import { cn, formatTime, toClipboardText } from "../lib/format";
import type { ChatMessage } from "../types/agent";

type MessageBubbleProps = {
  message: ChatMessage;
  disabled?: boolean;
  onClarificationSelect?: (originalQuery: string, option: string) => void;
};

export function MessageBubble({
  message,
  disabled = false,
  onClarificationSelect,
}: MessageBubbleProps) {
  const isUser = message.role === "user";

  const copy = async () => {
    const text = message.result ? toClipboardText(message.result) : message.content;
    await navigator.clipboard.writeText(text);
  };

  return (
    <article className={cn("group flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-parchment">
          <Bot className="h-4 w-4" aria-hidden="true" />
        </div>
      )}

      <div className={cn("max-w-[920px] flex-1", isUser && "flex max-w-[760px] justify-end")}>
        <div
          className={cn(
            "relative border px-5 py-4 shadow-line",
            isUser
              ? "border-ink/80 bg-ink text-parchment"
              : "border-ink/10 bg-[#fffaf1]/78 text-ink backdrop-blur",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="whitespace-pre-wrap text-[15px] leading-7">{message.content}</p>
            {!isUser && message.status !== "streaming" && (
              <button
                type="button"
                onClick={copy}
                className="shrink-0 rounded-full p-1.5 text-ink/45 opacity-0 outline-none transition hover:bg-ink/5 hover:text-ink focus:opacity-100 focus:ring-2 focus:ring-moss/40 group-hover:opacity-100"
                title="复制"
                aria-label="复制"
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>

          {message.error && (
            <div className="mt-3 border border-tomato/30 bg-tomato/10 px-3 py-2 text-sm text-tomato">
              {message.error}
            </div>
          )}

          {!isUser && <StepRail steps={message.steps} />}
          {!isUser && message.clarification && (
            <div className="mt-4 border border-moss/25 bg-moss/5 px-3 py-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-moss">
                需要确认业务口径
              </div>
              <div className="flex flex-wrap gap-2">
                {message.clarification.options.map((option) => (
                  <button
                    key={option}
                    type="button"
                    disabled={disabled}
                    onClick={() =>
                      onClarificationSelect?.(
                        message.clarification?.originalQuery ?? "",
                        option,
                      )
                    }
                    className="border border-moss/35 bg-white/70 px-3 py-2 text-sm font-semibold text-moss transition hover:bg-moss hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
          )}
          {!isUser && message.operationPlan && <OperationPlanCard plan={message.operationPlan} />}
          {!isUser && message.contextTrace && <ContextTraceCard trace={message.contextTrace} />}
          {!isUser && message.queryExplanation && (
            <QueryExplanationCard explanation={message.queryExplanation} />
          )}
          {!isUser && message.emptyResultDiagnosis && (
            <EmptyResultDiagnosisCard diagnosis={message.emptyResultDiagnosis} />
          )}
          {!isUser && message.resultAnalysis && (
            <ResultAnalysisCard analysis={message.resultAnalysis} data={message.result} />
          )}
          {!isUser && message.followupSuggestions && (
            <FollowupSuggestionsCard suggestions={message.followupSuggestions} />
          )}
          {!isUser && message.result !== undefined && <ResultTable data={message.result} />}

          <div
            className={cn(
              "mt-3 text-xs",
              isUser ? "text-parchment/55" : "text-ink/45",
            )}
          >
            {formatTime(message.createdAt)}
          </div>
        </div>
      </div>

      {isUser && (
        <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-moss text-white">
          <UserRound className="h-4 w-4" aria-hidden="true" />
        </div>
      )}
    </article>
  );
}
