"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { ACTIVE_STATUSES, type JobStatus, type JobSummary } from "@/lib/types";
import { AppShell } from "@/components/AppShell";
import { JobDrawer } from "@/components/JobDrawer";
import { JobsTable } from "@/components/JobsTable";
import { NewJob } from "@/components/NewJob";
import { statusLabel } from "@/components/ui";

const FILTERS: { key: string; label: string; match: (s: JobStatus) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  { key: "review", label: "Needs you", match: (s) => s === "awaiting_approval" || s === "email_not_found" || s === "failed" },
  { key: "active", label: "In progress", match: (s) => ACTIVE_STATUSES.includes(s) },
  { key: "sent", label: statusLabel("sent"), match: (s) => s === "sent" },
  { key: "closed", label: statusLabel("terminated"), match: (s) => s === "terminated" },
];

export default function JobsPage() {
  return (
    <AppShell>
      <Jobs />
    </AppShell>
  );
}

function Jobs() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<number | null>(null);

  const load = useCallback(() => api<JobSummary[]>("/api/jobs").then(setJobs).catch(() => {}), []);

  const anyActive = jobs.some((j) => ACTIVE_STATUSES.includes(j.status));

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const t = setInterval(load, anyActive ? 2500 : 15000);
    return () => clearInterval(t);
  }, [load, anyActive]);

  const counts = useMemo(() => Object.fromEntries(FILTERS.map((f) => [f.key, jobs.filter((j) => f.match(j.status)).length])), [jobs]);
  const visible = jobs.filter((j) => FILTERS.find((f) => f.key === filter)!.match(j.status));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            Your <span className="text-gradient">applications</span>
          </h1>
          <p className="mt-1 text-sm text-muted">Drop in a job post. The agents tailor your resume and draft the email; nothing is sent until you approve.</p>
        </div>
      </div>
      <NewJob
        onCreated={(job) => {
          setJobs((js) => [job, ...js]);
          setSelected(job.id);
        }}
      />
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter jobs">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            role="tab"
            aria-selected={filter === f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-full px-3.5 py-1.5 text-sm transition-all duration-200 ${
              filter === f.key
                ? "bg-linear-to-r from-accent to-accent-2 text-white shadow-md shadow-accent/25"
                : "glass text-muted hover:-translate-y-px hover:text-fg"
            }`}
          >
            {f.label}
            <span className="ml-1.5 tabular-nums opacity-70">{counts[f.key]}</span>
          </button>
        ))}
      </div>
      <JobsTable jobs={visible} selectedId={selected} onSelect={setSelected} />
      {selected != null && <JobDrawer jobId={selected} onClose={() => setSelected(null)} onChanged={load} />}
    </div>
  );
}
