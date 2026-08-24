'use client';

import { Navbar } from '@/components/landing/Navbar';
import { Hero } from '@/components/landing/Hero';
import { Features } from '@/components/landing/Features';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { Testimonials } from '@/components/landing/Testimonials';
import { PricingPreview } from '@/components/landing/pricing-preview';
import { FAQ } from '@/components/landing/faq';
import { CtaSection } from '@/components/landing/CtaSection';
import { Footer } from '@/components/landing/Footer';
import { ActivityTicker } from '@/components/landing/activity-ticker';
import { CursorGlow } from '@/components/landing/cursor-glow';
import { ScrollProgress } from '@/components/landing/scroll-progress';
import { MobileCta } from '@/components/landing/mobile-cta';
import { motion } from 'framer-motion';

function Capabilities() {
  const items = [
    { value: '2 channels', label: 'LinkedIn & WhatsApp' },
    { value: 'AI-written', label: 'Personalized messages' },
    { value: 'Smart', label: 'Automated follow-ups' },
    { value: 'Desktop or Cloud', label: 'Your choice of execution' },
  ];

  return (
    <div className="relative border-y border-zinc-800/40 bg-zinc-900/20 backdrop-blur-sm">
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-emerald-500/[0.02] to-transparent pointer-events-none" />
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-zinc-800/40">
          {items.map((item, i) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="flex flex-col items-center justify-center py-10 px-6 text-center"
            >
              <span className="text-2xl sm:text-3xl font-black text-white mb-1">{item.value}</span>
              <span className="text-xs sm:text-sm text-zinc-500 font-medium">{item.label}</span>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50 selection:bg-emerald-500/30 selection:text-emerald-200">
      <CursorGlow />
      <ScrollProgress />
      <Navbar />
      <main className="pb-16 md:pb-0">
        <Hero />
        <ActivityTicker />
        <Capabilities />
        <Features />
        <HowItWorks />
        <Testimonials />
        <PricingPreview />
        <FAQ />
        <CtaSection />
      </main>
      <Footer />
      <MobileCta />
    </div>
  );
}
