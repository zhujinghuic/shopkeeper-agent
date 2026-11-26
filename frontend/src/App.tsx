/**
 * 前端应用主组件
 * 负责聊天会话状态、事件流消费和整体页面布局
 */
import { Plus, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { MessageBubble } from "./components/MessageBubble";
import { streamQuery } from "./lib/agentApi";
import type { AgentEvent, ChatMessage, StepState } from "./types/agent";

const examples = [
  "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
  "统计 2025 年 3 月各商品品类的销量和销售额",
  "查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
  "按会员等级统计 2025 年第一季度的订单数和销售额",
];

function makeId() {
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

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

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
      content: "正在理解你的问题…",
      createdAt: Date.now(),
      status: "streaming",
      steps: [],
    };

    const controller = new AbortController();
    setActiveController(controller);
    setDraft("");
    setMessages((current) => [...current, userMessage, assistantMessage]);

    const onEvent = (event: AgentEvent) => {
      setMessages((current) =>
        current.map((message) => {
          if (message.id !== assistantId) return message;

          if (event.type === "progress") {
            return {
              ...message,
              content: event.status === "running" ? `正在${event.step}…` : message.content,
              steps: upsertStep(message.steps, event),
            };
          }

          if (event.type === "result") {
            const rows = Array.isArray(event.data) ? event.data.length : 0;
            return {
              ...message,
              status: "done",
              content: rows > 0 ? `已经查好了，共 ${rows} 条结果。` : "已经查好了，本次没有匹配的数据。",
              result: event.data,
            };
          }

          return {
            ...message,
            status: "error",
            content: "这次查询没有成功。",
            error: event.message,
          };
        }),
      );
    };

    try {
      await streamQuery(query, { signal: controller.signal, onEvent });
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId && message.status === "streaming"
            ? { ...message, status: "done", content: "流程已结束，但没有拿到查询结果。" }
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
                content: isAbort ? "已停止本次查询。" : "暂时连不上服务，请稍后再试。",
                error: isAbort ? undefined : error instanceof Error ? error.message : String(error),
              }
            : message,
        ),
      );
    } finally {
      setActiveController(null);
    }
  };

  const stopQuery = () => {
    activeController?.abort();
  };

  const clearConversation = () => {
    if (isStreaming) return;
    setMessages([]);
    setDraft("");
  };

  return (
    <div className="relative flex h-dvh flex-col overflow-hidden bg-canvas text-ink">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-[radial-gradient(70%_100%_at_50%_0%,rgba(77,107,254,0.10),transparent_72%)]" />

      <header className="relative z-10 flex h-16 shrink-0 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-brand to-[#7B8CFF] text-white shadow-soft">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </div>
          <span className="text-[15px] font-medium tracking-tight">问数助手</span>
        </div>

        <button
          type="button"
          onClick={clearConversation}
          disabled={messages.length === 0 || isStreaming}
          className="inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-medium text-muted transition hover:bg-surface hover:text-ink hover:shadow-soft disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:shadow-none"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          新对话
        </button>
      </header>

      <main
        ref={scrollRef}
        className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain"
      >
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-6 sm:px-6">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </div>
        )}
      </main>

      <div className="relative z-10 shrink-0 px-4 pb-3 sm:px-6">
        <Composer
          value={draft}
          disabled={!canSubmit}
          isStreaming={isStreaming}
          examples={examples}
          onChange={setDraft}
          onSubmit={() => startQuery()}
          onStop={stopQuery}
        />
      </div>
    </div>
  );
}
