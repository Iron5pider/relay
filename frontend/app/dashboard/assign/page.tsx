"use client";

import { useEffect, useState } from "react";
import { SplitSquareHorizontal, Clock, Zap } from "lucide-react";
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
    api.unassignedLoads()
      .then((r) => setUnassigned(Array.isArray(r) ? r : r.loads ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) {
      setCandidates([]);
      return;
    }
    api.loadCandidates(selected)
      .then((r) => setCandidates(r.ranking ?? []))
      .catch(() => setCandidates([]));
  }, [selected]);

  const handleAssign = async (loadId: string, driverId: string) => {
    setAssigning(true);
    try {
      await api.assignLoad(loadId, driverId);
      setUnassigned((prev) => prev.filter((l) => l.load_id !== loadId));
      setSelected(null);
    } catch {
      // toast error
    } finally {
      setAssigning(false);
    }
  };

  // When no candidates from API, show all drivers from realtime store
  const driverList = selected && candidates.length > 0
    ? candidates.map((c) => ({
        id: c.driver_id,
        name: c.driver_name,
        truck: c.truck_number,
        hos: c.hos_drive_remaining_minutes,
        status: c.status,
        score: c.score,
      }))
    : drivers.map((d) => ({
        id: d.driver_id,
        name: d.name,
        truck: d.truck_number,
        hos: d.hos_drive_remaining_minutes,
        status: d.status as string,
        score: null as number | null,
      }));

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
                <div
                  key={load.load_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelected(load.load_id === selected ? null : load.load_id)}
                  onKeyDown={(e) => { if (e.key === "Enter") setSelected(load.load_id === selected ? null : load.load_id); }}
                  className={`w-full rounded px-3 py-2.5 text-left transition-colors cursor-pointer ${
                    selected === load.load_id
                      ? "bg-ink-900 text-white"
                      : "bg-ink-50 text-ink-700 hover:bg-ink-100"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-mono font-semibold">
                      {load.load_number}
                    </span>
                    <span className={`text-[11px] font-mono tabular-nums ${
                      selected === load.load_id ? "text-ink-300" : "text-ink-400"
                    }`}>
                      {formatMoney(load.rate_linehaul)}
                    </span>
                  </div>
                  <div className={`mt-1 text-[11px] font-mono ${
                    selected === load.load_id ? "text-ink-400" : "text-ink-400"
                  }`}>
                    {load.pickup_name} → {load.delivery_name}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: driver list */}
        <div className="flex-1 overflow-auto">
          <div className="px-4 py-3 text-[10px] font-mono uppercase tracking-widest text-ink-400">
            {selected ? "Available drivers" : "Select a load to see matches"}
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
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => handleAssign(selected, candidates[0].driver_id)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleAssign(selected, candidates[0].driver_id); }}
                  className={`rounded bg-ink-900 px-3 py-1 text-[11px] font-mono font-medium text-white hover:bg-ink-800 cursor-pointer ${assigning ? "opacity-50 pointer-events-none" : ""}`}
                >
                  Assign
                </div>
              </div>
            </div>
          )}

          <div className="space-y-0.5 px-2 pb-4">
            {driverList.map((d) => {
              const hosMax = 660;
              const hosPct = Math.min(d.hos / hosMax, 1);

              return (
                <div
                  key={d.id}
                  className="flex items-center gap-3 rounded px-3 py-2.5 hover:bg-ink-50 transition-colors"
                >
                  <div className={`h-2 w-2 rounded-full shrink-0 ${
                    d.hos > 120 ? "bg-emerald-500" : d.hos > 60 ? "bg-amber-500" : "bg-red-500"
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-mono font-semibold text-ink-900 truncate">
                        {d.name}
                      </span>
                      <span className="text-[11px] font-mono text-ink-400">
                        #{d.truck}
                      </span>
                      {d.score !== null && (
                        <span className="text-[10px] font-mono text-ink-300">
                          score: {d.score.toFixed(1)}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-3">
                      <div className="flex items-center gap-1 text-[11px] font-mono text-ink-400">
                        <Clock size={10} />
                        {Math.floor(d.hos / 60)}h {d.hos % 60}m
                      </div>
                      <div className="h-1 w-16 rounded-full bg-ink-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            d.hos > 120 ? "bg-emerald-500" : d.hos > 60 ? "bg-amber-500" : "bg-red-500"
                          }`}
                          style={{ width: `${hosPct * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                  {selected && (
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => handleAssign(selected, d.id)}
                      onKeyDown={(e) => { if (e.key === "Enter") handleAssign(selected, d.id); }}
                      className={`shrink-0 rounded border border-ink-200 px-2.5 py-1 text-[11px] font-mono font-medium text-ink-600 hover:bg-ink-50 cursor-pointer ${assigning ? "opacity-50 pointer-events-none" : ""}`}
                    >
                      Assign
                    </div>
                  )}
                </div>
              );
            })}
            {driverList.length === 0 && selected && (
              <div className="px-4 py-8 text-center text-[12px] font-mono text-ink-300">
                No drivers available
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
