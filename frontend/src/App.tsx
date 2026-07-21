/**
 * 前端应用主组件
 * 负责聊天会话状态、SSE 事件消费和整体页面布局
 */
import {
  Activity,
  BarChart3,
  Eraser,
  History,
  Leaf,
  MessageSquarePlus,
  Server,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { MessageBubble } from "./components/MessageBubble";
import { DEFAULT_USER_ID, deleteSession, fetchSessionHistory, fetchSessions, streamQuery } from "./lib/agentApi";
import { sanitizeDisplayText, safeStepLabel } from "./lib/displaySafe";
import { cn, summarizeResult } from "./lib/format";
import type { AgentEvent, ChatMessage, QuerySession, StepState } from "./types/agent";

const examples = [
  "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
  "统计 2025 年 3 月各商品品类的销量和销售额",
  "查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
  "按会员等级统计 2025 年第一季度的订单数和销售额",
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "Vite /api proxy";
const demoUsers = [
  { id: "demo_admin", label: "管理员", description: "可查看全局经营数据" },
  { id: "region_east", label: "华东运营", description: "仅可查看华东数据" },
] as const;
type DemoUserId = (typeof demoUsers)[number]["id"];

function normalizeDemoUserId(userId: string): DemoUserId {
  return demoUsers.some((user) => user.id === userId) ? (userId as DemoUserId) : "demo_admin";
}

function makeId(): string {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function upsertStep(steps: StepState[] = [], event: Extract<AgentEvent, { type: "progress" }>) {
  const next = steps.filter((item) => item.step !== event.step);
  next.push({
    step: event.step,
    status: event.status,
    updatedAt: Date.now(),
  });
  return next;
}

function formatDisplayError(message?: string): string {
  if (!message) {
    return "本次查询没有返回明确错误原因，请稍后重试。";
  }

  if (message.includes("502 Bad Gateway")) {
    const target = message.match(/https?:\/\/([^/'"\s]+)/)?.[1];
    if (target) {
      return `后端调用下游服务失败：本次查询依赖的本地服务 ${target} 返回 502。请检查对应服务是否已启动、端口是否正确，或稍后重试。`;
    }
    return "后端调用下游服务失败：下游服务返回 502，请检查相关服务是否已启动后重试。";
  }

  if (message.includes("Connection refused") || message.includes("WinError 10061")) {
    return "后端连接下游服务失败：目标服务未启动或端口不可用，请检查本地依赖服务。";
  }

  return sanitizeDisplayText(
    message.replace(/\s*For more information check:\s*https?:\/\/\S+/i, "").trim(),
  );
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [activeSessionId, setActiveSessionId] = useState<string>(() => makeId());
  const [sessions, setSessions] = useState<QuerySession[]>([]);
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const [activeUserId, setActiveUserId] = useState<DemoUserId>(() => normalizeDemoUserId(DEFAULT_USER_ID));
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;

  const completedCount = useMemo(
    () => messages.filter((message) => message.role === "assistant" && message.status === "done").length,
    [messages],
  );

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await fetchSessions());
    } catch {
      // 中文注释：历史会话加载失败不阻断当前问数主流程。
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const loadSessionHistory = async (sessionId: string) => {
    if (isStreaming) return;
    try {
      const history = await fetchSessionHistory(sessionId);
      if (history.length === 0) {
        setActiveSessionId(sessionId);
        setMessages([
          {
            id: makeId(),
            role: "assistant",
            content: "这个历史会话没有查询明细，可能是之前后端空流问题留下的记录。",
            createdAt: Date.now(),
            status: "done",
          },
        ]);
        return;
      }
      const restoredMessages = history.flatMap<ChatMessage>((item) => [
        {
          id: makeId(),
          role: "user",
          content: item.query,
          createdAt: item.created_at ? new Date(item.created_at).getTime() : Date.now(),
        },
        {
          id: makeId(),
          role: "assistant",
          content:
            item.status === "failed"
              ? "这次查询没有成功。"
              : item.result_summary || "历史记录没有结果摘要。",
          createdAt: item.created_at ? new Date(item.created_at).getTime() : Date.now(),
          status: item.status === "failed" ? "error" : "done",
          result: item.result_data ?? undefined,
          resultAnalysis: item.result_analysis ?? undefined,
          queryExplanation: item.query_explanation ?? undefined,
          contextTrace: item.context_trace
            ? {
                ...item.context_trace,
                confidence: item.context_trace.confidence ?? item.rewrite_confidence ?? undefined,
              }
            : undefined,
          error: item.error_message ? formatDisplayError(item.error_message) : undefined,
        },
      ]);
      setActiveSessionId(sessionId);
      setMessages(restoredMessages);
      setDraft("");
    } catch (error) {
      setMessages([
        {
          id: makeId(),
          role: "assistant",
          content: "历史会话加载失败，请确认后端已重启并且 /api/sessions 接口可用。",
          createdAt: Date.now(),
          status: "error",
          error: error instanceof Error ? error.message : String(error),
        },
      ]);
    }
  };

  const startQuery = async (rawQuery = draft) => {
    const query = rawQuery.trim();
    if (!query || isStreaming) return;

    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: query,
      createdAt: Date.now(),
    };

    const assistantId = makeId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "正在连接问数智能体...",
      createdAt: Date.now(),
      status: "streaming",
      steps: [],
    };

    const controller = new AbortController();
    setActiveController(controller);
    setDraft("");
    setMessages((current) => [...current, userMessage, assistantMessage]);

    const onEvent = (event: AgentEvent) => {
      if (event.type === "session") {
        setActiveSessionId(event.session_id);
        return;
      }

      setMessages((current) =>
        current.map((message) => {
          if (message.id !== assistantId) return message;

          if (event.type === "progress") {
            return {
              ...message,
              content: event.status === "running" ? `正在执行：${safeStepLabel(event.step)}` : message.content,
              steps: upsertStep(message.steps, event),
            };
          }

          if (event.type === "result") {
            return {
              ...message,
              status: "done",
              content: summarizeResult(event.data),
              result: event.data,
            };
          }

          if (event.type === "result_analysis") {
            return {
              ...message,
              resultAnalysis: event.data,
            };
          }

          if (event.type === "context_trace") {
            return {
              ...message,
              contextTrace: event.data,
            };
          }

          if (event.type === "query_explanation") {
            return {
              ...message,
              queryExplanation: event.data,
            };
          }

          if (event.type === "empty_result_diagnosis") {
            return {
              ...message,
              emptyResultDiagnosis: event.data,
            };
          }

          if (event.type === "followup_suggestions") {
            return {
              ...message,
              followupSuggestions: event.data,
            };
          }

          if (event.type === "clarification") {
            return {
              ...message,
              status: "done",
              content: event.message,
              clarification: {
                ...event,
                // 保留原始问题，用户选择口径后用“原问题 + 口径”重新发起查询。
                originalQuery: query,
              },
            };
          }

          if (event.type === "operation_plan") {
            return {
              ...message,
              status: "done",
              content: "已生成数据变更审批方案。系统默认不会直接执行写操作。",
              operationPlan: event.data,
            };
          }

          if (event.type === "unable_to_answer") {
            return {
              ...message,
              status: "done",
              content:
                event.suggestion ||
                "当前问题不属于已接入的电商经营数据范围，请换一种问法或查询 GMV、订单数、AOV 等业务指标。",
              unableToAnswer: true,
            };
          }

          if (event.type === "error") {
            if (message.unableToAnswer) {
              return {
                ...message,
                error: formatDisplayError(event.message),
              };
            }

            return {
              ...message,
              status: "error",
              content: "这次查询没有成功。",
              error: formatDisplayError(event.message),
            };
          }

          return message;
        }),
      );
    };

    try {
      await streamQuery(query, {
        sessionId: activeSessionId,
        userId: activeUserId,
        signal: controller.signal,
        onEvent,
      });
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId && message.status === "streaming"
            ? { ...message, status: "done", content: "流程已结束，后端未返回查询结果。" }
            : message,
        ),
      );
    } catch (error) {
      const isAbort = error instanceof DOMException && error.name === "AbortError";
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                status: isAbort ? "done" : "error",
                content: isAbort ? "已停止本次查询。" : "无法连接问数接口。",
                error: isAbort
                  ? undefined
                  : formatDisplayError(error instanceof Error ? error.message : String(error)),
              }
            : message,
        ),
      );
    } finally {
      setActiveController(null);
      void loadSessions();
    }
  };

  const stopQuery = () => {
    activeController?.abort();
  };

  const clearConversation = () => {
    if (isStreaming) return;
    setActiveSessionId(makeId());
    setMessages([]);
    setDraft("");
  };

  const removeSession = async (sessionId: string) => {
    if (isStreaming) return;
    if (!window.confirm("确定要删除这条历史会话吗？删除后不可恢复。")) return;

    try {
      await deleteSession(sessionId);
      if (sessionId === activeSessionId) {
        setActiveSessionId(makeId());
        setMessages([]);
        setDraft("");
      }
      await loadSessions();
    } catch (error) {
      setMessages([
        {
          id: makeId(),
          role: "assistant",
          content: "删除历史会话失败，请确认后端已启动并且删除接口可用。",
          createdAt: Date.now(),
          status: "error",
          error: error instanceof Error ? error.message : String(error),
        },
      ]);
    }
  };

  return (
    <div className="h-dvh overflow-hidden bg-parchment text-ink">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(90deg,rgba(32,32,29,0.045)_1px,transparent_1px),linear-gradient(rgba(32,32,29,0.035)_1px,transparent_1px)] bg-[size:48px_48px]" />
      <div className="pointer-events-none fixed inset-0 grain" />

      <div className="relative grid h-full min-h-0 overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="hidden min-h-0 border-r border-ink/10 bg-[#efe6d8]/85 backdrop-blur lg:flex lg:flex-col">
          <div className="border-b border-ink/10 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center bg-ink text-parchment">
                <BarChart3 className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <div className="text-base font-semibold tracking-[0.02em]">电商问数</div>
                <div className="text-xs text-ink/50">shopkeeper-agent</div>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
            <button
              type="button"
              onClick={clearConversation}
              disabled={isStreaming}
              className="flex h-11 w-full items-center justify-center gap-2 bg-ink text-sm font-semibold text-parchment transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-ink/35"
            >
              <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
              新会话
            </button>

            <section>
              <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                <History className="h-3.5 w-3.5" aria-hidden="true" />
                历史会话
              </div>
              <div className="space-y-2">
                {sessions.length === 0 ? (
                  <div className="border border-ink/10 bg-white/30 px-3 py-3 text-xs text-ink/45">
                    暂无历史会话
                  </div>
                ) : (
                  sessions.map((session) => (
                    <div
                      key={session.session_id}
                      className={cn(
                        "group flex items-stretch border transition",
                        session.session_id === activeSessionId
                          ? "border-moss/45 bg-moss/10 text-ink"
                          : "border-ink/10 bg-white/42 text-ink/75 hover:border-moss/35 hover:bg-white/75",
                      )}
                    >
                      <button
                        type="button"
                        disabled={isStreaming}
                        onClick={() => loadSessionHistory(session.session_id)}
                        className="min-w-0 flex-1 px-3 py-3 text-left text-sm leading-5 transition disabled:cursor-not-allowed disabled:opacity-55"
                      >
                        <span className="line-clamp-2">{session.title || "未命名会话"}</span>
                      </button>
                      <button
                        type="button"
                        disabled={isStreaming}
                        onClick={(event) => {
                          event.stopPropagation();
                          void removeSession(session.session_id);
                        }}
                        className="grid w-10 shrink-0 place-items-center border-l border-ink/10 text-ink/40 transition hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-35"
                        title="删除历史会话"
                        aria-label="删除历史会话"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </section>

            <section>
              <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-[0.16em] text-ink/45">
                <History className="h-3.5 w-3.5" aria-hidden="true" />
                样例
              </div>
              <div className="space-y-2">
                {examples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    disabled={isStreaming}
                    onClick={() => startQuery(example)}
                    className="w-full border border-ink/10 bg-white/42 px-3 py-3 text-left text-sm leading-5 text-ink/75 transition hover:border-moss/35 hover:bg-white/75 disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </section>
          </div>

          <div className="border-t border-ink/10 p-4">
            <div className="grid gap-2 text-xs text-ink/55">
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <Server className="h-3.5 w-3.5" aria-hidden="true" />
                  API
                </span>
                <span className="truncate font-mono">{API_BASE_URL}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2">
                  <Activity className="h-3.5 w-3.5" aria-hidden="true" />
                  完成
                </span>
                <span>{completedCount}</span>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-ink/10 bg-parchment/88 px-4 backdrop-blur lg:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center bg-moss text-white lg:hidden">
                <BarChart3 className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-ink">智能数据分析 Agent</div>
                <div className="truncate text-xs text-ink/45">FastAPI SSE / LangGraph</div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <div className="inline-flex items-center gap-1 border border-ink/10 bg-white/40 p-1">
                <ShieldCheck className="ml-2 h-3.5 w-3.5 text-moss" aria-hidden="true" />
                {demoUsers.map((user) => (
                  <button
                    key={user.id}
                    type="button"
                    disabled={isStreaming}
                    onClick={() => setActiveUserId(user.id)}
                    className={cn(
                      "px-2.5 py-1.5 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
                      activeUserId === user.id
                        ? "bg-ink text-white"
                        : "text-ink/60 hover:bg-ink/5 hover:text-ink",
                    )}
                    title={user.description}
                  >
                    {user.label}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={clearConversation}
                disabled={messages.length === 0 || isStreaming}
                className={cn(
                  "grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-35",
                )}
                title="清空"
                aria-label="清空"
              >
                <Eraser className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </header>

          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {messages.length === 0 ? (
              <EmptyState examples={examples} onUseExample={(example) => setDraft(example)} />
            ) : (
              <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:px-8">
                {messages.map((message) => (
                  <MessageBubble
                    key={message.id}
                    message={message}
                    disabled={isStreaming}
                    onClarificationSelect={(originalQuery, option) =>
                      startQuery(`${originalQuery}，${option}`)
                    }
                  />
                ))}
              </div>
            )}
          </div>

          <div className="border-t border-ink/10 bg-[#efe6d8]/45 px-4 py-2 text-center text-xs text-ink/45">
            <span className="inline-flex items-center gap-2">
              <Leaf className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
              {isStreaming ? "运行中" : "就绪"}
            </span>
          </div>
          <Composer
            value={draft}
            disabled={!canSubmit}
            isStreaming={isStreaming}
            onChange={setDraft}
            onSubmit={() => startQuery()}
            onStop={stopQuery}
          />
        </main>
      </div>
    </div>
  );
}
