import Logo from "./Logo";

export default function Footer() {
  return (
    <footer className="border-t border-ink-100 bg-white">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
          <div className="flex items-center gap-2">
            <Logo className="h-6 w-6 text-accent-600" />
            <span className="text-base font-semibold tracking-tight text-ink-900">
              Relay
            </span>
            <span className="ml-3 text-xs text-ink-400">
              Voice-first dispatch, built for small fleets.
            </span>
          </div>
          <nav className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-ink-500">
            <a href="#features" className="hover:text-ink-900">Features</a>
            <a href="#how" className="hover:text-ink-900">How it works</a>
            <a href="#stats" className="hover:text-ink-900">Results</a>
            <a href="#demo" className="hover:text-ink-900">Book demo</a>
          </nav>
        </div>
        <div className="mt-10 flex flex-col items-start justify-between gap-3 border-t border-ink-100 pt-6 text-xs text-ink-400 md:flex-row md:items-center">
          <p>© {new Date().getFullYear()} Relay. All rights reserved.</p>
          <p>Built on NavPro · ElevenLabs · Twilio</p>
        </div>
      </div>
    </footer>
  );
}
