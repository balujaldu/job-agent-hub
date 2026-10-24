"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { JobSummary } from "@/lib/types";
import { ErrorNote, Spinner } from "./ui";

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

export function NewJob({ onCreated }: { onCreated: (job: JobSummary) => void }) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!image) return setPreview("");
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  function pick(file: File | undefined) {
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) return setError("Screenshots must be PNG, JPEG, WebP or GIF.");
    if (file.size > 5 * 1024 * 1024) return setError("Screenshots must be 5 MB or smaller.");
    setError("");
    setImage(file);
  }

  async function submit() {
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("text", text);
    if (image) form.append("screenshot", image);
    try {
      onCreated(await api<JobSummary>("/api/jobs", { method: "POST", body: form }));
      setText("");
      setImage(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className={`card p-4 transition-all duration-300 ${over ? "scale-[1.01] ring-2 ring-accent" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        pick(e.dataTransfer.files[0]);
      }}
    >
      <div className="flex flex-col gap-3 md:flex-row">
        <textarea
          className="input min-h-24 flex-1"
          placeholder="Paste a job description or link, or drop / paste a screenshot of the posting"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPaste={(e) => {
            const file = Array.from(e.clipboardData.files).find((f) => f.type.startsWith("image/"));
            if (file) {
              e.preventDefault();
              pick(file);
            }
          }}
        />
        <div className="flex shrink-0 flex-row items-start gap-2 md:w-56 md:flex-col">
          {preview ? (
            <div className="relative w-full">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={preview} alt="Screenshot to process" className="max-h-24 w-full rounded-xl border border-line object-cover object-top" />
              <button className="btn absolute right-1 top-1 px-2 py-0.5 text-xs" onClick={() => setImage(null)}>
                Remove
              </button>
            </div>
          ) : (
            <button className="btn w-full" onClick={() => fileInput.current?.click()}>
              Add screenshot
            </button>
          )}
          <button className="btn-primary w-full" onClick={submit} disabled={busy || (!text.trim() && !image)}>
            {busy && <Spinner />}
            Run agents
          </button>
        </div>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept={IMAGE_TYPES.join(",")}
        className="hidden"
        onChange={(e) => {
          pick(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {error && (
        <div className="mt-3">
          <ErrorNote message={error} />
        </div>
      )}
    </section>
  );
}
