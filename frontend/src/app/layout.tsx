import "./globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import { DM_Serif_Display, IBM_Plex_Sans, Sora } from "next/font/google";

import { AuthProvider } from "@/components/providers/AuthProvider";
import { ClientOnly } from "@/components/providers/ClientOnly";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { GlobalLoader } from "@/components/ui/global-loader";

export const metadata: Metadata = {
  title: "Silo Forge",
  description: "A control plane for building and operating agent silos.",
};

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-body",
  weight: ["400", "500", "600", "700"],
});

const headingFont = Sora({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-heading",
  weight: ["500", "600", "700"],
});

const displayFont = DM_Serif_Display({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
  weight: ["400"],
});

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${bodyFont.variable} ${headingFont.variable} ${displayFont.variable} min-h-screen bg-app text-strong antialiased`}
      >
        <ClientOnly>
          <AuthProvider>
            <QueryProvider>
              <GlobalLoader />
              {children}
            </QueryProvider>
          </AuthProvider>
        </ClientOnly>
      </body>
    </html>
  );
}
