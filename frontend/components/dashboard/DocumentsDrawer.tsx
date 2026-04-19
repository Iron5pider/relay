"use client";

import { useEffect, useState } from "react";
import { FileText, X, Download, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ActiveLoad, DriverRow } from "@/lib/api";

interface Props {
  driver: DriverRow;
  load: ActiveLoad;
  onClose: () => void;
}

type DocKind = "pod" | "rate_con" | "bol" | "lumper";

interface DocMeta {
  kind: DocKind;
  title: string;
  filename: string;
  pages: number;
  size_kb: number;
  received_at: string | null;
}

export default function DocumentsDrawer({ driver, load, onClose }: Props) {
  // Hardcoded demo document list. In production these come from a
  // /dispatcher/load/{id}/documents endpoint.
  const docs: DocMeta[] = [
    {
      kind: "pod",
      title: "Proof of Delivery",
      filename: `${load.load_number}-POD.pdf`,
      pages: 1,
      size_kb: 142,
      received_at: load.pod?.received_at ?? null,
    },
    {
      kind: "rate_con",
      title: "Rate Confirmation",
      filename: `${load.load_number}-RATECON.pdf`,
      pages: 2,
      size_kb: 318,
      received_at: null,
    },
    {
      kind: "bol",
      title: "Bill of Lading",
      filename: `${load.load_number}-BOL.pdf`,
      pages: 1,
      size_kb: 198,
      received_at: load.pod?.received_at ?? null,
    },
    {
      kind: "lumper",
      title: "Lumper Receipt",
      filename: `${load.load_number}-LUMPER.pdf`,
      pages: 1,
      size_kb: 64,
      received_at: load.pod?.received_at ?? null,
    },
  ];

  const [active, setActive] = useState<DocKind>("pod");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const activeDoc = docs.find((d) => d.kind === active)!;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-900/40 p-4 backdrop-blur-sm">
      <div className="flex h-[90vh] w-full max-w-6xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Sidebar: document list */}
        <aside className="flex w-64 flex-col border-r border-ink-100 bg-ink-50/60">
          <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-ink-400">
                Documents
              </div>
              <div className="text-sm font-semibold text-ink-900">
                {load.load_number}
              </div>
            </div>
          </div>
          <nav className="flex-1 overflow-y-auto p-2">
            {docs.map((d) => (
              <button
                key={d.kind}
                onClick={() => setActive(d.kind)}
                className={cn(
                  "group mb-1 flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left transition-colors",
                  active === d.kind
                    ? "bg-accent-50 text-accent-700"
                    : "text-ink-600 hover:bg-white",
                )}
              >
                <FileText
                  className={cn(
                    "mt-0.5 h-4 w-4 shrink-0",
                    active === d.kind ? "text-accent-600" : "text-ink-400",
                  )}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium truncate">{d.title}</div>
                  <div className="text-[10px] font-mono text-ink-400">
                    {d.pages} page{d.pages === 1 ? "" : "s"} · {d.size_kb} KB
                  </div>
                </div>
                {d.received_at && (
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                )}
              </button>
            ))}
          </nav>
          <div className="border-t border-ink-100 px-4 py-2 text-[10px] font-mono text-ink-400">
            {docs.length} documents
          </div>
        </aside>

        {/* Main: document viewer */}
        <div className="flex flex-1 flex-col">
          <div className="flex items-center justify-between border-b border-ink-100 bg-white px-5 py-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-ink-900">
                {activeDoc.title}
              </div>
              <div className="text-[11px] font-mono text-ink-400">
                {activeDoc.filename}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 rounded-lg border border-ink-200 bg-white px-3 py-1.5 text-xs font-medium text-ink-600 transition-colors hover:border-ink-300 hover:text-ink-900"
                onClick={() => {
                  /* Demo only — would download the file. */
                }}
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </button>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-ink-50 hover:text-ink-900"
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto bg-ink-100/60 p-8">
            <div className="mx-auto max-w-3xl">
              <DocumentPage driver={driver} load={load} doc={activeDoc} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rendered "PDF" pages — HTML demos that look like scanned/printed documents.
// Swap for a real <iframe src={pdfUrl}> or <object> once POD pipeline is live.
// ---------------------------------------------------------------------------

function DocumentPage({
  driver,
  load,
  doc,
}: {
  driver: DriverRow;
  load: ActiveLoad;
  doc: DocMeta;
}) {
  switch (doc.kind) {
    case "pod":
      return <PodPage driver={driver} load={load} />;
    case "rate_con":
      return <RateConPage driver={driver} load={load} />;
    case "bol":
      return <BolPage driver={driver} load={load} />;
    case "lumper":
      return <LumperPage load={load} />;
  }
}

function DocShell({ children, pageLabel }: { children: React.ReactNode; pageLabel?: string }) {
  return (
    <div className="relative mx-auto aspect-[8.5/11] w-full overflow-hidden rounded-md border border-ink-200 bg-white shadow-lg">
      <div className="absolute inset-0 flex flex-col p-10 font-mono text-[11px] leading-relaxed text-ink-800">
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

function PodPage({ driver, load }: { driver: DriverRow; load: ActiveLoad }) {
  const date = load.pod?.received_at
    ? new Date(load.pod.received_at).toLocaleString()
    : "—";
  return (
    <DocShell pageLabel="Page 1 of 1">
      <div className="mb-6 flex items-start justify-between border-b border-ink-300 pb-4">
        <div>
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            Mesa Freight LLC
          </div>
          <div className="mt-1 text-xl font-bold text-ink-900">
            PROOF OF DELIVERY
          </div>
        </div>
        <div className="text-right">
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            Load
          </div>
          <div className="text-lg font-semibold text-ink-900">
            {load.load_number}
          </div>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-6">
        <div>
          <Label>Shipper / Pickup</Label>
          <Line>{load.pickup.name}</Line>
          <Line>
            {load.pickup.lat.toFixed(4)}, {load.pickup.lng.toFixed(4)}
          </Line>
          <Line>
            Appt:{" "}
            {load.pickup.appointment
              ? new Date(load.pickup.appointment).toLocaleString()
              : "—"}
          </Line>
        </div>
        <div>
          <Label>Consignee / Delivery</Label>
          <Line>{load.delivery.name}</Line>
          <Line>
            {load.delivery.lat.toFixed(4)}, {load.delivery.lng.toFixed(4)}
          </Line>
          <Line>
            Appt:{" "}
            {load.delivery.appointment
              ? new Date(load.delivery.appointment).toLocaleString()
              : "—"}
          </Line>
        </div>
      </section>

      <section className="mt-6 grid grid-cols-2 gap-6">
        <div>
          <Label>Carrier</Label>
          <Line>Mesa Freight LLC</Line>
          <Line>MC-812390 · DOT-2944518</Line>
        </div>
        <div>
          <Label>Driver</Label>
          <Line>{driver.name}</Line>
          <Line>Unit #{driver.truck_number}</Line>
        </div>
      </section>

      <section className="mt-6">
        <Label>Commodity</Label>
        <Line>48 pallets · Palletized dry goods · 38,450 lbs</Line>
        <Line>Seal intact · No visible damage</Line>
      </section>

      <section className="mt-auto grid grid-cols-2 gap-10 border-t border-ink-200 pt-6">
        <div>
          <Label>Received By</Label>
          <div className="mt-6 border-b-2 border-ink-800 pb-0.5 font-serif text-lg italic text-ink-900">
            {load.pod?.signed_by ?? "—"}
          </div>
          <div className="mt-1 text-[10px] text-ink-500">Print name · signature</div>
        </div>
        <div>
          <Label>Date / Time</Label>
          <div className="mt-6 border-b-2 border-ink-800 pb-0.5 text-[13px] text-ink-900">
            {date}
          </div>
          <div className="mt-1 text-[10px] text-ink-500">Local time at delivery</div>
        </div>
      </section>

      <div className="absolute bottom-24 right-10 -rotate-12 rounded border-4 border-emerald-600 px-4 py-1 text-lg font-bold uppercase tracking-widest text-emerald-600 opacity-80">
        Delivered
      </div>
    </DocShell>
  );
}

function RateConPage({ driver, load }: { driver: DriverRow; load: ActiveLoad }) {
  const rate = load.rate_linehaul ?? 0;
  return (
    <DocShell pageLabel="Page 1 of 2">
      <div className="mb-6 flex items-start justify-between border-b border-ink-300 pb-4">
        <div>
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            {load.broker?.name ?? "Broker"}
          </div>
          <div className="mt-1 text-xl font-bold text-ink-900">
            RATE CONFIRMATION
          </div>
        </div>
        <div className="text-right">
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            Load
          </div>
          <div className="text-lg font-semibold text-ink-900">
            {load.load_number}
          </div>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-6">
        <div>
          <Label>Broker</Label>
          <Line>{load.broker?.name ?? "—"}</Line>
          <Line>MC-447892 · Phoenix, AZ</Line>
        </div>
        <div>
          <Label>Carrier</Label>
          <Line>Mesa Freight LLC</Line>
          <Line>MC-812390 · DOT-2944518</Line>
        </div>
      </section>

      <section className="mt-6 grid grid-cols-2 gap-6">
        <div>
          <Label>Pickup</Label>
          <Line>{load.pickup.name}</Line>
          <Line>
            {load.pickup.appointment
              ? new Date(load.pickup.appointment).toLocaleString()
              : "—"}
          </Line>
        </div>
        <div>
          <Label>Delivery</Label>
          <Line>{load.delivery.name}</Line>
          <Line>
            {load.delivery.appointment
              ? new Date(load.delivery.appointment).toLocaleString()
              : "—"}
          </Line>
        </div>
      </section>

      <section className="mt-6">
        <Label>Equipment</Label>
        <Line>53&apos; dry van · Team not required · Driver: {driver.name}</Line>
      </section>

      <section className="mt-6 rounded-md border border-ink-200 bg-ink-50/60 p-4">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
              All-in Linehaul
            </div>
            <div className="mt-1 text-3xl font-bold text-ink-900">
              ${rate.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
              Detention
            </div>
            <div className="mt-1 text-sm text-ink-800">
              ${load.detention_rate_per_hour ?? 0}/hr after{" "}
              {load.detention_free_minutes} min
            </div>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <Label>Terms</Label>
        <p className="mt-1 leading-5">
          Payment net-30 upon receipt of signed POD + invoice. Carrier to provide
          proactive status updates per broker SOP. Detention billable against
          signed driver-in / driver-out times.
        </p>
      </section>

      <section className="mt-auto grid grid-cols-2 gap-10 border-t border-ink-200 pt-6">
        <div>
          <Label>Booked by</Label>
          <Line>Broker Ops Desk</Line>
        </div>
        <div>
          <Label>Carrier Accepts</Label>
          <div className="mt-4 border-b-2 border-ink-800 pb-0.5 font-serif italic text-ink-900">
            Mesa Freight Dispatch
          </div>
        </div>
      </section>
    </DocShell>
  );
}

function BolPage({ driver, load }: { driver: DriverRow; load: ActiveLoad }) {
  return (
    <DocShell pageLabel="Page 1 of 1">
      <div className="mb-6 flex items-start justify-between border-b border-ink-300 pb-4">
        <div>
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            Uniform Straight
          </div>
          <div className="mt-1 text-xl font-bold text-ink-900">
            BILL OF LADING
          </div>
        </div>
        <div className="text-right">
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            Reference
          </div>
          <div className="text-lg font-semibold text-ink-900">
            {load.load_number}
          </div>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-6">
        <div>
          <Label>Shipper</Label>
          <Line>{load.pickup.name}</Line>
        </div>
        <div>
          <Label>Consignee</Label>
          <Line>{load.delivery.name}</Line>
        </div>
      </section>

      <section className="mt-6">
        <Label>Pieces / Description</Label>
        <table className="mt-2 w-full border-collapse text-[10px]">
          <thead>
            <tr className="border-b border-ink-300">
              <Th>Qty</Th>
              <Th>Type</Th>
              <Th>Description</Th>
              <Th className="text-right">Weight (lbs)</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            <Tr>
              <Td>48</Td>
              <Td>Pallet</Td>
              <Td>Palletized dry goods · NMFC 100540 · Class 70</Td>
              <Td className="text-right">38,450</Td>
            </Tr>
          </tbody>
        </table>
      </section>

      <section className="mt-6">
        <Label>Driver / Equipment</Label>
        <Line>{driver.name} · Unit #{driver.truck_number}</Line>
        <Line>Trailer seal: 492017 · Temp: ambient</Line>
      </section>

      <section className="mt-auto grid grid-cols-3 gap-6 border-t border-ink-200 pt-6">
        <div>
          <Label>Shipper sig</Label>
          <div className="mt-4 border-b border-ink-800 pb-0.5 font-serif italic">
            A. Rodriguez
          </div>
        </div>
        <div>
          <Label>Driver sig</Label>
          <div className="mt-4 border-b border-ink-800 pb-0.5 font-serif italic">
            {driver.name}
          </div>
        </div>
        <div>
          <Label>Consignee sig</Label>
          <div className="mt-4 border-b border-ink-800 pb-0.5 font-serif italic">
            {load.pod?.signed_by ?? "—"}
          </div>
        </div>
      </section>
    </DocShell>
  );
}

function LumperPage({ load }: { load: ActiveLoad }) {
  return (
    <DocShell pageLabel="Page 1 of 1">
      <div className="mb-6 flex items-start justify-between border-b border-ink-300 pb-4">
        <div>
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            {load.delivery.name}
          </div>
          <div className="mt-1 text-xl font-bold text-ink-900">
            LUMPER RECEIPT
          </div>
        </div>
        <div className="text-right">
          <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
            Receipt #
          </div>
          <div className="text-lg font-semibold text-ink-900">
            LMP-{load.load_number.replace("L-", "")}-A
          </div>
        </div>
      </div>

      <section className="grid grid-cols-2 gap-6">
        <div>
          <Label>Facility</Label>
          <Line>{load.delivery.name}</Line>
        </div>
        <div>
          <Label>Service</Label>
          <Line>Unload · 48 pallets · Palletized</Line>
        </div>
      </section>

      <section className="mt-8 rounded-md border border-ink-200 bg-ink-50/60 p-4">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
              Amount Paid
            </div>
            <div className="mt-1 text-3xl font-bold text-ink-900">$185.00</div>
          </div>
          <div className="text-right">
            <div className="text-[9px] uppercase tracking-[0.2em] text-ink-400">
              Payment
            </div>
            <div className="mt-1 text-sm">Comcheck · auth 4471982</div>
          </div>
        </div>
      </section>

      <section className="mt-auto grid grid-cols-2 gap-10 border-t border-ink-200 pt-6">
        <div>
          <Label>Lumper crew</Label>
          <Line>Crew 4 · 2 workers · 52 min</Line>
        </div>
        <div>
          <Label>Received by</Label>
          <div className="mt-4 border-b border-ink-800 pb-0.5 font-serif italic">
            {load.pod?.signed_by ?? "—"}
          </div>
        </div>
      </section>
    </DocShell>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[8px] font-semibold uppercase tracking-[0.18em] text-ink-400">
      {children}
    </div>
  );
}

function Line({ children }: { children: React.ReactNode }) {
  return <div className="mt-1 text-[11px] text-ink-800">{children}</div>;
}

function Th({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={cn(
        "py-1.5 text-left text-[9px] font-semibold uppercase tracking-wider text-ink-500",
        className,
      )}
    >
      {children}
    </th>
  );
}

function Tr({ children }: { children: React.ReactNode }) {
  return <tr>{children}</tr>;
}

function Td({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <td className={cn("py-1.5 text-[10px] text-ink-800", className)}>{children}</td>;
}
