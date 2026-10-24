"use client";

import { AppShell } from "@/components/AppShell";
import { ResumeSetup } from "@/components/ResumeSetup";

export default function ResumePage() {
  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Base resume</h1>
          <p className="mt-1 text-muted">Changes apply to jobs you add from now on.</p>
        </div>
        <ResumeSetup onConfirmed={() => {}} />
      </div>
    </AppShell>
  );
}
