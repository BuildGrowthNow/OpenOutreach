'use client';

import { Button } from '@/components/ui/button';
import { Calendar, Check, ChevronRight } from 'lucide-react';
import Link from 'next/link';

interface PricingTier {
  name: string;
  price: string;
  description: string;
  features: string[];
  highlighted?: boolean;
}

const pricingTiers: PricingTier[] = [
  {
    name: 'Starter',
    price: '$49',
    description: 'Perfect for freelancers and solo entrepreneurs',
    features: [
      '1,000 connections/month',
      '5 active campaigns',
      'Basic analytics',
      'Email support',
      '14-day free trial',
    ],
  },
  {
    name: 'Professional',
    price: '$99',
    description: 'For growing teams and agencies',
    features: [
      '5,000 connections/month',
      '15 active campaigns',
      'Advanced analytics',
      'Priority support',
      'AI message generation',
      'Smart follow-ups',
      '14-day free trial',
    ],
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    description: 'For large organizations',
    features: [
      'Unlimited connections',
      'Unlimited campaigns',
      'Custom integrations',
      'Dedicated account manager',
      'Custom training',
      'API access',
      'SLA guarantee',
    ],
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="py-20 sm:py-32 bg-zinc-950 relative">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-white sm:text-4xl mb-4">
            Simple, <span className="text-emerald-400">Transparent Pricing</span>
          </h2>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto">
            Choose the plan that fits your growth ambitions
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {pricingTiers.map((tier, index) => (
            <div
              key={index}
              className={`relative bg-zinc-900/50 border ${
                tier.highlighted
                  ? 'border-emerald-500 ring-2 ring-emerald-500/20 shadow-2xl shadow-emerald-500/10'
                  : 'border-zinc-800'
              } rounded-2xl p-8 flex flex-col`}
            >
              {tier.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-xs font-bold px-3 py-1 rounded-full">
                  MOST POPULAR
                </div>
              )}

              <h3 className="text-xl font-bold text-white mb-2">{tier.name}</h3>
              <p className="text-zinc-400 text-sm mb-6">{tier.description}</p>

              <div className="mb-6">
                <span className="text-4xl font-bold text-white">{tier.price}</span>
                {tier.price !== 'Custom' && <span className="text-zinc-400">/month</span>}
              </div>

              <div className="flex-1 space-y-4 mb-8">
                {tier.features.map((feature, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Check className="h-5 w-5 text-emerald-500 shrink-0" />
                    <span className="text-zinc-300 text-sm">{feature}</span>
                  </div>
                ))}
              </div>

              {tier.price === 'Custom' ? (
                <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
                  <Button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white">
                    Book a Consultation
                    <Calendar className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              ) : (
                <Link href="/signup">
                  <Button
                    className={`w-full ${
                      tier.highlighted
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25'
                        : 'bg-zinc-800 hover:bg-zinc-700 text-white'
                    }`}
                  >
                    Start Free Trial
                  </Button>
                </Link>
              )}
            </div>
          ))}
        </div>

        <div className="mt-16 text-center">
          <p className="text-zinc-500 mb-6">Have questions about our pricing?</p>
          <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
            <Button variant="outline" className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300">
              Schedule a Demo Call
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </section>
  );
}