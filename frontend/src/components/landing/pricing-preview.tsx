'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Check } from 'lucide-react';
import { motion } from 'framer-motion';
import { TextReveal } from './text-reveal';

const plans = [
  {
    name: 'Starter',
    price: '$19',
    tagline: 'For solo founders getting started',
    features: ['1 LinkedIn account', '3 campaigns', 'AI messages', 'Automated follow-ups'],
    highlighted: false,
  },
  {
    name: 'Pro',
    price: '$49',
    tagline: 'For teams scaling outbound',
    features: ['Unlimited campaigns', 'Sales Navigator', 'AI follow-ups', 'API access'],
    highlighted: true,
  },
  {
    name: 'Cloud',
    price: '$299',
    tagline: 'We run everything for you',
    features: ['Managed execution', 'AI included', 'No desktop app needed', 'Priority support'],
    highlighted: false,
  },
];

export function PricingPreview() {
  return (
    <section id="pricing-preview" className="py-28 sm:py-36 bg-zinc-950 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[500px] bg-emerald-500/[0.03] rounded-full filter blur-[160px]" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.4 }}
            className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4"
          >
            Pricing
          </motion.p>
          <TextReveal
            as="h2"
            className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-[1.08] mb-5"
          >
            Plans that scale with you.
          </TextReveal>
          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="text-lg text-zinc-400 max-w-md mx-auto"
          >
            Start free. Upgrade when you need more.
          </motion.p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 max-w-4xl mx-auto">
          {plans.map((plan, i) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className={`relative rounded-2xl p-6 transition-all duration-500 ${
                plan.highlighted
                  ? 'bg-zinc-900/70 border-2 border-emerald-500/50 shadow-xl shadow-emerald-500/5'
                  : 'bg-zinc-900/30 border border-zinc-800/80 hover:border-zinc-700/80'
              }`}
            >
              {plan.highlighted && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-emerald-600 text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-wide">
                  Most popular
                </div>
              )}

              <div className="mb-4">
                <h3 className="text-base font-bold text-white">{plan.name}</h3>
                <p className="text-xs text-zinc-500 mt-0.5">{plan.tagline}</p>
              </div>

              <div className="mb-5">
                <span className="text-3xl font-black text-white">{plan.price}</span>
                <span className="text-zinc-500 text-sm">/mo</span>
              </div>

              <ul className="space-y-2.5 mb-6">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-center gap-2">
                    <div className="w-4 h-4 rounded-full bg-emerald-500/10 flex items-center justify-center shrink-0">
                      <Check className="h-2.5 w-2.5 text-emerald-500" />
                    </div>
                    <span className="text-xs text-zinc-400">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link href="/signup">
                <Button
                  className={`w-full h-10 text-sm font-semibold transition-all duration-300 ${
                    plan.highlighted
                      ? 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20'
                      : 'bg-zinc-800 hover:bg-zinc-700 text-white border border-zinc-700/50'
                  }`}
                >
                  Try free for 7 days
                </Button>
              </Link>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-center mt-8"
        >
          <Link href="/pricing" className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-emerald-400 transition-colors">
            Compare all plans in detail
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
