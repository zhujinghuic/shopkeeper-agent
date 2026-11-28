/**
 * 聊天消息组件
 * 用户消息为右侧圆角气泡，助手消息为左侧无边框内容流
 */
import { useState } from "react";
import { Check, CircleHelp, Copy, CornerDownRight, Sparkles } from "lucide-react";
import { ResultTable } from "./ResultTable";
import { StepRail } from "./StepRail";
import { cn, copyText, formatTime } from "../lib/format";
import type { ChatMessage } from "../types/agent";

/** 复制按钮：点完给一个短反馈，避免用户不知道有没有复制上 */
function CopyButton({
  text,
  label,
  className,
}: {
  text: string;
  label: string;
  className?: string;
}) {
  const [state, setState] = useState<"idle" | "done" | "fail">("idle");

  const run = async () => {
    const ok = await copyText(text);
    setState(ok ? "done" : "fail");
    window.setTimeout(() => setState("idle"), 1800);
  };

  return (
    <button
      type="button"
      onClick={run}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] transition",
        state === "fail"
          ? "text-danger"
          : state === "done"
            ? "text-brand"
            : "text-muted hover:bg-brandSoft hover:text-brand",
        className,
      )}
      title={`${label}到剪贴板`}
      aria-label={label}
    >
      {state === "done" ? (
        <Check className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Copy className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      {state === "done" ? "已复制" : state === "fail" ? "复制失败" : label}
    </button>
  );
}

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <article className="flex animate-fade-in justify-end">
        <div className="max-w-[82%] whitespace-pre-wrap rounded-3xl rounded-tr-md bg-brandSoft px-4 py-2.5 text-[15px] leading-7 text-ink">
          {message.content}
        </div>
      </article>
    );
  }

  return (
    <article className="group flex animate-fade-in gap-3">
      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand to-[#7B8CFF] text-white shadow-soft">
        <Sparkles className="h-4 w-4" aria-hidden="true" />
      </div>

      <div className="min-w-0 flex-1">
        {message.rewritten?.fromHistory && (
          <div className="mb-2 flex items-start gap-1.5 text-[12px] leading-5 text-muted">
            <CornerDownRight className="mt-1 h-3 w-3 shrink-0" aria-hidden="true" />
            <span>
              结合上文理解为：<span className="text-ink/70">{message.rewritten.query}</span>
            </span>
          </div>
        )}

        {message.clarify && (
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-brandSoft px-2.5 py-1 text-[11px] font-medium text-brand">
            <CircleHelp className="h-3 w-3" aria-hidden="true" />
            需要你补充一下
          </div>
        )}

        <div
          className={cn(
            "whitespace-pre-wrap text-[15px] leading-7",
            message.status === "streaming" ? "text-muted" : "text-ink",
          )}
        >
          {message.content}
        </div>

        {message.error && (
          <div className="mt-3 rounded-xl border border-danger/20 bg-danger/5 px-3.5 py-2.5 text-[13px] leading-6 text-danger">
            {message.error}
          </div>
        )}

        <StepRail steps={message.steps} />
        {message.result !== undefined && <ResultTable data={message.result} />}

        {message.sql && (
          // 折叠展示：默认收起，保持页面干净，需要核对口径时再展开
          <details className="mt-3">
            <summary className="w-fit cursor-pointer list-none text-[12px] text-muted transition hover:text-brand">
              查看本轮生成的 SQL
            </summary>
            <div className="mt-2 overflow-hidden rounded-xl border border-line bg-canvas">
              <div className="flex items-center justify-between border-b border-line/70 px-2 py-1">
                <span className="pl-1 text-[11px] tracking-wide text-muted/60">SQL</span>
                <CopyButton text={message.sql} label="复制 SQL" />
              </div>
              <pre className="max-h-64 overflow-auto px-3.5 py-3 text-[12px] leading-6 text-ink/80">
                {message.sql}
              </pre>
            </div>
          </details>
        )}

        <div className="mt-2.5 flex items-center gap-1 text-[11px] text-muted/70">
          <span>{formatTime(message.createdAt)}</span>
        </div>
      </div>
    </article>
  );
}
