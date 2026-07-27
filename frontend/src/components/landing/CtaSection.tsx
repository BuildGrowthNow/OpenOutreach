'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Zap } from 'lucide-react';
import { motion } from 'framer-motion';

export function CtaSection() {
  return (
    <section className="py-28 sm:py-36 relative overflow-hidden bg-zinc-950">
      {/* Background effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[900px] h-[500px] bg-emerald-500/[0.08] rounded-full blur-[150px]" />
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.98 }}
          whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative max-w-4xl mx-auto"
        >
          {/* Card border gradient */}
          <div className="absolute -inset-px rounded-3xl bg-gradient-to-b from-emerald-500/30 via-zinc-700/30 to-zinc-800/30" />

          <div className="relative rounded-3xl bg-zinc-900/80 backdrop-blur-xl overflow-hidden p-12 sm:p-20 text-center">
            {/* Inner ambient */}
            <div className="absolute inset-0 bg-gradient-to-b from-emerald-500/[0.04] via-transparent to-transparent pointer-events-none" />
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[1px] bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent" />

            <div className="relative">
              {/* Lifetime deal nudge */}
              <Link
                href="/lifetime"
                className="inline-flex items-center gap-2 mb-10 rounded-full border border-emerald-500/25 bg-emerald-500/[0.08] px-5 py-2 text-sm font-medium text-emerald-400 hover:bg-emerald-500/[0.12] hover:border-emerald-500/40 transition-all duration-300"
              >
                <Zap className="h-3.5 w-3.5" />
                Limited lifetime deal — 100 spots, $149 once
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>

              <h2 className="text-4xl sm:text-5xl lg:text-6xl font-black text-white tracking-tight leading-[1.08] mb-7">
                Your next 10 qualified leads{' '}
                <br className="hidden sm:block" />
                <span className="bg-gradient-to-r from-emerald-400 via-emerald-300 to-teal-300 bg-clip-text text-transparent">
                  are already on LinkedIn.
                </span>
              </h2>

              <p className="text-lg sm:text-xl text-zinc-400 max-w-xl mx-auto mb-12 leading-relaxed">
                You&apos;ve seen how it works. Set up a campaign in 5 minutes and see your first replies by midweek.
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Link href="/signup">
                  <Button className="h-14 px-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/30 group transition-all duration-300 hover:-translate-y-0.5 hover:shadow-emerald-500/40">
                    Start your first campaign
                    <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </Button>
                </Link>
                <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
                  <Button
                    variant="outline"
                    className="h-14 px-12 text-base border-zinc-700/80 text-zinc-300 hover:bg-zinc-800/80 hover:border-zinc-600 hover:text-white transition-all duration-300"
                  >
                    Talk to us first
                  </Button>
                </Link>
              </div>

              <p className="mt-6 text-sm text-zinc-600">
                7-day free trial &middot; No setup fees &middot; Cancel anytime
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
