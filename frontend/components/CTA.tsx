export default function CTA() {
  return (
    <section id="demo" className="mx-auto max-w-7xl px-6 py-24">
      <div className="relative overflow-hidden rounded-3xl border border-ink-100 bg-gradient-to-br from-white via-accent-50/40 to-white p-10 shadow-soft sm:p-16">
        <div className="bg-grid-fade absolute inset-0 -z-10" />
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-balance text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
            See Relay close a detention call in real time.
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-ink-500">
            15-minute live walkthrough on your actual lanes. If we can't show
            you $1,000+ in unbilled detention by the end, the call's on us.
          </p>
          <div className="mx-auto mt-10 flex w-full max-w-md flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="/dashboard"
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-full bg-accent-600 px-6 py-3 text-sm font-semibold text-white shadow-soft transition hover:-translate-y-0.5 hover:bg-accent-700 sm:w-auto"
            >
              Open command center
              <svg aria-hidden viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                <path fillRule="evenodd" d="M7.22 14.78a.75.75 0 010-1.06L10.94 10 7.22 6.28a.75.75 0 111.06-1.06l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06 0z" clipRule="evenodd" />
              </svg>
            </a>
            <a
              href="#features"
              className="inline-flex w-full items-center justify-center rounded-full border border-ink-200 bg-white px-6 py-3 text-sm font-semibold text-ink-700 transition hover:border-ink-300 hover:text-ink-900 sm:w-auto"
            >
              See how it works
            </a>
          </div>
          <p className="mt-3 text-xs text-ink-400">
            Live dispatcher dashboard. Exception rows, live transcripts, dispute-ready invoices.
          </p>
        </div>
      </div>
    </section>
  );
}
