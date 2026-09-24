const TOKEN_KEY = "aether_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setAuth(data) {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem("aether_user", JSON.stringify({ username: data.username, is_admin: data.is_admin }));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem("aether_user");
}

export function currentUser() {
  try {
    return JSON.parse(localStorage.getItem("aether_user") || "null");
  } catch {
    return null;
  }
}

export async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body && !(opts.body instanceof FormData) && typeof opts.body !== "string") {
    headers["Content-Type"] = "application/json";
    opts = { ...opts, body: JSON.stringify(opts.body) };
  }
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    clearAuth();
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : res.statusText;
    throw new Error(msg || "Request failed");
  }
  return data;
}

export function wsUrl(path) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}${path}`;
}
