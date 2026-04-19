"use client";

import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Clock, CheckCircle2, Phone } from "lucide-react";
import { useExceptionFeed } from "@/lib/realtime";
import { formatRelative } from "@/lib/time";
import { useUI, selectLoad } from "@/lib/store";

const iconFor = (severity: string) =>
  severity === "critical" ? AlertTriangle : severity === "warn" ? Clock : CheckCircle2;

const colorFor = (severity: string) =>
  severity === "critical"
    ? "text-red-600 bg-red-50 border-red-100"
    : severity === "warn"
      ? "text-amber-700 bg-amber-50 border-amber-100"
      : "text-emerald-700 bg-emerald-50 border-emerald-100";

export default function ActivityFeed() {
  const events = useExceptionFeed();

  return (
    <footer className="flex h-12 shrink-0 items-center gap-3 overflow-x-auto border-t border-ink-100 bg-white px-4">
      <div className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
        <Phone className="h-3 w-3" />
        Activity
      </div>
      <div className="flex items-center gap-2">
        <AnimatePresence initial={false}>
          {events.length === 0 ? (
            <span className="text-xs text-ink-400">No recent events.</span>
          ) : (
            events.slice(0, 12).map((ev) => {
              const Icon = iconFor(ev.severity);
              const cls = colorFor(ev.severity);
              return (
                <motion.button
                  key={ev.id}
                  layout
                  initial={{ opacity: 0, x: 24 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -12 }}
                  transition={{ duration: 0.25 }}
                  onClick={() => {
                    if (ev.load_id && ev.driver_id) {
                      selectLoad(ev.load_id, ev.driver_id);
                    }
                  }}
                  className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-medium ${cls}`}
                >
                  <Icon className="h-3 w-3" />
                  <span>{ev.event_type.replace(/_/g, " ")}</span>
                  <span className="font-mono text-[10px] text-ink-400">
                    {formatRelative(ev.detected_at)}
                  </span>
                </motion.button>
              );
            })
          )}
        </AnimatePresence>
      </div>
    </footer>
  );
}
