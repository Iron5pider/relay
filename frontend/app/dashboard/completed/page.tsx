"use client";

import { useEffect, useState } from "react";
import { CheckSquare } from "lucide-react";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/time";

interface CompletedLoad {
  load_number: string;
  lane: string;
  delivered_at: string;
  base_rate: number;
  detention_amount: number;
  total: number;
  invoice_status: string | null;
}

const MOCK_COMPLETED: CompletedLoad[] = [
  { load_number: "L-12345", lane: "LA → Phoenix", delivered_at: "2026-04-18", base_rate: 3200, detention_amount: 1650, total: 4850, invoice_status: "sent" },
  { load_number: "L-12350", lane: "Phoenix → Denver", delivered_at: "2026-04-17", base_rate: 4100, detention_amount: 975, total: 5075, invoice_status: "paid" },
  { load_number: "L-12348", lane: "Flagstaff → OKC", delivered_at: "2026-04-17", base_rate: 2800, detention_amount: 0, total: 2800, invoice_status: null },
  { load_number: "L-12343", lane: "San Diego → Dallas", delivered_at: "2026-04-16", base_rate: 5200, detention_amount: 2202.5, total: 7402.5, invoice_status: "sent" },
  { load_number: "L-12340", lane: "Vegas → Amarillo", delivered_at: "2026-04-16", base_rate: 3600, detention_amount: 0, total: 3600, invoice_status: null },
  { load_number: "L-12338", lane: "Denver → Atlanta", delivered_at: "2026-04-15", base_rate: 6100, detention_amount: 0, total: 6100, invoice_status: null },
];

export default function CompletedPage() {
  const loads = MOCK_COMPLETED;
  const detentionTotal = loads.reduce((s, l) => s + l.detention_amount, 0);
  const detentionCount = loads.filter((l) => l.detention_amount > 0).length;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <CheckSquare size={18} className="text-ink-400" />
          <h1 className="text-[15px] font-mono font-semibold text-ink-900 tracking-tight">
            Completed Loads
          </h1>
        </div>
      </div>

      {/* Detention recovery hero number */}
      <div className="border-b border-ink-100 px-6 py-5">
        <p className="text-[11px] font-mono uppercase tracking-widest text-ink-400 mb-1">
          Detention recovered this week
        </p>
        <p className="text-[32px] font-mono font-bold text-ink-900 tabular-nums tracking-tight">
          {formatMoney(detentionTotal)}
        </p>
        <p className="text-[12px] font-mono text-ink-400 mt-1">
          {detentionCount} loads with detention charges recovered via Maya
        </p>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 py-4">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] font-mono uppercase tracking-widest text-ink-400 border-b border-ink-100">
              <th className="pb-2 pr-4">Load</th>
              <th className="pb-2 pr-4">Lane</th>
              <th className="pb-2 pr-4">Delivered</th>
              <th className="pb-2 pr-4 text-right">Base</th>
              <th className="pb-2 pr-4 text-right">Detention</th>
              <th className="pb-2 pr-4 text-right">Total</th>
              <th className="pb-2 text-right">Invoice</th>
            </tr>
          </thead>
          <tbody className="text-[13px] font-mono">
            {loads.map((l) => (
              <tr
                key={l.load_number}
                className={`border-b border-ink-50 ${
                  l.detention_amount > 0 ? "bg-red-50/40" : ""
                }`}
              >
                <td className="py-2.5 pr-4 font-semibold text-ink-900">
                  {l.load_number}
                </td>
                <td className="py-2.5 pr-4 text-ink-600">{l.lane}</td>
                <td className="py-2.5 pr-4 text-ink-400">{l.delivered_at}</td>
                <td className="py-2.5 pr-4 text-right text-ink-600 tabular-nums">
                  {formatMoney(l.base_rate)}
                </td>
                <td className={`py-2.5 pr-4 text-right tabular-nums ${
                  l.detention_amount > 0 ? "text-red-600 font-semibold" : "text-ink-300"
                }`}>
                  {l.detention_amount > 0 ? formatMoney(l.detention_amount) : "—"}
                </td>
                <td className="py-2.5 pr-4 text-right text-ink-900 font-semibold tabular-nums">
                  {formatMoney(l.total)}
                </td>
                <td className="py-2.5 text-right">
                  {l.invoice_status ? (
                    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider ${
                      l.invoice_status === "paid"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-amber-50 text-amber-700"
                    }`}>
                      {l.invoice_status}
                    </span>
                  ) : (
                    <span className="text-ink-200">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
