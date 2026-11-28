/**
 * 会话接口客户端
 * 封装会话列表、历史详情和删除会话三个接口
 * 所有请求都带超时：后端没起来时不能一直转圈，要及时把失败暴露给页面
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

// 会话接口都是小数据量，10 秒还没响应基本就是服务不可用
const TIMEOUT_MS = 10_000;

export type SessionSummary = {
  session_id: string;
  title: string;
  turn_count: number;
  updated_at: string | null;
};

export type SessionMessage = {
  role: "user" | "assistant";
  content: string;
  sql?: string | null;
  result?: unknown;
  row_count?: number | null;
  clarify?: boolean;
  created_at?: string | null;
};

export type SessionDetail = {
  session_id: string;
  title: string;
  messages: SessionMessage[];
};

/** 带上 HTTP 状态码的错误，调用方靠它区分“会话不存在”和“服务不可用” */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw new ApiError(`HTTP ${response.status}`, response.status);
    }
    return response;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      // status 0 表示请求没有走通：超时、端口没开、代理没起来都归到这里
      throw new ApiError("请求超时", 0);
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError(error instanceof Error ? error.message : String(error), 0);
  } finally {
    window.clearTimeout(timer);
  }
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const response = await request(`${API_BASE_URL}/api/sessions`);
  return (await response.json()) as SessionSummary[];
}

export async function fetchSessionDetail(sessionId: string): Promise<SessionDetail> {
  const response = await request(`${API_BASE_URL}/api/sessions/${sessionId}`);
  return (await response.json()) as SessionDetail;
}

export async function removeSession(sessionId: string): Promise<void> {
  try {
    await request(`${API_BASE_URL}/api/sessions/${sessionId}`, { method: "DELETE" });
  } catch (error) {
    // 会话本来就不存在，删除视为成功
    if (error instanceof ApiError && error.status === 404) return;
    throw error;
  }
}
