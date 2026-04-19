const features = [
  {
    title: "Detention capture",
    body: "Relay calls the receiver the minute the free-window closes, confirms the delay, and generates the invoice before the driver even rolls out of the yard.",
    icon: (
      <path d="M12 6v6l4 2M12 2a10 10 0 100 20 10 10 0 000-20z" />
    ),
  },
  {
    title: "Proactive driver check-ins",
    body: "A driver who goes stationary longer than their HOS allows gets a call — in English or Spanish — before dispatch even notices.",
    icon: (
      <path d="M3 5h12l2 3h4v9a2 2 0 01-2 2h-1a3 3 0 11-6 0H9a3 3 0 11-6 0 2 2 0 01-2-2V7a2 2 0 012-2z" />
    ),
  },
  {
    title: "Broker status updates",
    body: "One prompt — 'update all brokers on my PM loads' — and Relay fans out eight parallel calls with accurate ETAs and live GPS context.",
    icon: <path d="M3 5h18M3 12h18M3 19h18" />,
  },
  {
    title: "HOS + GPS-aware",
    body: "Every outbound call is grounded in the driver's actual hours, location, and load context pulled from NavPro. No hallucinated ETAs.",
    icon: (
      <path d="M12 2l3 7h7l-5.5 4.5L18 22l-6-4-6 4 1.5-8.5L2 9h7l3-7z" />
    ),
  },
  {
    title: "Anomaly agent",
    body: "A Claude-powered reasoning layer watches NavPro signals and decides when to trigger a call — not every stationary driver is a problem.",
    icon: <path d="M12 3v18M3 12h18M5.6 5.6l12.8 12.8M18.4 5.6L5.6 18.4" />,
  },
  {
    title: "Multilingual, multichannel",
    body: "EN + ES out of the box. Voice when it matters, SMS when it's faster. The driver talks to whoever speaks their language.",
    icon: <path d="M4 5h16M4 12h10M4 19h16" />,
  },
];

export default function Features() {
  return (
    <section id="features" className="border-t border-ink-100 bg-ink-50/40">
      <div className="mx-auto max-w-7xl px-6 py-24">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-accent-700">
            What Relay does
          </p>
          <h2 className="mt-3 text-balance text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
            Every missed call, made on time.
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-ink-500">
            Relay isn't another TMS. It sits on top of the tools you already
            run — and picks up the phone when your team can't.
          </p>
        </div>

        <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div
              key={f.title}
              className="group relative rounded-xl border border-ink-100 bg-white p-6 shadow-soft transition hover:-translate-y-1 hover:shadow-glow"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-50 text-accent-700 ring-1 ring-accent-100">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.75}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="h-5 w-5"
                >
                  {f.icon}
                </svg>
              </div>
              <h3 className="mt-5 text-base font-semibold text-ink-900">
                {f.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-500">
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
