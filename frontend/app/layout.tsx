import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Evolve v2",
  description: "Evolve artist management and operations platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
