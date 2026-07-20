'use client';

import { MessageSquare, Target, BarChart3, Clock, Brain, Shield } from 'lucide-react';
import { motion } from 'framer-motion';
import { TiltCard } from './tilt-card';
import { TextReveal } from './text-reveal';

const features = [
  {
    icon: Target,
    headline: 'Your pipeline, built automatically.',
    body: "Describe your ideal customer — industry, role, company size — and Lengrowth builds a prospect list and starts reaching out. No manual searching, no spreadsheets.",
    accent: 'from-emerald-400 to-teal-400',
  },
  {
    icon: Brain,
    headline: "A message they'll actually read.",
    body: "The AI reads each prospect's profile and writes a short, specific message — not a template blast. Replies come in because the outreach doesn't feel like outreach.",
    accent: 'from-teal-400 to-cyan-400',
  },
  {
    icon: MessageSquare,
    headline: "Follow-ups that don't annoy.",
    body: "Smart sequences send the right follow-up at the right interval. If someone replies, the sequence stops. If they connect but don't respond, a second touch goes out automatically.",
    accent: 'from-cyan-400 to-blue-400',
  },
  {
    icon: Clock,
    headline: 'Runs while you focus on selling.',
    body: "Lengrowth operates in the background — connection requests, follow-ups, inbox replies — all within safe daily limits. Check in on your dashboard whenever you want.",
    accent: 'from-emerald-400 to-green-400',
  },
  {
    icon: BarChart3,
    headline: "Know exactly what's working.",
    body: "See acceptance rates, reply rates, and which messages are converting. Adjust your targeting or messaging based on real campaign data, not guesswork.",
    accent: 'from-green-400 to-emerald-400',
  },
  {
    icon: Shield,
    headline: 'Built to protect your account.',
    body: "Human-like send timing, daily limits that mirror real usage patterns, and activity spread across the day. Your LinkedIn account stays healthy and undetected.",
    accent: 'from-emerald-400 to-lime-400',
  },
];

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.08,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as const },
  },
};

export function Features() {
  return (
    <section id="features" className="py-28 sm:py-36 bg-zinc-950 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1000px] h-[600px] bg-emerald-500/[0.03] rounded-full filter blur-[160px]" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="max-w-2xl mb-20">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.4 }}
            className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4"
          >
            How it works for you
          </motion.p>
          <TextReveal
            as="h2"
            className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-[1.08] mb-6"
          >
            From who should I target to booked meetings.
          </TextReveal>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-80px' }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="text-lg text-zinc-400 leading-relaxed"
          >
            Everything from finding prospects to closing conversations runs inside one platform.
            You define the outcome — Lengrowth handles the repetition.
          </motion.p>
        </div>

        {/* Feature grid — bento style with tilt */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-80px' }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {features.map((feature, i) => (
            <motion.div key={i} variants={itemVariants}>
              <TiltCard className="h-full">
                <div className="group relative h-full rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-8 hover:bg-zinc-900/70 hover:border-zinc-700/80 transition-all duration-500 overflow-hidden">
                  {/* Hover glow */}
                  <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none">
                    <div className={`absolute -top-20 -right-20 w-40 h-40 bg-gradient-to-br ${feature.accent} opacity-[0.08] rounded-full blur-3xl`} />
                  </div>

                  <div className="relative">
                    <div className={`mb-6 w-12 h-12 rounded-xl bg-gradient-to-br ${feature.accent} p-[1px]`}>
                      <div className="w-full h-full rounded-xl bg-zinc-900 flex items-center justify-center group-hover:bg-zinc-800 transition-colors duration-300">
                        <feature.icon className="h-5 w-5 text-zinc-400 group-hover:text-emerald-400 transition-colors duration-300" />
                      </div>
                    </div>
                    <h3 className="text-lg font-bold text-white mb-3 leading-snug">
                      {feature.headline}
                    </h3>
                    <p className="text-sm text-zinc-500 leading-relaxed group-hover:text-zinc-400 transition-colors duration-300">
                      {feature.body}
                    </p>
                  </div>
                </div>
              </TiltCard>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
