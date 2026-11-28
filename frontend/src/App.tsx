/**
 * 前端应用主组件
 * 负责会话列表、历史恢复、事件流消费和整体页面布局
 */
import { Menu, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Composer } from "./components/Composer";
import { EmptyState } from "./components/EmptyState";
import { MessageBubble } from "./components/MessageBubble";
import { SessionSidebar } from "./components/SessionSidebar";
import { streamQuery } from "./lib/agentApi";
import {
  ApiError,
  fetchSessionDetail,
  fetchSessions,
  removeSession,
  type SessionMessage,
  type SessionSummary,
} from "./lib/sessionApi";
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

// 会话编号存在浏览器本地：刷新页面后仍能回到上次的会话
const SESSION_KEY = "ask_session_id";

function readSessionId() {
  try {
    return localStorage.getItem(SESSION_KEY) || makeId();
  } catch {
    return makeId();
  }
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

/** 把后端回放的历史消息转成页面用的消息结构 */
function toChatMessages(messages: SessionMessage[]): ChatMessage[] {
  return messages.map((message) => ({
    id: makeId(),
    role: message.role,
    content: message.content,
    createdAt: message.created_at ? Date.parse(message.created_at) : Date.now(),
    status: "done" as const,
    result: message.result ?? undefined,
    sql: message.sql ?? undefined,
    clarify: message.clarify ?? false,
    rejected: message.rejected ?? false,
  }));
}

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string>(readSessionId);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState("");
  const [sessionsError, setSessionsError] = useState("");
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;

  useEffect(() => {
    try {
      localStorage.setItem(SESSION_KEY, sessionId);
    } catch {
      // 隐私模式下写不了本地存储，忽略即可，本次会话仍然可用
    }
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  useEffect(() => {
    // 首次进入：拉会话列表，并恢复上次停留的会话
    void refreshSessions();
    void restoreSession(sessionId);
    // 只在挂载时执行一次，后续切换会话由用户操作驱动
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refreshSessions() {
    try {
      setSessions(await fetchSessions());
      setSessionsError("");
    } catch (error) {
      // 列表加载失败不影响问数主流程，但要让用户知道是服务没通，而不是“没有历史”
      setSessionsError(
        error instanceof ApiError && error.status === 0
          ? "会话服务无响应"
          : "会话列表加载失败",
      );
    }
  }

  async function restoreSession(id: string) {
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const detail = await fetchSessionDetail(id);
      setMessages(toChatMessages(detail.messages));
      setSessionId(id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        // 新会话还没落库，接口会 404，保持空对话即可
        setMessages([]);
      } else {
        setMessages([]);
        setHistoryError(
          error instanceof ApiError && error.status === 0
            ? "连不上会话服务，请确认后端已启动后重试。"
            : `历史会话加载失败：${error instanceof Error ? error.message : String(error)}`,
        );
      }
    } finally {
      setHistoryLoading(false);
    }
  }

  const newChat = () => {
    if (isStreaming) return;
    setMessages([]);
    setDraft("");
    setHistoryError("");
    // 换会话编号；新会话要等第一轮落库后才会出现在左侧列表
    setSessionId(makeId());
    setSidebarOpen(false);
  };

  const selectSession = async (id: string) => {
    setSidebarOpen(false);
    if (isStreaming || id === sessionId) return;
    setDraft("");
    await restoreSession(id);
  };

  const deleteSession = async (id: string) => {
    if (isStreaming) return;
    try {
      await removeSession(id);
    } catch {
      // 删除失败也刷新一次列表，让状态回到真实情况
    }
    await refreshSessions();
    if (id === sessionId) {
      setMessages([]);
      setHistoryError("");
      setSessionId(makeId());
    }
  };

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
      // 会话编号由后端首轮下发，前端后续请求沿用它
      if (event.type === "session") {
        setSessionId(event.session_id);
        return;
      }

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

          if (event.type === "rewrite") {
            // 追问被改写成完整问题时给用户一个说明，避免答案看起来答非所问
            return {
              ...message,
              rewritten: { query: event.query, fromHistory: event.from_history },
            };
          }

          if (event.type === "clarify") {
            return {
              ...message,
              status: "done",
              clarify: true,
              content: event.question,
            };
          }

          if (event.type === "reject") {
            // 只读边界：不再往下生成 SQL，直接说明为什么不支持
            return {
              ...message,
              status: "done",
              rejected: true,
              content: event.reason,
            };
          }

          if (event.type === "result") {
            const rows = Array.isArray(event.data) ? event.data.length : 0;
            return {
              ...message,
              status: "done",
              content: rows > 0 ? `已经查好了，共 ${rows} 条结果。` : "已经查好了，本次没有匹配的数据。",
              result: event.data,
              sql: event.sql,
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
      await streamQuery(query, sessionId, { signal: controller.signal, onEvent });
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
      // 这一轮已经落库，刷新左侧列表的标题、轮数和排序
      void refreshSessions();
    }
  };

  const stopQuery = () => {
    activeController?.abort();
  };

  const sidebarProps = {
    sessions,
    activeId: sessionId,
    disabled: isStreaming,
    hint: sessionsError,
    onNew: newChat,
    onSelect: selectSession,
    onDelete: deleteSession,
    onRetry: () => void refreshSessions(),
  };

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas text-ink">
      {/* 桌面端常驻侧栏 */}
      <aside className="hidden w-[264px] shrink-0 border-r border-line md:block">
        <SessionSidebar {...sidebarProps} />
      </aside>

      {/* 移动端抽屉 */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div
            className="absolute inset-0 bg-ink/25"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative z-10 w-[264px] border-r border-line bg-surface shadow-float">
            <SessionSidebar {...sidebarProps} onClose={() => setSidebarOpen(false)} />
          </aside>
        </div>
      )}

      <div className="relative flex min-w-0 flex-1 flex-col">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-[radial-gradient(70%_100%_at_50%_0%,rgba(77,107,254,0.10),transparent_72%)]" />

        <header className="relative z-10 flex h-16 shrink-0 items-center gap-2 px-4 sm:px-6">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="grid h-9 w-9 place-items-center rounded-xl text-muted transition hover:bg-surface hover:text-ink md:hidden"
            aria-label="打开会话列表"
          >
            <Menu className="h-4 w-4" aria-hidden="true" />
          </button>

          <div className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-brand to-[#7B8CFF] text-white shadow-soft">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
          </div>
          <span className="text-[15px] font-medium tracking-tight">问数助手</span>
        </header>

        <main
          ref={scrollRef}
          className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain"
        >
          {historyLoading ? (
            <div className="flex h-full items-center justify-center text-[13px] text-muted">
              正在加载历史会话…
            </div>
          ) : historyError ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
              <p className="text-[13px] leading-6 text-muted">{historyError}</p>
              <button
                type="button"
                onClick={() => void restoreSession(sessionId)}
                className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[12.5px] text-ink transition hover:border-brand/40 hover:text-brand"
              >
                重新加载
              </button>
            </div>
          ) : messages.length === 0 ? (
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
    </div>
  );
}
