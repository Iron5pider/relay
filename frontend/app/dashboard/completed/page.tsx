"use client";

import { useState } from "react";
import {
  CheckSquare,
  ChevronDown,
  ChevronRight,
  FileText,
  Download,
  Check,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/lib/time";

interface CompletedLoad {
  load_number: string;
  lane: string;
  delivered_at: string;
  base_rate: number;
  detention_amount: number;
  total: number;
  invoice_status: string | null;
  // Expansion metadata — driver + broker + signer so the documents look real.
  driver: string;
  truck: string;
  broker: string;
  pod_signed_by: string;
}

const MOCK_COMPLETED: CompletedLoad[] = [
  { load_number: "L-12345", lane: "LA → Phoenix", delivered_at: "2026-04-18", base_rate: 3200, detention_amount: 1650, total: 4850, invoice_status: "sent", driver: "Carlos Ramirez", truck: "28", broker: "Acme Logistics", pod_signed_by: "R. Aguilar" },
  { load_number: "L-12350", lane: "Phoenix → Denver", delivered_at: "2026-04-17", base_rate: 4100, detention_amount: 975, total: 5075, invoice_status: "paid", driver: "Sarah Chen", truck: "09", broker: "Acme Logistics", pod_signed_by: "J. Ruiz" },
  { load_number: "L-12348", lane: "Flagstaff → OKC", delivered_at: "2026-04-17", base_rate: 2800, detention_amount: 0, total: 2800, invoice_status: null, driver: "Raj Singh", truck: "33", broker: "RXO", pod_signed_by: "M. Nakamura" },
  { load_number: "L-12343", lane: "San Diego → Dallas", delivered_at: "2026-04-16", base_rate: 5200, detention_amount: 2202.5, total: 7402.5, invoice_status: "sent", driver: "Miguel Rodriguez", truck: "22", broker: "Coyote Logistics", pod_signed_by: "A. Thompson" },
  { load_number: "L-12340", lane: "Vegas → Amarillo", delivered_at: "2026-04-16", base_rate: 3600, detention_amount: 0, total: 3600, invoice_status: null, driver: "Tommy Walsh", truck: "41", broker: "Arrive Logistics", pod_signed_by: "K. Brown" },
  { load_number: "L-12338", lane: "Denver → Atlanta", delivered_at: "2026-04-15", base_rate: 6100, detention_amount: 0, total: 6100, invoice_status: null, driver: "John Okafor", truck: "14", broker: "TQL", pod_signed_by: "L. Tanaka" },
];

type DocKind = "pod" | "rate_con" | "bol" | "lumper";

interface DocMeta {
  kind: DocKind;
  title: string;
  filename: string;
  pages: number;
  size_kb: number;
  signed: boolean;
}

function docsFor(l: CompletedLoad): DocMeta[] {
  return [
    { kind: "pod", title: "Proof of Delivery", filename: `${l.load_number}-POD.pdf`, pages: 1, size_kb: 142, signed: true },
    { kind: "rate_con", title: "Rate Confirmation", filename: `${l.load_number}-RATECON.pdf`, pages: 2, size_kb: 318, signed: true },
    { kind: "bol", title: "Bill of Lading", filename: `${l.load_number}-BOL.pdf`, pages: 1, size_kb: 198, signed: true },
    ...(l.detention_amount > 0
      ? [{ kind: "lumper" as DocKind, title: "Lumper Receipt", filename: `${l.load_number}-LUMPER.pdf`, pages: 1, size_kb: 64, signed: true }]
      : []),
  ];
}

export default function CompletedPage() {
  const loads = MOCK_COMPLETED;
  const detentionTotal = loads.reduce((s, l) => s + l.detention_amount, 0);
  const detentionCount = loads.filter((l) => l.detention_amount > 0).length;

  const [expanded, setExpanded] = useState<string | null>(null);
  const [activeDoc, setActiveDoc] = useState<Record<string, DocKind>>({});

  const toggle = (loadNum: string) =>
    setExpanded((cur) => (cur === loadNum ? null : loadNum));

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <CheckSquare size={18} className="text-ink-400" />
          <h1 className="text-[15px] font-mono font-semibold tracking-tight text-ink-900">
            Completed Loads
          </h1>
        </div>
      </div>

      <div className="border-b border-ink-100 px-6 py-5">
        <p className="mb-1 text-[11px] font-mono uppercase tracking-widest text-ink-400">
          Detention recovered this week
        </p>
        <p className="text-[32px] font-mono font-bold tabular-nums tracking-tight text-ink-900">
          {formatMoney(detentionTotal)}
        </p>
        <p className="mt-1 text-[12px] font-mono text-ink-400">
          {detentionCount} loads with detention charges recovered via Maya
        </p>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-ink-100 text-[10px] font-mono uppercase tracking-widest text-ink-400">
              <th className="w-6 pb-2"></th>
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
            {loads.map((l) => {
              const isOpen = expanded === l.load_number;
              const docs = docsFor(l);
              const currentDoc = activeDoc[l.load_number] ?? "pod";
              const doc = docs.find((d) => d.kind === currentDoc) ?? docs[0];
              return (
                <>
                  <tr
                    key={l.load_number}
                    onClick={() => toggle(l.load_number)}
                    className={cn(
                      "cursor-pointer border-b border-ink-50 transition-colors hover:bg-ink-50/50",
                      l.detention_amount > 0 && "bg-red-50/40",
                      isOpen && "bg-ink-50",
                    )}
                  >
                    <td className="py-2.5 pl-1 pr-1 text-ink-400">
                      {isOpen ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                    </td>
                    <td className="py-2.5 pr-4 font-semibold text-ink-900">
                      {l.load_number}
                    </td>
                    <td className="py-2.5 pr-4 text-ink-600">{l.lane}</td>
                    <td className="py-2.5 pr-4 text-ink-400">
                      {l.delivered_at}
                    </td>
                    <td className="py-2.5 pr-4 text-right tabular-nums text-ink-600">
                      {formatMoney(l.base_rate)}
                    </td>
                    <td
                      className={cn(
                        "py-2.5 pr-4 text-right tabular-nums",
                        l.detention_amount > 0
                          ? "font-semibold text-red-600"
                          : "text-ink-300",
                      )}
                    >
                      {l.detention_amount > 0
                        ? formatMoney(l.detention_amount)
                        : "—"}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-semibold tabular-nums text-ink-900">
                      {formatMoney(l.total)}
                    </td>
                    <td className="py-2.5 text-right">
                      {l.invoice_status ? (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider",
                            l.invoice_status === "paid"
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-amber-50 text-amber-700",
                          )}
                        >
                          {l.invoice_status}
                        </span>
                      ) : (
                        <span className="text-ink-200">—</span>
                      )}
                    </td>
                  </tr>
                  {isOpen && (
                    <tr className="border-b border-ink-100 bg-ink-50/40">
                      <td colSpan={8} className="px-4 py-4">
                        <div className="grid gap-4 lg:grid-cols-[240px,1fr]">
                          {/* Document list */}
                          <div className="rounded-lg border border-ink-200 bg-white">
                            <div className="border-b border-ink-100 px-3 py-2 text-[10px] font-mono uppercase tracking-widest text-ink-400">
                              Documents ({docs.length})
                            </div>
                            <nav className="p-2">
                              {docs.map((d) => (
                                <button
                                  key={d.kind}
                                  onClick={() =>
                                    setActiveDoc((s) => ({
                                      ...s,
                                      [l.load_number]: d.kind,
                                    }))
                                  }
                                  className={cn(
                                    "mb-1 flex w-full items-start gap-2 rounded-md px-2.5 py-2 text-left transition-colors",
                                    currentDoc === d.kind
                                      ? "bg-accent-50 text-accent-700"
                                      : "text-ink-600 hover:bg-ink-50",
                                  )}
                                >
                                  <FileText
                                    className={cn(
                                      "mt-0.5 h-3.5 w-3.5 shrink-0",
                                      currentDoc === d.kind
                                        ? "text-accent-600"
                                        : "text-ink-400",
                                    )}
                                  />
                                  <div className="min-w-0 flex-1">
                                    <div className="truncate text-[12px] font-medium">
                                      {d.title}
                                    </div>
                                    <div className="text-[10px] font-mono text-ink-400">
                                      {d.pages}p · {d.size_kb} KB
                                    </div>
                                  </div>
                                  {d.signed && (
                                    <Check className="mt-0.5 h-3 w-3 shrink-0 text-emerald-500" />
                                  )}
                                </button>
                              ))}
                            </nav>
                          </div>

                          {/* Viewer */}
                          <div className="rounded-lg border border-ink-200 bg-white">
                            <div className="flex items-center justify-between border-b border-ink-100 px-4 py-2.5">
                              <div className="min-w-0">
                                <div className="truncate text-[12px] font-semibold text-ink-900">
                                  {doc.title}
                                </div>
                                <div className="text-[10px] font-mono text-ink-400">
                                  {doc.filename}
                                </div>
                              </div>
                              <button
                                type="button"
                                className="inline-flex items-center gap-1.5 rounded-md border border-ink-200 bg-white px-2.5 py-1 text-[11px] font-medium text-ink-600 transition-colors hover:border-ink-300 hover:text-ink-900"
                              >
                                <Download className="h-3 w-3" />
                                Download
                              </button>
                            </div>
                            <div className="bg-ink-100/60 p-6">
                              <DocPage doc={doc.kind} load={l} />
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rendered "PDF" document pages — demo HTML styled to look like a printed doc.
// ---------------------------------------------------------------------------

function DocPage({ doc, load }: { doc: DocKind; load: CompletedLoad }) {
  switch (doc) {
    case "pod":
      return <PodDoc load={load} />;
    case "rate_con":
      return <RateConDoc load={load} />;
    case "bol":
      return <BolDoc load={load} />;
    case "lumper":
      return <LumperDoc load={load} />;
  }
}

function DocShell({
  children,
  pageLabel,
}: {
  children: React.ReactNode;
  pageLabel?: string;
}) {
  return (
    <div className="relative mx-auto aspect-[8.5/11] w-full max-w-2xl overflow-hidden rounded-md border border-ink-200 bg-white shadow-lg">
      <div className="absolute inset-0 flex flex-col p-8 font-mono text-[10px] leading-relaxed text-ink-800">
        {children}
      </div>
      {pageLabel && (
        <div className="absolute bottom-3 right-4 text-[9px] font-mono text-ink-300">
          {pageLabel}
        </div>
      )}
    </div>
  );
}

function PodDoc({ load }: { load: CompletedLoad }) {
  const [origin, dest] = load.lane.split(" → ");
  return (
    <DocShell pageLabel="Page 1 of 1">
      <Header title="PROOF OF DELIVERY" subtitle="Mesa Freight LLC" right={load.load_number} />
      <section className="grid grid-cols-2 gap-6">
        <Block label="Shipper / Pickup">
          <Line>{origin}</Line>
          <Line>Appt: {load.delivered_at} 06:00 local</Line>
        </Block>
        <Block label="Consignee / Delivery">
          <Line>{dest}</Line>
          <Line>Appt: {load.delivered_at} 14:00 local</Line>
        </Block>
      </section>
      <section className="mt-6 grid grid-cols-2 gap-6">
        <Block label="Carrier">
          <Line>Mesa Freight LLC</Line>
          <Line>MC-812390 · DOT-2944518</Line>
        </Block>
        <Block label="Driver">
          <Line>{load.driver}</Line>
          <Line>Unit #{load.truck}</Line>
        </Block>
      </section>
      <section className="mt-6">
        <Block label="Commodity">
          <Line>48 pallets · Palletized dry goods · 38,450 lbs</Line>
          <Line>Seal intact · No visible damage</Line>
        </Block>
      </section>
      <section className="mt-auto grid grid-cols-2 gap-8 border-t border-ink-200 pt-6">
        <Block label="Received By">
          <div className="mt-4 border-b-2 border-ink-800 pb-0.5 font-serif text-base italic text-ink-900">
            {load.pod_signed_by}
          </div>
          <div className="mt-1 text-[9px] text-ink-500">Print name · signature</div>
        </Block>
        <Block label="Date / Time">
          <div className="mt-4 border-b-2 border-ink-800 pb-0.5 text-[11px] text-ink-900">
            {load.delivered_at} · local time
          </div>
        </Block>
      </section>
      <div className="absolute bottom-20 right-10 -rotate-12 rounded border-4 border-emerald-600 px-4 py-1 text-base font-bold uppercase tracking-widest text-emerald-600 opacity-80">
        Delivered
      </div>
    </DocShell>
  );
}

function RateConDoc({ load }: { load: CompletedLoad }) {
  const [origin, dest] = load.lane.split(" → ");
  return (
    <DocShell pageLabel="Page 1 of 2">
      <Header title="RATE CONFIRMATION" subtitle={load.broker} right={load.load_number} />
      <section className="grid grid-cols-2 gap-6">
        <Block label="Broker">
          <Line>{load.broker}</Line>
          <Line>MC-447892 · Phoenix, AZ</Line>
        </Block>
        <Block label="Carrier">
          <Line>Mesa Freight LLC</Line>
          <Line>MC-812390 · DOT-2944518</Line>
        </Block>
      </section>
      <section className="mt-6 grid grid-cols-2 gap-6">
        <Block label="Pickup">
          <Line>{origin}</Line>
        </Block>
        <Block label="Delivery">
          <Line>{dest}</Line>
        </Block>
      </section>
      <section className="mt-6">
        <Block label="Equipment">
          <Line>53&apos; dry van · Driver: {load.driver} · Unit #{load.truck}</Line>
        </Block>
      </section>
      <section className="mt-6 rounded-md border border-ink-200 bg-ink-50/60 p-4">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[8px] uppercase tracking-[0.2em] text-ink-400">
              All-in Linehaul
            </div>
            <div className="mt-1 text-2xl font-bold text-ink-900">
              {formatMoney(load.base_rate)}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[8px] uppercase tracking-[0.2em] text-ink-400">
              Detention
            </div>
            <div className="mt-1 text-[11px] text-ink-800">
              $75/hr after 120 min
            </div>
          </div>
        </div>
      </section>
      <section className="mt-6">
        <Block label="Terms">
          <p className="mt-1 leading-5">
            Payment net-30 upon receipt of signed POD + invoice. Carrier to
            provide proactive status updates per broker SOP. Detention billable
            against signed driver-in / driver-out times.
          </p>
        </Block>
      </section>
      <section className="mt-auto grid grid-cols-2 gap-8 border-t border-ink-200 pt-6">
        <Block label="Booked by">
          <Line>Broker Ops Desk</Line>
        </Block>
        <Block label="Carrier Accepts">
          <div className="mt-3 border-b-2 border-ink-800 pb-0.5 font-serif italic">
            Mesa Freight Dispatch
          </div>
        </Block>
      </section>
    </DocShell>
  );
}

function BolDoc({ load }: { load: CompletedLoad }) {
  const [origin, dest] = load.lane.split(" → ");
  return (
    <DocShell pageLabel="Page 1 of 1">
      <Header title="BILL OF LADING" subtitle="Uniform Straight" right={load.load_number} />
      <section className="grid grid-cols-2 gap-6">
        <Block label="Shipper">
          <Line>{origin}</Line>
        </Block>
        <Block label="Consignee">
          <Line>{dest}</Line>
        </Block>
      </section>
      <section className="mt-6">
        <Block label="Pieces / Description" />
        <table className="mt-2 w-full border-collapse text-[9px]">
          <thead>
            <tr className="border-b border-ink-300">
              <th className="py-1.5 text-left text-[8px] font-semibold uppercase tracking-wider text-ink-500">
                Qty
              </th>
              <th className="py-1.5 text-left text-[8px] font-semibold uppercase tracking-wider text-ink-500">
                Type
              </th>
              <th className="py-1.5 text-left text-[8px] font-semibold uppercase tracking-wider text-ink-500">
                Description
              </th>
              <th className="py-1.5 text-right text-[8px] font-semibold uppercase tracking-wider text-ink-500">
                Weight (lbs)
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            <tr>
              <td className="py-1.5">48</td>
              <td className="py-1.5">Pallet</td>
              <td className="py-1.5">Palletized dry goods · NMFC 100540 · Class 70</td>
              <td className="py-1.5 text-right">38,450</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="mt-6">
        <Block label="Driver / Equipment">
          <Line>{load.driver} · Unit #{load.truck}</Line>
          <Line>Trailer seal: 492017 · Temp: ambient</Line>
        </Block>
      </section>
      <section className="mt-auto grid grid-cols-3 gap-6 border-t border-ink-200 pt-6">
        <Block label="Shipper sig">
          <div className="mt-3 border-b border-ink-800 pb-0.5 font-serif italic">
            A. Rodriguez
          </div>
        </Block>
        <Block label="Driver sig">
          <div className="mt-3 border-b border-ink-800 pb-0.5 font-serif italic">
            {load.driver}
          </div>
        </Block>
        <Block label="Consignee sig">
          <div className="mt-3 border-b border-ink-800 pb-0.5 font-serif italic">
            {load.pod_signed_by}
          </div>
        </Block>
      </section>
    </DocShell>
  );
}

function LumperDoc({ load }: { load: CompletedLoad }) {
  const [, dest] = load.lane.split(" → ");
  return (
    <DocShell pageLabel="Page 1 of 1">
      <Header
        title="LUMPER RECEIPT"
        subtitle={dest}
        right={`LMP-${load.load_number.replace("L-", "")}-A`}
      />
      <section className="grid grid-cols-2 gap-6">
        <Block label="Facility">
          <Line>{dest}</Line>
        </Block>
        <Block label="Service">
          <Line>Unload · 48 pallets · Palletized</Line>
        </Block>
      </section>
      <section className="mt-8 rounded-md border border-ink-200 bg-ink-50/60 p-4">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[8px] uppercase tracking-[0.2em] text-ink-400">
              Amount Paid
            </div>
            <div className="mt-1 text-2xl font-bold text-ink-900">$185.00</div>
          </div>
          <div className="text-right">
            <div className="text-[8px] uppercase tracking-[0.2em] text-ink-400">
              Payment
            </div>
            <div className="mt-1 text-[11px]">Comcheck · auth 4471982</div>
          </div>
        </div>
      </section>
      <section className="mt-auto grid grid-cols-2 gap-8 border-t border-ink-200 pt-6">
        <Block label="Lumper crew">
          <Line>Crew 4 · 2 workers · 52 min</Line>
        </Block>
        <Block label="Received by">
          <div className="mt-3 border-b border-ink-800 pb-0.5 font-serif italic">
            {load.pod_signed_by}
          </div>
        </Block>
      </section>
    </DocShell>
  );
}

// --- primitives ------------------------------------------------------------

function Header({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle: string;
  right: string;
}) {
  return (
    <div className="mb-6 flex items-start justify-between border-b border-ink-300 pb-4">
      <div>
        <div className="text-[8px] uppercase tracking-[0.2em] text-ink-400">
          {subtitle}
        </div>
        <div className="mt-1 text-lg font-bold text-ink-900">{title}</div>
      </div>
      <div className="text-right">
        <div className="text-[8px] uppercase tracking-[0.2em] text-ink-400">
          Load
        </div>
        <div className="text-base font-semibold text-ink-900">{right}</div>
      </div>
    </div>
  );
}

function Block({
  label,
  children,
}: {
  label: string;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[8px] font-semibold uppercase tracking-[0.18em] text-ink-400">
        {label}
      </div>
      {children}
    </div>
  );
}

function Line({ children }: { children: React.ReactNode }) {
  return <div className="mt-1 text-[10px] text-ink-800">{children}</div>;
}
