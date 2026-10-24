"use client";

import type { AppSettings } from "@/lib/types";

// Gmail: sends the user to Google's own consent page.
export function ConnectedAccounts({ s, busy, post }: { s: AppSettings; busy: boolean; post: (path: string) => void }) {
  return (
    <div className="divide-y divide-line">
      <Row
        title="Gmail"
        detail={
          s.gmail.address ? (
            <>
              Sending as <span className="font-medium text-fg">{s.gmail.address}</span>
            </>
          ) : (
            "Lets the agents send applications from your Gmail. Permission to send only, not to read your mail."
          )
        }
      >
        {!s.gmail.configured ? (
          <SetupHint provider="Google" redirect={s.gmail.redirect_uri} vars={["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]} />
        ) : s.gmail.address ? (
          <button className="btn" onClick={() => post("/api/gmail/disconnect")} disabled={busy}>
            Disconnect
          </button>
        ) : (
          <a className="btn-primary" href="/api/gmail/connect">
            Connect Gmail
          </a>
        )}
      </Row>
    </div>
  );
}

function Row({ title, detail, children }: { title: string; detail: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3 py-4 first:pt-0 last:pb-0">
      <div className="min-w-0 flex-1 basis-56">
        <h3 className="text-sm font-medium">{title}</h3>
        <div className="mt-0.5 text-sm text-muted">{detail}</div>
      </div>
      {children}
    </div>
  );
}

function SetupHint({ provider, redirect, vars }: { provider: string; redirect: string; vars: string[] }) {
  return (
    <details className="w-full text-sm text-muted">
      <summary className="cursor-pointer text-warn">Not set up yet: the app owner needs to add {provider} credentials</summary>
      <p className="mt-2">
        Create an OAuth app with {provider}, add the redirect URL{" "}
        <code className="break-all rounded bg-surface-2 px-1.5 py-0.5 text-fg">{redirect}</code>, then put{" "}
        {vars.map((v, i) => (
          <span key={v}>
            {i > 0 && " and "}
            <code className="rounded bg-surface-2 px-1">{v}</code>
          </span>
        ))}{" "}
        in <code className="rounded bg-surface-2 px-1">api/.env</code> and restart the API. The README has step-by-step instructions.
      </p>
    </details>
  );
}
