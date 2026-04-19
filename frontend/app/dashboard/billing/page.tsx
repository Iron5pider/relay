"use client";

import { useState } from "react";
import { Receipt, X, FileText, Send } from "lucide-react";
import { formatMoney } from "@/lib/time";

interface MockInvoice {
  id: string;
  load_number: string;
  broker: string;
  broker_contact: string;
  driver: string;
  truck: string;
  amount: number;
  detention_hours: number;
  rate_per_hour: number;
  status: string;
  generated_by: string;
  created_at: string;
  lane: string;
}

const MOCK_INVOICES: MockInvoice[] = [
  { id: "INV-001", load_number: "L-12345", broker: "Acme Logistics", broker_contact: "Jamie Chen", driver: "Carlos Ramirez", truck: "28", amount: 1650, detention_hours: 22, rate_per_hour: 75, status: "sent", generated_by: "maya", created_at: "2026-04-18", lane: "LA → Phoenix" },
  { id: "INV-002", load_number: "L-12343", broker: "TQL", broker_contact: "Marcus Rodriguez", driver: "John Okafor", truck: "14", amount: 2202.50, detention_hours: 29.37, rate_per_hour: 75, status: "sent", generated_by: "maya", created_at: "2026-04-16", lane: "San Diego → Dallas" },
  { id: "INV-003", load_number: "L-12350", broker: "CH Robinson", broker_contact: "Sarah Miller", driver: "Tommy Walsh", truck: "41", amount: 975, detention_hours: 13, rate_per_hour: 75, status: "paid", generated_by: "maya", created_at: "2026-04-17", lane: "Phoenix → Denver" },
  { id: "INV-004", load_number: "L-12339", broker: "XPO Logistics", broker_contact: "David Park", driver: "Sarah Chen", truck: "09", amount: 1125, detention_hours: 15, rate_per_hour: 75, status: "draft", generated_by: "manual", created_at: "2026-04-15", lane: "Vegas → Amarillo" },
  { id: "INV-005", load_number: "L-12336", broker: "Echo Global", broker_contact: "Lisa Thompson", driver: "Raj Singh", truck: "33", amount: 825, detention_hours: 11, rate_per_hour: 75, status: "paid", generated_by: "maya", created_at: "2026-04-14", lane: "Denver → Atlanta" },
];

function InvoicePreview({ inv, onClose }: { inv: MockInvoice; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-[600px] max-h-[90vh] overflow-auto rounded-lg bg-white shadow-xl">
        {/* Header bar */}
        <div className="flex items-center justify-between border-b border-ink-100 px-6 py-3">
          <div className="flex items-center gap-2 text-[13px] font-mono font-semibold text-ink-900">
            <FileText size={16} />
            {inv.id}
          </div>
          <div
            role="button"
            tabIndex={0}
            onClick={onClose}
            onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
            className="p-1 rounded hover:bg-ink-100 cursor-pointer text-ink-400"
          >
            <X size={16} />
          </div>
        </div>

        {/* Invoice body */}
        <div className="px-8 py-6">
          {/* From / To */}
          <div className="flex justify-between mb-8">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400 mb-1">From</p>
              <p className="text-[14px] font-mono font-bold text-ink-900">Radar Freight LLC</p>
              <p className="text-[12px] font-mono text-ink-500">Mesa, AZ 85201</p>
              <p className="text-[12px] font-mono text-ink-500">dispatch@radarfreight.com</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400 mb-1">Bill To</p>
              <p className="text-[14px] font-mono font-bold text-ink-900">{inv.broker}</p>
              <p className="text-[12px] font-mono text-ink-500">Attn: {inv.broker_contact}</p>
            </div>
          </div>

          {/* Invoice meta */}
          <div className="flex gap-8 mb-6 pb-4 border-b border-ink-100">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Invoice #</p>
              <p className="text-[13px] font-mono font-semibold text-ink-900">{inv.id}</p>
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Date</p>
              <p className="text-[13px] font-mono text-ink-700">{inv.created_at}</p>
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Load</p>
              <p className="text-[13px] font-mono font-semibold text-ink-900">{inv.load_number}</p>
            </div>
            <div>
              <p className="text-[10px] font-mono uppercase tracking-widest text-ink-400">Status</p>
              <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider ${
                inv.status === "paid" ? "bg-emerald-50 text-emerald-700" :
                inv.status === "sent" ? "bg-amber-50 text-amber-700" :
                "bg-ink-50 text-ink-500"
              }`}>
                {inv.status}
              </span>
            </div>
          </div>

          {/* Line items */}
          <table className="w-full mb-6">
            <thead>
              <tr className="text-[10px] font-mono uppercase tracking-widest text-ink-400 border-b border-ink-100">
                <th className="pb-2 text-left">Description</th>
                <th className="pb-2 text-right pr-4">Hours</th>
                <th className="pb-2 text-right pr-4">Rate</th>
                <th className="pb-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody className="text-[13px] font-mono">
              <tr className="border-b border-ink-50">
                <td className="py-3 text-ink-900">
                  <p className="font-semibold">Detention Charge</p>
                  <p className="text-[11px] text-ink-400 mt-0.5">
                    {inv.lane} — Driver: {inv.driver} (Truck #{inv.truck})
                  </p>
                  <p className="text-[11px] text-ink-400">
                    Per rate confirmation, detention begins after 2 free hours
                  </p>
                </td>
                <td className="py-3 text-right pr-4 text-ink-700 tabular-nums">{inv.detention_hours.toFixed(1)}</td>
                <td className="py-3 text-right pr-4 text-ink-700 tabular-nums">{formatMoney(inv.rate_per_hour)}/hr</td>
                <td className="py-3 text-right text-ink-900 font-semibold tabular-nums">{formatMoney(inv.amount)}</td>
              </tr>
            </tbody>
          </table>

          {/* Total */}
          <div className="flex justify-end mb-8">
            <div className="w-48 border-t-2 border-ink-900 pt-2">
              <div className="flex justify-between text-[13px] font-mono">
                <span className="font-semibold text-ink-900">Total Due</span>
                <span className="font-bold text-ink-900 text-[16px] tabular-nums">{formatMoney(inv.amount)}</span>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="border-t border-ink-100 pt-4">
            <p className="text-[10px] font-mono text-ink-400 text-center">
              {inv.generated_by === "maya" ? "Generated automatically by Maya AI — Radar Freight Dispatch" : "Generated manually — Radar Freight Dispatch"}
            </p>
            <p className="text-[10px] font-mono text-ink-300 text-center mt-1">
              Payment terms: Net 30 — Questions? dispatch@radarfreight.com
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function BillingPage() {
  const invoices = MOCK_INVOICES;
  const totalRecovered = invoices.filter((i) => i.generated_by === "maya").reduce((s, i) => s + i.amount, 0);
  const [preview, setPreview] = useState<MockInvoice | null>(null);

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
              <th className="pb-2 pr-4">Source</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody className="text-[13px] font-mono">
            {invoices.map((inv) => (
              <tr key={inv.id} className="border-b border-ink-50 hover:bg-ink-50/50">
                <td className="py-2.5 pr-4 text-ink-400 text-[11px]">
                  {inv.id}
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
                <td className="py-2.5 pr-4">
                  {inv.generated_by === "maya" ? (
                    <span className="inline-flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-mono font-medium text-red-700 uppercase tracking-wider">
                      Maya AI
                    </span>
                  ) : (
                    <span className="text-ink-300 text-[11px]">Manual</span>
                  )}
                </td>
                <td className="py-2.5">
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => setPreview(inv)}
                    onKeyDown={(e) => { if (e.key === "Enter") setPreview(inv); }}
                    className="flex items-center gap-1 rounded border border-ink-200 px-2 py-1 text-[10px] font-mono font-medium text-ink-600 hover:bg-ink-50 cursor-pointer"
                  >
                    <FileText size={10} />
                    View
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {preview && <InvoicePreview inv={preview} onClose={() => setPreview(null)} />}
    </div>
  );
}
