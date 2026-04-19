"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranscript } from "@/lib/realtime";
import { cn } from "@/lib/utils";

interface Props {
  callId: string | null;
}

export default function TranscriptFeed({ callId }: Props) {
  const turns = useTranscript(callId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const pausedRef = useRef(false);

  useEffect(() => {
    if (pausedRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  return (
    <div
      ref={containerRef}
      onMouseEnter={() => (pausedRef.current = true)}
      onMouseLeave={() => (pausedRef.current = false)}
      className="flex-1 space-y-2 overflow-y-auto px-4 py-3"
    >
      {turns.length === 0 ? (
        <div className="flex h-full items-center justify-center text-center text-xs text-ink-400">
          Waiting for first turn…
        </div>
      ) : (
        <AnimatePresence initial={false}>
          {turns.map((t) => {
            const isAgent = t.speaker === "agent";
            return (
              <motion.div
                key={t.turn_id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18 }}
                className={cn("flex", isAgent ? "justify-start" : "justify-end")}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-3 py-2 text-[13px] leading-relaxed",
                    isAgent
                      ? "rounded-tl-sm bg-accent-50 text-ink-800"
                      : "rounded-tr-sm bg-ink-100 text-ink-800",
                    !t.is_final && "opacity-60",
                  )}
                >
                  <div
                    className={cn(
                      "mb-0.5 text-[10px] font-semibold uppercase tracking-wider",
                      isAgent ? "text-accent-700" : "text-ink-500",
                    )}
                  >
                    {isAgent ? "Maya (Agent)" : "Receiver"}
                    {!t.is_final && <span className="ml-1 text-ink-400">·partial</span>}
                  </div>
                  <div>{t.text}</div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
