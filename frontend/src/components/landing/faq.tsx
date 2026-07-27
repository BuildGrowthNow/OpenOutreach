'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { TextReveal } from './text-reveal';

const faqs = [
  {
    question: "Will my LinkedIn account get banned?",
    answer: "Lengrowth runs on your own machine, using your real IP and browser. It mimics human timing — random delays, daily limits, activity spread across hours. We've designed it to be indistinguishable from manual use. Most users run it for months without any issues.",
  },
  {
    question: "How is this different from other LinkedIn tools?",
    answer: "Most tools run in the cloud on shared IPs that LinkedIn already flags. Lengrowth runs locally on your desktop — your IP, your browser session, your cookies. No proxy costs, no shared infrastructure, no red flags. Plus the AI writes genuinely personalized messages, not template swaps.",
  },
  {
    question: "Do the AI messages actually sound good?",
    answer: "The AI reads each prospect's full profile — experience, posts, about section — and writes a short, specific message referencing something real. It's not 'Hi {first_name}, I noticed we're in the same industry.' People respond because it doesn't feel automated.",
  },
  {
    question: "What happens when someone replies?",
    answer: "The sequence stops immediately. The reply lands in your Lengrowth inbox and you take over the conversation manually. We're an outreach tool, not a chatbot — you handle the selling.",
  },
  {
    question: "Can I use this with Sales Navigator?",
    answer: "Yes. If you have a Sales Navigator subscription, Lengrowth can use its advanced search filters to find more targeted prospects. It works with or without it.",
  },
  {
    question: "What if I already have a CRM?",
    answer: "Lengrowth has its own lightweight pipeline, but if you want to push leads elsewhere, the Pro plan includes API access. Export your connected leads and conversations to whatever system you use.",
  },
  {
    question: "Is there a free trial?",
    answer: "Yes — 7 days, full access, no credit card required to start exploring. You'll need to add payment to actually send outreach, but you can set up campaigns and see the interface immediately.",
  },
];

export function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <section id="faq" className="py-28 sm:py-36 bg-zinc-950 relative">
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />
      </div>

      <div className="container relative mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl">
        <div className="text-center mb-16">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-100px' }}
            transition={{ duration: 0.4 }}
            className="text-sm font-semibold uppercase tracking-widest text-emerald-500 mb-4"
          >
            Questions
          </motion.p>
          <TextReveal
            as="h2"
            className="text-4xl sm:text-5xl font-black text-white tracking-tight leading-[1.08]"
          >
            Everything you need to know.
          </TextReveal>
        </div>

        <div className="space-y-3">
          {faqs.map((faq, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
            >
              <button
                onClick={() => setOpenIndex(openIndex === i ? null : i)}
                className="w-full text-left rounded-xl border border-zinc-800/80 bg-zinc-900/30 hover:bg-zinc-900/60 hover:border-zinc-700/60 transition-all duration-300 p-5 group"
              >
                <div className="flex items-center justify-between gap-4">
                  <span className="text-sm sm:text-base font-semibold text-white group-hover:text-emerald-50 transition-colors">
                    {faq.question}
                  </span>
                  <ChevronDown
                    className={`h-4 w-4 text-zinc-500 shrink-0 transition-transform duration-300 ${
                      openIndex === i ? 'rotate-180 text-emerald-500' : ''
                    }`}
                  />
                </div>
                <AnimatePresence>
                  {openIndex === i && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.3, ease: 'easeInOut' }}
                      className="overflow-hidden"
                    >
                      <p className="text-sm text-zinc-400 leading-relaxed pt-4 border-t border-zinc-800/40 mt-4">
                        {faq.answer}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </button>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
