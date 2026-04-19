const stats = [
  { k: "$11k", label: "avg monthly detention recovered / 10-truck fleet" },
  { k: "92%", label: "proactive check-in answer rate" },
  { k: "<45s", label: "median call duration, signal to close" },
  { k: "8×", label: "parallel outbound calls, one prompt" },
];

export default function Stats() {
  return (
    <section id="stats" className="border-y border-ink-100 bg-ink-900 text-white">
      <div className="mx-auto max-w-7xl px-6 py-20">
        <div className="grid gap-10 lg:grid-cols-2 lg:gap-20">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-accent-400">
              The outcome
            </p>
            <h2 className="mt-3 text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
              A dispatcher that works your hours — plus the other sixteen.
            </h2>
            <p className="mt-5 text-lg leading-relaxed text-ink-300">
              Relay doesn't replace your dispatcher. It picks up the calls
              they physically can't — and hands back a closed loop.
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-6">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm"
              >
                <dt className="text-4xl font-semibold tracking-tight text-white">
                  {s.k}
                </dt>
                <dd className="mt-2 text-sm text-ink-300">{s.label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
