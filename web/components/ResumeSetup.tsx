"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { BaseResume, ResumeData } from "@/lib/types";
import { ErrorNote, Spinner } from "./ui";

/** Upload a resume, review what was parsed, add confirmed skills and notes, then confirm. */
export function ResumeSetup({ onConfirmed }: { onConfirmed: () => void }) {
  const [resume, setResume] = useState<BaseResume | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api<BaseResume | null>("/api/resume")
      .then(setResume)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function upload(file: File) {
    setUploading(true);
    setError("");
    setSaved(false);
    const form = new FormData();
    form.append("file", file);
    try {
      setResume(await api<BaseResume>("/api/resume", { method: "POST", body: form }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  async function confirm() {
    if (!resume) return;
    setSaving(true);
    setError("");
    try {
      const r = await api<BaseResume>(`/api/resume/${resume.id}`, {
        method: "PUT",
        json: { data: resume.data, extra_skills: resume.extra_skills, extra_notes: resume.extra_notes, confirmed: true },
      });
      setResume(r);
      setSaved(true);
      onConfirmed();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const setData = useCallback((patch: Partial<ResumeData>) => {
    setResume((r) => (r ? { ...r, data: { ...r.data, ...patch } } : r));
    setSaved(false);
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-16 text-muted">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <UploadBox uploading={uploading} hasResume={!!resume} filename={resume?.filename} onFile={upload} />
      <ErrorNote message={error} />

      {resume && !uploading && (
        <>
          <section className="card space-y-4 p-5">
            <h2 className="font-semibold">Check what we read</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {(["name", "email", "phone", "location"] as const).map((f) => (
                <div key={f}>
                  <label className="label">{f}</label>
                  <input className="input" value={resume.data[f]} onChange={(e) => setData({ [f]: e.target.value })} />
                </div>
              ))}
            </div>
            <div>
              <label className="label">Links (one per line)</label>
              <textarea
                className="input min-h-16"
                value={resume.data.links.join("\n")}
                onChange={(e) => setData({ links: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
              />
            </div>
            <div>
              <label className="label">Experience</label>
              <ul className="divide-y divide-line rounded-xl border border-line">
                {resume.data.experience.map((x, i) => (
                  <li key={i} className="px-3 py-2 text-sm">
                    <div className="font-medium">
                      {x.title} · {x.company}
                    </div>
                    <div className="text-xs text-muted">
                      {[x.start, x.end].filter(Boolean).join(" – ")} · {x.bullets.length} bullet{x.bullets.length === 1 ? "" : "s"}
                    </div>
                  </li>
                ))}
                {resume.data.experience.length === 0 && <li className="px-3 py-2 text-sm text-muted">No experience found. Check the file.</li>}
              </ul>
              <p className="mt-1 text-xs text-muted">Employers, titles and dates are always copied from here into tailored resumes, never changed.</p>
            </div>
            <div>
              <label className="label">Education</label>
              <ul className="text-sm">
                {resume.data.education.map((x, i) => (
                  <li key={i}>
                    {[x.degree, x.field].filter(Boolean).join(", ")} — {x.institution}
                  </li>
                ))}
              </ul>
            </div>
          </section>

          <section className="card space-y-4 p-5">
            <div>
              <h2 className="font-semibold">Skills you can handle</h2>
              <p className="text-sm text-muted">
                The agents may add these to a tailored resume when a job asks for them. Include anything you&apos;re comfortable being interviewed on.
              </p>
            </div>
            <div>
              <label className="label">On your resume</label>
              <SkillsInput value={resume.data.skills} onChange={(skills) => setData({ skills })} />
            </div>
            <div>
              <label className="label">Additional skills (not on the resume)</label>
              <SkillsInput
                value={resume.extra_skills}
                onChange={(extra_skills) => {
                  setResume({ ...resume, extra_skills });
                  setSaved(false);
                }}
                placeholder="e.g. Kubernetes, GraphQL, Tableau"
              />
            </div>
            <div>
              <label className="label">Notes on your past work</label>
              <textarea
                className="input min-h-28"
                placeholder="Responsibilities and work that aren't on your resume, e.g. 'At Acme I also owned on-call for the payments API and mentored two interns.'"
                value={resume.extra_notes}
                onChange={(e) => {
                  setResume({ ...resume, extra_notes: e.target.value });
                  setSaved(false);
                }}
              />
              <p className="mt-1 text-xs text-muted">The tailoring agent uses these to write additional experience points.</p>
            </div>
          </section>

          <div className="flex items-center justify-end gap-3">
            {saved && <span className="text-sm text-ok">Saved</span>}
            <button className="btn-primary" onClick={confirm} disabled={saving}>
              {saving && <Spinner />}
              {resume.confirmed ? "Save changes" : "Confirm and continue"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function UploadBox({
  uploading,
  hasResume,
  filename,
  onFile,
}: {
  uploading: boolean;
  hasResume: boolean;
  filename?: string;
  onFile: (f: File) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={`card flex flex-col items-center gap-3 border-dashed p-8 text-center ${over ? "border-accent bg-info-bg" : ""}`}
    >
      {uploading ? (
        <>
          <Spinner className="text-accent" />
          <p className="text-sm">Reading your resume. This takes about 20 seconds.</p>
        </>
      ) : (
        <>
          <p className="text-sm">
            {hasResume ? (
              <>
                Current file: <span className="font-medium">{filename}</span>
              </>
            ) : (
              "Drop your current resume here (PDF or DOCX)"
            )}
          </p>
          <button className="btn" onClick={() => input.current?.click()}>
            {hasResume ? "Replace file" : "Choose file"}
          </button>
        </>
      )}
      <input
        ref={input}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}

function SkillsInput({ value, onChange, placeholder }: { value: string[]; onChange: (v: string[]) => void; placeholder?: string }) {
  const [draft, setDraft] = useState("");
  function add() {
    const items = draft
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s && !value.some((v) => v.toLowerCase() === s.toLowerCase()));
    if (items.length) onChange([...value, ...items]);
    setDraft("");
  }
  return (
    <div className="rounded-xl border border-line bg-surface p-2">
      <div className="flex flex-wrap gap-1.5">
        {value.map((s) => (
          <span key={s} className="inline-flex items-center gap-1 rounded-full bg-surface-2 px-2.5 py-1 text-xs">
            {s}
            <button aria-label={`Remove ${s}`} className="text-muted hover:text-bad" onClick={() => onChange(value.filter((v) => v !== s))}>
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-40 flex-1 bg-transparent px-1 py-1 text-sm outline-none placeholder:text-muted"
          placeholder={placeholder ?? "Add a skill and press Enter"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === ",") {
              e.preventDefault();
              add();
            } else if (e.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          onBlur={add}
        />
      </div>
    </div>
  );
}
