import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "YTSearch — Educational Animation Finder",
  description:
    "Find the best educational animation and simulation videos on YouTube. Powered by multi-signal AI scoring — thumbnail analysis, transcript NLP, and trusted-channel detection.",
  keywords: ["educational videos", "YouTube animations", "science simulations", "visual learning"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
      </head>
      <body>{children}</body>
    </html>
  );
}
