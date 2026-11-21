import type { Metadata } from "next";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  Cloud,
  Layers,
  Lock,
  Monitor,
  Shield,
  UserPlus,
  Users,
} from "lucide-react";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Team Workspaces — Shared Seats and Roles | Lengrowth",
  description:
    "Invite your team, assign roles, and share one plan and seat pool. Desktop seats use the member's local IP; cloud seats include a managed proxy.",
};

const steps = [
  {
    icon: UserPlus,
    title: "Invite by email",
    body: "Owners and admins send a single-use invite. The member accepts it and joins the workspace without a separate checkout.",
  },
  {
    icon: Layers,
    title: "Assign seats",
    body: "Assign a cloud profile to a member, or assign a desktop profile they can enroll on their own machine.",
  },
  {
    icon: Shield,
    title: "Keep control",
    body: "Roles decide who can manage billing, invite people, assign seats, and see every profile. Members see only what is assigned to them.",
  },
];

const roleRows = [
  ["View billing", "Yes", "Yes", "No"],
  ["Change plan or seats", "Yes", "No", "No"],
  ["Invite or remove members", "Yes", "Yes", "No"],
  ["Assign cloud and desktop seats", "Yes", "Yes", "No"],
  ["See every workspace profile", "Yes", "Yes", "Assigned only"],
  ["Manage proxies", "Yes", "Yes", "No"],
];

export default function TeamsPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      <main>
        <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28">
          <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,rgba(16,185,129,0.16),transparent_60%)]" />
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300">
              <Users className="h-3.5 w-3.5" />
              Team workspaces
            </div>
            <h1 className="mt-6 text-4xl sm:text-6xl font-extrabold tracking-tight text-white">
              One workspace. Your whole team.
            </h1>
            <p className="mt-5 mx-auto max-w-2xl text-lg text-zinc-400">
              Invite members, assign roles, and share one plan and seat pool.
              Desktop seats run on the member&apos;s local IP. Cloud seats include
              a managed proxy and run on our infrastructure.
            </p>
            <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link href="/signup">
                <Button className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
                  Start a workspace
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
              <Link href="/pricing">
                <Button variant="outline" className="border-zinc-700 text-zinc-200 hover:bg-zinc-800">
                  See plans and seats
                </Button>
              </Link>
            </div>
            <p className="mt-4 text-xs text-zinc-500">
              Member logins are included during rollout. A login alone does not
              include a browser account or proxy.
            </p>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-6xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              How it works
            </h2>
            <div className="mt-12 grid gap-5 md:grid-cols-3">
              {steps.map(({ icon: Icon, title, body }, index) => (
                <div key={title} className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                  <div className="flex items-center justify-between">
                    <Icon className="h-5 w-5 text-emerald-400" />
                    <span className="text-xs font-semibold text-zinc-600">0{index + 1}</span>
                  </div>
                  <h3 className="mt-4 font-semibold text-white">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-400">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Two kinds of seat
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-center text-zinc-400">
              Mix desktop and cloud accounts in the same workspace. Each account
              has one execution mode.
            </p>
            <div className="mt-10 grid gap-5 md:grid-cols-2">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-7">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <Monitor className="h-5 w-5 text-emerald-400" />
                  Desktop seat
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                  Runs on the member&apos;s computer with the local IP. No proxy or
                  managed network. Included in team plans.
                </p>
                <ul className="mt-5 space-y-2 text-sm text-zinc-300">
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    Member enrolls their own device
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    Local IP · No proxy
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    Does not consume a cloud seat
                  </li>
                </ul>
              </div>
              <div className="rounded-2xl border border-sky-500/30 bg-sky-900/10 p-7">
                <div className="flex items-center gap-2 font-semibold text-white">
                  <Cloud className="h-5 w-5 text-sky-400" />
                  Cloud seat
                </div>
                <p className="mt-3 text-sm leading-relaxed text-zinc-400">
                  Runs on our infrastructure with a managed residential proxy,
                  region selection, and health monitoring.
                </p>
                <ul className="mt-5 space-y-2 text-sm text-zinc-300">
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                    $299/mo per cloud seat
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                    One LinkedIn or WhatsApp browser account
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                    Cloud Duo: 1 LinkedIn + 1 WhatsApp, still one seat
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                    Managed proxy included
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                    1 email slot (BYO SMTP/IMAP)
                  </li>
                  <li className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-sky-400" />
                    No customer-facing GB meter
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Roles that keep it simple
            </h2>
            <div className="mt-10 overflow-x-auto rounded-xl border border-zinc-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-900/60">
                    <th className="px-5 py-4 text-left font-semibold text-zinc-400">Capability</th>
                    <th className="px-4 py-4 text-center font-bold text-white">Owner</th>
                    <th className="px-4 py-4 text-center font-bold text-white">Admin</th>
                    <th className="px-4 py-4 text-center font-bold text-white">Member</th>
                  </tr>
                </thead>
                <tbody>
                  {roleRows.map(([capability, owner, admin, member], index) => (
                    <tr
                      key={capability}
                      className={index % 2 === 0 ? "bg-transparent" : "bg-zinc-900/20"}
                    >
                      <td className="px-5 py-3.5 text-zinc-300">{capability}</td>
                      <td className="px-4 py-3.5 text-center text-zinc-400">{owner}</td>
                      <td className="px-4 py-3.5 text-center text-zinc-400">{admin}</td>
                      <td className="px-4 py-3.5 text-center text-zinc-400">{member}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-center text-xs text-zinc-500">
              Only the owner manages billing. Admins can invite, remove, and
              assign seats. Members see only their assigned profiles and
              campaigns.
            </p>
          </div>
        </section>

        <section className="border-t border-zinc-800/60 py-20">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl">
            <h2 className="text-center text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Common questions
            </h2>
            <div className="mt-10 space-y-4">
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">Does a member login include a seat?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  No. Member logins are included in the current plan during
                  rollout, but a login alone does not include a browser account,
                  proxy, or email slot. Those remain seat-priced.
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">Can members see proxy credentials?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  No. Managed proxy credentials are encrypted at rest and never
                  shown to members. Owners and admins see proxy health and region
                  only.
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">What counts as a cloud seat?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  One browser account (LinkedIn or WhatsApp) plus one BYO email
                  slot and one managed proxy identity. A Cloud Duo uses one seat
                  for one LinkedIn account and one WhatsApp number of the same
                  identity, whether they share a proxy (Shared IP) or use two
                  proxies (Separate IP). Pausing or unassigning does not release
                  the seat; deleting the profile does.
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">What happens when a member leaves?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  Their assigned profiles pause, their devices are revoked, and
                  their proxy stays assigned to the same identity. The owner or
                  an admin can reassign the seat; a used proxy is never recycled
                  to a different LinkedIn account or WhatsApp number.
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
                <h3 className="font-semibold text-white">Can we mix desktop and cloud?</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-400">
                  Yes. Execution mode is per account, not per workspace. One
                  workspace can run some accounts on desktop and others in the
                  cloud.
                </p>
              </div>
            </div>
            <div className="mt-10 flex items-center justify-center gap-2 text-xs text-zinc-500">
              <Lock className="h-3.5 w-3.5" />
              Workspace data is scoped to active members and audited.
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
