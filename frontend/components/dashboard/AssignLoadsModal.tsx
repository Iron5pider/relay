"use client";

import { useEffect, useState, useCallback } from "react";
import { toast } from "sonner";
import {
  CheckCircle2,
  Sparkles,
  AlertTriangle,
  MapPin,
  Clock,
  Gauge,
  Truck,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  api,
  type CandidatesResponse,
  type CandidateScore,
  type UnassignedLoad,
} from "@/lib/api";
import { formatMinutes, formatMoney } from "@/lib/time";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const DISQUALIFY_LABEL: Record<string, string> = {
  status_driving: "Driving — don't pull off the road",
  status_off_duty: "Off duty",
  status_sleeper: "In sleeper berth",
  insufficient_hos: "Insufficient HOS for the haul",
  no_gps_fix: "No GPS fix",
};

export default function AssignLoadsModal({ open, onOpenChange }: Props) {
  const [loads, setLoads] = useState<UnassignedLoad[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<CandidatesResponse | null>(null);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [assigning, setAssigning] = useState<string | null>(null);

  const fetchLoads = useCallback(async () => {
    try {
      const res = await api.unassignedLoads();
      setLoads(res.loads);
      if (res.loads.length > 0 && !selectedId) {
        setSelectedId(res.loads[0].load_id);
      } else if (res.loads.length === 0) {
        setSelectedId(null);
        setCandidates(null);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load";
      toast.error(`Unassigned loads: ${msg}`);
    }
  }, [selectedId]);

  useEffect(() => {
    if (!open) return;
    setLoads(null);
    setSelectedId(null);
    setCandidates(null);
    void fetchLoads();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setLoadingCandidates(true);
    setCandidates(null);
    api
      .loadCandidates(selectedId)
      .then((res) => {
        if (!cancelled) setCandidates(res);
      })
      .catch((err: Error) => {
        if (!cancelled) {
          toast.error(`Candidates: ${err.message}`);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCandidates(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function handleAssign(driverId: string, driverName: string) {
    if (!selectedId || !candidates) return;
    setAssigning(driverId);
    try {
      await api.assignLoad(selectedId, driverId);
      toast.success(`${candidates.load_number} → ${driverName}`);
      // Remove the assigned load from the list, pick the next one.
      setLoads((prev) => {
        const next = (prev ?? []).filter((l) => l.load_id !== selectedId);
        setSelectedId(next[0]?.load_id ?? null);
        if (!next.length) setCandidates(null);
        return next;
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Assign failed";
      toast.error(msg);
    } finally {
      setAssigning(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] w-[min(1100px,95vw)] max-w-[1100px] overflow-hidden p-0 sm:max-w-[1100px]">
        <DialogHeader className="border-b border-ink-100 px-6 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Truck className="h-4 w-4 text-accent-600" />
            Assign loads
            {loads && loads.length > 0 && (
              <Badge className="bg-accent-50 text-accent-700 hover:bg-accent-50">
                {loads.length} unassigned
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription className="text-xs">
            HOS-ranked candidates with AI recommendation. Assignments post to{" "}
            <code className="font-mono">/dispatcher/load/[id]/assign</code>.
          </DialogDescription>
        </DialogHeader>

        <div className="flex h-[65vh] min-h-[440px]">
          {/* Left: unassigned loads list */}
          <aside className="w-[260px] shrink-0 overflow-y-auto border-r border-ink-100 bg-ink-50/40">
            {loads === null ? (
              <div className="space-y-2 p-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-20 w-full rounded-lg" />
                ))}
              </div>
            ) : loads.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center px-4 text-center">
                <CheckCircle2 className="mb-2 h-8 w-8 text-emerald-500" />
                <div className="text-sm font-medium text-ink-900">
                  All loads assigned
                </div>
                <div className="mt-1 text-[11px] text-ink-500">
                  No planned, driverless loads in the queue.
                </div>
              </div>
            ) : (
              <div className="space-y-1.5 p-3">
                {loads.map((l) => (
                  <LoadListCard
                    key={l.load_id}
                    load={l}
                    selected={l.load_id === selectedId}
                    onClick={() => setSelectedId(l.load_id)}
                  />
                ))}
              </div>
            )}
          </aside>

          {/* Right: candidates for selected load */}
          <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
            {!selectedId ? (
              <div className="flex h-full items-center justify-center text-sm text-ink-400">
                Select a load to see candidates.
              </div>
            ) : loadingCandidates || !candidates ? (
              <div className="space-y-3 p-5">
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-20 w-full rounded-lg" />
                <Skeleton className="h-20 w-full rounded-lg" />
                <Skeleton className="h-20 w-full rounded-lg" />
              </div>
            ) : (
              <CandidatesView
                data={candidates}
                onAssign={handleAssign}
                assigning={assigning}
              />
            )}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function LoadListCard({
  load,
  selected,
  onClick,
}: {
  load: UnassignedLoad;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full rounded-lg border bg-white p-2.5 text-left transition",
        selected
          ? "border-accent-500 bg-accent-50/60 ring-1 ring-accent-500"
          : "border-ink-100 hover:border-ink-200",
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[12px] font-semibold text-ink-900">
          {load.load_number}
        </span>
        <span className="font-mono text-[11px] text-ink-500">
          {formatMoney(load.rate_linehaul)}
        </span>
      </div>
      <div className="mt-1 text-[11px] text-ink-600">{load.broker_name}</div>
      <div className="mt-1 flex items-center gap-1 text-[11px] text-ink-500">
        <MapPin className="h-3 w-3 text-ink-300" />
        <span className="truncate">{load.pickup_name}</span>
        <span className="text-ink-300">→</span>
        <span className="truncate">{load.delivery_name}</span>
      </div>
      {load.delivery_appointment && (
        <div className="mt-1 flex items-center gap-1 text-[10px] text-ink-400">
          <Clock className="h-2.5 w-2.5" />
          Deliver {new Date(load.delivery_appointment).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          })}
        </div>
      )}
    </button>
  );
}

function CandidatesView({
  data,
  onAssign,
  assigning,
}: {
  data: CandidatesResponse;
  onAssign: (driverId: string, driverName: string) => Promise<void>;
  assigning: string | null;
}) {
  const qualified = data.ranking.filter((c) => c.qualified);
  const disqualified = data.ranking.filter((c) => !c.qualified);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Load header */}
      <div className="border-b border-ink-100 px-5 py-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-sm font-semibold text-ink-900">
              {data.load_number}
            </div>
            <div className="text-[11px] text-ink-500">
              Haul {data.haul_miles.toFixed(0)} miles · {qualified.length}{" "}
              qualified candidate{qualified.length === 1 ? "" : "s"}
            </div>
          </div>
        </div>
      </div>

      {/* AI recommendation */}
      <div className="border-b border-ink-100 bg-accent-50/40 px-5 py-3">
        <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-accent-700">
          <Sparkles className="h-3 w-3" />
          AI recommendation
          <Badge
            variant="outline"
            className={cn(
              "ml-1 border-0 text-[9px]",
              data.ai_recommendation.confidence === "high"
                ? "bg-emerald-100 text-emerald-800"
                : data.ai_recommendation.confidence === "medium"
                  ? "bg-accent-100 text-accent-800"
                  : "bg-ink-100 text-ink-700",
            )}
          >
            {data.ai_recommendation.confidence} confidence
          </Badge>
        </div>
        <p className="text-[13px] leading-relaxed text-ink-800">
          {data.ai_recommendation.recommendation}
        </p>
        {data.ai_recommendation.risk_flags.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {data.ai_recommendation.risk_flags.map((f) => (
              <span
                key={f}
                className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700"
              >
                {f.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Ranked list */}
      <div className="flex-1 space-y-2 overflow-y-auto px-5 py-3">
        {qualified.map((c, i) => (
          <CandidateCard
            key={c.driver_id}
            c={c}
            rank={i + 1}
            isAiPick={c.driver_id === data.ai_recommendation.recommended_driver_id}
            isAlternate={c.driver_id === data.ai_recommendation.alternative_driver_id}
            onAssign={() => onAssign(c.driver_id, c.driver_name)}
            assigning={assigning === c.driver_id}
            disabled={assigning !== null && assigning !== c.driver_id}
          />
        ))}
        {disqualified.length > 0 && (
          <>
            <div className="mt-4 mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-400">
              Not eligible
            </div>
            {disqualified.map((c) => (
              <DisqualifiedCard key={c.driver_id} c={c} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function CandidateCard({
  c,
  rank,
  isAiPick,
  isAlternate,
  onAssign,
  assigning,
  disabled,
}: {
  c: CandidateScore;
  rank: number;
  isAiPick: boolean;
  isAlternate: boolean;
  onAssign: () => void;
  assigning: boolean;
  disabled: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-white p-3 transition",
        isAiPick
          ? "border-accent-500 shadow-[0_0_0_1px_rgb(59,130,246)]"
          : "border-ink-100",
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-md font-mono text-xs font-bold",
            rank === 1
              ? "bg-accent-600 text-white"
              : "bg-ink-100 text-ink-600",
          )}
        >
          {rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-ink-900">
              {c.driver_name}
            </span>
            <span className="font-mono text-[11px] text-ink-500">
              #{c.truck_number}
            </span>
            <span className="rounded-sm bg-ink-100 px-1 font-mono text-[10px] uppercase text-ink-600">
              {c.preferred_language}
            </span>
            {isAiPick && (
              <Badge className="border-0 bg-accent-50 text-[9px] text-accent-700">
                <Sparkles className="mr-0.5 h-2.5 w-2.5" /> AI pick
              </Badge>
            )}
            {isAlternate && (
              <Badge className="border-0 bg-ink-100 text-[9px] text-ink-600">
                alt
              </Badge>
            )}
          </div>

          <div className="mt-1.5 grid grid-cols-4 gap-2 text-[11px]">
            <Stat label="Score" value={c.score.toFixed(1)} emphasize />
            <Stat
              label="To pickup"
              value={c.miles_to_pickup != null ? `${c.miles_to_pickup.toFixed(0)}mi` : "—"}
            />
            <Stat
              label="HOS headroom"
              value={formatMinutes(Math.max(0, c.hos_headroom_minutes))}
            />
            <Stat label="Fatigue" value={c.fatigue_level} />
          </div>

          {/* Component bars */}
          <div className="mt-2 grid grid-cols-4 gap-2">
            {(
              ["hos_headroom", "proximity", "freshness", "fatigue"] as const
            ).map((k) => (
              <Bar key={k} label={k.replace(/_/g, " ")} value={c.components[k] ?? 0} />
            ))}
          </div>

          {c.flags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {c.flags.map((f) => (
                <span
                  key={f}
                  className="rounded-full bg-amber-50 px-1.5 py-0.5 text-[9px] font-medium text-amber-700"
                >
                  {f.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>

        <button
          onClick={onAssign}
          disabled={assigning || disabled}
          className={cn(
            "shrink-0 rounded-lg px-3 py-2 text-xs font-semibold transition",
            "bg-accent-600 text-white shadow-soft hover:bg-accent-700",
            "disabled:cursor-not-allowed disabled:opacity-60",
          )}
        >
          {assigning ? "Assigning…" : "Assign"}
        </button>
      </div>
    </div>
  );
}

function DisqualifiedCard({ c }: { c: CandidateScore }) {
  const reason =
    c.disqualification_reason && DISQUALIFY_LABEL[c.disqualification_reason]
      ? DISQUALIFY_LABEL[c.disqualification_reason]
      : c.disqualification_reason?.replace(/_/g, " ") ?? "Not eligible";
  return (
    <div className="rounded-lg border border-ink-100 bg-ink-50/40 p-2.5">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-ink-400" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-xs font-medium text-ink-700">
              {c.driver_name}
            </span>
            <span className="font-mono text-[11px] text-ink-400">
              #{c.truck_number}
            </span>
          </div>
          <div className="text-[11px] text-ink-500">{reason}</div>
        </div>
        <span className="font-mono text-[10px] uppercase text-ink-400">
          {c.status}
        </span>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  emphasize = false,
}: {
  label: string;
  value: string | number;
  emphasize?: boolean;
}) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-ink-400">
        {label}
      </div>
      <div
        className={cn(
          "font-mono tabular-nums",
          emphasize ? "text-sm font-bold text-accent-700" : "text-[12px] text-ink-800",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div>
      <div className="mb-0.5 flex items-center justify-between text-[9px] text-ink-400">
        <span className="truncate">{label}</span>
        <span className="font-mono">{(pct * 100).toFixed(0)}</span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-ink-100">
        <div
          className="h-full rounded-full bg-accent-500"
          style={{ width: `${pct * 100}%` }}
        />
      </div>
    </div>
  );
}
