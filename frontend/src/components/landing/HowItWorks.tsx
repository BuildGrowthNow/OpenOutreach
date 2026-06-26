'use client';

import { Card } from '@/components/ui/card';
import { Check, Target, Settings, ChartBar } from 'lucide-react';

export function HowItWorks() {
  const steps = [
    {
      step: '01',
      title: 'Set Up Your Campaign',
      description: 'Configure your target audience, message templates, and automation workflow. Our easy-to-use interface guides you through every step.',
    },
    {
      step: '02',
      title: 'Let Automation Work',
      description: 'Our smart system will connect with prospects, send personalized messages, and follow up based on engagement - working 24/7.',
    },
    {
      step: '03',
      title: 'Track & Convert',
      description: 'Monitor performance in real-time, identify high-potential leads, and convert connections into valuable business relationships.',
    },
  ];

  return (
    <section id="how-it-works" className="py-20 sm:py-32 bg-zinc-950 relative overflow-hidden">
      {/* Decorative background */}
      <div className="absolute inset-0 opacity-5 pointer-events-none">
        <div className="absolute top-0 right-0 w-full h-full bg-[radial-gradient(#10b981_1px,transparent_1px)] [background-size:16px_16px]" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8">
         <div className="text-center mb-16">
           <h2 className="text-3xl font-bold text-white sm:text-4xl mb-4">
             How Lengrowth Outreach <span className="text-emerald-400">Works</span>
           </h2>
           <p className="text-lg text-zinc-400 max-w-2xl mx-auto">
             From first connection to qualified lead - our platform handles the entire process
           </p>
         </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {steps.map((step, index) => (
            <Card key={index} className="relative bg-zinc-900/80 border-zinc-800 p-8 overflow-hidden group hover:border-emerald-500/50 transition-all duration-300">
              {/* Step number */}
              <div className="absolute top-6 right-6 text-6xl font-bold text-zinc-800 group-hover:text-emerald-900/20 transition-colors">
                {step.step}
              </div>

              <div className="relative z-10">
                <div className="w-14 h-14 bg-zinc-800 rounded-xl flex items-center justify-center mb-6 group-hover:bg-emerald-600 transition-colors duration-300">
                  {index === 0 && <Settings className="h-7 w-7 text-zinc-400 group-hover:text-white" />}
                  {index === 1 && <Target className="h-7 w-7 text-zinc-400 group-hover:text-white" />}
                  {index === 2 && <ChartBar className="h-7 w-7 text-zinc-400 group-hover:text-white" />}
                </div>
                <h3 className="text-xl font-bold text-white mb-3">{step.title}</h3>
                <p className="text-zinc-400 leading-relaxed">{step.description}</p>
              </div>

              {/* Progress line for desktop */}
              {index !== steps.length - 1 && (
                <div className="hidden md:block absolute top-14 right-0 w-8 h-0.5 bg-zinc-800 group-hover:bg-emerald-500/50 transition-colors" />
              )}
            </Card>
          ))}
        </div>

      </div>
    </section>
  );
}