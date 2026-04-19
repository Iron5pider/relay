"use client";

import { useEffect, useState } from "react";
import { SplitSquareHorizontal, Truck, MapPin, Clock, Zap } from "lucide-react";
import { api, UnassignedLoad, CandidateScore } from "@/lib/api";
import { useDrivers } from "@/lib/realtime";
import { formatMoney } from "@/lib/time";

export default function AssignPage() {
  const drivers = useDrivers();
  const [unassigned, setUnassigned] = useState<UnassignedLoad[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CandidateScore[]>([]);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    api.unassignedLoads().then(setUnassigned).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) {
      setCandidates([]);
      return;
    }
    api.candidates(selected).then((r) => setCandidates(r.candidates)).catch(() => {});
  }, [selected]);

  const handleAssign = async (loadId: string, driverId: string) => {
    setAssigning(true);
    try {
      await api.assignLoad(loadId, driverId);
      setUnassigned((prev) => prev.filter((l) => l.id !== loadId));
      setSelected(null);
    } catch {
      // toast error
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <SplitSquareHorizontal size={18} className="text-ink-400" />
          <h1 className="text-[15px] font-mono font-semibold text-ink-900 tracking-tight">
            Assign Loads
          </h1>
          {unassigned.length > 0 && (
            <span className="rounded-full bg-red-500 px-2 py-0.5 text-[10px] font-mono font-bold text-white tabular-nums">
              {unassigned.length}
            </span>
          )}
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Left: unassigned loads */}
        <div className="w-[340px] shrink-0 border-r border-ink-100 overflow-auto">
          <div className="px-4 py-3 text-[10px] font-mono uppercase tracking-widest text-ink-400">
            Unassigned loads
          </div>
          {unassigned.length === 0 ? (
            <div className="px-4 py-8 text-center text-[12px] font-mono text-ink-300">
              No unassigned loads
            </div>
          ) : (
            <div className="space-y-1 px-2 pb-4">
              {unassigned.map((load) => (
                <button
                  key={load.id}
                  onClick={() => setSelected(load.id === selected ? null : load.id)}
                  className={`w-full rounded px-3 py-2.5 text-left transition-colors ${
                    selected === load.id
                      ? "bg-ink-900 text-white"
                      : "bg-ink-50 text-ink-700 hover:bg-ink-100"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-mono font-semibold">
                      {load.load_number}
                    </span>
                    <span className={`text-[11px] font-mono tabular-nums ${
                      selected === load.id ? "text-ink-300" : "text-ink-400"
                    }`}>
                      {formatMoney(load.rate_linehaul)}
                    </span>
                  </div>
                  <div className={`mt-1 text-[11px] font-mono ${
                    selected === load.id ? "text-ink-400" : "text-ink-400"
                  }`}>
                    {load.pickup_city} → {load.delivery_city}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: driver list */}
        <div className="flex-1 overflow-auto">
          <div className="px-4 py-3 text-[10px] font-mono uppercase tracking-widest text-ink-400">
            {selected ? "Suggested drivers" : "Select a load to see matches"}
          </div>

          {selected && candidates.length > 0 && (
            <div className="mx-4 mb-3 rounded border border-amber-200 bg-amber-50/50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-amber-700 mb-1.5">
                <Zap size={12} />
                Suggested match
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[13px] font-mono font-semibold text-ink-900">
                    {candidates[0].driver_name}
                  </span>
                  <span className="ml-2 text-[11px] font-mono text-ink-400">
                    Truck #{candidates[0].truck_number}
                  </span>
                </div>
                <button
                  onClick={() => handleAssign(selected, candidates[0].driver_id)}
                  disabled={assigning}
                  className="rounded bg-ink-900 px-3 py-1 text-[11px] font-mono font-medium text-white hover:bg-ink-800 disabled:opacity-50"
                >
                  Assign
                </button>
              </div>
            </div>
          )}

          <div className="space-y-0.5 px-2 pb-4">
            {(selected ? candidates : drivers).map((d: any) => {
              const driverId = d.driver_id || d.id;
              const name = d.driver_name || d.name;
              const truck = d.truck_number;
              const hos = d.hos_drive_remaining_min ?? d.hos_drive_remaining_minutes ?? 0;
              const hosMax = 660;
              const hosPct = Math.min(hos / hosMax, 1);

              return (
                <div
                  key={driverId}
                  className="flex items-center gap-3 rounded px-3 py-2.5 hover:bg-ink-50 transition-colors"
                >
                  <div className={`h-2 w-2 rounded-full shrink-0 ${
                    hos > 120 ? "bg-emerald-500" : hos > 60 ? "bg-amber-500" : "bg-red-500"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-mono font-semibold text-ink-900 truncate">
                        {name}
                      </span>
                      <span className="text-[11px] font-mono text-ink-400">
                        #{truck}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-3">
                      <div className="flex items-center gap-1 text-[11px] font-mono text-ink-400">
                        <Clock size={10} />
                        {Math.floor(hos / 60)}h {hos % 60}m
                      </div>
                      {/* HOS bar */}
                      <div className="h-1 w-16 rounded-full bg-ink-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            hos > 120 ? "bg-emerald-500" : hos > 60 ? "bg-amber-500" : "bg-red-500"
                          }`}
                          style={{ width: `${hosPct * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  {selected && (
                    <button
                      onClick={() => handleAssign(selected, driverId)}
                      disabled={assigning}
                      className="shrink-0 rounded border border-ink-200 px-2.5 py-1 text-[11px] font-mono font-medium text-ink-600 hover:bg-ink-50 disabled:opacity-50"
                    >
                      Assign
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
