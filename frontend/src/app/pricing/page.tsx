'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Check, ChevronRight, X } from 'lucide-react';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';

interface Plan {
  name: string;
  displayName: string;
  monthlyPrice: number;
  annualPrice: number;
  maxLinkedInAccounts: number;
  maxCampaigns: number | null;
  features: string[];
  highlighted?: boolean;
}

interface ComparisonFeature {
  name: string;
  starter: boolean;
  pro: boolean;
  business: boolean;
  agency: boolean;
}

const plans: Plan[] = [
  {
    name: 'starter',
    displayName: 'Starter',
    monthlyPrice: 19,
    annualPrice: 16,
    maxLinkedInAccounts: 1,
    maxCampaigns: 3,
    features: [
      '1 LinkedIn account',
      '3 campaigns',
      'AI messages',
      'Automated follow-ups',
      'Unified inbox',
      'Analytics',
      'Local desktop execution',
    ],
  },
  {
    name: 'pro',
    displayName: 'Pro',
    monthlyPrice: 49,
    annualPrice: 41,
    maxLinkedInAccounts: 1,
    maxCampaigns: null,
    features: [
      'Everything in Starter',
      'Unlimited campaigns',
      'Voice notes',
      'AI follow-ups',
      'Sales Navigator access',
      'API access',
    ],
    highlighted: true,
  },
  {
    name: 'business',
    displayName: 'Business',
    monthlyPrice: 99,
    annualPrice: 83,
    maxLinkedInAccounts: 3,
    maxCampaigns: null,
    features: [
      'Everything in Pro',
      '3 LinkedIn accounts',
      'Team member invites',
      'Workspace management',
      'Priority support',
    ],
  },
  {
    name: 'agency',
    displayName: 'Agency',
    monthlyPrice: 249,
    annualPrice: 208,
    maxLinkedInAccounts: 10,
    maxCampaigns: null,
    features: [
      'Everything in Business',
      '10 LinkedIn accounts',
      '(+$20/ea for additional)',
      'White-label branding',
      'Custom domain',
      'Unlimited team members',
    ],
  },
];

const comparisonFeatures: ComparisonFeature[] = [
  { name: 'LinkedIn Accounts', starter: true, pro: true, business: true, agency: true },
  { name: 'Campaigns', starter: true, pro: true, business: true, agency: true },
  { name: 'AI Messages', starter: true, pro: true, business: true, agency: true },
  { name: 'Automated Follow-ups', starter: true, pro: true, business: true, agency: true },
  { name: 'Unified Inbox', starter: true, pro: true, business: true, agency: true },
  { name: 'Analytics Dashboard', starter: true, pro: true, business: true, agency: true },
  { name: 'Local Desktop Execution', starter: true, pro: true, business: true, agency: true },
  { name: 'Voice Notes', starter: false, pro: true, business: true, agency: true },
  { name: 'AI Follow-ups', starter: false, pro: true, business: true, agency: true },
  { name: 'Sales Navigator', starter: false, pro: true, business: true, agency: true },
  { name: 'API Access', starter: false, pro: true, business: true, agency: true },
  { name: 'Team Members', starter: false, pro: false, business: true, agency: true },
  { name: 'Workspace Management', starter: false, pro: false, business: true, agency: true },
  { name: 'Priority Support', starter: false, pro: false, business: true, agency: true },
  { name: 'White Label', starter: false, pro: false, business: false, agency: true },
  { name: 'Custom Domain', starter: false, pro: false, business: false, agency: true },
];

const faqs = [
  {
    question: 'What is included in the free trial?',
    answer: 'Your free trial includes full Pro plan access for 3 days. A credit card is required to start the trial, but you can cancel anytime—if you cancel before the trial ends, you won\'t be charged.',
  },
  {
    question: 'Can I change my plan later?',
    answer: 'Yes! Upgrades take effect immediately with prorated charges. Downgrades take effect at the end of your billing period.',
  },
  {
    question: 'What happens if I exceed my plan limits?',
    answer: 'Plan limits are enforced server-side. You can\'t exceed your LinkedIn account or campaign limits—you\'ll need to upgrade to add more.',
  },
  {
    question: 'Do you offer refunds?',
    answer: 'Refunds are not available after 14 days of purchase. Contact support for disputes within the first 14 days.',
  },
  {
    question: 'Is there a commitment or long-term contract?',
    answer: 'No! All plans are month-to-month. You can cancel your subscription anytime from your billing settings.',
  },
  {
    question: 'Do you offer custom enterprise pricing?',
    answer: 'Yes! For teams with unique requirements, contact our sales team to discuss custom pricing and features.',
  },
];

export default function PricingPage() {
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'annual'>('monthly');
  const [expandedFaq, setExpandedFaq] = useState<number | null>(0);

  const getPrice = (plan: Plan) => {
    if (billingPeriod === 'annual') {
      return plan.annualPrice;
    }
    return plan.monthlyPrice;
  };

  const getAnnualSavings = (plan: Plan) => {
    if (billingPeriod === 'annual') {
      const monthlyTotal = plan.monthlyPrice * 12;
      const annualTotal = plan.annualPrice * 12;
      const savings = Math.round(((monthlyTotal - annualTotal) / monthlyTotal) * 100);
      return savings;
    }
    return 0;
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      {/* Hero Section */}
      <section className="py-16 sm:py-24">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">
              Simple, <span className="text-emerald-400">Transparent Pricing</span>
            </h1>
            <p className="text-xl text-zinc-400 mb-8">
              Choose the plan that fits your LinkedIn growth goals. Start with a 3-day free trial—cancel anytime before it ends.
            </p>

            {/* Billing Toggle */}
            <div className="inline-flex items-center bg-zinc-900 border border-zinc-800 rounded-lg p-1">
              <button
                onClick={() => setBillingPeriod('monthly')}
                className={`px-6 py-2 rounded-md font-medium transition-colors ${
                  billingPeriod === 'monthly'
                    ? 'bg-emerald-600 text-white'
                    : 'text-zinc-400 hover:text-zinc-300'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingPeriod('annual')}
                className={`px-6 py-2 rounded-md font-medium transition-colors ${
                  billingPeriod === 'annual'
                    ? 'bg-emerald-600 text-white'
                    : 'text-zinc-400 hover:text-zinc-300'
                }`}
              >
                Annual
              </button>
            </div>
            {billingPeriod === 'annual' && (
              <p className="text-emerald-400 text-sm mt-3 font-medium">Save 17% with annual billing</p>
            )}
          </div>

          {/* Pricing Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-7xl mx-auto mb-12">
            {plans.map((plan) => (
              <div
                key={plan.name}
                className={`relative rounded-xl border ${
                  plan.highlighted
                    ? 'border-emerald-500 ring-2 ring-emerald-500/20 shadow-2xl shadow-emerald-500/10 lg:scale-105'
                    : 'border-zinc-800'
                } bg-zinc-900/50 p-8 flex flex-col h-full`}
              >
                {plan.highlighted && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                    MOST POPULAR
                  </div>
                )}

                <div className="mb-8">
                  <h3 className="text-2xl font-bold text-white mb-2">{plan.displayName}</h3>
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-white">${getPrice(plan)}</span>
                    <span className="text-zinc-400">/{billingPeriod === 'monthly' ? 'mo' : 'mo billed annually'}</span>
                  </div>
                  {billingPeriod === 'annual' && getAnnualSavings(plan) > 0 && (
                    <p className="text-emerald-400 text-sm font-medium mt-2">Save {getAnnualSavings(plan)}%</p>
                  )}
                </div>

                <div className="mb-8">
                  <p className="text-zinc-400 text-sm mb-4">
                    {plan.maxLinkedInAccounts === 1 ? '1 LinkedIn account' : `${plan.maxLinkedInAccounts} LinkedIn accounts`}
                    {plan.maxCampaigns && ` • ${plan.maxCampaigns} campaigns`}
                    {!plan.maxCampaigns && ' • Unlimited campaigns'}
                  </p>
                </div>

                <ul className="space-y-3 mb-8 flex-1">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      <Check className="h-5 w-5 text-emerald-500 shrink-0 mt-0.5" />
                      <span className="text-zinc-300 text-sm">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Link href="/signup" className="w-full">
                  <Button
                    className={`w-full ${
                      plan.highlighted
                        ? 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg shadow-emerald-600/25'
                        : 'bg-zinc-800 hover:bg-zinc-700 text-white'
                    }`}
                  >
                    Start Free Trial
                  </Button>
                </Link>
              </div>
            ))}
          </div>

          {/* Cloud Add-on Section */}
          <div className="max-w-2xl mx-auto mb-16 p-6 bg-zinc-900/50 border border-zinc-800 rounded-xl">
            <h3 className="text-lg font-bold text-white mb-2">Cloud Add-on</h3>
            <p className="text-zinc-400 text-sm mb-4">
              Add cloud-based profile execution to any plan for $39/profile/month. Run campaigns on our infrastructure without needing a desktop client.
            </p>
            <Link href="/signup">
              <Button variant="outline" className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10">
                Learn More
              </Button>
            </Link>
          </div>

          {/* Lifetime Deal Banner */}
          <div className="max-w-2xl mx-auto mb-16 p-8 bg-gradient-to-r from-emerald-600/20 to-emerald-500/10 border border-emerald-500/30 rounded-xl text-center">
            <h3 className="text-2xl font-bold text-white mb-2">Limited Time: Lifetime Deal</h3>
            <p className="text-emerald-200 mb-4">Pro plan features forever for a one-time payment of $149. Offer ends in 30 days.</p>
            <Link href="/lifetime">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
                Learn About Lifetime Deal
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Feature Comparison Section */}
      <section className="py-16 sm:py-24 bg-zinc-900/50 border-y border-zinc-800">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl sm:text-4xl font-bold text-center text-white mb-12">
            Feature Comparison
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-4 px-4 font-bold text-white">Feature</th>
                  {['Starter', 'Pro', 'Business', 'Agency'].map((name) => (
                    <th key={name} className="text-center py-4 px-4 font-bold text-white min-w-28">
                      {name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonFeatures.map((feature, idx) => (
                  <tr key={idx} className="border-b border-zinc-800/50">
                    <td className="py-4 px-4 text-zinc-300">{feature.name}</td>
                    <td className="text-center py-4 px-4">
                      {feature.starter ? (
                        <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                      ) : (
                        <X className="h-5 w-5 text-zinc-600 mx-auto" />
                      )}
                    </td>
                    <td className="text-center py-4 px-4">
                      {feature.pro ? (
                        <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                      ) : (
                        <X className="h-5 w-5 text-zinc-600 mx-auto" />
                      )}
                    </td>
                    <td className="text-center py-4 px-4">
                      {feature.business ? (
                        <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                      ) : (
                        <X className="h-5 w-5 text-zinc-600 mx-auto" />
                      )}
                    </td>
                    <td className="text-center py-4 px-4">
                      {feature.agency ? (
                        <Check className="h-5 w-5 text-emerald-500 mx-auto" />
                      ) : (
                        <X className="h-5 w-5 text-zinc-600 mx-auto" />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="py-16 sm:py-24">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl">
          <h2 className="text-3xl sm:text-4xl font-bold text-center text-white mb-12">
            Frequently Asked Questions
          </h2>

          <div className="space-y-4">
            {faqs.map((faq, idx) => (
              <div key={idx} className="border border-zinc-800 rounded-lg">
                <button
                  onClick={() => setExpandedFaq(expandedFaq === idx ? null : idx)}
                  className="w-full flex items-center justify-between p-4 hover:bg-zinc-900/50 transition-colors"
                >
                  <h3 className="text-lg font-semibold text-white text-left">{faq.question}</h3>
                  <ChevronRight
                    className={`h-5 w-5 text-emerald-500 shrink-0 transition-transform ${
                      expandedFaq === idx ? 'rotate-90' : ''
                    }`}
                  />
                </button>
                {expandedFaq === idx && (
                  <div className="px-4 pb-4 text-zinc-400 border-t border-zinc-800 pt-4">
                    {faq.answer}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Enterprise CTA */}
          <div className="mt-12 p-8 bg-zinc-900/50 border border-zinc-800 rounded-xl text-center">
            <h3 className="text-xl font-bold text-white mb-2">Need something custom?</h3>
            <p className="text-zinc-400 mb-4">
              We offer custom enterprise plans for organizations with unique requirements.
            </p>
            <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
                Schedule a Consultation
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
