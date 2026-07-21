/**
 * 数据变更审批卡片
 * 用于展示 AI 生成的变更方案和影响范围，第一版只允许取消或提交审批，不执行 DML。
 */
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { useState } from "react";
import type { OperationPlanData } from "../types/agent";
import { safeLabel, sanitizeDisplayText } from "../lib/displaySafe";
import { ResultTable } from "./ResultTable";

const riskLabels: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
};

const approvalLabels: Record<string, string> = {
  draft: "草稿",
  pending: "待审批",
  pending_approval: "待审批",
  approved: "已批准",
  rejected: "已拒绝",
  cancelled: "已取消",
  expired: "已过期",
};

const executionLabels: Record<string, string> = {
  not_executed: "未执行",
  blocked: "禁止执行",
  external_only: "仅外部系统执行",
};

const thresholdLabels: Record<string, string> = {
  none: "无影响",
  medium: "中风险阈值",
  high: "高风险阈值",
};

export function OperationPlanCard({ plan }: { plan: OperationPlanData }) {
  const initialApprovalStatus = plan.approval_status || plan.status || "pending";
  const [approvalStatus, setApprovalStatus] = useState<string>(
    initialApprovalStatus === "pending_approval" ? "pending" : initialApprovalStatus,
  );

  const statusText = approvalLabels[approvalStatus] ?? approvalStatus;
  const executionText = executionLabels[plan.execution_status] ?? plan.execution_status;
  const canSubmit = approvalStatus === "draft";
  const canCancel = approvalStatus === "draft" || approvalStatus === "pending";

  return (
    <section className="mt-4 border border-amber-500/30 bg-amber-50/70 shadow-line">
      <div className="flex items-center gap-2 border-b border-amber-500/20 px-4 py-3 text-sm font-semibold text-amber-800">
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        检测到数据变更请求
      </div>

      <div className="space-y-4 px-4 py-4 text-sm text-ink/80">
        <div>
          <div className="mb-2 text-xs font-semibold text-ink/50">操作摘要</div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Info label="操作类型" value={sanitizeDisplayText(plan.operation_type || "-")} />
            <Info label="目标对象" value={sanitizeDisplayText(plan.target_object || "业务数据")} />
            <Info label="变更条件" value={sanitizeDisplayText(plan.condition_description || "-")} />
            <Info label="业务目的" value={sanitizeDisplayText(plan.business_purpose || "根据用户诉求生成变更方案")} />
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold text-ink/50">影响范围预估</div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Info label="预计影响" value={`${plan.impact_count ?? 0} 行`} />
            <Info label="风险阈值" value={thresholdLabels[plan.threshold_level] ?? plan.threshold_level ?? "-"} />
            <Info label="影响维度" value={plan.impact_dimensions?.map(safeLabel).join("、") || "变更条件"} />
            <Info label="预估方式" value="只读 SELECT 统计与样例预览" />
          </div>
          <div className="mt-2 border border-ink/10 bg-white/65 px-3 py-2 text-ink/70">
            {sanitizeDisplayText(plan.impact_summary || "本次影响范围基于只读查询预估，不代表已执行变更。")}
          </div>
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold text-ink/50">审批状态</div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Info label="审批单号" value={plan.approval_id || "-"} />
            <Info label="审批状态" value={statusText} />
            <Info label="执行状态" value={executionText || "未执行"} />
            <Info label="审批人" value={plan.approver || "数据负责人"} />
            <Info label="风险等级" value={riskLabels[plan.risk_level] ?? plan.risk_level} />
            <Info label="执行策略" value={plan.execution_policy === "plan_only" ? "仅生成方案，不直接执行" : plan.execution_policy} />
          </div>
          <div className="mt-2 border border-moss/20 bg-moss/5 px-3 py-2 text-moss">
            {sanitizeDisplayText(plan.status_description || "当前仅生成变更方案，系统不会直接执行写操作。")}
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <Info label="业务对象" value={plan.target_table ? "业务数据" : "-"} />
          <Info label="目标字段" value={plan.target_columns?.length ? plan.target_columns.map(safeLabel).join("、") : "整行或新增记录"} />
        </div>

        <div className="border border-ink/10 bg-white/65 px-3 py-2">
          <div className="text-xs text-ink/45">回滚建议</div>
          <div className="mt-1 font-semibold text-ink">
            {sanitizeDisplayText(plan.rollback_suggestion || "执行前备份命中数据，需人工复核回滚方案。")}
          </div>
        </div>

        {plan.warning && (
          <div className="border border-amber-500/25 bg-white/70 px-3 py-2 text-amber-800">
            {sanitizeDisplayText(plan.warning)}
          </div>
        )}

        {plan.preview_rows?.length > 0 && <ResultTable data={plan.preview_rows} title="影响范围预览" />}

        {approvalStatus === "pending" && (
          <div className="border border-moss/25 bg-moss/5 px-3 py-2 text-moss">
            审批单已进入待审批状态。当前系统只生成方案和影响预估，不会执行任何删除、修改或新增操作。
          </div>
        )}

        {approvalStatus === "cancelled" && (
          <div className="border border-ink/10 bg-white/70 px-3 py-2 text-ink/60">
            已取消本次变更申请，数据不会发生任何变化。
          </div>
        )}

        <div className="flex flex-wrap gap-2 border-t border-amber-500/20 pt-3">
          <button
            type="button"
            disabled={!canCancel}
            onClick={() => setApprovalStatus("cancelled")}
            className="border border-ink/15 bg-white/75 px-3 py-2 text-sm font-semibold text-ink/70 disabled:cursor-not-allowed disabled:opacity-45"
          >
            取消申请
          </button>
          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => setApprovalStatus("pending")}
            className="inline-flex items-center gap-2 bg-ink px-3 py-2 text-sm font-semibold text-parchment disabled:cursor-not-allowed disabled:bg-ink/40"
          >
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            提交审批
          </button>
        </div>
      </div>
    </section>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-ink/10 bg-white/65 px-3 py-2">
      <div className="text-xs text-ink/45">{label}</div>
      <div className="mt-1 font-semibold text-ink">{value}</div>
    </div>
  );
}
