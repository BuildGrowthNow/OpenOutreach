'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Check, X, ChevronDown, Zap, ArrowRight } from 'lucide-react';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';

interface Plan {
  name: string;
  displayName: string;
  tagline: string;
  monthlyPrice: number;
  annualPrice: number;
  maxLinkedInAccounts: number;
  maxCampaigns: number | null;
  features: string[];
  highlighted?: boolean;
  isCloudTier?: boolean;
}

interface ComparisonFeature {
  name: string;
  starter: boolean;
  pro: boolean;
  business: boolean;
  agency: boolean;
  cloud: boolean;
}

const plans: Plan[] = [
  {
    name: 'starter',
    displayName: 'Starter',
    tagline: 'Solo founders testing LinkedIn outreach',
    monthlyPrice: 19,
    annualPrice: 16,
    maxLinkedInAccounts: 1,
    maxCampaigns: 3,
    features: [
      '1 LinkedIn account',
      '3 active campaigns',
      'AI-written messages',
      'AI follow-up sequences',
      'Unified inbox',
      'Analytics dashboard',
    ],
  },
  {
    name: 'pro',
    displayName: 'Pro',
    tagline: 'Sales reps running consistent outreach',
    monthlyPrice: 49,
    annualPrice: 41,
    maxLinkedInAccounts: 1,
    maxCampaigns: null,
    features: [
      'Everything in Starter',
      'Unlimited campaigns',
    ],
    highlighted: true,
  },
  {
    name: 'business',
    displayName: 'Business',
    tagline: 'Small SDR teams scaling together',
    monthlyPrice: 99,
    annualPrice: 83,
    maxLinkedInAccounts: 3,
    maxCampaigns: null,
    features: [
      'Everything in Pro',
      '3 LinkedIn accounts',
      'Priority support',
    ],
  },
  {
    name: 'agency',
    displayName: 'Agency',
    tagline: 'Agencies running outreach for clients',
    monthlyPrice: 249,
    annualPrice: 208,
    maxLinkedInAccounts: 10,
    maxCampaigns: null,
    features: [
      'Everything in Business',
      '10 LinkedIn accounts',
      'Priority support',
    ],
  },
  {
    name: 'cloud',
    displayName: 'Cloud',
    tagline: 'Fully managed — we handle everything',
    monthlyPrice: 299,
    annualPrice: 0,
    maxLinkedInAccounts: 1,
    maxCampaigns: null,
    features: [
      'Fully managed execution',
      'AI included (no API key needed)',
      'No desktop app needed',
      'All Pro plan features',
      'Campaign performance reviews & tips',
      'Priority support',
    ],
    isCloudTier: true,
  },
];

const comparisonFeatures: ComparisonFeature[] = [
  { name: 'LinkedIn Accounts', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'Active Campaigns', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'AI-Written Messages', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'Automated Follow-ups', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'Unified Inbox', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'Analytics Dashboard', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'AI Follow-up Sequences', starter: true, pro: true, business: true, agency: true, cloud: true },
  { name: 'Priority Support', starter: false, pro: false, business: true, agency: true, cloud: true },
  { name: 'Managed Cloud Execution', starter: false, pro: false, business: false, agency: false, cloud: true },
  { name: 'AI Included (no API key needed)', starter: false, pro: false, business: false, agency: false, cloud: true },
  { name: 'Campaign Performance Reviews', starter: false, pro: false, business: false, agency: false, cloud: true },
];

const faqs = [
  {
    question: "What's included in the free trial?",
    answer:
      "Full Starter plan access for 7 days. No credit card required to start.",
  },
  {
    question: "Can my LinkedIn account get restricted?",
    answer:
      "Lengrowth is designed specifically to avoid this. Actions are spread across the day, volumes stay within normal usage ranges, and timing varies to mimic human behaviour. Thousands of accounts run without issue. That said, no tool can guarantee LinkedIn won't change its policies — you take that risk knowingly.",
  },
  {
    question: "What's the difference between the desktop plans and Cloud?",
    answer:
      "Desktop plans (Starter → Agency) run the automation software on your own computer using your own internet connection — giving you full control. Cloud runs it on our managed infrastructure with AI already configured. Cloud costs more but requires nothing from you.",
  },
  {
    question: "Do I need technical skills to set it up?",
    answer:
      "No. Desktop setup is a one-time install that takes about 5 minutes. You log in, describe your ideal customer, and the first campaign goes out the same day. No code, no configuration files.",
  },
  {
    question: "Can I change plans?",
    answer:
      "Yes — upgrades take effect immediately with prorated charges. Downgrades take effect at the end of your billing cycle. If you downgrade to a plan with fewer LinkedIn account slots, the oldest accounts are automatically deactivated to fit the new limit.",
  },
  {
    question: "Do you offer refunds?",
    answer:
      "We offer a full refund within 14 days of purchase if you haven't had results. Contact support@lengrowth.com.",
  },
];

export default function PricingPage() {
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'annual'>('monthly');
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null);

  const getPrice = (plan: Plan) =>
    billingPeriod === 'annual' ? plan.annualPrice : plan.monthlyPrice;

  const getSavings = (plan: Plan) => {
    if (billingPeriod !== 'annual') return 0;
    const monthly = plan.monthlyPrice * 12;
    const annual = plan.annualPrice * 12;
    return Math.round(((monthly - annual) / monthly) * 100);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      {/* Lifetime banner — fixed above navbar */}
      <div className="fixed top-0 left-0 right-0 z-[60] bg-zinc-950 border-b border-emerald-500/20">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex flex-col sm:flex-row items-center justify-center gap-2 text-center">
          <span className="flex items-center gap-1.5 text-sm font-medium text-emerald-300">
            <Zap className="h-4 w-4 shrink-0" />
            Limited lifetime deal — Pro features forever for $149 one-time.
          </span>
          <Link href="/lifetime" className="text-sm font-bold text-emerald-400 hover:text-emerald-300 underline underline-offset-2 transition-colors">
            Claim yours →
          </Link>
        </div>
      </div>

      {/* Push the fixed Navbar down below the banner */}
      <div className="[&_header]:top-[40px]">
        <Navbar />
      </div>

      {/* Spacer so content clears the fixed banner + navbar (40px banner + 64px nav) */}
      <div className="h-[104px]" />

      {/* Hero */}
      <section className="pt-16 pb-4 sm:pt-24 sm:pb-8">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 text-center max-w-2xl">
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight mb-4">
            Simple, honest pricing.
          </h1>
          <p className="text-lg text-zinc-400 mb-10">
            Start free. Scale when you're ready. No long-term contracts.
          </p>

          {/* Billing toggle */}
          <div className="inline-flex items-center bg-zinc-900 border border-zinc-800 rounded-lg p-1 text-sm">
            <button
              onClick={() => setBillingPeriod('monthly')}
              className={`px-5 py-2 rounded-md font-medium transition-colors ${
                billingPeriod === 'monthly'
                  ? 'bg-emerald-600 text-white shadow'
                  : 'text-zinc-400 hover:text-zinc-300'
              }`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingPeriod('annual')}
              className={`px-5 py-2 rounded-md font-medium transition-colors relative ${
                billingPeriod === 'annual'
                  ? 'bg-emerald-600 text-white shadow'
                  : 'text-zinc-400 hover:text-zinc-300'
              }`}
            >
              Annual
              {billingPeriod !== 'annual' && (
                <span className="absolute -top-2.5 -right-1 text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-1 rounded">
                  −17%
                </span>
              )}
            </button>
          </div>
          {billingPeriod === 'annual' && (
            <p className="text-emerald-400 text-sm font-medium mt-3">You save 17% with annual billing</p>
          )}
        </div>
      </section>

      {/* Plan cards */}
      <section className="py-10 sm:py-16">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-7xl">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-5">
            {plans.filter(p => !p.isCloudTier).map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-2xl border flex flex-col ${
                  plan.highlighted
                    ? 'border-emerald-500 ring-1 ring-emerald-500/30 shadow-2xl shadow-emerald-500/10 lg:scale-[1.03]'
                    : 'border-zinc-800'
                } bg-zinc-900/60 p-7`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[11px] font-bold px-3 py-1 rounded-full tracking-wide">
                    MOST POPULAR
                  </div>
                )}

                <div className="mb-6">
                  <h3 className="text-xl font-bold text-white mb-0.5">{plan.displayName}</h3>
                  <p className="text-xs text-zinc-500 mb-5">{plan.tagline}</p>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-extrabold text-white">${getPrice(plan)}</span>
                    <span className="text-zinc-500 text-sm">
                      /{billingPeriod === 'monthly' ? 'mo' : 'mo, billed annually'}
                    </span>
                  </div>
                  {billingPeriod === 'annual' && getSavings(plan) > 0 && (
                    <p className="text-emerald-400 text-xs font-semibold mt-1.5">
                      Save {getSavings(plan)}% vs monthly
                    </p>
                  )}
                </div>

                <ul className="space-y-2.5 mb-8 flex-1">
                  {plan.features.map((feat, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                      <Check className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                      <span className="text-zinc-300 text-sm">{feat}</span>
                    </li>
                  ))}
                </ul>

                <Link href="/signup">
                  <Button
                    className={`w-full font-semibold ${
                      plan.highlighted
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20'
                        : 'bg-zinc-800 hover:bg-zinc-700 text-white'
                    }`}
                  >
                    Start Free Trial
                  </Button>
                </Link>
              </div>
            ))}
          </div>

          {/* Cloud card */}
          <div className="rounded-2xl border border-sky-500/30 bg-gradient-to-r from-sky-900/20 via-zinc-900/60 to-zinc-900/60 p-8 relative mt-4">
            <div className="absolute -top-3.5 left-8 bg-sky-600 text-white text-[11px] font-bold px-3 py-1 rounded-full tracking-wide">
              FULLY MANAGED
            </div>
            <div className="flex flex-col lg:flex-row lg:items-center gap-8">
              <div className="flex-1">
                <h3 className="text-2xl font-bold text-white mb-1">Cloud</h3>
                <p className="text-xs text-zinc-500 mb-4">Fully managed — we handle everything</p>
                <div className="flex items-baseline gap-1 mb-4">
                  <span className="text-4xl font-extrabold text-white">$299</span>
                  <span className="text-zinc-500 text-sm">/mo</span>
                </div>
                <p className="text-sm text-zinc-400 max-w-lg">
                  We run your campaigns on our infrastructure with AI already configured.
                  No desktop app, no setup — just results. Optional hands-on campaign
                  adjustments included on request.
                </p>
              </div>
              <ul className="lg:w-64 space-y-2">
                {plans.find(p => p.isCloudTier)?.features.map((feat, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <Check className="h-4 w-4 text-sky-400 shrink-0 mt-0.5" />
                    <span className="text-zinc-300 text-sm">{feat}</span>
                  </li>
                ))}
              </ul>
              <div className="lg:w-44 shrink-0">
                <Link href="/signup">
                  <Button className="w-full bg-sky-600 hover:bg-sky-500 text-white font-semibold">
                    Get Started
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Feature comparison */}
      <section className="py-16 sm:py-24 border-t border-zinc-800/60">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-6xl">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white text-center mb-14 tracking-tight">
            Compare plans in detail
          </h2>

          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/60">
                  <th className="text-left py-4 px-5 font-semibold text-zinc-400 w-1/3">Feature</th>
                  {['Starter', 'Pro', 'Business', 'Agency', 'Cloud'].map((name) => (
                    <th
                      key={name}
                      className={`text-center py-4 px-4 font-bold min-w-24 ${
                        name === 'Cloud' ? 'text-sky-400' : name === 'Pro' ? 'text-emerald-400' : 'text-white'
                      }`}
                    >
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonFeatures.map((feat, i) => (
                  <tr
                    key={i}
                    className={`border-b border-zinc-800/50 ${
                      i % 2 === 0 ? 'bg-transparent' : 'bg-zinc-900/20'
                    }`}
                  >
                    <td className="py-3.5 px-5 text-zinc-300">{feat.name}</td>
                    {(['starter', 'pro', 'business', 'agency', 'cloud'] as const).map((key) => (
                      <td key={key} className="text-center py-3.5 px-4">
                        {feat[key] ? (
                          <Check className={`h-4 w-4 mx-auto ${key === 'cloud' ? 'text-sky-400' : 'text-emerald-500'}`} />
                        ) : (
                          <X className="h-4 w-4 text-zinc-700 mx-auto" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 sm:py-24 border-t border-zinc-800/60">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-2xl">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white text-center mb-12 tracking-tight">
            Common questions
          </h2>

          <div className="space-y-2">
            {faqs.map((faq, i) => (
              <div key={i} className="border border-zinc-800 rounded-xl overflow-hidden">
                <button
                  onClick={() => setExpandedFaq(expandedFaq === i ? null : i)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-zinc-900/60 transition-colors"
                >
                  <span className="font-semibold text-white">{faq.question}</span>
                  <ChevronDown
                    className={`h-4 w-4 text-zinc-500 shrink-0 transition-transform duration-200 ${
                      expandedFaq === i ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {expandedFaq === i && (
                  <div className="px-5 pb-5 text-sm text-zinc-400 leading-relaxed border-t border-zinc-800 pt-4">
                    {faq.answer}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Enterprise nudge */}
          <div className="mt-12 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-8 text-center">
            <h3 className="text-lg font-bold text-white mb-2">Need something custom?</h3>
            <p className="text-zinc-400 text-sm mb-5">
              Custom enterprise plans available for larger teams with specific requirements.
            </p>
            <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
              <Button className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
                Schedule a Consultation
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
