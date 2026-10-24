import Link from "next/link";
import { Brand } from "./Brand";
import { ThemeToggle } from "./ThemeToggle";

/** Public frame for the About, Privacy and Terms pages. Deliberately not AppShell: no sign-in redirect. */
export function LegalLayout({ title, updated, children }: { title: string; updated?: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen px-3 pb-10 pt-3 sm:px-4">
      <header className="mx-auto flex max-w-3xl items-center gap-3 rounded-2xl glass px-3 py-2 sm:px-4">
        <Brand />
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          <Link href="/login" className="btn">
            Sign in
          </Link>
        </div>
      </header>

      <main className="animate-in mx-auto mt-6 max-w-3xl rounded-3xl glass-strong p-6 sm:p-10">
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        {updated && <p className="mt-1 text-sm text-muted">Last updated {updated}</p>}
        <div className="mt-6 space-y-4 leading-relaxed text-[15px] [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:ml-5 [&_li]:list-disc [&_li]:pl-1 [&_ul]:space-y-1.5">
          {children}
        </div>
      </main>

      <footer className="mx-auto mt-6 flex max-w-3xl flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-muted">
        <Link href="/about" className="hover:text-fg">
          Home
        </Link>
        <Link href="/privacy" className="hover:text-fg">
          Privacy
        </Link>
        <Link href="/terms" className="hover:text-fg">
          Terms
        </Link>
      </footer>
    </div>
  );
}

export const CONTACT_EMAIL = "balujaldu25@gmail.com";
