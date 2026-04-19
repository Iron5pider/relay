"use client";

import { useEffect, useState } from "react";
import { Phone, Headset, Radio, FileText, MapPin, Clock, CheckCircle, Receipt, Truck, DollarSign, Folder, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { ActiveLoad, DriverRow } from "@/lib/api";
import { api } from "@/lib/api";
import { markCallDialing, appendSimulatedTranscript } from "@/lib/realtime";
import { setPanelView, useUI } from "@/lib/store";
import DocumentsDrawer from "./DocumentsDrawer";
import {
  detentionBillable,
  detentionAmount,
  formatMoney,
  formatTimer,
  formatMinutes,
} from "@/lib/time";
import { simulateTranscript } from "@/lib/fallback-transcript";

interface Props {
  driver: DriverRow;
  load: ActiveLoad;
}

export default function LoadDetailPanel({ driver, load }: Props) {
  const [, forceTick] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [docsOpen, setDocsOpen] = useState(false);
  const ui = useUI();
  const isException = load.status === "exception";

  useEffect(() => {
    if (!isException) return;
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [isException]);

  const billable = detentionBillable(load.arrived_at_stop_at, load.detention_free_minutes);
  const amount = detentionAmount(
    load.arrived_at_stop_at,
    load.detention_free_minutes,
    load.detention_rate_per_hour ?? 0,
  );

  async function handleAction(
    label: string,
    fn: () => Promise<{ voice_call_id: string }>,
    fallbackCallId?: string,
  ) {
    setBusy(label);
    try {
      if (ui.fallbackMode) {
        const callId = fallbackCallId ?? `sim-${Date.now()}`;
        markCallDialing(callId);
        setPanelView("call");
        simulateTranscript(callId, (t) => appendSimulatedTranscript(callId, t));
        toast.success(`${label} — simulated`);
        setTimeout(() => setBusy(null), 400);
        return;
      }
      const res = await fn();
      markCallDialing(res.voice_call_id);
      setPanelView("call");
      toast.success(`${label} initiated`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Request failed";
      toast.error(`${label} failed: ${msg}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <div className="space-y-3 px-4 pb-4 pt-3">
        {/* Load header */}
        <div>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-base font-semibold text-ink-900">
              {load.load_number}
            </span>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium",
                isException
                  ? "bg-red-50 text-red-700"
                  : "bg-accent-50 text-accent-700",
              )}
            >
              {load.status.replace(/_/g, " ")}
            </span>
          </div>
        </div>

        {/* Driver card */}
        <div className="rounded-lg border border-ink-100 bg-white p-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-ink-900">{driver.name}</div>
              <div className="font-mono text-[11px] text-ink-500">
                Truck #{driver.truck_number} · {driver.preferred_language?.toUpperCase()}
              </div>
            </div>
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-medium",
                driver.fatigue_level === "high"
                  ? "bg-red-50 text-red-700"
                  : driver.fatigue_level === "moderate"
                    ? "bg-amber-50 text-amber-700"
                    : driver.fatigue_level === "low"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-ink-100 text-ink-500",
              )}
            >
              {driver.fatigue_level}
            </span>
          </div>
          <div className="mt-2.5">
            <div className="flex items-center justify-between text-[11px] text-ink-500">
              <span>HOS drive remaining</span>
              <span className="font-mono tabular-nums">
                {formatMinutes(driver.hos_drive_remaining_minutes)}
              </span>
            </div>
            <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-ink-100">
              <div
                className={cn(
                  "h-full rounded-full",
                  driver.hos_drive_remaining_minutes < 30
                    ? "bg-red-500"
                    : driver.hos_drive_remaining_minutes < 90
                      ? "bg-amber-500"
                      : "bg-accent-500",
                )}
                style={{
                  width: `${Math.min(100, (driver.hos_drive_remaining_minutes / 660) * 100)}%`,
                }}
              />
            </div>
          </div>
        </div>

        {/* Route */}
        <div className="rounded-lg border border-ink-100 bg-white p-3 text-xs">
          <div className="flex items-center gap-2 text-ink-700">
            <MapPin className="h-3.5 w-3.5 text-ink-400" />
            <span className="font-medium">{load.pickup.name}</span>
          </div>
          <div className="ml-[7px] my-1 h-3 w-px border-l border-dashed border-ink-300" />
          <div className="flex items-center gap-2 text-ink-700">
            <MapPin className="h-3.5 w-3.5 text-accent-500" />
            <span className="font-medium">{load.delivery.name}</span>
          </div>
        </div>

        {/* Detention card */}
        {isException && (
          <div className="rounded-lg border border-red-200 bg-red-50/60 p-3">
            <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-red-600">
              <Clock className="h-3 w-3" />
              Detention in progress
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="font-mono text-[28px] font-bold text-red-600 tabular-nums">
                {formatTimer(billable.total)}
              </span>
              <span className="font-mono text-[28px] font-bold text-amber-600 tabular-nums">
                {formatMoney(amount)}
              </span>
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-red-700">
              <span>
                {billable.billable} billable min after {load.detention_free_minutes}{" "}
                free
              </span>
              <span className="font-mono">
                ${load.detention_rate_per_hour?.toFixed(0)}/hr
              </span>
            </div>
          </div>
        )}

        {/* Broker */}
        {load.broker && (
          <div className="rounded-lg border border-ink-100 bg-white p-3 text-xs">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">
              Broker
            </div>
            <div className="mt-1 font-medium text-ink-900">{load.broker.name}</div>
          </div>
        )}

        {/* Delivered summary */}
        {load.status === "delivered" && (
          <>
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                <CheckCircle className="h-3 w-3" />
                Delivered
              </div>
              {load.pod?.signed_by && (
                <div className="mt-2 text-[12px] text-ink-700">
                  <span className="text-ink-400">Signed by:</span>{" "}
                  <span className="font-medium">{load.pod.signed_by}</span>
                </div>
              )}
              {load.pod?.received_at && (
                <div className="mt-0.5 text-[11px] text-ink-400 font-mono">
                  {new Date(load.pod.received_at).toLocaleString()}
                </div>
              )}
            </div>

            {/* Financial summary */}
            <div className="rounded-lg border border-ink-100 bg-white p-3">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-400 mb-2">
                Financial summary
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[12px]">
                  <span className="text-ink-500 flex items-center gap-1.5">
                    <Truck className="h-3 w-3" /> Linehaul
                  </span>
                  <span className="font-mono font-medium text-ink-900 tabular-nums">
                    {formatMoney(load.rate_linehaul ?? 0)}
                  </span>
                </div>
                {load.detention_minutes_elapsed > load.detention_free_minutes && (
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="text-red-600 flex items-center gap-1.5">
                      <Clock className="h-3 w-3" /> Detention
                    </span>
                    <span className="font-mono font-semibold text-red-600 tabular-nums">
                      {formatMoney(amount)}
                    </span>
                  </div>
                )}
                <div className="border-t border-ink-100 pt-1.5 flex items-center justify-between text-[13px]">
                  <span className="text-ink-700 font-semibold flex items-center gap-1.5">
                    <DollarSign className="h-3.5 w-3.5" /> Total
                  </span>
                  <span className="font-mono font-bold text-ink-900 tabular-nums">
                    {formatMoney((load.rate_linehaul ?? 0) + (load.detention_minutes_elapsed > load.detention_free_minutes ? amount : 0))}
                  </span>
                </div>
              </div>
            </div>

            {/* Invoice link */}
            <div
              role="button"
              tabIndex={0}
              onClick={() => setPanelView("invoice")}
              onKeyDown={(e) => { if (e.key === "Enter") setPanelView("invoice"); }}
              className="rounded-lg border border-ink-200 bg-white p-3 flex items-center justify-between hover:bg-ink-50 cursor-pointer transition-colors"
            >
              <div className="flex items-center gap-2">
                <Receipt className="h-4 w-4 text-ink-400" />
                <div>
                  <div className="text-[12px] font-medium text-ink-900">View Invoice</div>
                  <div className="text-[10px] text-ink-400 font-mono">
                    {load.detention_minutes_elapsed > load.detention_free_minutes
                      ? `Detention invoice — ${formatMoney(amount)}`
                      : "Standard invoice"}
                  </div>
                </div>
              </div>
              <FileText className="h-4 w-4 text-ink-300" />
            </div>

            {/* Documents — opens in-app viewer with POD + rate con + BOL + lumper */}
            <button
              type="button"
              onClick={() => setDocsOpen(true)}
              className="w-full rounded-lg border border-ink-200 bg-white p-3 flex items-center justify-between hover:bg-ink-50 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Folder className="h-4 w-4 text-emerald-500" />
                <div className="text-left">
                  <div className="text-[12px] font-medium text-ink-900">
                    Documents
                  </div>
                  <div className="text-[10px] text-ink-400 font-mono">
                    POD · Rate Con · BOL · Lumper
                    {load.pod?.signed_by ? ` · Signed by ${load.pod.signed_by}` : ""}
                  </div>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-ink-300" />
            </button>
          </>
        )}
      </div>

      {docsOpen && (
        <DocumentsDrawer driver={driver} load={load} onClose={() => setDocsOpen(false)} />
      )}

      {/* Actions — sticky bottom (hide for delivered loads) */}
      {load.status !== "delivered" && (
      <div className="sticky bottom-0 mt-auto space-y-2 border-t border-ink-100 bg-white px-4 py-3">
        <button
          onClick={() =>
            handleAction("Call receiver", () =>
              api.triggerDetentionCall(load.load_id).then((r) => ({ voice_call_id: r.voice_call_id })),
            )
          }
          disabled={!!busy}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-xl bg-accent-600 py-3.5 text-[15px] font-semibold text-white shadow-md transition",
            "hover:bg-accent-700 active:scale-[0.98] disabled:opacity-60",
          )}
        >
          <Phone className="h-4 w-4" />
          {busy === "Call receiver" ? "Connecting…" : "Call receiver"}
        </button>
        <div className="text-[11px] text-ink-400 text-center -mt-1">
          Fire the detention escalation call with Maya (AI agent)
        </div>

        <div className="grid grid-cols-2 gap-2 pt-1">
          <button
            onClick={() =>
              handleAction("Check in on driver", () =>
                api.triggerDriverCheckin(driver.driver_id).then((r) => ({ voice_call_id: r.voice_call_id })),
              )
            }
            disabled={!!busy}
            className="inline-flex items-center justify-center gap-1 rounded-lg border border-accent-200 bg-white py-2.5 text-xs font-medium text-accent-700 transition hover:bg-accent-50 disabled:opacity-50"
          >
            <Headset className="h-3.5 w-3.5" />
            Check in on driver
          </button>
          <button
            onClick={() =>
              handleAction("Update broker", () =>
                api.triggerBrokerUpdate(load.load_id).then((r) => ({ voice_call_id: r.voice_call_id })),
              )
            }
            disabled={!!busy}
            className="inline-flex items-center justify-center gap-1 rounded-lg border border-accent-200 bg-white py-2.5 text-xs font-medium text-accent-700 transition hover:bg-accent-50 disabled:opacity-50"
          >
            <Radio className="h-3.5 w-3.5" />
            Update broker
          </button>
        </div>
      </div>
      )}
    </div>
  );
}
