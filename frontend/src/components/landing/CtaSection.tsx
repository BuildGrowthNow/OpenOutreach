'use client';

import { Button } from '@/components/ui/button';
import { ChevronRight, Calendar } from 'lucide-react';
import Link from 'next/link';

export function CtaSection() {
  return (
    <section className="py-20 sm:py-32 relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-b from-zinc-950 to-emerald-950/10 pointer-events-none" />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-3xl h-96 bg-emerald-500/20 rounded-full blur-3xl pointer-events-none" />

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl font-bold text-white sm:text-5xl mb-6">
          Ready to Scale Your <br />
          <span className="bg-gradient-to-r from-emerald-400 to-emerald-200 bg-clip-text text-transparent">
            LinkedIn Growth?
          </span>
        </h2>
        <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto mb-10">
          Join thousands of professionals who are already growing their LinkedIn presence with Lengrowth. Start your 14-day free trial today.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/signup">
            <Button className="h-12 px-8 text-lg bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25">
              Get Started Now
              <ChevronRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
          <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
            <Button variant="outline" className="h-12 px-8 text-lg border-zinc-700 text-zinc-200 hover:bg-zinc-800 hover:border-zinc-600">
              <Calendar className="mr-2 h-5 w-5" />
              Talk to Sales
            </Button>
          </Link>
        </div>

        <div className="mt-8 flex justify-center gap-8 text-sm text-zinc-500">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            No credit card required
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            14-day free trial
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            Cancel anytime
          </div>
        </div>
      </div>
    </section>
  );
}