import Link from "next/link";

/** Logo mark + wordmark used in the header and on the sign-in page. */
export function Brand({ href = "/", large = false }: { href?: string; large?: boolean }) {
  return (
    <Link href={href} className="group flex items-center gap-2.5 whitespace-nowrap">
      <span
        className={`relative grid place-items-center rounded-xl bg-linear-to-br from-accent to-accent-2 text-white shadow-lg shadow-accent/30 transition-transform duration-300 group-hover:rotate-6 group-hover:scale-105 ${
          large ? "h-11 w-11" : "h-8 w-8"
        }`}
        aria-hidden
      >
        <svg viewBox="0 0 24 24" className={large ? "h-6 w-6" : "h-[18px] w-[18px]"} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z" />
          <path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z" />
        </svg>
      </span>
      <span className={`font-semibold tracking-tight ${large ? "text-xl" : "text-[15px]"}`}>
        Job Agent <span className="text-gradient">Hub</span>
      </span>
    </Link>
  );
}
