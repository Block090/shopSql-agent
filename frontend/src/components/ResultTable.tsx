/**
 * 查询结果表格组件
 * 将后端返回的结构化数据归一化为可滚动表格
 */
import { Database, Download, FileJson } from "lucide-react";
import { exportResultToCsv } from "../lib/exportCsv";
import { sanitizeResultRows } from "../lib/displaySafe";

export function ResultTable({ data, title = "查询结果" }: { data: unknown; title?: string }) {
  const rows = sanitizeResultRows(data);
  const columns = Array.from(
    rows.reduce((keys, row) => {
      Object.keys(row).forEach((key) => keys.add(key));
      return keys;
    }, new Set<string>()),
  );

  if (columns.length === 0) {
    return null;
  }

  return (
    <section className="mt-4 overflow-hidden border border-ink/10 bg-white/70 shadow-line">
      <div className="flex items-center justify-between border-b border-ink/10 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Database className="h-4 w-4 text-moss" aria-hidden="true" />
          {title}
        </div>
        <div className="flex items-center gap-2 text-xs text-ink/55">
          <button
            type="button"
            onClick={() => exportResultToCsv(data)}
            className="inline-flex items-center gap-1 border border-ink/10 bg-white/70 px-2 py-1 text-[11px] font-medium text-ink/70 transition hover:bg-white"
            title="导出 CSV"
            aria-label="导出 CSV"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
            CSV
          </button>
          <FileJson className="h-3.5 w-3.5" aria-hidden="true" />
          {rows.length} 行
        </div>
      </div>
      <div className="max-h-[360px] overflow-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead className="sticky top-0 z-10 bg-[#efe6d8]">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  scope="col"
                  className="border-b border-ink/10 px-4 py-3 font-semibold text-ink/70"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-white/45 even:bg-white/20">
                {columns.map((column) => (
                  <td key={column} className="border-b border-ink/5 px-4 py-3 text-ink/80">
                    {row[column]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
