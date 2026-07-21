/**
 * 智能体类型定义
 * 定义问数智能体前端使用的 SSE 事件、流程步骤和聊天消息类型
 */
export type ProgressStatus = "running" | "success" | "error";

export type ProgressEvent = {
  type: "progress";
  step: string;
  status: ProgressStatus;
};

export type ResultEvent = {
  type: "result";
  data: unknown;
};

export type ResultAnalysisData = {
  summary: string;
  insights: string[];
  chart_recommendation?: {
    type?: string;
    x?: string;
    y?: string;
    reason?: string;
  } | null;
  result_facts?: {
    row_count?: number;
    columns?: string[];
    dimension_columns?: string[];
    metric_columns?: string[];
    time_columns?: string[];
    top_values?: Record<string, { label?: unknown; value?: unknown }>;
    chart_candidates?: Array<Record<string, unknown>>;
  } | null;
  generated_by?: string;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

export type UnableToAnswerEvent = {
  type: "unable_to_answer";
  status: "unable_to_answer";
  reason?: string;
  missing_concepts?: string[];
  suggestion?: string;
};

export type ContextTraceData = {
  original_query: string;
  resolved_query: string;
  is_follow_up: boolean;
  inherited_context: Record<string, unknown>;
  overwritten_context: Record<string, unknown>;
  source_turn_id?: string | number | null;
  rewrite_method: string;
  confidence?: number;
};

export type ContextTraceEvent = {
  type: "context_trace";
  data: ContextTraceData;
};

export type ResultAnalysisEvent = {
  type: "result_analysis";
  data: ResultAnalysisData;
};

export type QueryExplanationData = {
  business: {
    question?: string;
    resolved_question?: string;
    metrics?: string[];
    dimensions?: string[];
    time_range?: string;
    filters?: string[];
    result_summary?: string | null;
  };
  technical: {
    visibility: "admin_masked";
    sql_visible_to_user?: boolean;
    sql?: string;
    fields?: string[];
  };
  risk?: {
    level: "low" | "medium" | "high";
    label: string;
    reasons: string[];
    actions: string[];
  } | null;
};

export type QueryExplanationEvent = {
  type: "query_explanation";
  data: QueryExplanationData;
};

export type EmptyResultDiagnosisData = {
  summary: string;
  query?: string;
  resolved_query?: string;
  possible_reasons: string[];
  suggestions: string[];
};

export type EmptyResultDiagnosisEvent = {
  type: "empty_result_diagnosis";
  data: EmptyResultDiagnosisData;
};

export type FollowupSuggestionsData = {
  summary: string;
  query?: string;
  resolved_query?: string;
  suggestions: string[];
};

export type FollowupSuggestionsEvent = {
  type: "followup_suggestions";
  data: FollowupSuggestionsData;
};

export type ClarificationEvent = {
  type: "clarification";
  message: string;
  options: string[];
  clarification_type: string;
};

export type OperationPlanData = {
  operation_type: string;
  target_object: string;
  target_table: string;
  target_columns: string[];
  condition_description: string;
  business_purpose: string;
  planned_sql: string;
  impact_count_sql: string;
  impact_preview_sql: string;
  impact_count: number;
  impact_summary: string;
  impact_dimensions: string[];
  threshold_level: string;
  preview_rows: Array<Record<string, unknown>>;
  risk_level: string;
  requires_approval: boolean;
  status: string;
  approval_id: string;
  approval_status: string;
  execution_status: string;
  submitter?: string;
  approver: string;
  created_at?: string;
  status_description: string;
  rollback_suggestion: string;
  execution_policy: string;
  warning?: string;
  execution_enabled: boolean;
};

export type OperationPlanEvent = {
  type: "operation_plan";
  data: OperationPlanData;
};

export type SessionEvent = {
  type: "session";
  session_id: string;
};

export type AgentEvent =
  | ProgressEvent
  | ResultEvent
  | ResultAnalysisEvent
  | QueryExplanationEvent
  | EmptyResultDiagnosisEvent
  | FollowupSuggestionsEvent
  | UnableToAnswerEvent
  | ErrorEvent
  | ContextTraceEvent
  | ClarificationEvent
  | OperationPlanEvent
  | SessionEvent;

export type StepState = {
  step: string;
  status: ProgressStatus;
  updatedAt: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status?: "streaming" | "done" | "error";
  steps?: StepState[];
  result?: unknown;
  resultAnalysis?: ResultAnalysisData;
  queryExplanation?: QueryExplanationData;
  emptyResultDiagnosis?: EmptyResultDiagnosisData;
  followupSuggestions?: FollowupSuggestionsData;
  error?: string;
  unableToAnswer?: boolean;
  contextTrace?: ContextTraceData;
  clarification?: ClarificationEvent & { originalQuery: string };
  operationPlan?: OperationPlanData;
};

export type QuerySession = {
  session_id: string;
  title?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type QueryHistoryItem = {
  query: string;
  resolved_query?: string | null;
  sql?: string | null;
  result_summary?: string | null;
  result_data?: unknown;
  context_trace?: ContextTraceData | null;
  result_facts?: ResultAnalysisData["result_facts"] | null;
  result_analysis?: ResultAnalysisData | null;
  query_explanation?: QueryExplanationData | null;
  semantic_slots?: Record<string, unknown> | null;
  rewrite_confidence?: number | null;
  status: string;
  error_message?: string | null;
  created_at?: string;
};
