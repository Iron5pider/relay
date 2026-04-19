import Link from "next/link";
import Logo from "./Logo";

const nav = [
  { href: "#features", label: "Features" },
  { href: "#how", label: "How it works" },
  { href: "#stats", label: "Results" },
];

export default function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-ink-100/60 bg-white/70 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <Logo className="h-7 w-7 text-accent-600" />
          <span className="text-lg font-semibold tracking-tight text-ink-900">
            Relay
          </span>
        </Link>
        <nav className="hidden items-center gap-8 md:flex">
          {nav.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-sm font-medium text-ink-500 transition-colors hover:text-ink-900"
            >
              {item.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <a
            href="#demo"
            className="hidden text-sm font-medium text-ink-600 hover:text-ink-900 md:block"
          >
            Sign in
          </a>
          <a
            href="#demo"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink-900 px-4 py-2 text-sm font-medium text-white shadow-soft transition-transform hover:-translate-y-0.5 hover:bg-ink-800"
          >
            Book a demo
            <svg
              aria-hidden
              viewBox="0 0 20 20"
              fill="currentColor"
              className="h-3.5 w-3.5"
            >
              <path
                fillRule="evenodd"
                d="M7.22 14.78a.75.75 0 010-1.06L10.94 10 7.22 6.28a.75.75 0 111.06-1.06l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06 0z"
                clipRule="evenodd"
              />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}
