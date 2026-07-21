const BUSINESS_LABELS: Record<string, string> = {
  product_name: "商品",
  product: "商品",
  category: "商品品类",
  category_name: "商品品类",
  brand: "品牌",
  region_name: "大区",
  province: "省份",
  country: "国家",
  member_level: "会员等级",
  gender: "性别",
  date_id: "日期",
  order_date: "订单日期",
  month: "月份",
  quarter: "季度",
  year: "年份",
  day: "日期",
  order_amount: "销售额",
  pay_amount: "支付金额",
  gmv: "GMV",
  GMV: "GMV",
  order_quantity: "销量",
  quantity: "销量",
  order_count: "订单数",
  order_id: "订单数",
  customer_id: "客户",
  user_id: "用户",
  member_id: "会员",
  phone: "敏感信息",
  mobile: "敏感信息",
  address: "敏感信息",
  id_card: "敏感信息",
};

const INTERNAL_TOKEN_PATTERN =
  /\b(?:fact|dim|dwd|dws|ads|ods)_[A-Za-z0-9_]+\b|\b[A-Za-z]+_[A-Za-z0-9_]*\b/g;

const STEP_LABELS: Record<string, string> = {
  抽取关键词: "理解问题",
  召回字段信息: "匹配业务口径",
  召回指标信息: "匹配业务指标",
  召回字段取值: "匹配业务条件",
  合并召回信息: "整理候选信息",
  过滤权限上下文: "校验数据权限",
  过滤指标信息: "筛选业务指标",
  过滤表信息: "筛选可用数据",
  检查召回结果: "检查查询依据",
  添加额外上下文: "补充查询上下文",
  生成SQL: "生成查询方案",
  校验SQL: "校验查询方案",
  校正SQL: "修正查询方案",
  执行SQL: "执行查询",
  无法回答: "无法回答",
};

export function safeLabel(raw: unknown): string {
  const text = String(raw ?? "").trim();
  if (!text) return "";
  const mapped = BUSINESS_LABELS[text] ?? BUSINESS_LABELS[text.toLowerCase()];
  if (mapped) return mapped;
  if (isInternalToken(text)) return "业务字段";
  return sanitizeDisplayText(text);
}

export function safeStepLabel(step: string): string {
  return STEP_LABELS[step] ?? sanitizeDisplayText(step);
}

export function sanitizeDisplayText(raw: unknown): string {
  const text = String(raw ?? "");
  if (!text) return "";

  return text.replace(INTERNAL_TOKEN_PATTERN, (token) => BUSINESS_LABELS[token] ?? BUSINESS_LABELS[token.toLowerCase()] ?? "业务字段");
}

export function sanitizeDisplayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeDisplayValue(item)).join("、");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entryValue]) => `${safeLabel(key)}=${sanitizeDisplayValue(entryValue)}`)
      .join("，");
  }
  return sanitizeDisplayText(value);
}

export function sanitizeResultRows(data: unknown): Array<Record<string, string>> {
  const rows = normalizeRows(data);
  return rows.map((row, index) => sanitizeRow(row, index));
}

export function summarizeSafeResult(data: unknown): string {
  const rows = sanitizeResultRows(data);
  if (rows.length === 0) return "查询完成，结果为空。";

  const columns = collectColumns(rows);
  return `查询完成，共 ${rows.length} 行结果，字段：${columns.join("、")}`;
}

export function toSafeClipboardText(value: unknown): string {
  const rows = sanitizeResultRows(value);
  if (rows.length === 0) return sanitizeDisplayValue(value);

  const columns = collectColumns(rows);
  return [
    columns.join("\t"),
    ...rows.map((row) => columns.map((column) => row[column] ?? "").join("\t")),
  ].join("\n");
}

export function collectColumns(rows: Array<Record<string, unknown>>): string[] {
  return Array.from(
    rows.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(safeLabel(key)));
      return keys;
    }, new Set<string>()),
  );
}

function sanitizeRow(row: Record<string, unknown>, rowIndex: number): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(row)) {
    const safeKey = safeLabel(key) || `字段${rowIndex + 1}`;
    result[safeKey] = sanitizeDisplayValue(value);
  }
  return result;
}

function normalizeRows(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) {
    return data.map((item, index) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? (item as Record<string, unknown>)
        : { 序号: index + 1, 值: item },
    );
  }

  if (data && typeof data === "object" && !Array.isArray(data)) {
    return [data as Record<string, unknown>];
  }

  return data === null || data === undefined || data === "" ? [] : [{ 值: data }];
}

function isInternalToken(text: string): boolean {
  return /^(?:fact|dim|dwd|dws|ads|ods)_/i.test(text) || /^[a-z]+_[a-z0-9_]*$/i.test(text);
}
