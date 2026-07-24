"use client"

import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Navbar } from "@/components/landing/Navbar"
import { Footer } from "@/components/landing/Footer"
import {
  CheckCircle2,
  Download,
  Shield,
  Zap,
  ExternalLink,
  ArrowRight,
  Monitor,
  Clock,
} from "lucide-react"

const RELEASE_BASE =
  "https://github.com/Lengrowth/outbound/releases/latest/download"
const RELEASES_PAGE =
  "https://github.com/Lengrowth/outbound/releases/latest"
const GITHUB_API_LATEST =
  "https://api.github.com/repos/Lengrowth/outbound/releases/latest"

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
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801" />
    </svg>
  )
}

function AppleLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701" />
    </svg>
  )
}

const steps = [
  {
    number: "01",
    title: "Download & install",
    description: "Download the installer for your platform and run it. Takes about 30 seconds.",
    icon: Download,
  },
  {
    number: "02",
    title: "Log in to your account",
    description: "Open Lengrowth from your system tray or Applications folder and sign in.",
    icon: Shield,
  },
  {
    number: "03",
    title: "Your campaigns run automatically",
    description: "The app runs quietly in the background, sending outreach on your behalf while you focus on other work.",
    icon: Zap,
  },
]

const benefits = [
  {
    title: "Your account stays healthy",
    body: "Activity runs through your real internet connection — not a shared server — so your LinkedIn usage looks completely normal.",
  },
  {
    title: "Full control, always",
    body: "Pause, stop, or adjust campaigns instantly from the system tray. Nothing runs without your say-so.",
  },
  {
    title: "Credentials stay on your machine",
    body: "Your LinkedIn login is stored securely in your system keychain. It never leaves your device.",
  },
  {
    title: "Auto-starts, auto-updates",
    body: "Lengrowth starts on login and updates silently in the background. Nothing to manage.",
  },
]

export default function DownloadPage() {
  const searchParams = useSearchParams()
  const isWelcome = searchParams.get("welcome") === "1"
  const [detectedOS, setDetectedOS] = useState<OS>("other")
  const [latestVersion, setLatestVersion] = useState<string | null>(null)

  useEffect(() => {
    setDetectedOS(detectOS())
    fetch(GITHUB_API_LATEST, { headers: { Accept: "application/vnd.github+json" } })
      .then((r) => r.json())
      .then((data) => {
        // tag_name is like "v1.2.2-abc1234" — extract the semver part
        const tag: string = data?.tag_name ?? ""
        const match = tag.match(/v?(\d+\.\d+\.\d+)/)
        if (match) setLatestVersion(match[1])
      })
      .catch(() => {})
  }, [])

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      {/* Welcome banner */}
      {isWelcome && (
        <div className="border-b border-emerald-500/20 bg-emerald-500/[0.08]">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-2.5">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
            <span className="text-sm font-medium text-emerald-300">
              Email verified —
            </span>
            <span className="text-sm text-emerald-400/70">
              download the desktop app to start your first campaign.
            </span>
          </div>
        </div>
      )}

      {/* Hero */}
      <section className="relative overflow-hidden pt-20 pb-16 sm:pt-28 sm:pb-20">
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-emerald-500/[0.05] rounded-full blur-[120px]" />
        </div>

        <div className="container relative mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/[0.08] px-4 py-1.5 text-sm font-medium text-emerald-400 mb-8">
            <Monitor className="h-3.5 w-3.5" />
            Desktop App
          </div>
          <h1
            className="text-5xl sm:text-6xl font-extrabold text-white tracking-tight mb-6"
            style={{ lineHeight: 1.08 }}
          >
            LinkedIn outreach,{" "}
            <span className="bg-gradient-to-r from-emerald-400 via-emerald-300 to-teal-300 bg-clip-text text-transparent">
              running on your computer.
            </span>
          </h1>
          <p className="text-lg sm:text-xl text-zinc-400 leading-relaxed">
            Install the Lengrowth desktop app and your campaigns run
            automatically in the background — no browser tabs, no manual
            clicking, no interruptions.
          </p>
        </div>
      </section>

      {/* Download cards */}
      <section className="pb-4 sm:pb-8">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Windows */}
            <div
              className={`rounded-2xl border bg-zinc-900/60 p-8 transition-all ${
                detectedOS === "windows"
                  ? "border-emerald-500/50 ring-1 ring-emerald-500/20 shadow-xl shadow-emerald-500/10"
                  : "border-zinc-800"
              }`}
            >
              {detectedOS === "windows" && (
                <div className="inline-flex items-center gap-1.5 mb-4 text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 rounded-full px-3 py-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Your platform detected
                </div>
              )}
              <div className="flex items-center gap-3 mb-8">
                <WindowsLogo className="h-9 w-9 text-sky-400" />
                <div>
                  <h2 className="text-xl font-bold text-white">Windows</h2>
                  <p className="text-xs text-zinc-500">Windows 10 or later, 64-bit</p>
                </div>
              </div>

              <div className="space-y-3">
                <a
                  href={DOWNLOADS.windowsInstaller}
                  download
                  className="flex items-center justify-center gap-2 w-full h-11 rounded-lg px-4 font-semibold text-sm text-white bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-600/20 transition-colors"
                >
                  <Download className="h-4 w-4 shrink-0" />
                  Download Installer (.exe){latestVersion && <span className="opacity-70 font-normal">v{latestVersion}</span>}
                </a>
                <p className="text-center text-xs text-zinc-600">
                  Recommended — start menu shortcut &amp; auto-start included
                </p>
                <a
                  href={DOWNLOADS.windowsStandalone}
                  download
                  className="flex items-center justify-center gap-2 w-full h-10 rounded-lg px-4 font-medium text-sm text-zinc-300 border border-zinc-700 hover:bg-zinc-800 hover:text-white transition-colors"
                >
                  <Download className="h-4 w-4 shrink-0" />
                  Standalone (.exe)
                </a>
                <p className="text-center text-xs text-zinc-600">
                  No installation — run directly from any folder
                </p>
              </div>

              <div className="mt-6 rounded-xl border border-amber-500/20 bg-amber-500/[0.08] p-3 text-xs text-amber-300/80">
                <strong className="text-amber-300">Windows SmartScreen:</strong> Click{" "}
                <strong>"More info" → "Run anyway"</strong> if prompted. Normal for new
                apps not yet in Microsoft&apos;s catalog.
              </div>
            </div>

            {/* macOS */}
            <div
              className={`rounded-2xl border bg-zinc-900/60 p-8 transition-all ${
                detectedOS === "mac"
                  ? "border-emerald-500/50 ring-1 ring-emerald-500/20 shadow-xl shadow-emerald-500/10"
                  : "border-zinc-800"
              }`}
            >
              {detectedOS === "mac" && (
                <div className="inline-flex items-center gap-1.5 mb-4 text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/25 rounded-full px-3 py-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Your platform detected
                </div>
              )}
              <div className="flex items-center gap-3 mb-8">
                <AppleLogo className="h-9 w-9 text-zinc-300" />
                <div>
                  <h2 className="text-xl font-bold text-white">macOS</h2>
                  <p className="text-xs text-zinc-500">macOS 10.15 Catalina or later</p>
                </div>
              </div>

              <div className="space-y-3">
                <a
                  href={DOWNLOADS.macos}
                  download
                  className="flex items-center justify-center gap-2 w-full h-11 rounded-lg px-4 font-semibold text-sm text-white bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-600/20 transition-colors"
                >
                  <Download className="h-4 w-4 shrink-0" />
                  Download for macOS (.dmg){latestVersion && <span className="opacity-70 font-normal">v{latestVersion}</span>}
                </a>
                <p className="text-center text-xs text-zinc-600">
                  Open the DMG and drag Lengrowth to Applications
                </p>
              </div>

              <div className="mt-6 rounded-xl border border-sky-500/20 bg-sky-500/[0.06] p-3 text-xs text-sky-300/80">
                <strong className="text-sky-300">First launch:</strong> Right-click → Open →
                click <strong>Open</strong> again. One-time step for apps outside the App Store.
              </div>

              {/* Fill vertical space on mac card to match Windows */}
              <div className="mt-3 rounded-xl border border-zinc-800/50 bg-transparent p-3">
                <p className="text-xs text-zinc-600 text-center">
                  Apple Silicon and Intel Macs both supported
                </p>
              </div>
            </div>
          </div>

          {/* Releases link */}
          <div className="mt-5 text-center">
            <a
              href={RELEASES_PAGE}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              View all releases on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-20 sm:py-24 border-t border-zinc-800/60">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4">
              Setup
            </p>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              Up and running in{" "}
              <span className="text-emerald-400">under 5 minutes.</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {steps.map((step) => (
              <div key={step.number} className="flex flex-col items-center text-center">
                <div className="w-16 h-16 rounded-2xl border border-zinc-800 bg-zinc-900 flex items-center justify-center mb-5 shadow-lg">
                  <span className="text-2xl font-black text-zinc-700 tabular-nums">{step.number}</span>
                </div>
                <step.icon className="h-5 w-5 text-emerald-500 mb-3" />
                <h3 className="font-bold text-white mb-2">{step.title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why run locally */}
      <section className="py-20 sm:py-24 border-t border-zinc-800/60">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
          <div className="text-center mb-16">
            <p className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4">
              Why desktop
            </p>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
              More control.{" "}
              <span className="text-emerald-400">Better outcomes.</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {benefits.map((b, i) => (
              <div key={i} className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6">
                <CheckCircle2 className="h-5 w-5 text-emerald-500 mb-3" />
                <h3 className="font-bold text-white mb-1.5">{b.title}</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">{b.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 sm:py-28 border-t border-zinc-800/60">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-2xl text-center">
          <div className="inline-flex items-center gap-2 text-sm text-zinc-500 mb-6">
            <Clock className="h-4 w-4" />
            Most users are running their first campaign within 10 minutes of installing.
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 tracking-tight">
            Ready to start?
          </h2>
          <p className="text-lg text-zinc-400 mb-10">
            Download the app, log in, and your outreach starts
            running automatically today.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/signup">
              <Button className="h-12 px-8 font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25 group">
                Create Free Account
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Button>
            </Link>
            <Link href="/login">
              <Button
                variant="outline"
                className="h-12 px-8 border-zinc-700 text-zinc-300 hover:bg-zinc-800 hover:border-zinc-600 hover:text-white"
              >
                Log in to your account
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  )
}
