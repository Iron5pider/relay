import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// Primary font — used across landing + dashboard per product direction.
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Relay — Voice-first dispatch command center",
  description:
    "Relay handles detention, driver check-ins, and broker updates for small fleets — so dispatchers never miss a call that pays.",
  openGraph: {
    title: "Relay — Voice-first dispatch command center",
    description:
      "Relay handles detention, driver check-ins, and broker updates for small fleets — so dispatchers never miss a call that pays.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={cn("font-sans", inter.variable, mono.variable)}>
      <body className="min-h-screen bg-white font-sans text-ink-800 antialiased">
        <TooltipProvider delay={200}>{children}</TooltipProvider>
        <Toaster position="top-right" />
      </body>
    </html>
  );
}
