import type { CurrentUser } from "../types";
import type { AssistantMode, NextActionResponse } from "../types/assistant";
import { normalizeNextActionResponse } from "../types/assistant";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

type RequestOptions = RequestInit & {
  body?: BodyInit | null;
};

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function getCsrfToken(): Promise<string> {
  const response = await apiFetch<{ csrfToken: string }>("/auth/csrf/");
  return response.csrfToken;
}

export async function login(username: string, password: string): Promise<CurrentUser> {
  const csrfToken = await getCsrfToken();
  return apiFetch<CurrentUser>("/auth/login/", {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken,
    },
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  const csrfToken = await getCsrfToken();
  await apiFetch<void>("/auth/logout/", {
    method: "POST",
    headers: {
      "X-CSRFToken": csrfToken,
    },
  });
}

export type NextActionParams = {
  route?: string;
  objectType?: string;
  objectId?: string | number;
  mode?: AssistantMode;
  limit?: number;
};

export async function fetchNextActions(
  params: NextActionParams = {},
): Promise<NextActionResponse> {
  const query = new URLSearchParams();
  if (params.route) query.set("route", params.route);
  if (params.objectType) query.set("object_type", params.objectType);
  if (params.objectId !== undefined) query.set("object_id", String(params.objectId));
  if (params.mode) query.set("mode", params.mode);
  if (params.limit !== undefined) query.set("limit", String(params.limit));

  const suffix = query.toString() ? `?${query.toString()}` : "";
  const raw = await apiFetch<unknown>(`/assistant/next-actions/${suffix}`);
  return normalizeNextActionResponse(raw);
}
