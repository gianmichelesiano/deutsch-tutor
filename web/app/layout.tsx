import type { Metadata } from "next";
import { Newsreader, Work_Sans } from "next/font/google";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  weight: ["400", "500", "600"],
});

const workSans = Work_Sans({
  subsets: ["latin"],
  variable: "--font-work-sans",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "Deutsch-Tutor",
  description: "Impara il tedesco (A2→B1) con lezioni di 30 minuti basate su roleplay.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="it">
      <body
        className={`${newsreader.variable} ${workSans.variable} bg-page font-sans text-primary antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
