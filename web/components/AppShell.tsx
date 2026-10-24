"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BaseResume } from "@/lib/types";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";
import { Spinner } from "./ui";

const NAV = [
  { href: "/", label: "Jobs" },
  { href: "/resume", label: "Base resume" },
  { href: "/settings", label: "Settings" },
];

/** Signed-in frame. Sends first-time users to resume onboarding. */
export function AppShell({ children, requireResume = true }: { children: React.ReactNode; requireResume?: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const me = await api<{ email: string }>("/api/auth/me");
        if (requireResume) {
          const resume = await api<BaseResume | null>("/api/resume");
          if (!resume || !resume.confirmed) {
            router.replace("/onboarding");
            return;
          }
        }
        setEmail(me.email);
      } catch {
        router.replace("/login");
      }
    })();
  }, [router, requireResume]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    router.replace("/login");
  }

  if (!email) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="min-h-screen pb-10">
      <header className="sticky top-0 z-20 px-3 pt-3 sm:px-4">
        <div className="glass mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 rounded-2xl px-3 py-2 sm:flex-nowrap sm:px-4">
          <Brand />
          <nav className="order-last -mx-1 flex w-full gap-1 overflow-x-auto whitespace-nowrap text-sm sm:order-none sm:mx-0 sm:w-auto">
            {NAV.map((n) => {
              const active = pathname === n.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={`relative rounded-xl px-3 py-1.5 transition-colors duration-200 ${
                    active ? "bg-accent/12 font-medium text-fg shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--accent)_22%,transparent)]" : "text-muted hover:bg-surface-2 hover:text-fg"
                  }`}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2 text-sm text-muted">
            <span className="mr-1 hidden max-w-48 truncate lg:inline">{email}</span>
            <ThemeToggle />
            <button className="btn" onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main key={pathname} className="animate-in mx-auto max-w-7xl px-4 py-6">
        {children}
      </main>
    </div>
  );
}
