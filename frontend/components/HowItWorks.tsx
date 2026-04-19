const steps = [
  {
    n: "01",
    title: "Relay listens to your fleet",
    body: "We connect to NavPro, watch GPS, HOS, and load context in real time — no rip-and-replace.",
  },
  {
    n: "02",
    title: "An anomaly triggers a call",
    body: "A detention clock crosses free-time, a driver stalls, a broker needs a PM update. Relay decides to dial.",
  },
  {
    n: "03",
    title: "The driver or broker picks up",
    body: "A voice agent grounded in the load's actual data confirms the outcome — in 30 seconds, in their language.",
  },
  {
    n: "04",
    title: "The outcome lands in your dashboard",
    body: "Invoice generated, ETA updated, exception closed. You see it live on dispatcher.demo the moment the call hangs up.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-7xl px-6 py-24">
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-accent-700">
          How it works
        </p>
        <h2 className="mt-3 text-balance text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
          From signal to resolution in under a minute.
        </h2>
      </div>

      <ol className="mt-16 grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {steps.map((s, i) => (
          <li
            key={s.n}
            className="relative rounded-xl border border-ink-100 bg-white p-6 shadow-soft"
          >
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono font-semibold tracking-wider text-accent-700">
                {s.n}
              </span>
              {i < steps.length - 1 && (
                <span className="hidden h-px flex-1 bg-gradient-to-r from-accent-200 to-transparent lg:block" />
              )}
            </div>
            <h3 className="mt-4 text-base font-semibold text-ink-900">
              {s.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-ink-500">
              {s.body}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
