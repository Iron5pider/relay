import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
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
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-white font-sans text-ink-800 antialiased">
        {children}
      </body>
    </html>
  );
}
