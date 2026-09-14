export const API =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = sessionStorage.getItem("access_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`${API}${path}`, { ...options, headers });
  if (!response.ok) {
    if (response.status === 401) sessionStorage.removeItem("access_token");
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json();
}
export interface User {
  name: string;
  role: "manager" | "analyst";
}
export interface Item {
  id: string;
  type: string;
  title: string;
  status: string;
  owner_raw: string | null;
  due_at: string | null;
  validation_status: string;
}
export interface Chat {
  id: string;
  name: string;
  source: string;
}
export interface Evidence {
  message_id: string;
  chat_id: string;
  quote?: string;
  text: string;
  ts?: string;
}
export interface Action {
  id: string;
  kind: string;
  status: string;
  payload: { subject?: string; body?: string };
  result: unknown;
}
export interface Escalation {
  id: string;
  rule: string;
  severity: string;
  rationale: string;
  status: string;
}
export interface Run {
  id: string;
  agent: string;
  node: string;
  iteration: number;
  status: string;
  ts: string;
  output_summary: string;
}
