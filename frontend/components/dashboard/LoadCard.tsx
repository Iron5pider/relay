"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import type { ActiveLoad, DriverRow } from "@/lib/api";
import { detentionBillable, detentionAmount, formatMoney, formatTimer } from "@/lib/time";
import { MapPin, Truck, AlertCircle } from "lucide-react";

interface Props {
  driver: DriverRow;
  load: ActiveLoad;
  selected: boolean;
  onClick: () => void;
}

const STATUS_LABEL: Record<string, { label: string; cls: string }> = {
  planned: { label: "Planned", cls: "bg-ink-100 text-ink-600" },
  in_transit: { label: "In transit", cls: "bg-accent-50 text-accent-700" },
  at_pickup: { label: "At pickup", cls: "bg-emerald-50 text-emerald-700" },
  at_delivery: { label: "At delivery", cls: "bg-emerald-50 text-emerald-700" },
  delivered: { label: "Delivered", cls: "bg-ink-100 text-ink-500" },
  exception: { label: "Exception", cls: "bg-red-50 text-red-700" },
};

export default function LoadCard({ driver, load, selected, onClick }: Props) {
  const [, forceTick] = useState(0);
  const isException = load.status === "exception";

  useEffect(() => {
    if (!isException) return;
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [isException]);

  const status = STATUS_LABEL[load.status] ?? STATUS_LABEL.in_transit;
  const billable = detentionBillable(load.arrived_at_stop_at, load.detention_free_minutes);
  const amount = detentionAmount(
    load.arrived_at_stop_at,
    load.detention_free_minutes,
    load.detention_rate_per_hour ?? 0,
  );

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full rounded-lg border bg-white p-3 text-left transition-all",
        "hover:border-ink-200 hover:shadow-soft",
        selected && !isException && "border-accent-500 bg-accent-50/40 ring-1 ring-accent-500",
        isException && "border-red-200",
        isException && "animate-exception-pulse",
      )}
    >
      {isException && (
        <span className="absolute inset-y-0 left-0 w-1 rounded-l-lg bg-red-500" />
      )}
      {selected && !isException && (
        <span className="absolute inset-y-0 left-0 w-1 rounded-l-lg bg-accent-500" />
      )}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[13px] font-semibold text-ink-900">
              {load.load_number}
            </span>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", status.cls)}>
              {status.label}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-1 text-xs text-ink-600">
            <Truck className="h-3 w-3 text-ink-400" />
            {driver.name}
            <span className="text-ink-300">·</span>
            <span className="font-mono text-[11px]">#{driver.truck_number}</span>
          </div>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1 text-[11px] text-ink-500">
        <MapPin className="h-3 w-3 text-ink-300" />
        <span className="truncate">{load.pickup.name}</span>
        <span className="text-ink-300">→</span>
        <span className="truncate">{load.delivery.name}</span>
      </div>

      {isException ? (
        <div className="mt-2.5 flex items-center justify-between rounded-md bg-red-50 px-2 py-1.5">
          <div className="flex items-center gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 text-red-500" />
            <span className="font-mono text-sm font-semibold text-red-700 tabular-nums">
              {formatTimer(billable.total)}
            </span>
          </div>
          <span className="font-mono text-sm font-semibold text-red-700 tabular-nums">
            {formatMoney(amount)}
          </span>
        </div>
      ) : (
        <div className="mt-2.5 text-[11px] text-ink-400">
          HOS {Math.round(driver.hos_drive_remaining_minutes / 60)}h remaining
        </div>
      )}
    </button>
  );
}
