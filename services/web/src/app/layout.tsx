import type { Metadata } from "next";
import { Montserrat, Source_Code_Pro } from "next/font/google";
import { Suspense } from "react";
import { AuthProvider } from "@/components/auth/AuthProvider";
import "./globals.css";

const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
  display: "swap",
});

const sourceCode = Source_Code_Pro({
  subsets: ["latin"],
  variable: "--font-source-code",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Pitchside",
  description: "Football analyst control room — RAG-powered match intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap"
        />
      </head>
      <body
        className={`${montserrat.variable} ${sourceCode.variable} font-sans`}
      >
        <AuthProvider>
          <Suspense fallback={<div className="h-screen bg-background" />}>
            {children}
          </Suspense>
        </AuthProvider>
      </body>
    </html>
  );
}
