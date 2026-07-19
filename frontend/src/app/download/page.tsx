"use client"

import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  CheckCircle2,
  Download,
  Shield,
  Zap,
  ExternalLink,
  Sparkles,
  MonitorSmartphone,
} from "lucide-react"

const RELEASE_BASE =
  "https://github.com/Lengrowth/outbound/releases/latest/download"
const RELEASES_PAGE =
  "https://github.com/Lengrowth/outbound/releases/latest"

const DOWNLOADS = {
  windowsInstaller: `${RELEASE_BASE}/Lengrowth-Windows-Setup.exe`,
  windowsStandalone: `${RELEASE_BASE}/Lengrowth.exe`,
  macos: `${RELEASE_BASE}/Lengrowth-macOS.dmg`,
}

type OS = "windows" | "mac" | "other"

function detectOS(): OS {
  if (typeof window === "undefined") return "other"
  const ua = window.navigator.userAgent.toLowerCase()
  if (ua.includes("win")) return "windows"
  if (ua.includes("mac")) return "mac"
  return "other"
}

function WindowsLogo({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801" />
    </svg>
  )
}

function AppleLogo({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701" />
    </svg>
  )
}

const BENEFITS = [
  "Use your own residential IP — LinkedIn won't flag your account",
  "Save $25–75/month per account in proxy costs",
  "Your credentials never leave your computer",
  "System tray app — runs silently in the background",
  "Auto-starts on login and auto-updates silently",
  "Full control — pause or stop anytime from the tray",
]

const STEPS = [
  {
    number: "1",
    title: "Download & install",
    description:
      "Download the installer for your platform and run it. Takes about 30 seconds.",
    Icon: Download,
  },
  {
    number: "2",
    title: "Log in",
    description:
      "Open Lengrowth from your system tray or Applications folder and log in with your account.",
    Icon: Shield,
  },
  {
    number: "3",
    title: "Automation runs locally",
    description:
      "The daemon runs in the background on your machine using your real residential IP. No proxies needed.",
    Icon: Zap,
  },
]

export default function DownloadPage() {
  const searchParams = useSearchParams()
  const isWelcome = searchParams.get("welcome") === "1"
  const [detectedOS, setDetectedOS] = useState<OS>("other")

  useEffect(() => {
    setDetectedOS(detectOS())
  }, [])

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2 font-bold text-xl">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Sparkles className="h-5 w-5" />
            </div>
            <span>Lengrowth</span>
          </Link>
          <div className="flex items-center gap-2">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Log in
              </Button>
            </Link>
            <Link href="/dashboard">
              <Button size="sm">Dashboard</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Welcome Banner */}
      {isWelcome && (
        <div className="border-b border-green-200 bg-green-50 py-3">
          <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 text-green-800">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600" />
            <span className="font-medium">Email verified!</span>
            <span className="text-green-700">
              Download the desktop app to start running LinkedIn automation.
            </span>
          </div>
        </div>
      )}

      {/* Hero */}
      <section className="py-16 text-center">
        <div className="mx-auto max-w-3xl px-4">
          <div className="mb-4 flex justify-center">
            <Badge variant="secondary" className="flex items-center gap-1.5 px-3 py-1">
              <MonitorSmartphone className="h-3.5 w-3.5" />
              Desktop App
            </Badge>
          </div>
          <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
            Download Lengrowth Desktop
          </h1>
          <p className="text-xl text-muted-foreground">
            Run LinkedIn automation from your own computer. Use your residential
            IP — no proxies, no extra costs.
          </p>
        </div>
      </section>

      {/* Download Cards */}
      <section className="pb-4">
        <div className="mx-auto grid max-w-4xl grid-cols-1 gap-6 px-4 md:grid-cols-2">
          {/* Windows */}
          <Card
            className={
              detectedOS === "windows"
                ? "border-2 border-primary shadow-md"
                : ""
            }
          >
            <CardContent className="p-8">
              {detectedOS === "windows" && (
                <Badge className="mb-4">Detected: your platform</Badge>
              )}
              <div className="mb-6 flex items-center gap-3">
                <WindowsLogo className="h-10 w-10 text-blue-600" />
                <div>
                  <h2 className="text-xl font-bold">Windows</h2>
                  <p className="text-sm text-muted-foreground">
                    Windows 10 or later (64-bit)
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <Button className="w-full" size="lg" asChild>
                  <a href={DOWNLOADS.windowsInstaller} download>
                    <Download className="mr-2 h-4 w-4" />
                    Download Installer (.exe)
                  </a>
                </Button>
                <p className="text-center text-xs text-muted-foreground">
                  Recommended — adds start menu shortcut &amp; auto-start
                </p>

                <Button variant="outline" className="w-full" asChild>
                  <a href={DOWNLOADS.windowsStandalone} download>
                    <Download className="mr-2 h-4 w-4" />
                    Standalone (.exe)
                  </a>
                </Button>
                <p className="text-center text-xs text-muted-foreground">
                  No installation — run directly from any folder
                </p>
              </div>

              <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                <strong>Windows SmartScreen:</strong> If you see "Windows
                protected your PC", click{" "}
                <strong>"More info" → "Run anyway"</strong>. This is normal for
                new apps not yet in Microsoft&apos;s catalog.
              </div>
            </CardContent>
          </Card>

          {/* macOS */}
          <Card
            className={
              detectedOS === "mac" ? "border-2 border-primary shadow-md" : ""
            }
          >
            <CardContent className="p-8">
              {detectedOS === "mac" && (
                <Badge className="mb-4">Detected: your platform</Badge>
              )}
              <div className="mb-6 flex items-center gap-3">
                <AppleLogo className="h-10 w-10 text-gray-800" />
                <div>
                  <h2 className="text-xl font-bold">macOS</h2>
                  <p className="text-sm text-muted-foreground">
                    macOS 10.15 Catalina or later
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <Button className="w-full" size="lg" asChild>
                  <a href={DOWNLOADS.macos} download>
                    <Download className="mr-2 h-4 w-4" />
                    Download for macOS (.dmg)
                  </a>
                </Button>
                <p className="text-center text-xs text-muted-foreground">
                  Open the DMG and drag Lengrowth to Applications
                </p>
              </div>

              <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
                <strong>First launch:</strong> Right-click Lengrowth in
                Applications → <strong>"Open"</strong> → click{" "}
                <strong>"Open"</strong> again. This one-time step is required
                for apps from outside the App Store.
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* All releases link */}
      <div className="pb-12 text-center">
        <a
          href={RELEASES_PAGE}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          View all releases on GitHub
        </a>
      </div>

      {/* How it works */}
      <section className="border-t bg-white py-16">
        <div className="mx-auto max-w-4xl px-4">
          <h2 className="mb-12 text-center text-2xl font-bold">
            How it works
          </h2>
          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            {STEPS.map(({ number, title, description, Icon }) => (
              <div key={number} className="text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-xl font-bold text-primary">
                  {number}
                </div>
                <Icon className="mx-auto mb-3 h-6 w-6 text-primary" />
                <h3 className="mb-2 font-semibold">{title}</h3>
                <p className="text-sm text-muted-foreground">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Benefits */}
      <section className="py-12">
        <div className="mx-auto max-w-3xl px-4">
          <h2 className="mb-8 text-center text-2xl font-bold">
            Why run it locally?
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {BENEFITS.map((benefit) => (
              <div key={benefit} className="flex items-start gap-3">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-green-600" />
                <span className="text-sm">{benefit}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t bg-white py-16 text-center">
        <div className="mx-auto max-w-xl px-4">
          <h2 className="mb-4 text-2xl font-bold">Ready to start?</h2>
          <p className="mb-6 text-muted-foreground">
            Download the app, log in, and your first campaign will be running in
            minutes.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Link href="/login">
              <Button size="lg" variant="outline" className="w-full sm:w-auto">
                Log in to your account
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="lg" className="w-full sm:w-auto">
                Create free account
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-gray-50 py-6 text-center text-sm text-muted-foreground">
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
          <span>© {new Date().getFullYear()} Lengrowth</span>
          <Link href="/privacy" className="hover:underline">
            Privacy
          </Link>
          <Link href="/terms" className="hover:underline">
            Terms
          </Link>
          <Link href="/pricing" className="hover:underline">
            Pricing
          </Link>
        </div>
      </footer>
    </div>
  )
}
