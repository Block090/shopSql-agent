/**
 * CSV 导出工具
 * 把结果表格导出成浏览器可下载的 CSV 文件。
 */
import { collectColumns, sanitizeResultRows } from "./displaySafe";

function csvEscape(value: unknown) {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

export function exportResultToCsv(data: unknown, filename = "query-result.csv") {
  const rows = sanitizeResultRows(data);
  if (rows.length === 0) return false;

  const columns = collectColumns(rows);

  const lines = [
    columns.map((column) => csvEscape(column)).join(","),
    ...rows.map((row) => columns.map((column) => csvEscape(row[column])).join(",")),
  ];

  const blob = new Blob(["\ufeff", lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
  return true;
}
