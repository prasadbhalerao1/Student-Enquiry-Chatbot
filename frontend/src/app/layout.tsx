import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AuthGate } from "@/components/auth-gate";
import { SessionProvider } from "@/components/session-provider";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CSBS Faculty Workspace",
  description:
    "Teacher-facing student information assistant for a third-year CSBS department. Demonstration system using synthetic data.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <SessionProvider>
          <AuthGate>{children}</AuthGate>
        </SessionProvider>
      </body>
    </html>
  );
}
