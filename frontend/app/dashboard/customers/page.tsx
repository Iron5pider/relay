"use client";

import { useEffect, useState } from "react";
import { Building2, Phone, Mail } from "lucide-react";
import { api } from "@/lib/api";

interface Broker {
  id: string;
  name: string;
  contact_name: string;
  phone: string;
  email: string;
  preferred_update_channel: string;
  active_loads: number;
}

const MOCK_BROKERS: Broker[] = [
  { id: "br-1", name: "Acme Logistics", contact_name: "Jamie Chen", phone: "+12135550010", email: "jamie@acmelogistics.com", preferred_update_channel: "call", active_loads: 2 },
  { id: "br-2", name: "TQL", contact_name: "Marcus Rodriguez", phone: "+15135550020", email: "marcus@tql.com", preferred_update_channel: "call", active_loads: 1 },
  { id: "br-3", name: "CH Robinson", contact_name: "Sarah Miller", phone: "+16125550030", email: "sarah@chrobinson.com", preferred_update_channel: "email", active_loads: 1 },
  { id: "br-4", name: "XPO Logistics", contact_name: "David Park", phone: "+16035550040", email: "david@xpo.com", preferred_update_channel: "call", active_loads: 0 },
  { id: "br-5", name: "Echo Global", contact_name: "Lisa Thompson", phone: "+13125550050", email: "lisa@echo.com", preferred_update_channel: "sms", active_loads: 1 },
];

export default function CustomersPage() {
  const [brokers] = useState<Broker[]>(MOCK_BROKERS);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-ink-100 px-6 py-4">
        <div className="flex items-center gap-3">
          <Building2 size={18} className="text-ink-400" />
          <h1 className="text-[15px] font-mono font-semibold text-ink-900 tracking-tight">
            Customers & Brokers
          </h1>
          <span className="text-[12px] font-mono text-ink-400">
            {brokers.length} total
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <table className="w-full text-left">
          <thead>
            <tr className="text-[10px] font-mono uppercase tracking-widest text-ink-400 border-b border-ink-100">
              <th className="pb-2 pr-4">Broker</th>
              <th className="pb-2 pr-4">Contact</th>
              <th className="pb-2 pr-4">Phone</th>
              <th className="pb-2 pr-4">Email</th>
              <th className="pb-2 pr-4">Update Pref</th>
              <th className="pb-2 text-right">Active Loads</th>
            </tr>
          </thead>
          <tbody className="text-[13px] font-mono">
            {brokers.map((b) => (
              <tr key={b.id} className="border-b border-ink-50 hover:bg-ink-50/50">
                <td className="py-2.5 pr-4 font-semibold text-ink-900">{b.name}</td>
                <td className="py-2.5 pr-4 text-ink-600">{b.contact_name}</td>
                <td className="py-2.5 pr-4 text-ink-400 text-[12px]">
                  <span className="flex items-center gap-1">
                    <Phone size={10} />
                    {b.phone}
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-ink-400 text-[12px]">
                  <span className="flex items-center gap-1">
                    <Mail size={10} />
                    {b.email}
                  </span>
                </td>
                <td className="py-2.5 pr-4">
                  <span className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-mono font-medium uppercase tracking-wider ${
                    b.preferred_update_channel === "call" ? "bg-blue-50 text-blue-700" :
                    b.preferred_update_channel === "email" ? "bg-purple-50 text-purple-700" :
                    "bg-emerald-50 text-emerald-700"
                  }`}>
                    {b.preferred_update_channel}
                  </span>
                </td>
                <td className="py-2.5 text-right">
                  {b.active_loads > 0 ? (
                    <span className="font-semibold text-ink-900 tabular-nums">{b.active_loads}</span>
                  ) : (
                    <span className="text-ink-300">0</span>
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
