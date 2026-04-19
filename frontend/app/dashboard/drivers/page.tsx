"use client";

import { Users, Phone, Clock, MapPin } from "lucide-react";
import { useDrivers } from "@/lib/realtime";
import { formatMoney } from "@/lib/time";

export default function DriversPage() {
  const drivers = useDrivers();

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
              <th className="pb-2 pr-4">Language</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2 pr-4">Fatigue</th>
              <th className="pb-2 pr-4">HOS Drive</th>
              <th className="pb-2">Current Load</th>
            </tr>
          </thead>
          <tbody className="text-[13px] font-mono">
            {drivers.map((d) => {
              const hosHrs = Math.floor(d.hos_drive_remaining_minutes / 60);
              const hosMin = d.hos_drive_remaining_minutes % 60;
              const hosLow = d.hos_drive_remaining_minutes < 120;

              return (
                <tr key={d.driver_id} className="border-b border-ink-50 hover:bg-ink-50/50">
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
                        d.status === "sleeper" ? "bg-ink-200" :
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
                      <Clock size={10} className="text-ink-300" />
                      <span className={`tabular-nums ${hosLow ? "text-red-600 font-semibold" : "text-ink-600"}`}>
                        {hosHrs}h {hosMin}m
                      </span>
                      <div className="h-1 w-12 rounded-full bg-ink-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            hosLow ? "bg-red-500" : d.hos_drive_remaining_minutes > 240 ? "bg-emerald-500" : "bg-amber-500"
                          }`}
                          style={{ width: `${Math.min(d.hos_drive_remaining_minutes / 660, 1) * 100}%` }}
                        />
                      </div>
                    </span>
                  </td>
                  <td className="py-2.5">
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
                      <span className="text-ink-300 text-[11px]">No active load</span>
                    )}
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
    </div>
  );
}
