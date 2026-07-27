'use client';

import { Button } from '@/components/ui/button';
import { Calendar, Check, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { motion } from 'framer-motion';

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
    price: '$19',
    description: 'Get started with automated LinkedIn outreach',
    features: [
      '1 LinkedIn account',
      '3 campaigns',
      'AI messages',
      'Automated follow-ups',
      'Unified inbox',
      '7-day free trial',
    ],
  },
  {
    name: 'Pro',
    price: '$49',
    description: 'Unlimited campaigns and advanced features',
    features: [
      '1 LinkedIn account',
      'Unlimited campaigns',
      'Voice notes',
      'AI follow-ups',
      'Sales Navigator access',
      'API access',
      '7-day free trial',
    ],
    highlighted: true,
  },
  {
    name: 'Cloud',
    price: '$299',
    description: 'Fully managed — we run everything for you',
    features: [
      'Managed cloud execution',
      'AI included (Sonnet)',
      'No desktop app needed',
      'Priority support',
      'Campaign adjustments',
    ],
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="py-28 sm:py-36 bg-zinc-950 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[600px] bg-emerald-500/[0.03] rounded-full filter blur-[160px]" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4">
            Pricing
          </p>
          <h2 className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-[1.08] mb-5">
            Simple, <span className="bg-gradient-to-r from-emerald-400 to-teal-300 bg-clip-text text-transparent">transparent pricing.</span>
          </h2>
          <p className="text-lg text-zinc-400 max-w-xl mx-auto">
            Choose the plan that fits your growth ambitions. All plans include a 7-day free trial.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {pricingTiers.map((tier, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: index * 0.1 }}
              className={`relative rounded-2xl p-8 flex flex-col transition-all duration-500 ${
                tier.highlighted
                  ? 'bg-zinc-900/70 border-2 border-emerald-500/60 shadow-2xl shadow-emerald-500/10 scale-[1.02]'
                  : 'bg-zinc-900/30 border border-zinc-800/80 hover:border-zinc-700/80 hover:bg-zinc-900/50'
              }`}
            >
              {tier.highlighted && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-xs font-bold px-4 py-1.5 rounded-full shadow-lg shadow-emerald-600/30">
                  MOST POPULAR
                </div>
              )}

              <h3 className="text-xl font-bold text-white mb-2">{tier.name}</h3>
              <p className="text-zinc-500 text-sm mb-6">{tier.description}</p>

              <div className="mb-8">
                <span className="text-5xl font-black text-white">{tier.price}</span>
                {tier.price !== 'Custom' && <span className="text-zinc-500 text-lg">/month</span>}
              </div>

              <div className="flex-1 space-y-4 mb-8">
                {tier.features.map((feature, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
                      <Check className="h-3 w-3 text-emerald-500" />
                    </div>
                    <span className="text-zinc-300 text-sm">{feature}</span>
                  </div>
                ))}
              </div>

              {tier.price === 'Custom' ? (
                <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
                  <Button className="w-full h-12 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold transition-all duration-300">
                    Book a Consultation
                    <Calendar className="ml-2 h-4 w-4" />
                  </Button>
                </Link>
              ) : (
                <Link href="/signup">
                  <Button
                    className={`w-full h-12 font-semibold transition-all duration-300 ${
                      tier.highlighted
                        ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25 hover:-translate-y-0.5'
                        : 'bg-zinc-800 hover:bg-zinc-700 text-white border border-zinc-700/50'
                    }`}
                  >
                    Start Free Trial
                  </Button>
                </Link>
              )}
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-16 text-center"
        >
          <p className="text-zinc-600 mb-4 text-sm">Have questions about our pricing?</p>
          <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
            <Button variant="outline" className="border-zinc-700/80 text-zinc-300 hover:bg-zinc-800/80 hover:border-zinc-600 hover:text-white transition-all duration-300">
              Schedule a Demo Call
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
