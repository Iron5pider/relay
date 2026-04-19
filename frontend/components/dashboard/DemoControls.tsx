"use client";

import { useState } from "react";
import { Play, RotateCw, Zap } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { api } from "@/lib/api";
import {
  markCallDialing,
  appendSimulatedTranscript,
  hydrateFleet,
} from "@/lib/realtime";
import { selectLoad, setPanelView, setFallbackMode, useUI } from "@/lib/store";
import { seedFleet } from "@/lib/seed-data";
import { simulateTranscript } from "@/lib/fallback-transcript";

const HERO_LOAD_ID = "b17e9c2d-4a5f-4e88-9c12-a6bd2e4f7123";
const HERO_DRIVER_ID = "d1a2b3c4-0000-0000-0000-000000000001";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function DemoControls({ open, onOpenChange }: Props) {
  const ui = useUI();
  const [busy, setBusy] = useState(false);

  async function runHero() {
    setBusy(true);
    try {
      selectLoad(HERO_LOAD_ID, HERO_DRIVER_ID);
      if (ui.fallbackMode) {
        const callId = `hero-${Date.now()}`;
        markCallDialing(callId);
        setPanelView("call");
        simulateTranscript(callId, (t) => appendSimulatedTranscript(callId, t));
        toast.success("Hero demo — simulated transcript starting");
      } else {
        const res = await api.triggerDetentionCall(HERO_LOAD_ID);
        markCallDialing(res.voice_call_id);
        setPanelView("call");
        toast.success("Hero detention call initiated");
      }
      onOpenChange(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      toast.error(`Hero demo failed: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[380px] sm:w-[420px]">
        <SheetHeader>
          <SheetTitle>Demo controls</SheetTitle>
          <SheetDescription>
            Presenter shortcuts for the live walkthrough.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-3">
          <button
            onClick={runHero}
            disabled={busy}
            className="flex w-full items-center justify-between rounded-xl bg-accent-600 px-4 py-4 text-left text-white shadow-md transition hover:bg-accent-700 disabled:opacity-60"
          >
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Play className="h-4 w-4" /> Run hero demo
              </div>
              <div className="mt-1 text-[11px] text-white/80">
                Fires the L-12345 detention escalation — selects the row, opens the panel,
                streams the transcript.
              </div>
            </div>
            <Zap className="h-5 w-5 opacity-80" />
          </button>

          <button
            onClick={() => {
              hydrateFleet(seedFleet.drivers);
              toast.message("Fleet snapshot reset to seed data");
            }}
            className="flex w-full items-center gap-2 rounded-lg border border-ink-200 bg-white px-3 py-2.5 text-sm font-medium text-ink-700 transition hover:bg-ink-50"
          >
            <RotateCw className="h-4 w-4 text-ink-400" />
            Reset fleet snapshot (local)
          </button>

          <div className="rounded-lg border border-ink-200 bg-ink-50/50 p-3">
            <label className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-ink-900">Fallback mode</div>
                <div className="mt-0.5 text-[11px] text-ink-500">
                  Action buttons simulate a canned transcript instead of hitting the real
                  backend. Use if the live voice path is down.
                </div>
              </div>
              <input
                type="checkbox"
                checked={ui.fallbackMode}
                onChange={(e) => setFallbackMode(e.target.checked)}
                className="mt-1 h-4 w-4 accent-accent-600"
              />
            </label>
          </div>

          <div className="rounded-lg border border-dashed border-ink-200 p-3 text-[11px] text-ink-500">
            <div className="font-semibold text-ink-700">Keyboard shortcuts</div>
            <ul className="mt-1 space-y-0.5">
              <li>
                <kbd className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px]">Esc</kbd> —
                close detail panel
              </li>
              <li>
                <kbd className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px]">1–8</kbd> —
                select load by position
              </li>
            </ul>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
