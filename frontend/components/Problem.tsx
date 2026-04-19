export default function Problem() {
  const rows = [
    {
      k: "$1,400",
      label: "average unbilled detention per truck per month",
    },
    { k: "47%", label: "of check-in calls go to voicemail after 6pm" },
    { k: "12×", label: "broker status-update calls per dispatcher per day" },
  ];
  return (
    <section className="mx-auto max-w-7xl px-6 py-24">
      <div className="grid gap-12 lg:grid-cols-2 lg:gap-20">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-accent-700">
            The problem
          </p>
          <h2 className="mt-3 text-balance text-4xl font-semibold tracking-tight text-ink-900 sm:text-5xl">
            Small fleets lose money on the calls they never get to make.
          </h2>
          <p className="mt-5 text-lg leading-relaxed text-ink-500">
            One dispatcher juggling twenty drivers cannot call every receiver,
            every broker, and every driver on every delay. The missed call is
            the unbilled detention, the late status update, the driver stuck
            at a truck stop with a dead HOS clock.
          </p>
        </div>
        <div className="space-y-4">
          {rows.map((r) => (
            <div
              key={r.k}
              className="flex items-baseline gap-6 rounded-xl border border-ink-100 bg-white p-6 shadow-soft"
            >
              <div className="text-4xl font-semibold tracking-tight text-ink-900">
                {r.k}
              </div>
              <div className="text-sm text-ink-500">{r.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
