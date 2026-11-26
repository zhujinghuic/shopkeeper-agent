/**
 * 查询结果表格组件
 * 将后端返回的结构化数据归一化为可滚动表格
 */
import { Rows3 } from "lucide-react";

function normalizeRows(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) {
    return data.map((item, index) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? (item as Record<string, unknown>)
        : { 序号: index + 1, 值: item },
    );
  }

  if (data && typeof data === "object") {
    return [data as Record<string, unknown>];
  }

  return [{ 值: data ?? "" }];
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ResultTable({ data }: { data: unknown }) {
  const rows = normalizeRows(data);
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
    <section className="mt-4 overflow-hidden rounded-2xl border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <div className="text-[12.5px] font-medium text-ink/80">查询结果</div>
        <div className="inline-flex items-center gap-1 text-[11px] text-muted">
          <Rows3 className="h-3.5 w-3.5" aria-hidden="true" />
          {rows.length} 行
        </div>
      </div>

      <div className="max-h-[360px] overflow-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-[13px]">
          <thead className="sticky top-0 z-10 bg-canvas">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  scope="col"
                  className="whitespace-nowrap border-b border-line px-4 py-2.5 font-medium text-muted"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="transition hover:bg-brandSoft/40">
                {columns.map((column) => (
                  <td
                    key={column}
                    className="whitespace-nowrap border-b border-line/70 px-4 py-2.5 text-ink/85 last:border-r-0"
                  >
                    {formatCell(row[column])}
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
