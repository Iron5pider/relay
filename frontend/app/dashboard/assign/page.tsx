"use client";

import { useEffect, useState } from "react";
import { SplitSquareHorizontal, Clock, Zap, AlertTriangle, Brain } from "lucide-react";
import { api, UnassignedLoad, CandidateScore, AiRecommendation } from "@/lib/api";
import { useDrivers } from "@/lib/realtime";
import { formatMoney } from "@/lib/time";

export default function AssignPage() {
  const drivers = useDrivers();
  const [unassigned, setUnassigned] = useState<UnassignedLoad[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CandidateScore[]>([]);
  const [aiRec, setAiRec] = useState<AiRecommendation | null>(null);
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    api.unassignedLoads()
      .then((r) => setUnassigned(Array.isArray(r) ? r : r.loads ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) {
      setCandidates([]);
      setAiRec(null);
      return;
    }
    api.loadCandidates(selected)
      .then((r) => {
        setCandidates(r.ranking ?? []);
        setAiRec(r.ai_recommendation ?? null);
      })
      .catch(() => { setCandidates([]); setAiRec(null); });
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

          {/* AI Recommendation panel */}
          {selected && aiRec && (
            <div className="mx-4 mb-3 rounded border border-blue-200 bg-blue-50/40 px-4 py-3">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-blue-700 mb-2">
                <Brain size={12} />
                AI recommendation
                <span className={`ml-1 rounded px-1 py-0.5 text-[9px] ${
                  aiRec.confidence === "high" ? "bg-emerald-100 text-emerald-700" :
                  aiRec.confidence === "medium" ? "bg-amber-100 text-amber-700" :
                  "bg-red-100 text-red-700"
                }`}>
                  {aiRec.confidence} confidence
                </span>
              </div>
              <p className="text-[12px] font-mono text-ink-700 leading-relaxed mb-2">
                {aiRec.recommendation}
              </p>
              {aiRec.risk_flags.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {aiRec.risk_flags.map((flag, i) => (
                    <span key={i} className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-mono text-amber-800">
                      <AlertTriangle size={9} />
                      {flag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Suggested match from scoring */}
          {selected && candidates.length > 0 && (
            <div className="mx-4 mb-3 rounded border border-amber-200 bg-amber-50/50 px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-amber-700 mb-1.5">
                <Zap size={12} />
                Top ranked driver
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[13px] font-mono font-semibold text-ink-900">
                    {candidates[0].driver_name}
                  </span>
                  <span className="ml-2 text-[11px] font-mono text-ink-400">
                    Truck #{candidates[0].truck_number}
                  </span>
                  <span className="ml-2 text-[10px] font-mono text-ink-300">
                    score: {candidates[0].score.toFixed(1)}
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
              {/* Scoring breakdown */}
              {candidates[0].components && Object.keys(candidates[0].components).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(candidates[0].components).map(([k, v]) => (
                    <span key={k} className="text-[10px] font-mono text-ink-400">
                      {k}: <span className="text-ink-600 font-medium">{(v as number).toFixed(1)}</span>
                    </span>
                  ))}
                </div>
              )}
              {candidates[0].disqualification_reason && (
                <p className="mt-1 text-[10px] font-mono text-red-500">
                  {candidates[0].disqualification_reason}
                </p>
              )}
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
