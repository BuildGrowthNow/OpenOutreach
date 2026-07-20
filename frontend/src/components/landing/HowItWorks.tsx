'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Search, Sparkles, MessageCircle } from 'lucide-react';
import { motion } from 'framer-motion';
import { TextReveal } from './text-reveal';

const steps = [
  {
    number: '01',
    icon: Search,
    label: 'Define',
    title: 'Describe your ideal customer.',
    description:
      "Tell Lengrowth who you're after — job title, industry, company size, geography. That's it. No CSV imports, no manual scraping.",
    time: '5 minutes to configure',
  },
  {
    number: '02',
    icon: Sparkles,
    label: 'Automate',
    title: 'Personalized messages go out automatically.',
    description:
      "For each prospect, the AI reads their profile and writes a short, specific message. Connection requests and follow-ups send on human-like timing — no batches, no blasts.",
    time: 'Runs 24/7 in the background',
  },
  {
    number: '03',
    icon: MessageCircle,
    label: 'Convert',
    title: 'Qualified conversations land in your inbox.',
    description:
      "Replies get surfaced in your Lengrowth inbox. You pick up the conversation when someone is warm. No context switching, no lost threads.",
    time: 'Most users see replies in 48–72 hrs',
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-28 sm:py-36 bg-zinc-950 relative overflow-hidden">
      {/* Background elements */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />
        <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto mb-24">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.4 }}
            className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4"
          >
            Three steps, then hands off
          </motion.p>
          <TextReveal
            as="h2"
            className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-[1.08]"
          >
            Up and running in under 10 minutes.
          </TextReveal>
        </div>

        {/* Steps */}
        <div className="relative max-w-6xl mx-auto">
          {/* Connecting line */}
          <div className="hidden lg:block absolute top-24 left-[16%] right-[16%] h-px">
            <div className="w-full h-full bg-gradient-to-r from-emerald-500/40 via-teal-500/40 to-emerald-500/40" />
            <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/20 via-teal-500/20 to-emerald-500/20 blur-sm" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-16 lg:gap-8">
            {steps.map((step, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-80px' }}
                transition={{ duration: 0.5, delay: i * 0.15 }}
                className="relative flex flex-col items-center text-center"
              >
                {/* Step icon */}
                <div className="relative z-10 mb-8">
                  <div className="w-20 h-20 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center shadow-xl shadow-black/20 group">
                    <step.icon className="h-8 w-8 text-emerald-500" />
                  </div>
                  <div className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-emerald-600 border-2 border-zinc-950 flex items-center justify-center">
                    <span className="text-[10px] font-bold text-white">{step.number}</span>
                  </div>
                </div>

                <div className="space-y-3">
                  <p className="text-xs font-bold uppercase tracking-[0.2em] text-emerald-500">
                    {step.label}
                  </p>
                  <h3 className="text-xl font-bold text-white leading-snug">
                    {step.title}
                  </h3>
                  <p className="text-zinc-400 text-sm leading-relaxed max-w-xs mx-auto">
                    {step.description}
                  </p>
                  <p className="text-xs text-zinc-600 font-medium pt-2 inline-flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-emerald-500/60" />
                    {step.time}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="mt-24 text-center"
        >
          <Link href="/signup">
            <Button className="h-13 px-10 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/25 group transition-all duration-300 hover:-translate-y-0.5">
              Launch your first campaign
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Button>
          </Link>
          <p className="mt-4 text-sm text-zinc-600">
            Takes 5 minutes. No credit card to explore.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
