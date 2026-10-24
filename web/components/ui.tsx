"use client";

import type { JobStatus } from "@/lib/types";

const STATUS: Record<JobStatus, { label: string; tone: Tone }> = {
  queued: { label: "Queued", tone: "neutral" },
  processing: { label: "Processing", tone: "info" },
  awaiting_approval: { label: "Awaiting approval", tone: "warn" },
  email_not_found: { label: "Email Not Found", tone: "warn" },
  approved: { label: "Approved", tone: "info" },
  sending: { label: "Sending", tone: "info" },
  sent: { label: "Sent", tone: "ok" },
  failed: { label: "Failed", tone: "bad" },
  terminated: { label: "Terminated", tone: "neutral" },
};

type Tone = "neutral" | "info" | "warn" | "ok" | "bad";

const TONE: Record<Tone, string> = {
  neutral: "bg-neutral-bg text-muted",
  info: "bg-info-bg text-info",
  warn: "bg-warn-bg text-warn",
  ok: "bg-ok-bg text-ok",
  bad: "bg-bad-bg text-bad",
};

export function statusLabel(s: JobStatus) {
  return STATUS[s].label;
}

export function StatusChip({ status }: { status: JobStatus }) {
  const { label, tone } = STATUS[status];
  const live = status === "processing" || status === "sending" || status === "queued";
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${TONE[tone]}`}>
      {live && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" aria-hidden />}
      {label}
    </span>
  );
}

export function ScoreDelta({ before, after }: { before: number | null; after: number | null }) {
  if (after == null) return <span className="text-muted">—</span>;
  const delta = before != null ? after - before : null;
  return (
    <span className="tabular-nums">
      <span className="font-semibold">{after}</span>
      {delta != null && delta !== 0 && (
        <span className={`ml-1 text-xs ${delta > 0 ? "text-ok" : "text-bad"}`}>
          {delta > 0 ? "+" : ""}
          {delta}
        </span>
      )}
    </span>
  );
}

export function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="animate-fade rounded-xl border border-bad/20 bg-bad-bg px-3.5 py-2.5 text-sm text-bad">
      {message}
    </p>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
      aria-hidden
    />
  );
}

export function timeAgo(iso: string) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
