export default function Hero() {
  return (
    <section className="relative isolate">
      <div className="bg-grid-fade absolute inset-0 -z-10" />
      <div className="absolute inset-0 -z-10 bg-dot-grid opacity-60 [mask-image:radial-gradient(ellipse_at_top,black_40%,transparent_75%)]" />

      <div className="mx-auto max-w-7xl px-6 pb-24 pt-20 lg:pt-28">
        <div className="mx-auto max-w-3xl text-center animate-fade-up">
          <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-ink-200 bg-white/80 px-3 py-1 text-xs font-medium text-ink-600 shadow-sm">
            <span className="flex h-1.5 w-1.5 rounded-full bg-accent-500 animate-pulse-slow" />
            Live for small-fleet dispatchers
          </div>

          <h1 className="mt-6 text-balance text-5xl font-semibold tracking-tight text-ink-900 sm:text-6xl lg:text-7xl">
            Your dispatch desk,{" "}
            <span className="relative inline-block">
              <span className="relative z-10 bg-gradient-to-r from-accent-600 to-accent-400 bg-clip-text text-transparent">
                on the phone
              </span>
              <span className="absolute inset-x-0 bottom-1 -z-0 h-3 rounded bg-accent-100/70" />
            </span>
            .
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-balance text-lg leading-relaxed text-ink-500">
            Relay is a voice-first command center that handles detention,
            driver check-ins, and broker updates — so a one-dispatcher fleet
            runs like a ten-dispatcher fleet.
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="#demo"
              className="inline-flex items-center gap-2 rounded-full bg-ink-900 px-6 py-3 text-sm font-semibold text-white shadow-soft transition hover:-translate-y-0.5 hover:bg-ink-800"
            >
              Book a 15-minute demo
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path
                  fillRule="evenodd"
                  d="M7.22 14.78a.75.75 0 010-1.06L10.94 10 7.22 6.28a.75.75 0 111.06-1.06l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06 0z"
                  clipRule="evenodd"
                />
              </svg>
            </a>
            <a
              href="#how"
              className="inline-flex items-center gap-2 rounded-full border border-ink-200 bg-white px-6 py-3 text-sm font-semibold text-ink-700 transition hover:border-ink-300 hover:text-ink-900"
            >
              See how it works
            </a>
          </div>

          <p className="mt-5 text-xs text-ink-400">
            Runs on NavPro · ElevenLabs voice · Twilio · No rip-and-replace
          </p>
        </div>

        <div className="mx-auto mt-20 max-w-5xl animate-fade-up">
          <HeroMockup />
        </div>
      </div>
    </section>
  );
}

function HeroMockup() {
  return (
    <div className="relative rounded-2xl border border-ink-100 bg-white p-3 shadow-glow">
      <div className="rounded-xl border border-ink-100 bg-ink-50/50 p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-medium text-ink-500">
            <span className="flex h-2 w-2 rounded-full bg-accent-500 animate-pulse" />
            Live — dispatcher.demo
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-ink-200" />
            <span className="h-2 w-2 rounded-full bg-ink-200" />
            <span className="h-2 w-2 rounded-full bg-ink-200" />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <CallCard
            status="calling"
            driver="Carlos Ramirez"
            load="L-12345"
            context="Detention — Acme · 2h 18m over"
            tone="accent"
          />
          <CallCard
            status="listening"
            driver="Miguel Ortega"
            load="L-12302"
            context="Proactive check-in · 47m stationary"
            tone="blue"
          />
          <CallCard
            status="resolved"
            driver="Carlos Ramirez"
            load="L-12345"
            context="Detention confirmed · Invoice $183"
            tone="muted"
          />
        </div>

        <div className="mt-5 rounded-lg border border-ink-100 bg-white px-4 py-3 text-xs font-mono text-ink-500">
          <span className="text-accent-600">●</span> call.transcript ·
          <span className="ml-1 text-ink-700">
            "Hey Carlos, this is Relay calling on behalf of dispatch. Are you
            still at the Acme receiver?"
          </span>
        </div>
      </div>
    </div>
  );
}

function CallCard({
  status,
  driver,
  load,
  context,
  tone,
}: {
  status: "calling" | "listening" | "resolved";
  driver: string;
  load: string;
  context: string;
  tone: "accent" | "blue" | "muted";
}) {
  const toneMap = {
    accent: "border-accent-200 bg-accent-50/60",
    blue: "border-blue-200 bg-blue-50/60",
    muted: "border-ink-100 bg-white",
  } as const;
  const dotMap = {
    calling: "bg-accent-500 animate-pulse",
    listening: "bg-blue-500 animate-pulse",
    resolved: "bg-ink-300",
  } as const;
  return (
    <div className={`rounded-lg border p-4 ${toneMap[tone]}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${dotMap[status]}`} />
          <span className="text-xs font-medium uppercase tracking-wide text-ink-500">
            {status}
          </span>
        </div>
        <span className="text-[10px] font-mono text-ink-400">{load}</span>
      </div>
      <div className="mt-3 text-sm font-semibold text-ink-900">{driver}</div>
      <div className="mt-0.5 text-xs text-ink-500">{context}</div>
    </div>
  );
}
