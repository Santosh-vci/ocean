import type { CurrentUser } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

type RequestOptions = RequestInit & {
  body?: BodyInit | null;
};

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
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
