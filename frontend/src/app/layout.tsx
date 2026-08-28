import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Rituchakra — weather and farm advice for India",
  description: "Live rain, flood, air, mandi prices and what to do today — in English, Hindi and Bengali.",
  manifest: "/manifest.webmanifest",
  applicationName: "Rituchakra",
  appleWebApp: { capable: true, title: "Rituchakra", statusBarStyle: "default" },
  icons: {
    icon: [{ url: "/icon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/apple-touch-icon.svg" }],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0d6e63",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="sand">
      <head>
        <link rel="manifest" href="/manifest.webmanifest" />
      </head>
      <body className="min-h-screen antialiased pb-[env(safe-area-inset-bottom)]">{children}</body>
    </html>
  );
}
