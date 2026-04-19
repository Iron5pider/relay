"use client";

import { Settings } from "lucide-react";

export default function SettingsPage() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <Settings size={32} className="mx-auto mb-3 text-ink-200" />
        <h2 className="text-[15px] font-mono font-semibold text-ink-400">Settings</h2>
        <p className="mt-1 text-[12px] font-mono text-ink-300">
          Coming soon — wire after dispatcher feedback.
        </p>
      </div>
    </div>
  );
}
