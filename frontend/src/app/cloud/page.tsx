import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Cloud,
  Globe2,
  KeyRound,
  Mail,
  MapPin,
  Monitor,
  Server,
  Shield,
  Users,
} from "lucide-react";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Cloud Outreach — Managed Browser, AI, and Proxy | Lengrowth",
  description:
    "Lengrowth Cloud runs your LinkedIn outreach on managed infrastructure with AI included, a managed residential proxy, and region selection. No desktop app needed.",
};

const features = [
  {
    icon: Server,
    title: "Fully managed execution",
    body: "The browser, scheduling, AI messaging, and follow-ups run on our infrastructure. Nothing to install or keep online.",
  },
  {
    icon: Globe2,
    title: "Managed residential proxy",
    body: "Each cloud account gets a managed proxy on the Massive residential network. Choose a country; state and city are optional.",
  },
  {
    icon: MapPin,
    title: "Region selection",
    body: "195+ countries. Country-level targeting is the default; narrower regions are available when the pool is healthy enough.",
  },
  {
    icon: KeyRound,
    title: "Credentials stay hidden",
    body: "Proxy credentials are encrypted at rest and never shown in the app. You see health and region, not passwords.",
  },
  {
    icon: Shield,
    title: "Account-safety guardrails",
    body: "Cloud profiles never launch without a proxy. A profile without a healthy proxy is paused instead of using the server IP.",
  },
  {
    icon: Cloud,
    title: "AI included",
    body: "No API key or model setup. Cloud includes the AI messaging and follow-up features from the Pro plan.",
  },
];

const included = [
  "1 LinkedIn account",
  "1 managed residential proxy",
  "195+ countries with region selection",
  "AI-written messages and follow-ups",
  "Managed browser and scheduler",
  "Health monitoring and support",
];

export default function CloudPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      <main>
        <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(14,165,233,0.18),transparent_60%)]" />
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-300">
              <Cloud className="h-3.5 w-3.5" />
              Lengrowth Cloud
            </div>
            <h1 className="mt-6 text-4xl sm:text-6xl font-extrabold tracking-tight text-white">
              Your outreach, fully managed.
            </h1>
            <p className="mt-5 mx-auto max-w-2xl text-lg text-zinc-400">
              We run the browser, the AI, and the managed proxy. You choose the
              region and review the results — no desktop app, no server IP, no
              proxy setup.
            </p>
            <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/signup?plan=cloud">
                <Button className="bg-sky-600 hover:bg-sky-500 text-white font-semibold">
                  Start with Cloud
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/pricing">
                <Button variant="outline" className="border-zinc-700 text-zinc-200 hover:bg-zinc-800">
                  Compare plans
                </Button>
              </Link>
            </div>
            <p className="mt-4 text-xs text-zinc-500">
              $299/mo. Cloud requires a paid subscription; there is no Cloud trial.
            </p>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-6xl">
            <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-start">
              <div>
                <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
                  What runs in the cloud
                </h2>
                <p className="mt-3 max-w-2xl text-zinc-400">
                  Cloud is the same outreach engine as the desktop plans, with
                  the machine, browser session, AI, and proxy handled for you.
                </p>
                <div className="mt-10 grid gap-5 sm:grid-cols-2">
                  {features.map(({ icon: Icon, title, body }) => (
                    <div
                      key={title}
                      className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6"
                    >
                      <Icon className="h-5 w-5 text-sky-400" />
                      <h3 className="mt-4 font-semibold text-white">{title}</h3>
                      <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                        {body}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <aside className="rounded-2xl border border-sky-500/30 bg-gradient-to-b from-sky-950/40 to-zinc-900/60 p-7">
                <p className="text-xs font-semibold uppercase tracking-widest text-sky-300">
                  Cloud seat
                </p>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className="text-4xl font-extrabold text-white">$299</span>
                  <span className="text-sm text-zinc-400">/mo</span>
                </div>
                <p className="mt-2 text-sm text-zinc-400">
                  One browser account, one managed proxy identity, and one email
                  slot. Add extra seats whenever you need another account.
                </p>
                <ul className="mt-6 space-y-3">
                  {included.map((item) => (
                    <li key={item} className="flex items-start gap-2.5 text-sm text-zinc-300">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                      {item}
                    </li>
                  ))}
                </ul>
                <p className="mt-6 text-xs leading-relaxed text-zinc-500">
                  Flat per-seat pricing. There is no customer-facing GB meter or
                  overage charge; usage is monitored internally under fair use.
                </p>
                <Link href="/signup?plan=cloud" className="mt-6 block">
                  <Button className="w-full bg-sky-600 hover:bg-sky-500 text-white font-semibold">
                    Get started
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </aside>
            </div>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Cloud Solo or Cloud Duo?
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-zinc-400">
              Both are flat per-seat products. The unit is the client identity,
              not the number of channels.
            </p>
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <Cloud className="h-5 w-5 text-sky-400" />
                  Cloud Solo
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                  One browser account (LinkedIn or WhatsApp), one email slot,
                  and one managed proxy identity. Best for a single channel.
                </p>
                <p className="mt-4 text-sm font-medium text-sky-300">$299/mo</p>
              </div>
              <div className="rounded-2xl border border-sky-500/30 bg-sky-900/10 p-7">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <Users className="h-5 w-5 text-sky-400" />
                  Cloud Duo
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                  One LinkedIn account, one WhatsApp number, and one email slot
                  for the same client identity. The channels share one managed
                  proxy and one seat.
                </p>
                <p className="mt-4 text-sm font-medium text-sky-300">$299/mo</p>
              </div>
            </div>
            <div className="mt-6 flex items-start justify-center gap-2 text-xs text-zinc-500">
              <Mail className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              Email is BYO SMTP/IMAP: no proxy, no managed mailbox cost. Separate
              IPs for the two channels are a support configuration; pricing stays
              flat per seat during rollout.
            </div>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Cloud or desktop?
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-zinc-400">
              Both run the same outreach engine. The difference is where the
              browser runs and who owns the IP.
            </p>
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <Monitor className="h-5 w-5 text-emerald-400" />
                  Desktop
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                  Runs on your computer with your local IP. No proxy. Best when
                  you want full control and already keep a machine online.
                </p>
                <p className="mt-4 text-sm font-medium text-emerald-300">
                  Included in desktop plans
                </p>
              </div>
              <div className="rounded-2xl border border-sky-500/30 bg-sky-900/10 p-7">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <Cloud className="h-5 w-5 text-sky-400" />
                  Cloud
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                  Runs on our infrastructure with a managed residential proxy,
                  region selection, and health monitoring. Best when you want
                  nothing to install or keep online.
                </p>
                <p className="mt-4 text-sm font-medium text-sky-300">
                  $299/mo per cloud seat
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Common questions
            </h2>
            <div className="mt-10 space-y-4">
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">Can I see my proxy credentials?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  No. Managed proxy credentials are encrypted at rest and never
                  shown in the app. You see the region, health, and last check.
                  Replacing a managed proxy is a support action.
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">What happens if the proxy IP changes?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  Cloud accounts use a sticky residential session with a fixed
                  TTL, so the egress IP stays stable during normal work. A new
                  session or a region change can produce a new IP and may trigger
                  a one-time LinkedIn challenge.
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">Can my team share cloud seats?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  Yes. A workspace owner can invite members, assign roles, and
                  assign cloud profiles to members. Members see only their
                  assigned profiles and never see proxy credentials. Member
                  logins are included during rollout; a login alone does not
                  include a browser account or proxy.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
