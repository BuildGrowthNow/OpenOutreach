'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Calendar } from 'lucide-react';
import { motion } from 'framer-motion';
import { RotatingText } from './rotating-text';

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-28 sm:pt-40 pb-24 sm:pb-32">
      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[1100px] h-[800px] bg-emerald-500/[0.07] rounded-full filter blur-[160px]" />
        <div className="absolute top-20 -right-40 w-[600px] h-[600px] bg-teal-500/[0.04] rounded-full filter blur-[120px]" />
        <div className="absolute -bottom-20 -left-40 w-[400px] h-[400px] bg-emerald-600/[0.03] rounded-full filter blur-[100px]" />
      </div>

      {/* Grain overlay */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.015]" style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=\'0 0 256 256\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cfilter id=\'noise\'%3E%3CfeTurbulence type=\'fractalNoise\' baseFrequency=\'0.65\' numOctaves=\'3\' stitchTiles=\'stitch\'/%3E%3C/filter%3E%3Crect width=\'100%25\' height=\'100%25\' filter=\'url(%23noise)\' opacity=\'1\'/%3E%3C/svg%3E")' }} />

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center text-center mb-20">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mb-8"
          >
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/[0.06] px-5 py-2 text-sm font-medium text-emerald-400 backdrop-blur-sm">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
              LinkedIn + WhatsApp Outreach
            </span>
          </motion.div>

          {/* Headline with rotating text */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="mb-7 max-w-5xl text-5xl font-black tracking-tight text-white sm:text-6xl lg:text-[4.5rem]"
            style={{ lineHeight: 1.05 }}
          >
            Fill your calendar with
            <br />
            <RotatingText
              words={['qualified meetings.', 'warm conversations.', 'pipeline growth.', 'booked demos.']}
              interval={3200}
            />
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mx-auto mb-10 max-w-2xl text-lg text-zinc-400 leading-relaxed sm:text-xl"
          >
            Define your ideal customer once. Lengrowth finds them on LinkedIn
            or WhatsApp, writes a unique message for each, and follows up until
            they&apos;re ready to talk — completely hands-off.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-col sm:flex-row gap-4 mb-6"
          >
            <Link href="/signup">
              <Button className="h-13 px-10 text-base font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/25 group transition-all duration-300 hover:shadow-emerald-500/30 hover:-translate-y-0.5">
                Start Free Trial
                <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Button>
            </Link>
            <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
              <Button
                variant="outline"
                className="h-13 px-10 text-base border-zinc-700/80 text-zinc-300 hover:bg-zinc-800/80 hover:border-zinc-600 hover:text-white transition-all duration-300"
              >
                <Calendar className="mr-2 h-4 w-4" />
                Book a Demo
              </Button>
            </Link>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="text-sm text-zinc-600"
          >
            7-day free trial &middot; No setup fees &middot; Cancel anytime
          </motion.p>
        </div>

        {/* Video placeholder */}
        <motion.div
          initial={{ opacity: 0, y: 40, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="relative max-w-5xl mx-auto"
        >
          <div className="absolute -inset-px rounded-2xl bg-gradient-to-b from-emerald-500/20 via-emerald-500/5 to-transparent pointer-events-none" />
          <div className="absolute -inset-12 bg-emerald-500/[0.04] rounded-3xl blur-3xl pointer-events-none" />
          <div className="relative rounded-2xl border border-zinc-800/80 bg-zinc-900/90 overflow-hidden shadow-2xl shadow-black/60 backdrop-blur-sm">
            {/* Window chrome */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800/60 bg-zinc-950/80">
              <span className="h-3 w-3 rounded-full bg-red-500/60" />
              <span className="h-3 w-3 rounded-full bg-yellow-500/60" />
              <span className="h-3 w-3 rounded-full bg-green-500/60" />
              <span className="mx-auto text-xs text-zinc-600 font-mono tracking-wide">
                lengrowth.app
              </span>
            </div>
            {/* Video demo */}
            <div className="aspect-[16/9] relative bg-zinc-950">
              <video
                className="w-full h-full object-cover"
                autoPlay
                muted
                loop
                playsInline
                controls
              >
                <source src="/video-demo.mp4" type="video/mp4" />
              </video>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
