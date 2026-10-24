"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AppSettings } from "@/lib/types";
import { AppShell } from "@/components/AppShell";
import { ConnectedAccounts } from "@/components/ConnectedAccounts";
import { ErrorNote, Spinner } from "@/components/ui";

export default function SettingsPage() {
  return (
    <AppShell>
      <Suspense>
        <Settings />
      </Suspense>
    </AppShell>
  );
}

function Settings() {
  const params = useSearchParams();
  const [s, setS] = useState<AppSettings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<AppSettings>("/api/settings").then(setS).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
  }, [load]);

  async function update(patch: Partial<AppSettings>) {
    setError("");
    try {
      setS(await api<AppSettings>("/api/settings", { method: "PUT", json: patch }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function post(path: string) {
    setBusy(true);
    setError("");
    try {
      await api(path, { method: "POST" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!s) {
    return error ? (
      <ErrorNote message={error} />
    ) : (
      <div className="flex justify-center py-16 text-muted">
        <Spinner />
      </div>
    );
  }

  const gmailResult = params.get("gmail");

  return (
    <div className="stagger mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Settings</h1>
      <ErrorNote message={error} />

      <section className={`card flex items-center gap-4 p-5 ${s.sending_paused ? "border-bad" : ""}`}>
        <div className="flex-1">
          <h2 className="font-semibold">Pause all sending</h2>
          <p className="text-sm text-muted">Stops every email, including ones you already approved that haven&apos;t gone out. Agents keep preparing drafts.</p>
        </div>
        <Toggle checked={s.sending_paused} onChange={(v) => update({ sending_paused: v })} label="Pause all sending" danger />
      </section>

      <section className="card space-y-3 p-5">
        <div>
          <h2 className="font-semibold">Connected accounts</h2>
          <p className="text-sm text-muted">You sign in on Google&apos;s own page; this app never sees your Google password or needs API keys from you.</p>
        </div>
        {gmailResult === "connected" && <p className="rounded-xl bg-ok-bg px-3 py-2 text-sm text-ok">Gmail connected.</p>}
        {gmailResult === "error" && <ErrorNote message={`Gmail connection failed (${params.get("reason") ?? "unknown"}). Try again.`} />}
        <ConnectedAccounts s={s} busy={busy} post={post} />
      </section>

      <p className="text-xs text-muted">Agents run on {s.model}.</p>
    </div>
  );
}

function Toggle({ checked, onChange, label, danger }: { checked: boolean; onChange: (v: boolean) => void; label: string; danger?: boolean }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-all duration-300 ${checked ? (danger ? "bg-bad shadow-md shadow-bad/30" : "bg-linear-to-r from-accent to-accent-2 shadow-md shadow-accent/30") : "bg-muted/25"}`}
    >
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow-md transition-all duration-300 ease-[cubic-bezier(.3,1.5,.6,1)] ${checked ? "left-5.5" : "left-0.5"}`} />
    </button>
  );
}
