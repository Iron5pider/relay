"use client";

import Link from "next/link";
import { Settings, Radio, AlertTriangle, Truck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import Logo from "@/components/Logo";
import { useDrivers, useConnectionState } from "@/lib/realtime";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface HeaderProps {
  onOpenDemoControls: () => void;
  onOpenAssignLoads: () => void;
}

export default function DashboardHeader({
  onOpenDemoControls,
  onOpenAssignLoads,
}: HeaderProps) {
  const drivers = useDrivers();
  const conn = useConnectionState();
  const [clock, setClock] = useState<string>("");
  const [unassignedCount, setUnassignedCount] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      api
        .unassignedLoads()
        .then((r) => {
          if (!cancelled) setUnassignedCount(r.count);
        })
        .catch(() => void 0);
    };
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const activeLoads = drivers.filter((d) => d.active_load).length;
  const onDuty = drivers.filter((d) =>
    ["driving", "on_duty"].includes(d.status),
  ).length;
  const exceptions = drivers.filter(
    (d) => d.active_load?.status === "exception",
  ).length;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-ink-100 bg-white px-5">
      <div className="flex items-center gap-4">
        <Link href="/" className="flex items-center gap-2">
          <Logo className="h-6 w-6 text-accent-600" />
          <span className="text-sm font-semibold tracking-tight text-ink-900">
            RELAY
          </span>
        </Link>
        <div className="ml-4 flex items-center gap-2 border-l border-ink-100 pl-4">
          <span className="text-sm font-medium text-ink-700">Mesa Freight</span>
          <Badge variant="outline" className="border-ink-200 text-ink-600">
            {activeLoads} loads
          </Badge>
          <Badge className="bg-status-ok/10 text-[color:var(--status-ok,#15803d)] hover:bg-status-ok/15">
            <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
            {onDuty} drivers on
          </Badge>
          {exceptions > 0 && (
            <Badge className="bg-red-50 text-red-700 hover:bg-red-100">
              <AlertTriangle className="mr-1 h-3 w-3" />
              {exceptions} exception{exceptions === 1 ? "" : "s"}
            </Badge>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onOpenAssignLoads}
          className="inline-flex h-8 items-center gap-1.5 rounded-md border border-ink-200 bg-white px-2.5 text-xs font-medium text-ink-700 transition hover:border-accent-300 hover:text-accent-700"
        >
          <Truck className="h-3.5 w-3.5" />
          Assign loads
          {unassignedCount > 0 && (
            <span className="ml-1 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent-600 px-1 font-mono text-[10px] font-semibold text-white">
              {unassignedCount}
            </span>
          )}
        </button>
        <div className="ml-2 hidden items-center gap-2 border-l border-ink-100 pl-3 text-xs text-ink-400 md:flex">
          <Radio
            className={`h-3.5 w-3.5 ${conn === "connected" ? "text-emerald-500" : conn === "connecting" ? "text-amber-500" : "text-ink-300"}`}
          />
          <span className="font-mono tabular-nums">{clock}</span>
        </div>
        <button
          onClick={onOpenDemoControls}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-500 transition hover:bg-ink-50 hover:text-ink-900"
          aria-label="Demo controls"
        >
          <Settings className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
