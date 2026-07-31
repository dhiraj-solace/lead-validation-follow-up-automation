import type { Metadata } from "next";
import AppShell from "./app-shell";
import ThemeRegistry from "./theme-registry";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lead Validation & Follow up Automation",
  description: "Lead validation, scoring, and follow-up automation"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeRegistry>
          <AppShell>{children}</AppShell>
        </ThemeRegistry>
      </body>
    </html>
  );
}
