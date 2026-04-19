"use client";

import { useEffect, useState } from "react";
import {
  Users, Phone, Clock, MapPin, ChevronDown, ChevronRight,
  PhoneOutgoing, PhoneIncoming, AlertTriangle, Fuel, Wrench,
  Navigation, Activity, FileText, Truck as TruckIcon,
} from "lucide-react";
import { useDrivers } from "@/lib/realtime";
import { api, CallSummary, DriverTimelineEvent, DriverRow } from "@/lib/api";
import { formatMoney, formatRelative, formatMinutes } from "@/lib/time";

function DriverDetailPanel({ driver, onClose }: { driver: DriverRow; onClose: () => void }) {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [timeline, setTimeline] = useState<DriverTimelineEvent[]>([]);
  const [tab, setTab] = useState<"overview" | "calls" | "timeline">("overview");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.driverDetail(driver.driver_id).then((d) => setCalls(d.recent_calls ?? [])).catch(() => {}),
      api.driverTimeline(driver.driver_id, 50).then((t) => setTimeline(t.events ?? [])).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, [driver.driver_id]);

  const hosHrs = Math.floor(driver.hos_drive_remaining_minutes / 60);
  const hosMin = driver.hos_drive_remaining_minutes % 60;
  const shiftHrs = Math.floor(driver.hos_shift_remaining_minutes / 60);
  const shiftMin = driver.hos_shift_remaining_minutes % 60;
  const cycleHrs = Math.floor(driver.hos_cycle_remaining_minutes / 60);
  const cycleMin = driver.hos_cycle_remaining_minutes % 60;

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30" onClick={onClose} />

      {/* Panel */}
      <div className="w-[520px] bg-white h-full overflow-auto border-l border-ink-100 shadow-xl">
        {/* Header */}
        <div className="sticky top-0 bg-white z-10 border-b border-ink-100 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-[16px] font-mono font-bold text-ink-900">{driver.name}</h2>
              <p className="text-[12px] font-mono text-ink-400 mt-0.5">
                Truck #{driver.truck_number} · {driver.phone} · {driver.preferred_language.toUpperCase()}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded px-2 py-1 text-[11px] font-mono font-medium ${
                driver.status === "driving" || driver.status === "rolling" ? "bg-emerald-50 text-emerald-700" :
                driver.status === "on_duty" || driver.status === "ready" ? "bg-blue-50 text-blue-700" :
                "bg-ink-50 text-ink-500"
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${
                  driver.status === "driving" || driver.status === "rolling" ? "bg-emerald-500" :
                  driver.status === "on_duty" || driver.status === "ready" ? "bg-blue-500" :
                  "bg-ink-300"
                }`} />
                {driver.status}
              </span>
            </div>
          </div>
        </div>

        {/* HOS clocks */}
        <div className="px-6 py-4 border-b border-ink-100">
          <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400 mb-3">
            Hours of Service — FMCSA 3-clock model
          </p>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Drive", hours: hosHrs, mins: hosMin, total: driver.hos_drive_remaining_minutes, max: 660, color: driver.hos_drive_remaining_minutes < 120 ? "red" : driver.hos_drive_remaining_minutes > 240 ? "emerald" : "amber" },
              { label: "Shift", hours: shiftHrs, mins: shiftMin, total: driver.hos_shift_remaining_minutes, max: 840, color: driver.hos_shift_remaining_minutes < 120 ? "red" : "blue" },
              { label: "Cycle", hours: cycleHrs, mins: cycleMin, total: driver.hos_cycle_remaining_minutes, max: 4200, color: "ink" },
            ].map((c) => (
              <div key={c.label}>
                <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">{c.label}</p>
                <p className={`text-[18px] font-mono font-bold tabular-nums ${
                  c.color === "red" ? "text-red-600" : c.color === "emerald" ? "text-emerald-700" : c.color === "amber" ? "text-amber-700" : "text-ink-700"
                }`}>
                  {c.hours}h {c.mins}m
                </p>
                <div className="h-1.5 w-full rounded-full bg-ink-100 mt-1 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      c.color === "red" ? "bg-red-500" : c.color === "emerald" ? "bg-emerald-500" : c.color === "amber" ? "bg-amber-500" : "bg-ink-400"
                    }`}
                    style={{ width: `${Math.min(c.total / c.max, 1) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Status cards */}
        <div className="px-6 py-4 border-b border-ink-100 grid grid-cols-2 gap-3">
          <div className="rounded border border-ink-100 px-3 py-2.5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Fatigue</p>
            <p className={`text-[14px] font-mono font-semibold mt-0.5 ${
              driver.fatigue_level === "high" ? "text-red-600" :
              driver.fatigue_level === "moderate" ? "text-amber-600" :
              driver.fatigue_level === "low" ? "text-emerald-600" :
              "text-ink-400"
            }`}>
              {driver.fatigue_level}
            </p>
          </div>
          <div className="rounded border border-ink-100 px-3 py-2.5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Last check-in</p>
            <p className="text-[14px] font-mono font-semibold text-ink-700 mt-0.5">
              {driver.last_checkin_at ? formatRelative(driver.last_checkin_at) : "Never"}
            </p>
          </div>
          <div className="rounded border border-ink-100 px-3 py-2.5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Current load</p>
            <p className="text-[14px] font-mono font-semibold text-ink-700 mt-0.5">
              {driver.active_load?.load_number ?? "None"}
            </p>
          </div>
          <div className="rounded border border-ink-100 px-3 py-2.5">
            <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Load status</p>
            {driver.active_load ? (
              <span className={`inline-flex rounded px-1.5 py-0.5 text-[11px] font-mono font-medium uppercase mt-0.5 ${
                driver.active_load.status === "exception" ? "bg-red-50 text-red-600" : "bg-ink-50 text-ink-600"
              }`}>
                {driver.active_load.status}
              </span>
            ) : (
              <p className="text-[14px] font-mono text-ink-300 mt-0.5">—</p>
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="px-6 border-b border-ink-100 flex gap-4">
          {(["overview", "calls", "timeline"] as const).map((t) => (
            <div
              key={t}
              role="button"
              tabIndex={0}
              onClick={() => setTab(t)}
              onKeyDown={(e) => { if (e.key === "Enter") setTab(t); }}
              className={`py-3 text-[12px] font-mono font-medium cursor-pointer border-b-2 transition-colors ${
                tab === t
                  ? "border-red-500 text-ink-900"
                  : "border-transparent text-ink-400 hover:text-ink-600"
              }`}
            >
              {t === "overview" ? "Overview" : t === "calls" ? `Calls (${calls.length})` : `Timeline (${timeline.length})`}
            </div>
          ))}
        </div>

        {/* Tab content */}
        <div className="px-6 py-4">
          {loading && (
            <div className="text-center py-8 text-[12px] font-mono text-ink-300">Loading...</div>
          )}

          {!loading && tab === "overview" && (
            <div className="space-y-3">
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Position</p>
              <div className="flex items-center gap-2 text-[13px] font-mono text-ink-600">
                <MapPin size={14} className="text-ink-300" />
                {driver.current_lat && driver.current_lng
                  ? `${driver.current_lat.toFixed(4)}, ${driver.current_lng.toFixed(4)}`
                  : "Unknown"}
              </div>
              {driver.updated_at && (
                <p className="text-[11px] font-mono text-ink-400">
                  Last updated: {formatRelative(driver.updated_at)}
                </p>
              )}
              {driver.next_scheduled_checkin_at && (
                <div className="mt-4">
                  <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400 mb-1">Next scheduled check-in</p>
                  <p className="text-[13px] font-mono text-ink-700">
                    {new Date(driver.next_scheduled_checkin_at).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          )}

          {!loading && tab === "calls" && (
            <div className="space-y-2">
              {calls.length === 0 && (
                <p className="text-[12px] font-mono text-ink-300 text-center py-6">No call history</p>
              )}
              {calls.map((c) => (
                <div key={c.call_id} className="rounded border border-ink-100 px-3 py-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {c.direction === "outbound" ? (
                        <PhoneOutgoing size={12} className="text-blue-500" />
                      ) : (
                        <PhoneIncoming size={12} className="text-emerald-500" />
                      )}
                      <span className="text-[12px] font-mono font-semibold text-ink-900">
                        {c.purpose?.replace(/_/g, " ") ?? c.direction}
                      </span>
                    </div>
                    <span className={`inline-flex rounded px-1.5 py-0.5 text-[9px] font-mono font-medium uppercase tracking-wider ${
                      c.outcome === "resolved" ? "bg-emerald-50 text-emerald-700" :
                      c.outcome === "escalated" ? "bg-amber-50 text-amber-700" :
                      c.outcome === "failed" ? "bg-red-50 text-red-700" :
                      c.outcome === "voicemail" ? "bg-purple-50 text-purple-700" :
                      "bg-ink-50 text-ink-500"
                    }`}>
                      {c.outcome ?? c.call_status}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-3 text-[11px] font-mono text-ink-400">
                    {c.started_at && <span>{formatRelative(c.started_at)}</span>}
                    {c.duration_seconds != null && <span>{Math.floor(c.duration_seconds / 60)}m {c.duration_seconds % 60}s</span>}
                    {c.trigger_reason && <span className="text-ink-300">{c.trigger_reason}</span>}
                    {c.language && <span className="uppercase">{c.language}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && tab === "timeline" && (
            <div className="space-y-1">
              {timeline.length === 0 && (
                <p className="text-[12px] font-mono text-ink-300 text-center py-6">No timeline events</p>
              )}
              {timeline.map((ev) => (
                <div key={ev.event_id} className="flex items-start gap-3 py-2 border-b border-ink-50">
                  <div className="mt-0.5">
                    {ev.kind === "exception" ? <AlertTriangle size={12} className="text-red-500" /> :
                     ev.kind === "call" ? <Phone size={12} className="text-blue-500" /> :
                     ev.kind === "status_change" ? <Activity size={12} className="text-amber-500" /> :
                     ev.kind === "checkin" ? <PhoneOutgoing size={12} className="text-emerald-500" /> :
                     <Navigation size={12} className="text-ink-300" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[12px] font-mono text-ink-700">
                      {ev.kind.replace(/_/g, " ")}
                    </p>
                    {ev.payload && Object.keys(ev.payload).length > 0 && (
                      <p className="text-[11px] font-mono text-ink-400 mt-0.5 truncate">
                        {JSON.stringify(ev.payload).slice(0, 120)}
                      </p>
                    )}
                    <p className="text-[10px] font-mono text-ink-300 mt-0.5">
                      {formatRelative(ev.detected_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function DriversPage() {
  const drivers = useDrivers();
  const [selectedDriver, setSelectedDriver] = useState<DriverRow | null>(null);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <Users size={18} className="text-ink-400" />
          <h1 className="text-[15px] font-mono font-semibold text-ink-900 tracking-tight">
            Drivers
          </h1>
          <span className="text-[12px] font-mono text-ink-400">
            {drivers.length} total
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] font-mono uppercase tracking-widest text-ink-400 border-b border-ink-100">
              <th className="pb-2 pr-4">Driver</th>
              <th className="pb-2 pr-4">Truck</th>
              <th className="pb-2 pr-4">Phone</th>
              <th className="pb-2 pr-4">Lang</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">Fatigue</th>
              <th className="pb-2 pr-4">HOS Drive</th>
              <th className="pb-2 pr-4">Current Load</th>
              <th className="pb-2">Last Check-in</th>
            </tr>
          </thead>
          <tbody className="text-[13px] font-mono">
            {drivers.map((d) => {
              const hosHrs = Math.floor(d.hos_drive_remaining_minutes / 60);
              const hosMin = d.hos_drive_remaining_minutes % 60;
              const hosLow = d.hos_drive_remaining_minutes < 120;

              return (
                <tr
                  key={d.driver_id}
                  className="border-b border-ink-50 hover:bg-ink-50/50 cursor-pointer"
                  onClick={() => setSelectedDriver(d)}
                >
                  <td className="py-2.5 pr-4">
                    <span className="font-semibold text-ink-900">{d.name}</span>
                  </td>
                  <td className="py-2.5 pr-4 text-ink-600">#{d.truck_number}</td>
                  <td className="py-2.5 pr-4 text-ink-400 text-[12px]">
                    <span className="flex items-center gap-1">
                      <Phone size={10} />
                      {d.phone}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider ${
                      d.preferred_language === "es" ? "bg-amber-50 text-amber-700" :
                      d.preferred_language === "pa" ? "bg-purple-50 text-purple-700" :
                      "bg-ink-50 text-ink-600"
                    }`}>
                      {d.preferred_language}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="flex items-center gap-1.5">
                      <span className={`h-2 w-2 rounded-full ${
                        d.status === "driving" || d.status === "rolling" ? "bg-emerald-500" :
                        d.status === "on_duty" || d.status === "ready" ? "bg-blue-500" :
                        d.status === "off_duty" || d.status === "resting" ? "bg-ink-300" :
                        "bg-amber-500"
                      }`} />
                      <span className="text-ink-600 text-[12px]">{d.status}</span>
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider ${
                      d.fatigue_level === "high" ? "bg-red-50 text-red-700" :
                      d.fatigue_level === "moderate" ? "bg-amber-50 text-amber-700" :
                      d.fatigue_level === "low" ? "bg-emerald-50 text-emerald-700" :
                      "bg-ink-50 text-ink-400"
                    }`}>
                      {d.fatigue_level}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span className="flex items-center gap-2">
                      <span className={`tabular-nums ${hosLow ? "text-red-600 font-semibold" : "text-ink-600"}`}>
                        {hosHrs}h {hosMin}m
                      </span>
                      <div className="h-1 w-12 rounded-full bg-ink-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${hosLow ? "bg-red-500" : d.hos_drive_remaining_minutes > 240 ? "bg-emerald-500" : "bg-amber-500"}`}
                          style={{ width: `${Math.min(d.hos_drive_remaining_minutes / 660, 1) * 100}%` }}
                        />
                      </div>
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    {d.active_load ? (
                      <span className="flex items-center gap-1.5">
                        <span className="font-semibold text-ink-900">{d.active_load.load_number}</span>
                        <span className={`inline-flex rounded px-1 py-0.5 text-[9px] font-mono font-medium uppercase ${
                          d.active_load.status === "exception" ? "bg-red-50 text-red-600" : "bg-ink-50 text-ink-500"
                        }`}>
                          {d.active_load.status}
                        </span>
                      </span>
                    ) : (
                      <span className="text-ink-300 text-[11px]">—</span>
                    )}
                  </td>
                  <td className="py-2.5">
                    <span className="text-ink-400 text-[11px]">
                      {d.last_checkin_at ? formatRelative(d.last_checkin_at) : "Never"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {drivers.length === 0 && (
          <div className="py-12 text-center text-[13px] font-mono text-ink-300">
            No drivers loaded — check backend connection.
          </div>
        )}
      </div>

      {selectedDriver && (
        <DriverDetailPanel driver={selectedDriver} onClose={() => setSelectedDriver(null)} />
      )}
    </div>
  );
}
