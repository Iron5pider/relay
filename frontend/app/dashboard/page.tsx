"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import DashboardHeader from "@/components/dashboard/Header";
import ActivityFeed from "@/components/dashboard/ActivityFeed";
import LoadSidebar from "@/components/dashboard/LoadSidebar";
import DetailPanel from "@/components/dashboard/DetailPanel";
import DemoControls from "@/components/dashboard/DemoControls";
import AssignLoadsModal from "@/components/dashboard/AssignLoadsModal";
import { api } from "@/lib/api";
import { seedFleet } from "@/lib/seed-data";
import {
  connectPusher,
  disconnectPusher,
  getDriversSnapshot,
  hydrateFleet,
} from "@/lib/realtime";
import { closePanel, deselect, selectLoad } from "@/lib/store";

const FleetMap = dynamic(() => import("@/components/dashboard/FleetMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-ink-50 text-sm text-ink-400">
      Loading map…
    </div>
  ),
});

export default function DashboardPage() {
  const [status, setStatus] = useState<"loading" | "ready" | "fallback">("loading");
  const [demoOpen, setDemoOpen] = useState(false);
  const [assignOpen, setAssignOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let retries = 0;

    async function load(initial = false) {
      try {
        const fleet = await api.fleetLive();
        if (cancelled) return;
        hydrateFleet(fleet.drivers);
        retries = 0;
        setStatus("ready");
      } catch {
        retries += 1;
        if (retries >= 3 && initial) {
          hydrateFleet(seedFleet.drivers);
          setStatus("fallback");
        }
      }
    }

    load(true);
    pollTimer = setInterval(() => load(false), 5000);
    connectPusher();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closePanel();
        deselect();
        return;
      }
      // 1–8 quick-select by position
      if (/^[1-8]$/.test(e.key) && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const target = document.activeElement;
        if (
          target &&
          (target.tagName === "INPUT" || target.tagName === "TEXTAREA")
        )
          return;
        const idx = Number(e.key) - 1;
        const sorted = [...getDriversSnapshot()]
          .filter((d) => d.active_load)
          .sort((a, b) => {
            const aEx = a.active_load!.status === "exception" ? 0 : 1;
            const bEx = b.active_load!.status === "exception" ? 0 : 1;
            if (aEx !== bEx) return aEx - bEx;
            return a.active_load!.load_number.localeCompare(b.active_load!.load_number);
          });
        const pick = sorted[idx];
        if (pick?.active_load) selectLoad(pick.active_load.load_id, pick.driver_id);
      }
    };
    window.addEventListener("keydown", onKey);

    return () => {
      cancelled = true;
      if (pollTimer) clearInterval(pollTimer);
      disconnectPusher();
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <>
      <div className="relative z-30">
        <DashboardHeader
          onOpenDemoControls={() => setDemoOpen(true)}
          onOpenAssignLoads={() => setAssignOpen(true)}
        />
      </div>
      <div className="flex min-h-0 flex-1">
        <div className="relative z-20 shrink-0">
          <LoadSidebar />
        </div>
        <div
          className="relative min-w-0 flex-1"
          style={{ isolation: "isolate", zIndex: 0 }}
        >
          <FleetMap />
          {status === "fallback" && (
            <div className="pointer-events-none absolute bottom-3 left-3 z-[450] rounded-md bg-amber-50 px-3 py-1.5 text-[11px] font-medium text-amber-800 shadow-sm">
              Using offline snapshot — backend unreachable
            </div>
          )}
        </div>
        <div className="relative z-20 shrink-0">
          <DetailPanel />
        </div>
      </div>
      <div className="relative z-30">
        <ActivityFeed />
      </div>
      <DemoControls open={demoOpen} onOpenChange={setDemoOpen} />
      <AssignLoadsModal open={assignOpen} onOpenChange={setAssignOpen} />
    </>
  );
}
