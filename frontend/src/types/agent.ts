/**
 * 智能体类型定义
 * 定义问数智能体前端使用的 SSE 事件、流程步骤和聊天消息类型
 */
export type ProgressStatus = "running" | "success" | "error";

export type ProgressEvent = {
  type: "progress";
  step: string;
  status: ProgressStatus;
};

export type ResultEvent = {
  type: "result";
  data: unknown;
  /** 本轮实际执行的 SQL，多轮问数时用户可以确认改了哪些条件 */
  sql?: string;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

/** 会话编号事件：首次请求由后端生成，前端后续请求沿用 */
export type SessionEvent = {
  type: "session";
  session_id: string;
};

/** 追问改写事件：from_history 为 true 表示结合了上文 */
export type RewriteEvent = {
  type: "rewrite";
  query: string;
  from_history: boolean;
};

/** 澄清事件：关键口径缺失时不再硬生成 SQL，而是反问一句 */
export type ClarifyEvent = {
  type: "clarify";
  question: string;
  slots?: string[];
};

/** 拒绝事件：问数只读，删除/更新/导出类请求在改写阶段就被挡下 */
export type RejectEvent = {
  type: "reject";
  reason: string;
};

export type AgentEvent =
  | ProgressEvent
  | ResultEvent
  | ErrorEvent
  | SessionEvent
  | RewriteEvent
  | ClarifyEvent
  | RejectEvent;

export type StepState = {
  step: string;
  status: ProgressStatus;
  updatedAt: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status?: "streaming" | "done" | "error";
  steps?: StepState[];
  result?: unknown;
  error?: string;
  /** 本轮实际执行的 SQL */
  sql?: string;
  /** 结合上文改写后的完整问题 */
  rewritten?: { query: string; fromHistory: boolean };
  /** 这条助手消息是在向用户确认口径 */
  clarify?: boolean;
  /** 这条助手消息是在说明请求超出只读范围 */
  rejected?: boolean;
};
