"use client";

import { useState } from "react";
import { Download, Send, FileText, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { useLatestInvoice } from "@/lib/realtime";
import { API_BASE_URL } from "@/lib/constants";
import { formatMoney } from "@/lib/time";

export default function InvoicePanel() {
  const invoice = useLatestInvoice();
  const [sending, setSending] = useState(false);

  if (!invoice) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-ink-400">
        No invoice generated yet. Complete a detention call to produce one.
      </div>
    );
  }

  async function handleSend() {
    if (!invoice) return;
    setSending(true);
    try {
      await api.sendInvoice(invoice.invoice_id);
      toast.success("Invoice sent to broker");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Send failed";
      toast.error(msg);
    } finally {
      setSending(false);
    }
  }

  const pdfUrl = invoice.pdf_url ?? `${API_BASE_URL}/dispatcher/invoices/${invoice.invoice_id}/pdf`;

  return (
    <div className="flex flex-1 flex-col overflow-y-auto px-4 py-4">
      <div className="rounded-xl border border-ink-100 bg-white p-4 shadow-soft">
        <div className="flex items-center justify-between border-b border-ink-100 pb-3">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-400">
              Detention invoice
            </div>
            <div className="font-mono text-sm text-ink-900">
              #{invoice.invoice_id.slice(0, 8)}
            </div>
          </div>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
              invoice.status === "sent"
                ? "bg-emerald-50 text-emerald-700"
                : invoice.status === "paid"
                  ? "bg-accent-50 text-accent-700"
                  : "bg-ink-100 text-ink-600"
            }`}
          >
            {invoice.status}
          </span>
        </div>

        <div className="mt-3 space-y-1.5 text-xs text-ink-600">
          <Row label="Load" value={invoice.load_id.slice(0, 8)} mono />
          <Row label="Call" value={invoice.call_id?.slice(0, 8) ?? "—"} mono />
          <Row label="Detention" value={`${invoice.detention_minutes} min`} />
          <Row label="Billable" value={`${invoice.billable_minutes} min`} />
          <Row label="Rate" value={`$${invoice.rate_per_hour}/hr`} mono />
        </div>

        <div className="mt-4 border-t border-ink-100 pt-3">
          <div className="flex items-baseline justify-between">
            <span className="text-xs font-medium text-ink-500">Total</span>
            <span className="font-mono text-2xl font-bold text-ink-900 tabular-nums">
              {formatMoney(invoice.amount_usd)}
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-1.5 rounded-md bg-accent-50 px-2.5 py-2 text-[11px] text-accent-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          AI call transcript attached as evidence
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <a
            href={pdfUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-1 rounded-lg border border-accent-200 bg-white px-3 py-2 text-xs font-medium text-accent-700 transition hover:bg-accent-50"
          >
            <Download className="h-3.5 w-3.5" />
            Download PDF
          </a>
          <button
            onClick={handleSend}
            disabled={sending || invoice.status === "sent" || invoice.status === "paid"}
            className="inline-flex items-center justify-center gap-1 rounded-lg bg-accent-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-accent-700 disabled:opacity-50"
          >
            <Send className="h-3.5 w-3.5" />
            {invoice.status === "sent" ? "Already sent" : sending ? "Sending…" : "Send to broker"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-ink-500">{label}</span>
      <span className={mono ? "font-mono tabular-nums" : ""}>{value}</span>
    </div>
  );
}
