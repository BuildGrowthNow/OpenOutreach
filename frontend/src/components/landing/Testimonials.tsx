'use client';

import Image from 'next/image';
import { motion } from 'framer-motion';
import { Quote } from 'lucide-react';
import { TiltCard } from './tilt-card';
import { TextReveal } from './text-reveal';

const testimonials = [
  {
    name: 'James Whitfield',
    role: 'Head of Sales, Claritec',
    avatar: 'https://randomuser.me/api/portraits/men/32.jpg',
    content: "We went from 5 meetings a week to 18 — without hiring another SDR. The messages actually sound like something I'd write, which is why people respond.",
    metric: '3.6x more meetings',
  },
  {
    name: 'Priya Sharma',
    role: 'Co-founder, NovaBridge',
    avatar: 'https://randomuser.me/api/portraits/women/44.jpg',
    content: "I was spending 2 hours a day manually prospecting on LinkedIn. Now I spend 10 minutes reviewing conversations that are already warm. Complete game-changer for a small team.",
    metric: '92% time saved',
  },
  {
    name: 'Marcus Adeyemi',
    role: 'Account Executive, Streamline.io',
    avatar: 'https://randomuser.me/api/portraits/men/75.jpg',
    content: "The follow-up sequencing is what really sets it apart. I've closed deals from leads who didn't respond to the first message but came back on the third touch. That never happened with manual outreach.",
    metric: '41% reply rate',
  },
  {
    name: 'Laura Chen',
    role: 'VP Business Development, Axiom Labs',
    avatar: 'https://randomuser.me/api/portraits/women/68.jpg',
    content: "We tested it against our existing outbound motion and Lengrowth outperformed by 2x on acceptance rate. Plus my reps can finally focus on closing instead of prospecting.",
    metric: '2x acceptance rate',
  },
  {
    name: 'David Andersson',
    role: 'Founder, Scalebound',
    avatar: 'https://randomuser.me/api/portraits/men/52.jpg',
    content: "Running it from my own laptop means I never worry about getting flagged. It uses my IP, my browser — LinkedIn has no idea. Six months in, zero issues with my account.",
    metric: '6 months, 0 flags',
  },
  {
    name: 'Nina Kowalski',
    role: 'Growth Lead, Finova Partners',
    avatar: 'https://randomuser.me/api/portraits/women/26.jpg',
    content: "I was skeptical about AI-written messages, but the personalization is genuinely impressive. People think I actually read their whole profile. Because the AI does.",
    metric: '34% response rate',
  },
];

export function Testimonials() {
  return (
    <section id="testimonials" className="py-28 sm:py-36 bg-zinc-950 relative overflow-hidden">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/3 right-0 w-[500px] h-[500px] bg-emerald-500/[0.03] rounded-full filter blur-[140px]" />
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
            Real results
          </motion.p>
          <TextReveal
            as="h2"
            className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-[1.08] mb-5"
          >
            Teams that switched don&apos;t switch back.
          </TextReveal>
          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="text-lg text-zinc-400 max-w-xl mx-auto"
          >
            Hear from sales professionals who automated their outreach and scaled their pipeline.
          </motion.p>
        </div>

        {/* Testimonial grid with tilt */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {testimonials.map((t, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.5, delay: index * 0.08 }}
            >
              <TiltCard className="h-full">
                <div className="group relative h-full rounded-2xl border border-zinc-800/80 bg-zinc-900/30 p-7 hover:bg-zinc-900/60 hover:border-zinc-700/60 transition-all duration-500">
                  {/* Metric badge */}
                  <div className="absolute top-6 right-6">
                    <span className="inline-flex items-center rounded-full bg-emerald-500/[0.08] border border-emerald-500/20 px-3 py-1 text-xs font-semibold text-emerald-400">
                      {t.metric}
                    </span>
                  </div>

                  {/* Quote icon */}
                  <Quote className="h-8 w-8 text-zinc-800 mb-4" />

                  {/* Content */}
                  <p className="text-zinc-300 text-sm leading-relaxed mb-6">
                    &ldquo;{t.content}&rdquo;
                  </p>

                  {/* Author */}
                  <div className="flex items-center gap-3 pt-4 border-t border-zinc-800/60">
                    <Image
                      src={t.avatar}
                      alt={t.name}
                      width={40}
                      height={40}
                      className="w-10 h-10 rounded-full object-cover ring-2 ring-zinc-800 group-hover:ring-emerald-500/30 transition-all duration-300"
                    />
                    <div>
                      <div className="text-sm font-semibold text-white">{t.name}</div>
                      <div className="text-xs text-zinc-500">{t.role}</div>
                    </div>
                  </div>
                </div>
              </TiltCard>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
