import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Sans } from "next/font/google";
import AuthGate from "@/components/AuthGate";
import Nav from "@/components/Nav";
import "./globals.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display", weight: ["400", "600"] });
const text = IBM_Plex_Sans({ subsets: ["latin"], variable: "--font-text", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Thodar",
  description: "One follow-up thread for every mother and baby.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${text.variable}`}>
      <body>
        <div className="thread-bar" />
        <div className="shell">
          <Nav />
          <AuthGate>{children}</AuthGate>
          <p className="scope-note">
            Assistive, not clinical: Thodar schedules and reminds. It never diagnoses, scores risk or gives advice.
            Demo data is synthetic.
          </p>
        </div>
      </body>
    </html>
  );
}
