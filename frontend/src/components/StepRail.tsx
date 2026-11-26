/**
 * 执行进度组件
 * 以紧凑的进度条和状态标签展示各环节执行情况
 */
import { Activity, Check, LoaderCircle, X } from "lucide-react";
import { cn } from "../lib/format";
import type { ProgressStatus, StepState } from "../types/agent";

/** 环节的标准顺序，用于计算整体进度 */
const stepOrder = [
  "抽取关键词",
  "召回字段信息",
  "召回指标信息",
  "召回字段取值",
  "合并召回信息",
  "过滤表信息",
  "过滤指标信息",
  "添加额外上下文",
  "生成SQL",
  "校验SQL",
  "校正SQL",
  "执行SQL",
];

function StatusIcon({ status }: { status: ProgressStatus }) {
  if (status === "running") {
    return <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" />;
  }
  if (status === "success") {
    return <Check className="h-3 w-3" aria-hidden="true" />;
  }
  return <X className="h-3 w-3" aria-hidden="true" />;
}

export function StepRail({ steps = [] }: { steps?: StepState[] }) {
  if (steps.length === 0) return null;

  const statusMap = steps.reduce<Record<string, StepState>>((map, item) => {
    map[item.step] = item;
    return map;
  }, {});

  const visible = stepOrder
    .filter((step) => statusMap[step])
    .map((step) => ({ step, status: statusMap[step].status }));

  if (visible.length === 0) return null;

  const lastIndex = Math.max(...visible.map((item) => stepOrder.indexOf(item.step)));
  const progress = Math.round(((lastIndex + 1) / stepOrder.length) * 100);
  const running = visible.find((item) => item.status === "running");

  return (
    <section className="mt-4 rounded-2xl border border-line bg-surface/70 px-3.5 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-muted">
          <Activity className="h-3.5 w-3.5 text-brand/70" aria-hidden="true" />
          {running ? `正在${running.step}` : "执行进度"}
        </div>
        <span className="text-[11px] tabular-nums text-muted/80">{progress}%</span>
      </div>

      <div className="mt-2 h-1 overflow-hidden rounded-full bg-line">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand to-[#7B8CFF] transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {visible.map((item) => (
          <span
            key={item.step}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[11.5px] transition",
              item.status === "running" && "border-brand/25 bg-brandSoft text-brand",
              item.status === "success" && "border-success/20 bg-success/10 text-success",
              item.status === "error" && "border-danger/20 bg-danger/10 text-danger",
            )}
          >
            <StatusIcon status={item.status} />
            {item.step}
          </span>
        ))}
      </div>
    </section>
  );
}
