"use client";

import { useMemo, useState } from "react";
import { Search, AlertCircle, Truck, CheckCircle2 } from "lucide-react";
import LoadCard from "./LoadCard";
import { cn } from "@/lib/utils";
import { useDrivers } from "@/lib/realtime";
import { selectLoad, useUI } from "@/lib/store";

type Filter = "all" | "active" | "exception" | "delivered";

const FILTERS: Array<{ id: Filter; label: string; icon: typeof Truck }> = [
  { id: "all", label: "All", icon: Truck },
  { id: "active", label: "Active", icon: Truck },
  { id: "exception", label: "Exceptions", icon: AlertCircle },
  { id: "delivered", label: "Delivered", icon: CheckCircle2 },
];

export default function LoadSidebar() {
  const drivers = useDrivers();
  const ui = useUI();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");

  const rows = useMemo(
    () =>
      drivers
        .filter((d) => d.active_load)
        .sort((a, b) => {
          const aEx = a.active_load!.status === "exception" ? 0 : 1;
          const bEx = b.active_load!.status === "exception" ? 0 : 1;
          if (aEx !== bEx) return aEx - bEx;
          return a.active_load!.load_number.localeCompare(b.active_load!.load_number);
        }),
    [drivers],
  );

  const counts = useMemo(
    () => ({
      all: rows.length,
      active: rows.filter((d) => d.active_load!.status !== "delivered").length,
      exception: rows.filter((d) => d.active_load!.status === "exception").length,
      delivered: rows.filter((d) => d.active_load!.status === "delivered").length,
    }),
    [rows],
  );

  const filtered = useMemo(() => {
    let list = rows;
    if (filter === "exception") {
      list = list.filter((d) => d.active_load!.status === "exception");
    } else if (filter === "delivered") {
      list = list.filter((d) => d.active_load!.status === "delivered");
    } else if (filter === "active") {
      list = list.filter((d) => d.active_load!.status !== "delivered");
    }
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(
        (d) =>
          d.active_load!.load_number.toLowerCase().includes(q) ||
          d.name.toLowerCase().includes(q) ||
          d.truck_number.toLowerCase().includes(q),
      );
    }
    return list;
  }, [filter, rows, query]);

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-r border-ink-100 bg-[#FAFAFA]">
      {/* Title + count */}
      <div className="border-b border-ink-100 px-4 pb-2 pt-3.5">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[13px] font-semibold uppercase tracking-wider text-ink-500">
            Loads
          </h2>
          <span className="font-mono text-[11px] text-ink-400 tabular-nums">
            {filtered.length} / {rows.length}
          </span>
        </div>

        {/* Search */}
        <div className="relative mt-2.5">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-300" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search load, driver, truck…"
            className="w-full rounded-md border border-ink-200 bg-white py-1.5 pl-8 pr-2.5 text-[12px] placeholder:text-ink-300 focus:border-accent-500 focus:outline-none focus:ring-2 focus:ring-accent-100"
          />
        </div>

        {/* Filter pills */}
        <div className="-mx-0.5 mt-2.5 flex flex-wrap gap-1">
          {FILTERS.map((f) => {
            const active = filter === f.id;
            const count = counts[f.id];
            const isExc = f.id === "exception";
            return (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition",
                  active
                    ? isExc
                      ? "border-red-300 bg-red-50 text-red-700"
                      : "border-accent-500 bg-accent-50 text-accent-700"
                    : "border-ink-200 bg-white text-ink-600 hover:border-ink-300 hover:text-ink-900",
                )}
              >
                <span>{f.label}</span>
                <span
                  className={cn(
                    "min-w-[16px] rounded-full px-1 text-center font-mono tabular-nums",
                    active
                      ? isExc
                        ? "bg-red-200/60 text-red-800"
                        : "bg-accent-200/70 text-accent-800"
                      : "bg-ink-100 text-ink-500",
                  )}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 space-y-2 overflow-y-auto px-3 py-3">
        {filtered.length === 0 ? (
          <div className="mt-10 flex flex-col items-center px-4 text-center">
            <div className="text-[12px] text-ink-400">No loads match.</div>
            {query && (
              <button
                onClick={() => setQuery("")}
                className="mt-1 text-[11px] text-accent-600 hover:underline"
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          filtered.map((d) => (
            <LoadCard
              key={d.active_load!.load_id}
              driver={d}
              load={d.active_load!}
              selected={ui.selectedLoadId === d.active_load!.load_id}
              onClick={() => selectLoad(d.active_load!.load_id, d.driver_id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}
