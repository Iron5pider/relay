"use client";

import { useDrivers, useExceptionFeed } from "@/lib/realtime";
import { formatRelative } from "@/lib/time";

export default function OverviewPanel() {
  const drivers = useDrivers();
  const events = useExceptionFeed();

  const activeLoads = drivers.filter((d) => d.active_load && d.active_load.status !== "delivered").length;
  const onDuty = drivers.filter((d) => ["driving", "on_duty"].includes(d.status)).length;
  const exceptions = drivers.filter((d) => d.active_load?.status === "exception").length;

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-4 pb-4 pt-2">
      <div className="grid grid-cols-2 gap-2.5">
        <StatCard label="Active loads" value={activeLoads} />
        <StatCard label="Drivers on duty" value={onDuty} />
        <StatCard label="Exceptions" value={exceptions} tone={exceptions > 0 ? "danger" : "neutral"} />
        <StatCard label="Events today" value={events.length} />
      </div>

      <div className="mt-5">
        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-ink-400">
          Recent activity
        </div>
        <div className="space-y-1.5">
          {events.length === 0 ? (
            <div className="rounded-lg border border-dashed border-ink-200 p-4 text-center text-xs text-ink-400">
              No recent exception events.
            </div>
          ) : (
            events.slice(0, 6).map((e) => (
              <div
                key={e.id}
                className="rounded-lg border border-ink-100 bg-white p-2.5 text-xs"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink-900">
                    {e.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="font-mono text-[10px] text-ink-400">
                    {formatRelative(e.detected_at)}
                  </span>
                </div>
                <div className="mt-0.5 text-[11px] text-ink-500">
                  severity: {e.severity}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: number;
  tone?: "neutral" | "danger";
}) {
  return (
    <div className="rounded-lg border border-ink-100 bg-white p-3">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">
        {label}
      </div>
      <div
        className={`mt-1 font-mono text-[28px] font-bold tabular-nums ${tone === "danger" ? "text-red-600" : "text-ink-900"}`}
      >
        {value}
      </div>
    </div>
  );
}
