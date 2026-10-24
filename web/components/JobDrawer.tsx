"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { ACTIVE_STATUSES, type ATSDetail, type JobDetail, type Provenance, type TailoredResume } from "@/lib/types";
import { ErrorNote, Spinner, StatusChip, timeAgo } from "./ui";

type Tab = "overview" | "email" | "resume" | "activity";
const EDITABLE = ["awaiting_approval", "email_not_found", "failed"];

export function JobDrawer({ jobId, onClose, onChanged }: { jobId: number; onClose: () => void; onChanged: () => void }) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState("");

  const load = useCallback(
    () =>
      api<JobDetail>(`/api/jobs/${jobId}`)
        .then(setJob)
        .catch((e) => setError(e.message)),
    [jobId],
  );

  useEffect(() => {
    setJob(null);
    setError("");
    load();
  }, [load]);

  const active = !!job && ACTIVE_STATUSES.includes(job.status);
  useEffect(() => {
    if (!active) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [active, load]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  /** Runs an action that returns the updated job. */
  const act = useCallback(
    async (path: string, init: RequestInit & { json?: unknown } = { method: "POST" }) => {
      setError("");
      try {
        const updated = await api<JobDetail>(path, init);
        if (updated && "id" in updated) setJob(updated);
        onChanged();
        return true;
      } catch (e) {
        setError((e as Error).message);
        return false;
      }
    },
    [onChanged],
  );

  return (
    <>
      <div className="animate-fade fixed inset-0 z-30 bg-black/25 backdrop-blur-[2px] lg:bg-black/15" onClick={onClose} aria-hidden />
      <aside
        role="dialog"
        aria-label="Job details"
        className="glass-strong animate-slide fixed inset-y-0 right-0 z-40 flex w-full max-w-3xl flex-col sm:inset-y-3 sm:right-3 sm:w-[calc(100%-1.5rem)] sm:rounded-3xl"
      >
        <header className="flex items-start gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-lg font-semibold tracking-tight">{job?.company || "New job"}</h2>
              {job && <StatusChip status={job.status} />}
            </div>
            <p className="truncate text-sm text-muted">{job?.role || (job ? "Agents are reading the posting…" : "")}</p>
          </div>
          <button className="btn h-9 w-9 rounded-full p-0" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </header>

        <nav className="flex gap-1 overflow-x-auto border-b border-line px-3 py-2" role="tablist">
          {(
            [
              ["overview", "Overview"],
              ["email", "Email"],
              ["resume", "Resume"],
              ["activity", `Activity${job ? ` (${job.events.length})` : ""}`],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`whitespace-nowrap rounded-xl px-3 py-1.5 text-sm transition-all duration-200 ${
                tab === key ? "bg-linear-to-r from-accent to-accent-2 font-medium text-white shadow-md shadow-accent/25" : "text-muted hover:bg-surface-2 hover:text-fg"
              }`}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="flex-1 overflow-y-auto p-5">
          {!job ? (
            error ? (
              <ErrorNote message={error} />
            ) : (
              <div className="flex justify-center py-16 text-muted">
                <Spinner />
              </div>
            )
          ) : (
            <div key={tab} className="animate-in space-y-4">
              {error && <ErrorNote message={error} />}
              {job.status === "failed" && job.error && <ErrorNote message={job.error} />}
              {tab === "overview" && <Overview job={job} />}
              {tab === "email" && <EmailTab job={job} act={act} />}
              {tab === "resume" && <ResumeTab job={job} act={act} />}
              {tab === "activity" && <Activity job={job} />}
            </div>
          )}
        </div>

        {job && <Footer job={job} act={act} goTo={setTab} />}
      </aside>
    </>
  );
}

type Act = (path: string, init?: RequestInit & { json?: unknown }) => Promise<boolean>;

/* ---------------------------------------------------------------- footer -- */

function Footer({ job, act, goTo }: { job: JobDetail; act: Act; goTo: (t: Tab) => void }) {
  const [confirming, setConfirming] = useState<null | "send" | "terminate">(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => setConfirming(null), [job.status]);

  async function run(path: string, body?: unknown) {
    setBusy(true);
    await act(path, body === undefined ? { method: "POST" } : { method: "POST", json: body });
    setBusy(false);
    setConfirming(null);
  }

  const canTerminate = !["sending", "sent", "terminated"].includes(job.status);

  if (confirming) {
    return (
      <footer className="flex flex-wrap items-center gap-3 border-t border-line px-5 py-3">
        <p className="flex-1 text-sm">
          {confirming === "send" ? (
            <>
              Send the email and tailored resume to <span className="font-semibold">{job.to_email}</span> from your Gmail?
            </>
          ) : (
            "Terminate this job? Nothing will be sent."
          )}
        </p>
        <button className="btn" onClick={() => setConfirming(null)} disabled={busy}>
          Cancel
        </button>
        {confirming === "send" ? (
          <button className="btn-primary" onClick={() => run(`/api/jobs/${job.id}/approve-email`)} disabled={busy}>
            {busy && <Spinner />} Yes, send it
          </button>
        ) : (
          <button className="btn-danger" onClick={() => run(`/api/jobs/${job.id}/terminate`)} disabled={busy}>
            {busy && <Spinner />} Terminate
          </button>
        )}
      </footer>
    );
  }

  return (
    <footer className="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3">
      {job.has_pdf && (
        <a className="btn" href={`/api/jobs/${job.id}/resume.pdf?download=1`}>
          Download resume
        </a>
      )}
      <div className="flex-1 text-sm text-muted">
        {job.status === "email_not_found" && (
          <>
            No hiring email found.{" "}
            <button className="underline hover:text-fg" onClick={() => goTo("email")}>
              Add one
            </button>{" "}
            or copy the draft.
          </>
        )}
        {job.status === "sent" && job.sent_at && <>Sent {timeAgo(job.sent_at)}</>}
        {(job.status === "queued" || job.status === "processing") && "Agents are working. Nothing is sent without your approval."}
      </div>
      {canTerminate && (
        <button className="btn-danger" onClick={() => setConfirming("terminate")}>
          Terminate
        </button>
      )}
      {job.status === "failed" && (
        <>
          {job.email_body && job.to_email && (
            <button className="btn" onClick={() => run(`/api/jobs/${job.id}/retry`, { mode: "resend" })} disabled={busy}>
              Back to approval
            </button>
          )}
          <button className="btn" onClick={() => run(`/api/jobs/${job.id}/retry`, { mode: "reprocess" })} disabled={busy}>
            Reprocess
          </button>
        </>
      )}
      {job.status === "awaiting_approval" && (
        <button className="btn-primary" onClick={() => setConfirming("send")}>
          Approve &amp; send email
        </button>
      )}
    </footer>
  );
}

/* -------------------------------------------------------------- overview -- */

function Overview({ job }: { job: JobDetail }) {
  const [showSource, setShowSource] = useState(false);
  const rows: [string, React.ReactNode][] = [
    ["Role", job.role],
    ["Location", job.location],
    ["Recruiter", job.recruiter_name],
    [
      "Website",
      job.company_website && (
        <a className="text-accent hover:underline" href={job.company_website} target="_blank" rel="noreferrer">
          {job.company_website}
        </a>
      ),
    ],
    [
      "Posting",
      job.job_url && (
        <a className="break-all text-accent hover:underline" href={job.job_url} target="_blank" rel="noreferrer">
          {job.job_url}
        </a>
      ),
    ],
    ["Recipient", job.to_email ? `${job.to_email} (${sourceLabel(job.email_source)})` : "Not found"],
  ];
  return (
    <>
      <section className="card p-4">
        <dl className="grid grid-cols-[110px_1fr] gap-x-4 gap-y-2 text-sm">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted">{k}</dt>
              <dd className="min-w-0">{v || <span className="text-muted">—</span>}</dd>
            </div>
          ))}
        </dl>
      </section>

      {job.ats_after_detail && (
        <section className="card space-y-4 p-4">
          <h3 className="font-semibold">ATS score</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <Meter label="Your base resume" ats={job.ats_before_detail} />
            <Meter label="Tailored resume" ats={job.ats_after_detail} highlight />
          </div>
          <Keywords ats={job.ats_after_detail} />
          {job.ats_after_detail.format_issues.length > 0 && (
            <p className="text-sm text-warn">Format: {job.ats_after_detail.format_issues.join("; ")}</p>
          )}
          <p className="text-xs text-muted">
            Score = keyword coverage (70 points, using keywords pulled from this job description) + format checks (30 points). The same keyword list scores both versions.
          </p>
        </section>
      )}

      <section className="card p-4">
        <button className="text-sm font-medium text-accent hover:underline" onClick={() => setShowSource((s) => !s)}>
          {showSource ? "Hide" : "Show"} what you submitted
        </button>
        {showSource && (
          <div className="mt-3 space-y-3">
            {job.has_screenshot && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={`/api/jobs/${job.id}/screenshot`} alt="Submitted screenshot" className="max-w-full rounded-xl border border-line" />
            )}
            {job.source_text && <pre className="whitespace-pre-wrap rounded-xl bg-surface-2 p-3 text-xs">{job.source_text}</pre>}
            {job.jd_text && (
              <details>
                <summary className="cursor-pointer text-sm text-muted">Job description as the agent read it</summary>
                <pre className="mt-2 whitespace-pre-wrap rounded-xl bg-surface-2 p-3 text-xs">{job.jd_text}</pre>
              </details>
            )}
          </div>
        )}
      </section>
    </>
  );
}

function sourceLabel(source: string) {
  if (source === "input") return "from the posting";
  if (source === "entered by you") return source;
  return source ? `found on ${source.replace(/^https?:\/\//, "")}` : "";
}

function Meter({ label, ats, highlight }: { label: string; ats: ATSDetail | null; highlight?: boolean }) {
  const score = ats?.score ?? 0;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-muted">{label}</span>
        <span className={`text-2xl font-semibold tabular-nums ${highlight ? "" : "text-muted"}`}>{ats ? score : "—"}</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-2" role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={`h-full rounded-full transition-[width] duration-700 ease-out ${highlight ? "bg-linear-to-r from-accent to-accent-2" : "bg-muted/50"}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function Keywords({ ats }: { ats: ATSDetail }) {
  return (
    <div className="space-y-2 text-sm">
      <div>
        <span className="label">Matched ({ats.matched.length})</span>
        <div className="flex flex-wrap gap-1">
          {ats.matched.map((k) => (
            <span key={k} className="rounded bg-ok-bg px-1.5 py-0.5 text-xs text-ok">
              {k}
            </span>
          ))}
        </div>
      </div>
      {ats.missing.length > 0 && (
        <div>
          <span className="label">Still missing ({ats.missing.length})</span>
          <div className="flex flex-wrap gap-1">
            {ats.missing.map((k) => (
              <span key={k} className="rounded bg-bad-bg px-1.5 py-0.5 text-xs text-bad">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ----------------------------------------------------------------- email -- */

function useDraft<T extends Record<string, string>>(source: T) {
  const [draft, setDraft] = useState<T>(source);
  const [dirty, setDirty] = useState(false);
  const key = JSON.stringify(source);
  useEffect(() => {
    if (!dirty) setDraft(JSON.parse(key));
  }, [key, dirty]);
  return {
    draft,
    dirty,
    set: (patch: Partial<T>) => {
      setDraft((d) => ({ ...d, ...patch }));
      setDirty(true);
    },
    reset: () => setDirty(false),
  };
}

function EmailTab({ job, act }: { job: JobDetail; act: Act }) {
  const editable = EDITABLE.includes(job.status);
  const { draft, dirty, set, reset } = useDraft({ to_email: job.to_email, email_subject: job.email_subject, email_body: job.email_body });
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    const body: Record<string, string> = { email_subject: draft.email_subject, email_body: draft.email_body };
    if (draft.to_email.trim()) body.to_email = draft.to_email.trim();
    if (await act(`/api/jobs/${job.id}`, { method: "PATCH", json: body })) reset();
    setSaving(false);
  }

  if (!job.email_body && !editable) return <Pending what="The email draft" job={job} />;

  return (
    <section className="card space-y-4 p-4">
      <div>
        <label className="label" htmlFor="to">
          To
        </label>
        <input
          id="to"
          className="input"
          type="email"
          placeholder="Recipient email"
          value={draft.to_email}
          disabled={!editable}
          onChange={(e) => set({ to_email: e.target.value })}
        />
        {job.to_email && <p className="mt-1 text-xs text-muted">{sourceLabel(job.email_source)}</p>}
      </div>
      <div>
        <label className="label" htmlFor="subject">
          Subject
        </label>
        <input id="subject" className="input" value={draft.email_subject} disabled={!editable} onChange={(e) => set({ email_subject: e.target.value })} />
      </div>
      <div>
        <label className="label" htmlFor="body">
          Message
        </label>
        <textarea id="body" className="input min-h-72 leading-relaxed" value={draft.email_body} disabled={!editable} onChange={(e) => set({ email_body: e.target.value })} />
        <p className="mt-1 text-xs text-muted">The tailored resume PDF is attached automatically.</p>
      </div>
      <div className="flex items-center justify-end gap-2">
        <CopyButton text={`Subject: ${draft.email_subject}\n\n${draft.email_body}`} label="Copy email" />
        {editable && (
          <button className="btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving && <Spinner />} Save
          </button>
        )}
      </div>
      {dirty && job.status === "awaiting_approval" && <p className="text-right text-xs text-warn">Save your edits before approving.</p>}
    </section>
  );
}

/* ---------------------------------------------------------------- resume -- */

const PROV: Record<Provenance, { label: string; cls: string }> = {
  original: { label: "Original", cls: "bg-surface-2 text-muted" },
  reworded: { label: "Reworded", cls: "bg-info-bg text-info" },
  inferred: { label: "Inferred", cls: "bg-warn-bg text-warn" },
};

function ResumeTab({ job, act }: { job: JobDetail; act: Act }) {
  const [view, setView] = useState<"review" | "pdf">("review");
  const [draft, setDraft] = useState<TailoredResume | null>(job.tailored);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const editable = EDITABLE.includes(job.status);
  const tailoredKey = JSON.stringify(job.tailored);

  useEffect(() => {
    if (!dirty) setDraft(JSON.parse(tailoredKey));
  }, [tailoredKey, dirty]);

  if (!job.tailored || !draft) return <Pending what="The tailored resume" job={job} />;

  const inferredCount =
    draft.skills.filter((s) => s.provenance === "inferred").length +
    draft.experience.reduce((n, e) => n + e.bullets.filter((b) => b.provenance === "inferred").length, 0);

  function update(next: TailoredResume) {
    setDraft(next);
    setDirty(true);
  }

  async function save() {
    setSaving(true);
    if (await act(`/api/jobs/${job.id}/tailored`, { method: "PUT", json: { tailored: draft } })) setDirty(false);
    setSaving(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="glass inline-flex rounded-xl p-1 text-sm">
          {(["review", "pdf"] as const).map((v) => (
            <button key={v} onClick={() => setView(v)} className={`rounded-lg px-3 py-1 transition-all duration-200 ${view === v ? "bg-linear-to-r from-accent to-accent-2 font-medium text-white shadow-sm" : "text-muted hover:text-fg"}`}>
              {v === "review" ? "Review changes" : "PDF preview"}
            </button>
          ))}
        </div>
        {inferredCount > 0 && (
          <span className="text-sm text-warn">
            {inferredCount} inferred item{inferredCount === 1 ? "" : "s"}: check you can speak to each one.
          </span>
        )}
      </div>

      {view === "pdf" ? (
        job.has_pdf ? (
          <iframe title="Tailored resume" src={`/api/jobs/${job.id}/resume.pdf#view=FitH&v=${job.ats_after ?? 0}`} className="h-[75vh] w-full rounded-lg border border-line bg-white" />
        ) : (
          <Pending what="The PDF" job={job} />
        )
      ) : (
        <>
          <section className="card space-y-2 p-4">
            <span className="label">Summary</span>
            <textarea
              className="input min-h-20"
              value={draft.summary}
              disabled={!editable}
              onChange={(e) => update({ ...draft, summary: e.target.value })}
            />
          </section>

          <section className="card space-y-2 p-4">
            <span className="label">Skills</span>
            <div className="flex flex-wrap gap-1.5">
              {draft.skills.map((s, i) => (
                <span
                  key={s.name}
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs ${s.provenance === "inferred" ? "bg-inferred-bg ring-1 ring-inferred-line" : "bg-surface-2"}`}
                  title={PROV[s.provenance].label}
                >
                  {s.name}
                  {editable && (
                    <button aria-label={`Remove ${s.name}`} className="text-muted hover:text-bad" onClick={() => update({ ...draft, skills: draft.skills.filter((_, j) => j !== i) })}>
                      ×
                    </button>
                  )}
                </span>
              ))}
            </div>
          </section>

          {draft.experience.map((exp, ei) => (
            <section key={ei} className="card p-4">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h4 className="font-medium">
                  {exp.title} · {exp.company}
                </h4>
                <span className="text-xs text-muted">{[exp.start, exp.end].filter(Boolean).join(" – ")}</span>
              </div>
              <ul className="mt-2 space-y-1.5">
                {exp.bullets.map((b, bi) => (
                  <li
                    key={bi}
                    className={`group flex items-start gap-2 rounded-xl px-2 py-1.5 text-sm ${b.provenance === "inferred" ? "bg-inferred-bg ring-1 ring-inferred-line" : ""}`}
                  >
                    <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${PROV[b.provenance].cls}`}>
                      {PROV[b.provenance].label}
                    </span>
                    <span className="flex-1">{b.text}</span>
                    {editable && exp.bullets.length > 1 && (
                      <button
                        aria-label="Remove bullet"
                        className="text-muted opacity-0 hover:text-bad group-hover:opacity-100 focus:opacity-100"
                        onClick={() =>
                          update({
                            ...draft,
                            experience: draft.experience.map((x, j) => (j === ei ? { ...x, bullets: x.bullets.filter((_, k) => k !== bi) } : x)),
                          })
                        }
                      >
                        ×
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}

          {editable && (
            <div className="flex justify-end gap-2">
              {dirty && (
                <button
                  className="btn"
                  onClick={() => {
                    setDirty(false);
                    setDraft(job.tailored);
                  }}
                >
                  Discard
                </button>
              )}
              <button className="btn-primary" onClick={save} disabled={!dirty || saving}>
                {saving && <Spinner />} Save &amp; regenerate PDF
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* -------------------------------------------------------------- activity -- */

const AGENT_LABEL: Record<string, string> = {
  pipeline: "Pipeline",
  extractor: "Extractor",
  ats: "ATS scorer",
  tailor: "Resume tailor",
  renderer: "PDF renderer",
  email_finder: "Email finder",
  composer: "Composer",
  approval: "Approval",
  sender: "Gmail sender",
  you: "You",
};

function Activity({ job }: { job: JobDetail }) {
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => end.current?.scrollIntoView({ block: "nearest" }), [job.events.length]);
  return (
    <ol className="card divide-y divide-line">
      {job.events.map((e) => (
        <li key={e.id} className="flex gap-3 px-4 py-2.5 text-sm">
          <span className="w-16 shrink-0 text-xs tabular-nums text-muted">{new Date(e.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}</span>
          <span className="w-28 shrink-0 text-xs font-semibold uppercase tracking-wide text-muted">{AGENT_LABEL[e.agent] ?? e.agent}</span>
          <span className={`min-w-0 flex-1 break-words ${e.level === "error" ? "text-bad" : e.level === "warn" ? "text-warn" : ""}`}>{e.message}</span>
        </li>
      ))}
      <li ref={end} className="sr-only" />
    </ol>
  );
}

/* ---------------------------------------------------------------- shared -- */

function Pending({ what, job }: { what: string; job: JobDetail }) {
  const working = ACTIVE_STATUSES.includes(job.status);
  return (
    <div className="card flex items-center gap-3 p-6 text-sm text-muted">
      {working ? (
        <>
          <Spinner /> {what} will appear here when the agents finish.
        </>
      ) : (
        <>{what} wasn&apos;t produced for this job.</>
      )}
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? "Copied" : label}
    </button>
  );
}
