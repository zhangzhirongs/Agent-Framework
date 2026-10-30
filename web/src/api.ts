let csrf = "";
export function setCSRF(value: string) { csrf = value; }

export async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const form = body instanceof FormData;
  const response = await fetch(`/api${path}`, {
    method, credentials: "same-origin", cache: "no-store",
    headers: { ...(body && !form ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" && csrf ? { "X-CSRF-Token": csrf } : {}) },
    body: body === undefined ? undefined : form ? body : JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") window.dispatchEvent(new Event("signed-out"));
    throw new Error(typeof result.detail === "string" ? result.detail : "请求失败，请稍后重试");
  }
  return result;
}

export type Profile = { id: string; username: string; is_admin: boolean; csrf_token: string };
export type Skill = { name: string; display_name?: string; description: string; author: string; content?: string; resources?: string[] };
export type Attachment = { id: string; name: string; media_type: string };
export type Message = { id: string; role: string; content: string; file_ids: string[]; skills: string[] };
export type RunUsage = { requests: number; input_bytes: number; input_tokens: number; output_tokens: number; total_tokens: number; usage_reported: boolean; cached_input_tokens: number; reasoning_output_tokens: number; omitted_history_items: number; request_input_bytes: number[] };
export type Run = { id: string; status: string; output: string; error: string; created: number; finished?: number; usage?: Partial<RunUsage> };
export type Thread = { id: string; title: string; created: number };
export type Detail = { thread: Thread; messages: Message[]; files: Attachment[]; runs: Run[] };
