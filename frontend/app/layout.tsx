import type { Metadata } from "next";
import { Geist, Manrope } from "next/font/google";
import { AuthProvider } from "@/components/auth/auth-provider";
import { PwaLifecycle } from "@/components/pwa-lifecycle";
import "./globals.css";

const sans = Geist({ subsets: ["latin"], variable: "--font-sans" });
const display = Manrope({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: { default: "Evolve", template: "%s | Evolve" },
  description: "Evolve artist management and operations platform",
  applicationName: "Evolve",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Evolve" },
  formatDetection: { telephone: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html className={`${sans.variable} ${display.variable}`} lang="en">
      <body><AuthProvider><PwaLifecycle />{children}</AuthProvider></body>
    </html>
  );
}
