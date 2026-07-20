import type { Metadata } from "next"
import { Geist, Geist_Mono, Roboto_Slab, Lato } from "next/font/google"
import "./globals.css"
import { AuthProviderV2 } from "@/components/auth/auth-provider-v2"
import { BillingProvider } from "@/lib/contexts/billing-context"
import { ToastProvider } from "@/components/ui/toast"
import { Toaster } from "@/components/ui/toaster"

export const dynamic = "force-dynamic"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

const robotoSlab = Roboto_Slab({
  variable: "--font-roboto-slab",
  subsets: ["latin"],
})

const lato = Lato({
  variable: "--font-lato",
  subsets: ["latin"],
  weight: ["400", "700", "900"],
})

export const metadata: Metadata = {
  title: "Lengrowth Outreach — LinkedIn Growth Automation",
  description: "Scale your LinkedIn presence with AI-powered automation and smart workflows",
  icons: {
    icon: [
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
    shortcut: "/favicon.ico",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${robotoSlab.variable} ${lato.variable} h-full antialiased font-lato`}
    >
      <body className="min-h-full flex flex-col">
        <ToastProvider>
          <AuthProviderV2>
            <BillingProvider>
              {children}
            </BillingProvider>
          </AuthProviderV2>
          <Toaster />
        </ToastProvider>
      </body>
    </html>
  )
}