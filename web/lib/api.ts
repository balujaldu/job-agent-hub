export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors
    return detail
      .map((d: { loc?: string[]; msg?: string }) => `${d.loc?.slice(1).join(".") ?? ""} ${d.msg ?? ""}`.trim())
      .join("; ");
  }
  return "Something went wrong.";
}

/* ---- Server wake-up ---------------------------------------------------------------
   The free backend sleeps after ~15 idle minutes and takes up to a minute to start. While
   any request is slow or being retried, ServerWakeNotice tells the user what's happening. */

const SLOW_AFTER_MS = 4000; // show the notice once a request has waited this long
const WAKE_RETRY_MS = 120_000; // keep retrying reads for up to this long
const RETRY_EVERY_MS = 3000;
const GATEWAY_ERRORS = new Set([502, 503, 504]); // the proxy gave up waiting for the backend

let slowRequests = 0;
const listeners = new Set<(waking: boolean) => void>();

export function onServerWaking(listener: (waking: boolean) => void): () => void {
  listeners.add(listener);
  listener(slowRequests > 0);
  return () => listeners.delete(listener);
}

function markSlow(delta: 1 | -1) {
  slowRequests = Math.max(0, slowRequests + delta);
  listeners.forEach((l) => l(slowRequests > 0));
}

const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  // Only reads are retried automatically: repeating a POST could create a job or approve twice.
  const retryable = (rest.method ?? "GET").toUpperCase() === "GET";
  const started = Date.now();
  let slow = false;
  const becomeSlow = () => {
    if (!slow) {
      slow = true;
      markSlow(1);
    }
  };
  const timer = setTimeout(becomeSlow, SLOW_AFTER_MS);

  try {
    for (;;) {
      let res: Response;
      try {
        res = await fetch(path, {
          ...rest,
          credentials: "same-origin",
          headers: json !== undefined ? { "Content-Type": "application/json", ...rest.headers } : rest.headers,
          body: json !== undefined ? JSON.stringify(json) : rest.body,
        });
      } catch {
        if (retryable && Date.now() - started < WAKE_RETRY_MS) {
          becomeSlow();
          await pause(RETRY_EVERY_MS);
          continue;
        }
        throw new ApiError(0, "Can't reach the server. Check your internet connection and try again.");
      }

      if (GATEWAY_ERRORS.has(res.status)) {
        if (retryable && Date.now() - started < WAKE_RETRY_MS) {
          becomeSlow();
          await pause(RETRY_EVERY_MS);
          continue;
        }
        throw new ApiError(
          res.status,
          retryable
            ? "The server didn't start in time. Please refresh the page in a minute."
            : "The server was still starting up, so this didn't go through. Please try again.",
        );
      }

      if (!res.ok) {
        let message = res.statusText;
        try {
          message = detailMessage((await res.json()).detail);
        } catch {
          /* non-JSON error body */
        }
        if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/api/auth/")) {
          window.location.href = "/login";
        }
        throw new ApiError(res.status, message);
      }
      return (await res.json()) as T;
    }
  } finally {
    clearTimeout(timer);
    if (slow) markSlow(-1);
  }
}
