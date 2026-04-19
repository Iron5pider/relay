"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  SplitSquareHorizontal,
  Truck,
  CheckSquare,
  Receipt,
  Users,
  Building2,
  Settings,
  Plus,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const NAV_ITEMS = [
  { href: "/dashboard", icon: Home, label: "Dashboard" },
  { href: "/dashboard/assign", icon: SplitSquareHorizontal, label: "Assign" },
  { href: "/dashboard/active", icon: Truck, label: "Active" },
  { href: "/dashboard/completed", icon: CheckSquare, label: "Completed" },
  { href: "/dashboard/billing", icon: Receipt, label: "Billing" },
  { href: "/dashboard/drivers", icon: Users, label: "Drivers" },
  { href: "/dashboard/customers", icon: Building2, label: "Customers" },
];

const BOTTOM_ITEMS = [
  { href: "/dashboard/settings", icon: Settings, label: "Settings" },
];

export default function NavSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("relay-sidebar-collapsed");
    if (saved !== null) setCollapsed(saved === "true");
  }, []);

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("relay-sidebar-collapsed", String(next));
  };

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname.startsWith(href);
  };

  const renderItem = (item: (typeof NAV_ITEMS)[0]) => {
    const active = isActive(item.href);
    const Icon = item.icon;

    const link = (
      <Link
        href={item.href}
        className={`
          group relative flex items-center gap-3 px-4 py-2.5
          text-[13px] font-medium transition-colors
          ${active
            ? "text-ink-950 before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-5 before:w-[2px] before:bg-red-500"
            : "text-ink-400 hover:text-ink-700"
          }
        `}
        aria-label={item.label}
      >
        <Icon size={18} strokeWidth={active ? 2 : 1.5} className="shrink-0" />
        {!collapsed && (
          <span className="truncate font-mono">{item.label}</span>
        )}
      </Link>
    );

    if (collapsed) {
      return (
        <Tooltip key={item.href}>
          <TooltipTrigger asChild>{link}</TooltipTrigger>
          <TooltipContent
            side="right"
            className="bg-ink-900 text-white font-mono text-[11px] px-2 py-1"
          >
            {item.label}
          </TooltipContent>
        </Tooltip>
      );
    }

    return <div key={item.href}>{link}</div>;
  };

  return (
    <nav
      className={`
        flex h-full flex-col border-r border-ink-100 bg-white
        transition-[width] duration-200 ease-out
        ${collapsed ? "w-[56px]" : "w-[200px]"}
      `}
    >
      {/* Logo / collapse toggle */}
      <button
        onClick={toggle}
        className="flex items-center gap-2 px-4 py-3 text-ink-400 hover:text-ink-700 transition-colors border-b border-ink-100"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <div className="h-5 w-5 rounded bg-ink-900 flex items-center justify-center">
          <span className="text-[9px] font-bold text-white font-mono">R</span>
        </div>
        {!collapsed && (
          <span className="text-[13px] font-mono font-semibold text-ink-900 tracking-tight">
            RELAY
          </span>
        )}
      </button>

      {/* Main nav */}
      <div className="flex-1 py-2 space-y-0.5">
        {NAV_ITEMS.map(renderItem)}
      </div>

      {/* New Load button */}
      <div className="px-2 pb-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              className={`
                flex items-center justify-center gap-2 w-full rounded
                bg-ink-900 text-white py-2 text-[12px] font-mono font-medium
                hover:bg-ink-800 transition-colors
                ${collapsed ? "px-0" : "px-3"}
              `}
              aria-label="New Load"
            >
              <Plus size={14} />
              {!collapsed && <span>New Load</span>}
            </button>
          </TooltipTrigger>
          {collapsed && (
            <TooltipContent
              side="right"
              className="bg-ink-900 text-white font-mono text-[11px] px-2 py-1"
            >
              New Load
            </TooltipContent>
          )}
        </Tooltip>
      </div>

      {/* Bottom items */}
      <div className="border-t border-ink-100 py-2">
        {BOTTOM_ITEMS.map(renderItem)}
      </div>
    </nav>
  );
}
