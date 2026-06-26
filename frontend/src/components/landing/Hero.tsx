'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight, Zap, Users, TrendingUp, LayoutTemplate, Mail, Calendar } from 'lucide-react';

export function Hero() {
  return (
    <section className="relative overflow-hidden py-20 sm:py-32 lg:py-48">
      {/* Background particles */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full mix-blend-screen filter blur-3xl animate-pulse" />
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full mix-blend-screen filter blur-3xl animate-pulse delay-1000" />
        <div className="absolute -bottom-32 left-1/2 w-96 h-96 bg-purple-500/10 rounded-full mix-blend-screen filter blur-3xl animate-pulse delay-2000" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center text-center">
          {/* Badge */}
          <div className="mb-8">
            <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-400 backdrop-blur-sm">
              <span className="mr-2 flex h-2 w-2 rounded-full bg-emerald-500"></span>
              New: AI-Powered LinkedIn Automation
            </span>
          </div>

          {/* Heading */}
          <h1 className="mb-6 text-4xl font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
            Scale Your LinkedIn <br />
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-200 bg-clip-text text-transparent">
              Outreach with Ease
            </span>
          </h1>

          {/* Subheading */}
          <p className="mx-auto mb-8 max-w-2xl text-lg sm:text-xl text-zinc-400">
            The all-in-one platform to automate your LinkedIn presence, 
            engage with prospects, and convert connections into customers.
            Powered by advanced AI and smart workflows.
          </p>

           {/* CTA Buttons */}
           <div className="flex flex-col sm:flex-row gap-4">
             <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank">
               <Button variant="outline" className="h-12 px-8 text-lg border-zinc-700 text-zinc-200 hover:bg-zinc-800 hover:border-zinc-600">
                 <Calendar className="mr-2 h-5 w-5" />
                 Book a Demo
               </Button>
             </Link>
           </div>

        </div>
      </div>
    </section>
  );
}