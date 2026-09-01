import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ElevateBox Telemetry",
  description: "Real-time AI voice agent command center.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
