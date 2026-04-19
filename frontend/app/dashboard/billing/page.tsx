"use client";

import { useEffect, useState } from "react";
import { Receipt } from "lucide-react";
import { api, InvoiceRow } from "@/lib/api";
import { formatMoney } from "@/lib/time";

const MOCK_INVOICES = [
  { id: "inv-001", load_number: "L-12345", broker: "Acme Logistics", amount: 1650, status: "sent", generated_by: "maya", created_at: "2026-04-18T16:45:00Z" },
  { id: "inv-002", load_number: "L-12343", broker: "TQL", amount: 2202.5, status: "sent", generated_by: "maya", created_at: "2026-04-16T14:20:00Z" },
  { id: "inv-003", load_number: "L-12350", broker: "CH Robinson", amount: 975, status: "paid", generated_by: "maya", created_at: "2026-04-17T11:30:00Z" },
  { id: "inv-004", load_number: "L-12339", broker: "XPO Logistics", amount: 1125, status: "draft", generated_by: "manual", created_at: "2026-04-15T09:00:00Z" },
  { id: "inv-005", load_number: "L-12336", broker: "Echo Global", amount: 825, status: "paid", generated_by: "maya", created_at: "2026-04-14T15:45:00Z" },
];

export default function BillingPage() {
  const invoices = MOCK_INVOICES;
  const totalRecovered = invoices.filter((i) => i.generated_by === "maya").reduce((s, i) => s + i.amount, 0);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <Receipt size={18} className="text-ink-400" />
          <h1 className="text-[15px] font-mono font-semibold text-ink-900 tracking-tight">
            Billing & Invoices
          </h1>
        </div>
      </div>

      <div className="border-b border-ink-100 px-6 py-5 flex gap-8">
        <div>
          <p className="text-[11px] font-mono uppercase tracking-widest text-ink-400 mb-1">
            AI-recovered total
          </p>
          <p className="text-[28px] font-mono font-bold text-ink-900 tabular-nums tracking-tight">
            {formatMoney(totalRecovered)}
          </p>
        </div>
        <div>
          <p className="text-[11px] font-mono uppercase tracking-widest text-ink-400 mb-1">
            Invoices sent
          </p>
          <p className="text-[28px] font-mono font-bold text-ink-900 tabular-nums tracking-tight">
            {invoices.filter((i) => i.status !== "draft").length}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] font-mono uppercase tracking-widest text-ink-400 border-b border-ink-100">
              <th className="pb-2 pr-4">Invoice</th>
              <th className="pb-2 pr-4">Load</th>
              <th className="pb-2 pr-4">Broker</th>
              <th className="pb-2 pr-4 text-right">Amount</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2">Source</th>
            </tr>
          </thead>
          <tbody className="text-[13px] font-mono">
            {invoices.map((inv) => (
              <tr key={inv.id} className="border-b border-ink-50">
                <td className="py-2.5 pr-4 text-ink-400 text-[11px]">
                  {inv.id.toUpperCase()}
                </td>
                <td className="py-2.5 pr-4 font-semibold text-ink-900">
                  {inv.load_number}
                </td>
                <td className="py-2.5 pr-4 text-ink-600">{inv.broker}</td>
                <td className="py-2.5 pr-4 text-right text-ink-900 font-semibold tabular-nums">
                  {formatMoney(inv.amount)}
                </td>
                <td className="py-2.5 pr-4">
                  <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider ${
                    inv.status === "paid"
                      ? "bg-emerald-50 text-emerald-700"
                      : inv.status === "sent"
                      ? "bg-amber-50 text-amber-700"
                      : "bg-ink-50 text-ink-500"
                  }`}>
                    {inv.status}
                  </span>
                </td>
                <td className="py-2.5">
                  {inv.generated_by === "maya" ? (
                    <span className="inline-flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-mono font-medium text-red-700 uppercase tracking-wider">
                      Maya AI
                    </span>
                  ) : (
                    <span className="text-ink-300 text-[11px]">Manual</span>
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
