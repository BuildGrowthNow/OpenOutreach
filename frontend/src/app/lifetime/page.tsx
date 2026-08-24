'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Check, ArrowRight, Zap, Lock, Infinity } from 'lucide-react';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';

const END_DATE = new Date('2026-09-30T23:59:59Z');
const TOTAL_SPOTS = 100;
const BASELINE_SPOTS = 23; // pre-launch buyers shown for social proof

const features = [
  'Unlimited campaigns',
  'LinkedIn & WhatsApp outreach channels',
  'AI-written messages per prospect',
  'Automated follow-up sequences',
  'Unified conversation inbox',
  'Analytics & performance dashboard',
  'All future Pro plan updates',
  'Forever - no recurring charges',
];

const faqs = [
  {
    q: 'Is this actually limited to 100 buyers?',
    a: "Yes. Once the 100th purchase goes through, the page closes. The 30-day window is also a hard deadline - whichever comes first ends the offer.",
  },
  {
    q: 'What do I need to supply myself?',
    a: "An LLM API key for AI messaging - OpenAI, Anthropic, or similar. Costs typically a few dollars a month based on usage. The automation itself, all features, and all updates are included in the $149.",
  },
  {
    q: "What if I'm already on a monthly plan?",
    a: "Contact support@lengrowth.com and we'll credit your remaining subscription time toward the $149. You'll switch to lifetime immediately.",
  },
  {
    q: "What about the Cloud tier?",
    a: "The Cloud plan ($299/mo, fully managed with AI included) is separate and not part of this deal. This lifetime offer covers the Pro-equivalent desktop tier.",
  },
  {
    q: "Can I get a refund?",
    a: "Lifetime deals are non-refundable. If you haven't used the product yet, contact us within 14 days for an exception.",
  },
  {
    q: "Will my access change if Pro pricing goes up?",
    a: "No. Your lifetime deal is locked at Pro-equivalent features. Future price increases for new customers don't affect you.",
  },
];

export default function LifetimeDealPage() {
  const [time, setTime] = useState({ days: 0, hours: 0, minutes: 0, seconds: 0 });
  const [expired, setExpired] = useState(false);
  const [spotsTaken, setSpotsTaken] = useState(BASELINE_SPOTS);

  useEffect(() => {
    const tick = () => {
      const dist = END_DATE.getTime() - Date.now();
      if (dist <= 0) {
        setExpired(true);
        return;
      }
      setTime({
        days: Math.floor(dist / 86400000),
        hours: Math.floor((dist % 86400000) / 3600000),
        minutes: Math.floor((dist % 3600000) / 60000),
        seconds: Math.floor((dist % 60000) / 1000),
      });
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    fetch('/api/billing/lifetime-deal-active')
      .then((r) => r.json())
      .then((data) => {
        if (typeof data.buyer_count === 'number') {
          setSpotsTaken(BASELINE_SPOTS + data.buyer_count);
        }
      })
      .catch(() => {});
  }, []);

  const spotsLeft = TOTAL_SPOTS - spotsTaken;
  const progressPct = (spotsTaken / TOTAL_SPOTS) * 100;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      <main>
        {/* Hero */}
        <section className="relative overflow-hidden pt-20 pb-16 sm:pt-28 sm:pb-24">
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[900px] h-[600px] bg-emerald-500/[0.07] rounded-full blur-[120px]" />
          </div>

          <div className="container relative mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/[0.08] px-4 py-1.5 text-sm font-semibold text-emerald-400 mb-8">
              <Zap className="h-3.5 w-3.5" />
              Limited Time - {spotsTaken} of {TOTAL_SPOTS} spots taken
            </div>

            <h1
              className="text-5xl sm:text-6xl lg:text-7xl font-extrabold text-white mb-6 tracking-tight"
              style={{ lineHeight: 1.06 }}
            >
              Pro plan.{' '}
              <span className="bg-gradient-to-r from-emerald-400 via-emerald-300 to-teal-300 bg-clip-text text-transparent">
                Forever.
              </span>
              <br />
              <span className="text-4xl sm:text-5xl lg:text-6xl">$149 once.</span>
            </h1>

            <p className="text-lg sm:text-xl text-zinc-400 mb-10 max-w-xl mx-auto leading-relaxed">
              Lock in unlimited campaigns, AI outreach, and every future Pro
              update - with a single payment. No subscriptions, ever.
            </p>

            {/* Spots progress */}
            <div className="mb-10 max-w-sm mx-auto">
              <div className="flex justify-between text-xs font-medium mb-2">
                <span className="text-zinc-400">{spotsTaken} spots claimed</span>
                <span className="text-emerald-400 font-bold">{spotsLeft} left</span>
              </div>
              <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <p className="text-xs text-zinc-600 mt-2 text-center">
                Capped at 100 buyers - first come, first served
              </p>
            </div>

            {/* Countdown */}
            {!expired ? (
              <div className="mb-10">
                <p className="text-xs text-zinc-500 uppercase tracking-widest mb-4">
                  Offer closes in
                </p>
                <div className="flex justify-center gap-3">
                  {[
                    { label: 'Days', value: time.days },
                    { label: 'Hrs', value: time.hours },
                    { label: 'Min', value: time.minutes },
                    { label: 'Sec', value: time.seconds },
                  ].map((unit) => (
                    <div
                      key={unit.label}
                      className="flex flex-col items-center justify-center w-20 h-20 sm:w-24 sm:h-24 rounded-2xl border border-emerald-500/25 bg-zinc-900 shadow-lg"
                    >
                      <span className="text-2xl sm:text-3xl font-black text-white tabular-nums leading-none">
                        {String(unit.value).padStart(2, '0')}
                      </span>
                      <span className="text-[10px] text-zinc-500 mt-1 uppercase tracking-wider">
                        {unit.label}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="mb-10 rounded-xl border border-red-500/30 bg-red-500/10 p-5">
                <p className="text-red-300 font-semibold">This offer has closed. Thank you to everyone who participated.</p>
              </div>
            )}

            {!expired && (
              <Link href="/signup">
                <Button className="h-14 px-10 text-lg font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-2xl shadow-emerald-600/30 group">
                  Claim My Spot - $149 Once
                  <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
            )}

            <p className="mt-5 text-sm text-zinc-600">
              Non-refundable &middot; Non-transferable &middot; Desktop execution
            </p>
          </div>
        </section>

        {/* What's included */}
        <section className="py-20 sm:py-24 border-t border-zinc-800/60">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-5xl">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
              <div>
                <p className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4">
                  What you get
                </p>
                <h2 className="text-3xl sm:text-4xl font-extrabold text-white mb-4 tracking-tight leading-[1.1]">
                  Everything in Pro,{' '}
                  <span className="text-emerald-400">locked in forever.</span>
                </h2>
                <p className="text-zinc-400 mb-8">
                  No feature gates. No plan expiry. If we ship improvements to
                  Pro in the future, you get them automatically at zero extra cost.
                </p>

                <ul className="space-y-3">
                  {features.map((f, i) => (
                    <li key={i} className="flex items-start gap-3">
                      <Check className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                      <span className="text-zinc-200">{f}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Price card */}
              <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-br from-emerald-600/10 to-zinc-900/80 p-8 sm:p-10">
                <div className="flex items-start justify-between mb-8">
                  <div>
                    <p className="text-xs text-zinc-500 uppercase tracking-widest mb-1">One-time payment</p>
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-6xl font-black text-emerald-400">$149</span>
                    </div>
                    <p className="text-sm text-zinc-400 mt-1">vs $492/year on annual billing</p>
                  </div>
                  <div className="flex flex-col items-center justify-center w-14 h-14 rounded-2xl bg-emerald-500/10 border border-emerald-500/25">
                    <Infinity className="h-6 w-6 text-emerald-400" />
                  </div>
                </div>

                {/* Break-even */}
                <div className="rounded-xl border border-zinc-700 bg-zinc-900/60 p-4 mb-6">
                  <p className="text-sm text-zinc-400 text-center">
                    Breaks even vs annual billing in{' '}
                    <span className="font-bold text-white">4 months.</span>{' '}
                    After that - you&apos;re saving{' '}
                    <span className="text-emerald-400 font-bold">$492 every year</span>.
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-6 text-center">
                  <div className="rounded-lg bg-zinc-900 border border-zinc-800 p-3">
                    <p className="text-xs text-zinc-500 mb-1">Year 1</p>
                    <p className="font-bold text-white text-sm">$149</p>
                  </div>
                  <div className="rounded-lg bg-zinc-900 border border-zinc-800 p-3">
                    <p className="text-xs text-zinc-500 mb-1">Year 3</p>
                    <p className="font-bold text-zinc-500 text-sm line-through">$1,476</p>
                    <p className="font-bold text-emerald-400 text-sm">$149</p>
                  </div>
                  <div className="rounded-lg bg-zinc-900 border border-zinc-800 p-3">
                    <p className="text-xs text-zinc-500 mb-1">Year 10</p>
                    <p className="font-bold text-zinc-500 text-sm line-through">$4,920</p>
                    <p className="font-bold text-emerald-400 text-sm">$149</p>
                  </div>
                </div>

                {!expired && (
                  <Link href="/signup" className="block">
                    <Button className="w-full h-12 font-bold text-base bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25">
                      Claim My Spot
                      <Lock className="ml-2 h-4 w-4" />
                    </Button>
                  </Link>
                )}
                <p className="text-xs text-zinc-600 text-center mt-3">
                  {spotsLeft} of {TOTAL_SPOTS} spots remaining
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Own your stack callout */}
        <section className="py-16 border-t border-zinc-800/60">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-4xl">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-8 sm:p-10">
              <h3 className="text-xl font-bold text-white mb-2">
                You own the stack.
              </h3>
              <p className="text-zinc-400 mb-6">
                The lifetime deal runs on your own machine - automation uses your
                own internet connection. That means your account activity looks
                exactly like you manually browsing LinkedIn and WhatsApp. You also bring your
                own LLM API key, which keeps costs predictable and puts you in
                full control of how AI messaging is used.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {[
                  { label: 'Your machine, your IP', sub: 'Looks like normal browsing on both channels' },
                  { label: 'Your AI key', sub: 'Full control, typically a few $/mo' },
                  { label: 'No ongoing fees', sub: '$149 and done - forever' },
                ].map((item, i) => (
                  <div key={i} className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
                    <p className="font-semibold text-white text-sm mb-1">{item.label}</p>
                    <p className="text-xs text-zinc-500">{item.sub}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="py-20 sm:py-24 border-t border-zinc-800/60">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-2xl">
            <h2 className="text-3xl font-extrabold text-white text-center mb-12 tracking-tight">
              Questions about the deal
            </h2>

            <div className="space-y-5">
              {faqs.map((faq, i) => (
                <div key={i}>
                  <h3 className="text-base font-bold text-white mb-2">{faq.q}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed">{faq.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Terms */}
        <section className="py-10 border-t border-zinc-800/60">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-2xl">
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
              <h4 className="text-sm font-bold text-zinc-300 mb-4">Lifetime Deal Terms</h4>
              <ul className="space-y-1.5 text-xs text-zinc-500">
                <li>Non-transferable and non-refundable (14-day unused exception applies)</li>
                <li>Includes Pro plan features; 1 LinkedIn + 1 WhatsApp account limit</li>
                <li>Desktop execution only - runs on your machine</li>
                <li>Requires your own LLM API key for AI features</li>
                <li>Cloud tier ($299/mo managed) not included</li>
                <li>Capped at 100 buyers, valid through September 30, 2026</li>
                <li>All future Pro plan updates included at no cost</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Final CTA */}
        {!expired && (
          <section className="py-20 sm:py-28 border-t border-zinc-800/60">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-2xl text-center">
              <h2 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 tracking-tight">
                {spotsLeft} spots left.
              </h2>
              <p className="text-lg text-zinc-400 mb-8">
                After that, the only way in is a monthly subscription.
                Lock in Pro forever before the cap is hit.
              </p>
              <Link href="/signup">
                <Button className="h-14 px-10 text-lg font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-2xl shadow-emerald-600/30 group">
                  Claim My Spot - $149 Once
                  <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
              <p className="mt-4 text-sm text-zinc-600">
                One-time payment &middot; No recurring charges &middot; Forever access
              </p>
            </div>
          </section>
        )}
      </main>

      <Footer />
    </div>
  );
}
