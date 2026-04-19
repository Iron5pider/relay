"use client";

import NavSidebar from "@/components/dashboard/NavSidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex h-screen w-screen overflow-hidden bg-white">
        <NavSidebar />
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {children}
        </div>
      </div>
    </TooltipProvider>
  );
}
