"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { AppSettings } from "@/lib/types";
import { AppShell } from "@/components/AppShell";
import { ConnectedAccounts } from "@/components/ConnectedAccounts";
import { ResumeSetup } from "@/components/ResumeSetup";
import { ErrorNote } from "@/components/ui";

export default function OnboardingPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<AppSettings>("/api/settings").then(setSettings).catch((e) => setError(e.message)), []);

  async function post(path: string) {
    setBusy(true);
    try {
      await api(path, { method: "POST" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell requireResume={false}>
      <div className="mx-auto max-w-3xl space-y-6">
        {settings ? (
          <>
            <div>
              <h1 className="text-2xl font-semibold">Connect Gmail</h1>
              <p className="mt-1 text-muted">
                Optional, and you can do it later in Settings. The button takes you to Google to sign in and allow sending; you
                don&apos;t need any API keys.
              </p>
            </div>
            <ErrorNote message={error} />
            <section className="card p-5">
              <ConnectedAccounts s={settings} busy={busy} post={post} />
            </section>
            <div className="flex justify-end">
              <button className="btn-primary" onClick={() => router.replace("/")}>
                Continue
              </button>
            </div>
          </>
        ) : (
          <>
            <div>
              <h1 className="text-2xl font-semibold">Start with your current resume</h1>
              <p className="mt-1 text-muted">
                The agents use it as the source of truth for every tailored resume: your employers, titles, dates and education are never changed.
              </p>
            </div>
            <ErrorNote message={error} />
            <ResumeSetup onConfirmed={load} />
          </>
        )}
      </div>
    </AppShell>
  );
}
