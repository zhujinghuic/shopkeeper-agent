/**
 * 聊天消息组件
 * 用户消息为右侧圆角气泡，助手消息为左侧无边框内容流
 */
import { Copy, Sparkles } from "lucide-react";
import { ResultTable } from "./ResultTable";
import { StepRail } from "./StepRail";
import { cn, formatTime, toClipboardText } from "../lib/format";
import type { ChatMessage } from "../types/agent";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  const copy = async () => {
    const text = message.result ? toClipboardText(message.result) : message.content;
    await navigator.clipboard.writeText(text);
  };

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

        <div className="mt-2.5 flex items-center gap-1 text-[11px] text-muted/70">
          <span>{formatTime(message.createdAt)}</span>
          {message.status !== "streaming" && (
            <button
              type="button"
              onClick={copy}
              className="ml-1 rounded-md p-1 text-muted/70 opacity-0 transition hover:bg-brandSoft hover:text-brand focus:opacity-100 focus:outline-none group-hover:opacity-100"
              title="复制"
              aria-label="复制"
            >
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
