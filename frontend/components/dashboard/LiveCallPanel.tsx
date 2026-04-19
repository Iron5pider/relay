"use client";

import { useEffect, useState } from "react";
import { Phone, PhoneOff, Mic, MicOff } from "lucide-react";
import { cn } from "@/lib/utils";
import TranscriptFeed from "./TranscriptFeed";
import { useCallMeta, useLatestInvoice } from "@/lib/realtime";
import { setPanelView } from "@/lib/store";

export default function LiveCallPanel() {
  const meta = useCallMeta();
  const invoice = useLatestInvoice();
  const [duration, setDuration] = useState(0);
  const [muted, setMuted] = useState(false);

  useEffect(() => {
    if (!meta.startedAt) return;
    const start = new Date(meta.startedAt).getTime();
    const id = setInterval(() => {
      const end = meta.endedAt ? new Date(meta.endedAt).getTime() : Date.now();
      setDuration(Math.max(0, Math.floor((end - start) / 1000)));
    }, 1000);
    return () => clearInterval(id);
  }, [meta.startedAt, meta.endedAt]);

  const mm = Math.floor(duration / 60).toString().padStart(2, "0");
  const ss = (duration % 60).toString().padStart(2, "0");

  const statusLabel =
    meta.status === "calling"
      ? "Calling receiver…"
      : meta.status === "connected"
        ? "Connected"
        : meta.status === "completed"
          ? `Call ended · ${meta.outcome ?? "completed"}`
          : "—";

  const statusDot =
    meta.status === "calling"
      ? "bg-amber-500"
      : meta.status === "connected"
        ? "bg-red-500 animate-pulse"
        : meta.status === "completed"
          ? "bg-emerald-500"
          : "bg-ink-300";

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-ink-100 bg-white px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className={cn("h-2 w-2 rounded-full", statusDot)} />
          <span className="text-sm font-medium text-ink-900">{statusLabel}</span>
        </div>
        <span className="font-mono text-xs tabular-nums text-ink-500">
          {mm}:{ss}
        </span>
      </div>

      <TranscriptFeed callId={meta.callId} />

      {meta.status === "completed" && invoice && (
        <button
          onClick={() => setPanelView("invoice")}
          className="m-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-left text-xs text-emerald-800 transition hover:bg-emerald-100"
        >
          <div className="font-medium">
            Invoice generated · ${invoice.amount_usd.toFixed(2)}
          </div>
          <div className="text-[11px] text-emerald-700">
            {invoice.billable_minutes} billable min · tap to review →
          </div>
        </button>
      )}

      <div className="flex items-center justify-end gap-2 border-t border-ink-100 bg-white px-4 py-2.5">
        <button
          onClick={() => setMuted((m) => !m)}
          className={cn(
            "inline-flex h-8 items-center gap-1 rounded-md border px-2.5 text-xs transition",
            muted
              ? "border-amber-200 bg-amber-50 text-amber-800"
              : "border-ink-200 bg-white text-ink-600 hover:bg-ink-50",
          )}
        >
          {muted ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
          {muted ? "Muted" : "Mute"}
        </button>
        <button
          disabled={meta.status === "completed"}
          onClick={() => setPanelView("load")}
          className={cn(
            "inline-flex h-8 items-center gap-1 rounded-md border px-2.5 text-xs transition",
            "border-red-200 bg-white text-red-700 hover:bg-red-50 disabled:opacity-40",
          )}
        >
          <PhoneOff className="h-3.5 w-3.5" />
          End call
        </button>
      </div>
    </div>
  );
}
