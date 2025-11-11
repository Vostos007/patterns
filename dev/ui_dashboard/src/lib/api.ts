const LOCAL_DEFAULT = "http://localhost:9000";

export function getApiBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE;
  }

  if (typeof window !== "undefined") {
    if (window.location.port === "3050") {
      return LOCAL_DEFAULT;
    }
    return window.location.origin;
  }

  return LOCAL_DEFAULT;
}

export async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBase();
  const url = base ? `${base}${path}` : path;
  const resp = await fetch(url, init);
  if (!resp.ok) {
    throw new Error(`Request failed: ${resp.status}`);
  }
  return (await resp.json()) as T;
}
