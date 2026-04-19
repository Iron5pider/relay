const items = [
  "NavPro partner",
  "ElevenLabs ConvAI",
  "Twilio Voice",
  "FMCSA HOS-aware",
  "SOC-friendly",
];

export default function TrustBand() {
  return (
    <section className="border-y border-ink-100 bg-ink-50/40">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <p className="text-center text-xs font-medium uppercase tracking-[0.2em] text-ink-400">
          Built on the rails fleets already trust
        </p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
          {items.map((it) => (
            <span
              key={it}
              className="text-sm font-semibold tracking-tight text-ink-400"
            >
              {it}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
