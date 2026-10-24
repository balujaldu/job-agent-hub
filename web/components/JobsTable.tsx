"use client";

import type { JobSummary } from "@/lib/types";
import { ScoreDelta, StatusChip, timeAgo } from "./ui";

export function JobsTable({ jobs, selectedId, onSelect }: { jobs: JobSummary[]; selectedId: number | null; onSelect: (id: number) => void }) {
  if (jobs.length === 0) {
    return (
      <div className="card animate-in px-6 py-14 text-center text-sm text-muted">
        No jobs here yet. Paste a job description or drop a screenshot above to start.
      </div>
    );
  }
  return (
    <div className="card animate-in overflow-x-auto">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-muted">
            <th className="px-4 py-2.5 font-semibold">Company / role</th>
            <th className="px-4 py-2.5 font-semibold">Recipient</th>
            <th className="px-4 py-2.5 text-right font-semibold">ATS</th>
            <th className="px-4 py-2.5 font-semibold">Status</th>
            <th className="px-4 py-2.5 text-right font-semibold">Added</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr
              key={j.id}
              onClick={() => onSelect(j.id)}
              onKeyDown={(e) => e.key === "Enter" && onSelect(j.id)}
              tabIndex={0}
              aria-selected={selectedId === j.id}
              className={`cursor-pointer border-b border-line outline-none transition-colors duration-150 last:border-0 hover:bg-accent/6 focus-visible:bg-accent/8 ${
                selectedId === j.id ? "bg-accent/10" : ""
              }`}
            >
              <td className="px-4 py-3">
                <div className="font-medium">{j.company || <span className="text-muted">Reading posting…</span>}</div>
                <div className="text-muted">{j.role}</div>
              </td>
              <td className="max-w-56 truncate px-4 py-3">{j.to_email || <span className="text-muted">—</span>}</td>
              <td className="px-4 py-3 text-right">
                <ScoreDelta before={j.ats_before} after={j.ats_after} />
              </td>
              <td className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusChip status={j.status} />
                </div>
                {j.status === "failed" && j.error && <div className="mt-1 max-w-72 truncate text-xs text-bad">{j.error}</div>}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right text-muted">{timeAgo(j.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
