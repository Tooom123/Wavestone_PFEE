import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent Data",
  description: "Une question métier, un jeu de données, une réponse analytique : l'agent conduit l'analyse.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
