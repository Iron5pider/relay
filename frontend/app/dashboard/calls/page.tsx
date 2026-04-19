"use client";

import { useEffect, useMemo, useState } from "react";
import {
  PhoneCall,
  PhoneOutgoing,
  PhoneIncoming,
  Voicemail,
  CheckCircle2,
  XCircle,
  AlertCircle,
  CircleDashed,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/time";
import type {
  CallDetail,
  CallListRow,
  DataCollectionField,
  EvaluationCriterion,
} from "@/shared/types";

// -----------------------------------------------------------------------------
// Outcome / status badges
// -----------------------------------------------------------------------------

const OUTCOME_STYLE: Record<string, string> = {
  resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  escalated: "bg-amber-50 text-amber-700 border-amber-200",
  voicemail: "bg-sky-50 text-sky-700 border-sky-200",
  no_answer: "bg-zinc-50 text-zinc-500 border-zinc-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  in_progress: "bg-indigo-50 text-indigo-700 border-indigo-200",
};

const STATUS_STYLE: Record<string, string> = {
  done: "bg-emerald-50 text-emerald-700",
  dialing: "bg-indigo-50 text-indigo-700",
  in_progress: "bg-indigo-50 text-indigo-700",
  voicemail: "bg-sky-50 text-sky-700",
  no_answer: "bg-zinc-50 text-zinc-500",
  failed: "bg-rose-50 text-rose-700",
};

const EVAL_STYLE: Record<string, string> = {
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  failure: "bg-rose-50 text-rose-700 border-rose-200",
  unknown: "bg-zinc-50 text-zinc-500 border-zinc-200",
};

function OutcomePill({ value }: { value: string | null }) {
  const cls = OUTCOME_STYLE[value || ""] ?? "bg-zinc-50 text-zinc-500 border-zinc-200";
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-[1px] text-[10px] font-mono uppercase tracking-wider ${cls}`}
    >
      {value || "—"}
    </span>
  );
}

function StatusPill({ value }: { value: string | null }) {
  const cls = STATUS_STYLE[value || ""] ?? "bg-zinc-50 text-zinc-500";
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-[1px] text-[10px] font-mono uppercase tracking-wider ${cls}`}
    >
      {value || "—"}
    </span>
  );
}

function EvalPill({ value }: { value: string }) {
  const cls = EVAL_STYLE[value] ?? "bg-zinc-50 text-zinc-500 border-zinc-200";
  const Icon =
    value === "success" ? CheckCircle2 : value === "failure" ? XCircle : AlertCircle;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-[1px] text-[10px] font-mono uppercase tracking-wider ${cls}`}
    >
      <Icon size={10} />
      {value}
    </span>
  );
}

function DirectionIcon({ value }: { value: string | null }) {
  if (value === "inbound") return <PhoneIncoming size={12} className="text-ink-400" />;
  return <PhoneOutgoing size={12} className="text-ink-400" />;
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function formatCallLength(secs: number | null): string {
  if (secs == null) return "—";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatTimeInCall(secs: number | null): string {
  if (secs == null) return "+0:00";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `+${m}:${String(s).padStart(2, "0")}`;
}

function truncate(s: string | null, n: number) {
  if (!s) return "—";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function prettyFieldName(id: string): string {
  return id.replace(/_/g, " ");
}

function renderDataValue(val: DataCollectionField["value"]): string {
  if (val === null || val === undefined) return "—";
  if (val === "") return "—";
  if (typeof val === "boolean") return val ? "yes" : "no";
  return String(val);
}

// -----------------------------------------------------------------------------
// Detail panel
// -----------------------------------------------------------------------------

type Tab = "overview" | "transcript" | "evaluation" | "data";

function CallDetailPanel({
  callId,
  onClose,
}: {
  callId: string;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<CallDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    api
      .callDetail(callId)
      .then((d) => {
        if (alive) setDetail(d);
      })
      .catch((e: Error) => {
        if (alive) setErr(e.message);
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [callId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[620px] bg-white h-full overflow-auto border-l border-ink-100 shadow-xl">
        {/* Header */}
        <div className="sticky top-0 bg-white z-10 border-b border-ink-100 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <PhoneCall size={14} className="text-ink-500" />
                <h2 className="text-[14px] font-mono font-bold text-ink-900 truncate">
                  {detail?.call_summary_title || "Call"}
                </h2>
              </div>
              <p className="text-[11px] font-mono text-ink-400 mt-1 truncate">
                {detail?.conversation_id || callId}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-ink-400 hover:text-ink-900 text-[18px] leading-none"
              aria-label="Close"
            >
              ×
            </button>
          </div>

          {detail && (
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <OutcomePill value={detail.outcome} />
              <StatusPill value={detail.call_status} />
              <span className="text-[11px] font-mono text-ink-500">
                {formatCallLength(detail.duration_seconds)}
              </span>
              {detail.cost != null && (
                <span className="text-[11px] font-mono text-ink-500">
                  · cost {detail.cost}
                </span>
              )}
              {detail.has_audio && (
                <span className="text-[10px] font-mono text-emerald-700 uppercase tracking-wider">
                  ● audio
                </span>
              )}
            </div>
          )}

          {/* Tabs */}
          <div className="flex items-center gap-4 mt-4 border-b border-ink-100 -mb-4">
            {(["overview", "transcript", "evaluation", "data"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`pb-2 text-[11px] font-mono uppercase tracking-wider transition-colors ${
                  tab === t
                    ? "text-ink-900 border-b-2 border-red-500"
                    : "text-ink-400 hover:text-ink-700"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 text-[12px] font-mono text-ink-700 space-y-5">
          {loading && <div className="text-ink-400">Loading…</div>}
          {err && <div className="text-rose-600">{err}</div>}
          {detail && !loading && (
            <>
              {tab === "overview" && <OverviewTab d={detail} />}
              {tab === "transcript" && <TranscriptTab turns={detail.transcript} />}
              {tab === "evaluation" && (
                <EvaluationTab items={detail.evaluation_criteria_results} />
              )}
              {tab === "data" && (
                <DataTab items={detail.data_collection_results} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Tab: Overview
// -----------------------------------------------------------------------------

function OverviewTab({ d }: { d: CallDetail }) {
  return (
    <div className="space-y-4">
      {d.transcript_summary && (
        <section>
          <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400 mb-1">
            summary
          </div>
          <p className="text-[13px] font-mono text-ink-900 leading-relaxed">
            {d.transcript_summary}
          </p>
        </section>
      )}

      {d.termination_reason && (
        <section>
          <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400 mb-1">
            termination reason
          </div>
          <p className="text-[12px] font-mono text-ink-700 leading-relaxed">
            {d.termination_reason}
          </p>
        </section>
      )}

      {d.trigger_reasoning && (
        <section>
          <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400 mb-1">
            trigger reasoning (claude)
          </div>
          <p className="text-[12px] font-mono text-ink-700 leading-relaxed">
            {d.trigger_reasoning}
          </p>
        </section>
      )}

      <section className="grid grid-cols-2 gap-3">
        <MetaCell label="agent" value={d.agent_id?.slice(0, 18) + "…"} />
        <MetaCell label="purpose" value={d.purpose} />
        <MetaCell label="direction" value={d.phone_call?.direction ?? d.direction} />
        <MetaCell label="language" value={d.language} />
        <MetaCell label="from" value={d.phone_call?.from_number} />
        <MetaCell label="to" value={d.phone_call?.to_number} />
        <MetaCell label="call sid" value={d.phone_call?.call_sid} />
        <MetaCell label="phone_number_id" value={d.phone_call?.phone_number_id} />
        <MetaCell
          label="started"
          value={d.started_at ? formatRelative(d.started_at) : null}
        />
        <MetaCell
          label="ended"
          value={d.ended_at ? formatRelative(d.ended_at) : null}
        />
      </section>

      {(d.driver || d.load || d.broker) && (
        <section>
          <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400 mb-2">
            linked
          </div>
          <div className="space-y-1.5">
            {d.driver && (
              <div className="text-[12px] font-mono">
                driver: <span className="text-ink-900">{d.driver.name}</span>{" "}
                <span className="text-ink-400">· truck {d.driver.truck_number}</span>
              </div>
            )}
            {d.load != null && typeof d.load === "object" && "load_number" in d.load && (
              <div className="text-[12px] font-mono">
                load:{" "}
                <span className="text-ink-900">
                  {(d.load as { load_number: string }).load_number}
                </span>
              </div>
            )}
            {d.broker && (
              <div className="text-[12px] font-mono">
                broker: <span className="text-ink-900">{d.broker.name}</span>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}

function MetaCell({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400">
        {label}
      </div>
      <div className="text-[12px] font-mono text-ink-900 truncate">{value || "—"}</div>
    </div>
  );
}

// -----------------------------------------------------------------------------
// Tab: Transcript
// -----------------------------------------------------------------------------

function TranscriptTab({
  turns,
}: {
  turns: CallDetail["transcript"];
}) {
  if (!turns || turns.length === 0) {
    return <div className="text-ink-400">No transcript recorded.</div>;
  }
  return (
    <div className="space-y-3">
      {turns.map((t, i) => {
        const isAgent = t.role === "agent";
        return (
          <div
            key={i}
            className={`flex ${isAgent ? "justify-start" : "justify-end"} gap-2`}
          >
            {isAgent && (
              <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400 pt-1 shrink-0 w-10 text-right">
                agent
              </div>
            )}
            <div
              className={`max-w-[80%] rounded px-3 py-2 ${
                isAgent ? "bg-ink-50 border border-ink-100" : "bg-red-50 border border-red-100"
              }`}
            >
              <div className="text-[12px] font-mono text-ink-900 leading-relaxed whitespace-pre-wrap">
                {t.message || <span className="text-ink-400">(no text)</span>}
                {t.interrupted && (
                  <span className="ml-1 text-[10px] uppercase tracking-wider text-amber-700">
                    · interrupted
                  </span>
                )}
              </div>
              {t.tool_calls && t.tool_calls.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {t.tool_calls.map((tc, j) => (
                    <span
                      key={j}
                      className="text-[10px] font-mono px-1.5 py-[1px] bg-white border border-ink-200 rounded text-ink-600"
                    >
                      tool:{" "}
                      {typeof tc === "object" && tc && "name" in tc
                        ? String((tc as { name: unknown }).name)
                        : "—"}
                    </span>
                  ))}
                </div>
              )}
              <div
                className={`mt-1 text-[10px] font-mono ${
                  isAgent ? "text-ink-400" : "text-red-400"
                }`}
              >
                {formatTimeInCall(t.time_in_call_secs)}
              </div>
            </div>
            {!isAgent && (
              <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400 pt-1 shrink-0 w-10">
                human
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Tab: Evaluation criteria
// -----------------------------------------------------------------------------

function EvaluationTab({ items }: { items: EvaluationCriterion[] }) {
  if (!items || items.length === 0) {
    return <div className="text-ink-400">No evaluation criteria recorded.</div>;
  }
  return (
    <div className="space-y-3">
      {items.map((c) => (
        <div key={c.criteria_id} className="space-y-1">
          <div className="flex items-center gap-2">
            <EvalPill value={String(c.result || "unknown")} />
            <span className="text-[12px] font-mono text-ink-900">
              {prettyFieldName(c.criteria_id)}
            </span>
          </div>
          {c.rationale && (
            <div className="text-[11px] font-mono text-ink-500 leading-relaxed pl-1">
              {c.rationale}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Tab: Data collection
// -----------------------------------------------------------------------------

function DataTab({ items }: { items: DataCollectionField[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!items || items.length === 0) {
    return <div className="text-ink-400">No structured data recorded.</div>;
  }
  const PRIMARY = new Set([
    "issues_flagged",
    "issue_type",
    "issue_description",
    "ready_status",
    "hos_remaining_min",
    "location_city",
  ]);
  const primary = items.filter((i) => PRIMARY.has(i.data_collection_id));
  const rest = items.filter((i) => !PRIMARY.has(i.data_collection_id));
  const toShow = expanded ? [...primary, ...rest] : primary;
  return (
    <div className="space-y-2">
      {toShow.map((i) => (
        <div
          key={i.data_collection_id}
          className="flex items-start gap-3 py-1.5 border-b border-ink-100"
        >
          <div className="w-[160px] shrink-0">
            <div className="text-[11px] font-mono text-ink-700">
              {prettyFieldName(i.data_collection_id)}
            </div>
            {i.description && (
              <div className="text-[10px] font-mono text-ink-400 leading-snug">
                {truncate(i.description, 70)}
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div
              className={`text-[12px] font-mono ${
                i.value === null || i.value === "" ? "text-ink-400" : "text-ink-900"
              }`}
            >
              {renderDataValue(i.value)}
            </div>
            {i.rationale && (
              <div className="text-[10px] font-mono text-ink-400 leading-snug mt-0.5">
                {truncate(i.rationale, 180)}
              </div>
            )}
          </div>
        </div>
      ))}
      {!expanded && rest.length > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="text-[11px] font-mono text-red-600 hover:text-red-700 mt-2"
        >
          show all {items.length} fields ↓
        </button>
      )}
    </div>
  );
}

// -----------------------------------------------------------------------------
// Page
// -----------------------------------------------------------------------------

export default function CallsPage() {
  const [rows, setRows] = useState<CallListRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("");
  const [purposeFilter, setPurposeFilter] = useState<string>("");
  const [openId, setOpenId] = useState<string | null>(null);

  const load = (showLoader = false) => {
    if (showLoader) setLoading(true);
    api
      .callsList({ outcome: outcomeFilter || undefined, purpose: purposeFilter || undefined, limit: 100 })
      .then((d) => {
        setRows(d.calls ?? []);
        setErr(null);
      })
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load(true);
    const id = setInterval(() => load(false), 10000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outcomeFilter, purposeFilter]);

  const filtered = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (r.conversation_id || "").toLowerCase().includes(q) ||
        (r.call_summary_title || "").toLowerCase().includes(q) ||
        (r.transcript_summary || "").toLowerCase().includes(q) ||
        (r.termination_reason || "").toLowerCase().includes(q),
    );
  }, [rows, search]);

  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header */}
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <PhoneCall size={16} className="text-ink-700" />
            <h1 className="text-[15px] font-mono font-bold text-ink-900 tracking-tight">
              Calls
            </h1>
            <span className="text-[11px] font-mono text-ink-400">
              {loading ? "…" : `${filtered.length} of ${rows.length}`}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search
                size={12}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-ink-400"
              />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="search conversation, summary, reason"
                className="pl-7 pr-3 py-1.5 text-[12px] font-mono border border-ink-200 rounded bg-white w-[280px] focus:outline-none focus:border-ink-400"
              />
            </div>
            <select
              value={purposeFilter}
              onChange={(e) => setPurposeFilter(e.target.value)}
              className="px-2 py-1.5 text-[12px] font-mono border border-ink-200 rounded bg-white focus:outline-none"
            >
              <option value="">all purposes</option>
              <option value="detention_escalation">detention_escalation</option>
              <option value="driver_checkin">driver_checkin</option>
              <option value="driver_proactive_checkin">driver_proactive_checkin</option>
              <option value="broker_check_call">broker_check_call</option>
              <option value="other">other</option>
            </select>
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="px-2 py-1.5 text-[12px] font-mono border border-ink-200 rounded bg-white focus:outline-none"
            >
              <option value="">all outcomes</option>
              <option value="resolved">resolved</option>
              <option value="escalated">escalated</option>
              <option value="voicemail">voicemail</option>
              <option value="no_answer">no_answer</option>
              <option value="failed">failed</option>
              <option value="in_progress">in_progress</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {err && (
          <div className="m-4 p-3 border border-rose-200 bg-rose-50 text-rose-700 text-[12px] font-mono rounded">
            {err}
          </div>
        )}
        {!err && !loading && filtered.length === 0 && (
          <div className="flex items-center justify-center h-full text-ink-400 text-[12px] font-mono">
            <div className="flex items-center gap-2">
              <Voicemail size={14} />
              no calls yet
            </div>
          </div>
        )}
        {filtered.length > 0 && (
          <table className="w-full">
            <thead className="sticky top-0 bg-white border-b border-ink-100">
              <tr className="text-[10px] font-mono uppercase tracking-wider text-ink-400">
                <th className="px-6 py-2 text-left font-medium">started</th>
                <th className="px-3 py-2 text-left font-medium">dir</th>
                <th className="px-3 py-2 text-left font-medium">purpose</th>
                <th className="px-3 py-2 text-left font-medium">outcome</th>
                <th className="px-3 py-2 text-left font-medium">status</th>
                <th className="px-3 py-2 text-left font-medium">to</th>
                <th className="px-3 py-2 text-right font-medium">len</th>
                <th className="px-3 py-2 text-left font-medium">summary / reason</th>
                <th className="px-6 py-2 text-right font-medium">&nbsp;</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => {
                const rowKey = r.call_id;
                const summaryLine =
                  r.call_summary_title ||
                  r.transcript_summary ||
                  r.termination_reason ||
                  "—";
                return (
                  <tr
                    key={rowKey}
                    onClick={() => setOpenId(r.conversation_id || r.call_id)}
                    className="border-b border-ink-100 hover:bg-ink-50/50 cursor-pointer text-[13px] font-mono text-ink-700"
                  >
                    <td className="px-6 py-2 whitespace-nowrap text-ink-500">
                      {r.started_at ? formatRelative(r.started_at) : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <DirectionIcon value={r.direction} />
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-ink-600">
                      {r.purpose}
                    </td>
                    <td className="px-3 py-2">
                      <OutcomePill value={r.outcome} />
                    </td>
                    <td className="px-3 py-2">
                      <StatusPill value={r.call_status} />
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap text-ink-600">
                      {/* to_number lives in the full row but we have dup in summary only —
                          for the list view use trigger_reason or driver_id as secondary */}
                      {r.trigger_reason || "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-ink-500 tabular-nums">
                      {formatCallLength(r.duration_seconds)}
                    </td>
                    <td className="px-3 py-2 text-ink-500 max-w-[380px] truncate">
                      {truncate(summaryLine, 90)}
                    </td>
                    <td className="px-6 py-2 text-right">
                      <CircleDashed size={12} className="text-ink-300 inline" />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {openId && <CallDetailPanel callId={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}
