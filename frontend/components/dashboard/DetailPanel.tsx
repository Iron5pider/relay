"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { motion, AnimatePresence } from "framer-motion";
import { X, Truck } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDrivers, useCallMeta, useLatestInvoice } from "@/lib/realtime";
import { useUI, closePanel, setPanelView } from "@/lib/store";
import LoadDetailPanel from "./LoadDetailPanel";
import LiveCallPanel from "./LiveCallPanel";
import OverviewPanel from "./OverviewPanel";
import InvoicePanel from "./InvoicePanel";

const MiniTruckScene = dynamic(() => import("./MiniTruckScene"), {
  ssr: false,
  loading: () => <div className="h-[160px] w-full bg-ink-50" />,
});

const PANEL_WIDTH = 400;

export default function DetailPanel() {
  const ui = useUI();
  const drivers = useDrivers();
  const call = useCallMeta();
  const invoice = useLatestInvoice();

  // When the panel opens/closes, the center map's container width changes.
  // Leaflet doesn't observe the container resize by default, so trigger a
  // window resize to kick invalidateSize internally. Fire on the trailing
  // edge of the animation so tiles fill the new area cleanly.
  useEffect(() => {
    const t = setTimeout(() => window.dispatchEvent(new Event("resize")), 320);
    return () => clearTimeout(t);
  }, [ui.panelOpen]);

  const selected = drivers.find(
    (d) =>
      (ui.selectedLoadId && d.active_load?.load_id === ui.selectedLoadId) ||
      (ui.selectedDriverId && d.driver_id === ui.selectedDriverId),
  );

  const truckColor =
    selected?.active_load?.status === "exception"
      ? "#ef4444"
      : selected?.active_load?.status === "at_pickup" || selected?.active_load?.status === "at_delivery"
        ? "#22c55e"
        : selected?.status === "off_duty"
          ? "#9ca3af"
          : "#3b82f6";

  return (
    <AnimatePresence initial={false}>
      {ui.panelOpen && (
        <motion.aside
          key="detail-panel"
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: PANEL_WIDTH, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="flex shrink-0 flex-col overflow-hidden border-l border-ink-100 bg-white"
        >
          <div className="flex min-h-0 flex-1 flex-col" style={{ width: PANEL_WIDTH }}>
            {/* 3D truck header */}
            <div className="relative shrink-0 border-b border-ink-100">
              <MiniTruckScene
                color={truckColor}
                pulse={selected?.active_load?.status === "exception"}
              />
              <button
                onClick={closePanel}
                className="absolute right-2 top-2 z-10 inline-flex h-7 w-7 items-center justify-center rounded-md bg-white/85 text-ink-500 shadow-sm ring-1 ring-ink-100 backdrop-blur transition hover:bg-white hover:text-ink-900"
                aria-label="Close panel"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Identity strip — sits UNDER the 3D area so it never collides with
                the close button. Serves as the permanent "who is this?" anchor. */}
            {selected && (
              <div className="flex shrink-0 items-center justify-between border-b border-ink-100 bg-white px-4 py-2.5">
                <div className="flex items-center gap-2 min-w-0">
                  <div
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-md",
                      selected.active_load?.status === "exception"
                        ? "bg-red-50 text-red-600"
                        : "bg-accent-50 text-accent-600",
                    )}
                  >
                    <Truck className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-semibold text-ink-900">
                      {selected.name}
                    </div>
                    <div className="font-mono text-[10px] uppercase tracking-wider text-ink-400">
                      Truck #{selected.truck_number} · {selected.preferred_language}
                    </div>
                  </div>
                </div>
                {selected.active_load && (
                  <span className="font-mono text-[11px] text-ink-500">
                    {selected.active_load.load_number}
                  </span>
                )}
              </div>
            )}

            {/* View switcher — only when > 1 view is relevant */}
            {selected && (call.callId || invoice) && (
              <div className="flex shrink-0 items-center gap-1 border-b border-ink-100 bg-ink-50/40 px-3 py-1.5 text-[11px]">
                <ViewTab active={ui.panelView === "load"} onClick={() => setPanelView("load")}>
                  Load
                </ViewTab>
                {call.callId && (
                  <ViewTab active={ui.panelView === "call"} onClick={() => setPanelView("call")}>
                    {call.status === "completed" ? "Call (ended)" : "Live call"}
                  </ViewTab>
                )}
                {invoice && (
                  <ViewTab active={ui.panelView === "invoice"} onClick={() => setPanelView("invoice")}>
                    Invoice
                  </ViewTab>
                )}
              </div>
            )}

            {/* Body */}
            <div className="flex min-h-0 flex-1 flex-col">
              <AnimatePresence mode="wait">
                <motion.div
                  key={`${ui.panelView}-${ui.selectedLoadId}`}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.18 }}
                  className="flex min-h-0 flex-1 flex-col"
                >
                  {ui.panelView === "call" && <LiveCallPanel />}
                  {ui.panelView === "invoice" && <InvoicePanel />}
                  {ui.panelView === "load" && selected && selected.active_load && (
                    <LoadDetailPanel driver={selected} load={selected.active_load} />
                  )}
                  {ui.panelView === "overview" && <OverviewPanel />}
                  {ui.panelView === "load" && !selected && <OverviewPanel />}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function ViewTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-md px-2.5 py-1 font-medium transition",
        active ? "bg-accent-50 text-accent-700" : "text-ink-500 hover:bg-ink-50 hover:text-ink-800",
      )}
    >
      {children}
    </button>
  );
}
