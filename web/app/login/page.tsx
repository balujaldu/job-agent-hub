"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Brand } from "@/components/Brand";
import { ThemeToggle } from "@/components/ThemeToggle";
import { ErrorNote, Spinner } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register" | "reset" | null>(null);
  const [signupsOpen, setSignupsOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ has_user: boolean; signups_open: boolean }>("/api/auth/status")
      .then((s) => {
        setMode(s.has_user ? "login" : "register");
        setSignupsOpen(s.signups_open);
      })
      .catch(() => setError("Can't reach the backend. Is the API server running on port 8000?"));
  }, []);

  function switchTo(next: "login" | "register" | "reset") {
    setMode(next);
    setError("");
    setPassword("");
    setConfirm("");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (mode === "reset" && password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api(`/api/auth/${mode === "reset" ? "reset-password" : mode}`, { method: "POST", json: { email, password } });
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-10">
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="animate-in">
        <Brand href="/login" large />
      </div>
      <form onSubmit={submit} className="glass-strong animate-pop w-full max-w-sm space-y-4 rounded-3xl p-7">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            {mode === "register" ? "Create your account" : mode === "reset" ? "Reset your password" : "Welcome back"}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {mode === "register" ? "Create your account." : mode === "reset" ? "Forgot your password? Choose a new one and you'll be signed in." : "Sign in to continue."}
          </p>
        </div>
        {mode === null && !error ? (
          <div className="flex justify-center py-6 text-muted">
            <Spinner />
          </div>
        ) : (
          <>
            <div>
              <label className="label" htmlFor="email">
                Email
              </label>
              <input id="email" className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="password">
                {mode === "reset" ? "New password" : "Password"}
              </label>
              <input
                id="password"
                className="input"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                minLength={8}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {mode !== "login" && <p className="mt-1 text-xs text-muted">At least 8 characters.</p>}
            </div>
            {mode === "reset" && (
              <div>
                <label className="label" htmlFor="confirm">
                  Confirm new password
                </label>
                <input
                  id="confirm"
                  className="input"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                />
              </div>
            )}
            <ErrorNote message={error} />
            <button className="btn-primary w-full" disabled={busy || mode === null}>
              {busy && <Spinner />}
              {mode === "register" ? "Create account" : mode === "reset" ? "Set new password" : "Sign in"}
            </button>
            {mode === "login" && (
              <p className="text-center text-sm">
                <button type="button" className="text-accent underline" onClick={() => switchTo("reset")}>
                  Forgot password?
                </button>
              </p>
            )}
            {mode === "reset" && (
              <p className="text-center text-sm">
                <button type="button" className="text-accent underline" onClick={() => switchTo("login")}>
                  Back to sign in
                </button>
              </p>
            )}
            {signupsOpen && mode !== "reset" && (
              <p className="text-center text-sm text-muted">
                {mode === "register" ? "Already have an account? " : "New here? "}
                <button type="button" className="text-accent underline" onClick={() => switchTo(mode === "register" ? "login" : "register")}>
                  {mode === "register" ? "Sign in" : "Create an account"}
                </button>
              </p>
            )}
          </>
        )}
      </form>
      <p className="animate-fade text-xs text-muted">Tailored resumes and emails, sent only when you approve.</p>
    </div>
  );
}
