"use client";

import { useEffect, useState } from "react";
import { onServerWaking } from "@/lib/api";
import { Spinner } from "./ui";

/** Shown while a request is slow, which almost always means the free backend is waking up. */
export function ServerWakeNotice() {
  const [waking, setWaking] = useState(false);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => onServerWaking(setWaking), []);

  useEffect(() => {
    if (!waking) {
      setSeconds(0);
      return;
    }
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [waking]);

  if (!waking) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center px-4" role="status" aria-live="polite">
      <div className="glass-strong animate-pop pointer-events-auto flex max-w-md items-start gap-3 rounded-2xl px-4 py-3 text-sm">
        <Spinner className="mt-0.5 shrink-0 text-accent" />
        <div>
          <p className="font-medium">Starting the server…</p>
          <p className="mt-0.5 text-muted">
            After a quiet spell it takes up to a minute to wake up. Your data is safe, and the page continues on its own.
            {seconds >= 5 && <span className="tabular-nums"> ({seconds}s)</span>}
          </p>
        </div>
      </div>
    </div>
  );
}
