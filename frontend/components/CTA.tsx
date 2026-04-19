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
          <form
            className="mx-auto mt-10 flex w-full max-w-md flex-col gap-3 sm:flex-row"
            action="#"
            method="post"
          >
            <input
              type="email"
              required
              placeholder="dispatcher@yourfleet.com"
              className="flex-1 rounded-full border border-ink-200 bg-white px-5 py-3 text-sm text-ink-800 placeholder:text-ink-400 focus:border-accent-500 focus:outline-none focus:ring-4 focus:ring-accent-100"
            />
            <button
              type="submit"
              className="inline-flex items-center justify-center gap-1.5 rounded-full bg-ink-900 px-6 py-3 text-sm font-semibold text-white shadow-soft transition hover:-translate-y-0.5 hover:bg-ink-800"
            >
              Book demo
            </button>
          </form>
          <p className="mt-3 text-xs text-ink-400">
            No credit card. No calendar ping-pong. Pick a slot and we'll be
            there.
          </p>
        </div>
      </div>
    </section>
  );
}
