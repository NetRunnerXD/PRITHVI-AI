import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PRITHVI-AI — WeatherGPT for India",
  description: "Live rain, flood, air, hazards and farm advice — in English, Hindi and Bengali.",
  manifest: "/manifest.webmanifest",
  applicationName: "PRITHVI-AI",
  appleWebApp: { capable: true, title: "PRITHVI-AI", statusBarStyle: "black-translucent" },
  icons: {
    icon: [
      { url: "/logo-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
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
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* Default-theme fonts only; other themes load theirs on demand (lib/themeFonts.ts). */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body className="min-h-screen antialiased pb-[env(safe-area-inset-bottom)]">{children}</body>
    </html>
  );
}
