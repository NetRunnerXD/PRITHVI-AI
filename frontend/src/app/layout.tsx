import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PRITHVI-AI — Earth intelligence for India",
  description: "Live rain, flood, air, hazards and farm advice — in English, Hindi and Bengali.",
  manifest: "/manifest.webmanifest",
  applicationName: "PRITHVI-AI",
  appleWebApp: { capable: true, title: "PRITHVI-AI", statusBarStyle: "black-translucent" },
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
    <html lang="en" data-theme="midnight">
      <head>
        <link rel="manifest" href="/manifest.webmanifest" />
      </head>
      <body className="min-h-screen antialiased pb-[env(safe-area-inset-bottom)]">{children}</body>
    </html>
  );
}
