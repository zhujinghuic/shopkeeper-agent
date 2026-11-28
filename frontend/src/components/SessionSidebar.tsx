/**
 * 左侧会话列表
 * 展示历史会话标题和时间，支持新建、切换和删除
 */
import { MessageSquare, Plus, Trash2, X } from "lucide-react";
import { cn, formatSessionTime } from "../lib/format";
import type { SessionSummary } from "../lib/sessionApi";

type SessionSidebarProps = {
  sessions: SessionSummary[];
  activeId: string;
  disabled: boolean;
  /** 列表加载失败时的提示，为空表示一切正常 */
  hint?: string;
  onNew: () => void;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onRetry?: () => void;
  /** 移动端打开侧栏后需要关闭按钮 */
  onClose?: () => void;
};

export function SessionSidebar({
  sessions,
  activeId,
  disabled,
  hint,
  onNew,
  onSelect,
  onDelete,
  onRetry,
  onClose,
}: SessionSidebarProps) {
  return (
    <div className="flex h-full w-full flex-col bg-surface/70">
      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <span className="text-[13px] font-medium text-muted">会话</span>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="grid h-7 w-7 place-items-center rounded-lg text-muted transition hover:bg-brandSoft hover:text-brand md:hidden"
            aria-label="关闭会话列表"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={onNew}
          disabled={disabled}
          className="flex w-full items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2.5 text-[13.5px] font-medium text-ink transition hover:border-brand/40 hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          新对话
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4">
        {sessions.length === 0 ? (
          <div className="px-2.5 py-6 text-center text-[12.5px] leading-6 text-muted/70">
            {hint ? (
              <>
                <p className="text-muted">{hint}</p>
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="mt-2 rounded-lg border border-line bg-surface px-2.5 py-1 text-[12px] text-ink transition hover:border-brand/40 hover:text-brand"
                  >
                    重试
                  </button>
                )}
              </>
            ) : (
              <>
                还没有历史会话
                <br />
                问第一个问题后会出现在这里
              </>
            )}
          </div>
        ) : (
          <ul className="space-y-0.5">
            {sessions.map((session) => {
              const active = session.session_id === activeId;
              return (
                <li key={session.session_id}>
                  <div
                    className={cn(
                      "group flex items-start gap-2 rounded-xl px-2.5 py-2 transition",
                      active ? "bg-brandSoft" : "hover:bg-canvas",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(session.session_id)}
                      disabled={disabled}
                      className="min-w-0 flex-1 text-left disabled:cursor-not-allowed"
                    >
                      <span
                        className={cn(
                          "block truncate text-[13.5px] leading-5",
                          active ? "font-medium text-brand" : "text-ink/80",
                        )}
                        title={session.title}
                      >
                        {session.title}
                      </span>
                      <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted/70">
                        <MessageSquare className="h-3 w-3" aria-hidden="true" />
                        {session.turn_count} 轮
                        <span aria-hidden="true">·</span>
                        {formatSessionTime(session.updated_at)}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onDelete(session.session_id)}
                      disabled={disabled}
                      className="mt-0.5 rounded-md p-1 text-muted/60 opacity-0 transition hover:bg-danger/10 hover:text-danger focus:opacity-100 disabled:hidden group-hover:opacity-100"
                      title="删除会话"
                      aria-label="删除会话"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
