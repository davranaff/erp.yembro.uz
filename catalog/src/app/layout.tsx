import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

import { SITE_URL } from "@/lib/env";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: "Yembro",
  authors: [{ name: "Yembro" }],
  creator: "Yembro",
  publisher: "Yembro",
  formatDetection: { email: false, address: false, telephone: false },
  icons: {
    icon: [
      { url: "/mark.png", type: "image/png" },
    ],
    apple: [{ url: "/mark.png" }],
    shortcut: ["/mark.png"],
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FBF7F0" },
    { media: "(prefers-color-scheme: dark)", color: "#1A0E10" },
  ],
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
