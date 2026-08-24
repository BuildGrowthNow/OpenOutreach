'use client';

import { motion } from 'framer-motion';

const activities = [
  'New connection accepted',
  'Campaign started',
  'Reply received',
  'Meeting booked',
  'Follow-up sent',
  'Connection request accepted',
  'Warm reply landed',
  'Profile viewed',
  'Message delivered',
  'Demo scheduled',
  'Prospect connected',
  'Sequence completed',
  'New conversation started',
  'Pipeline updated',
  'WhatsApp reply received',
  'WhatsApp message delivered',
];

const duplicated = [...activities, ...activities];

export function ActivityTicker() {
  return (
    <div className="relative overflow-hidden py-4 border-y border-zinc-800/30 bg-zinc-950/80">
      {/* Fade edges */}
      <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-zinc-950 to-transparent z-10 pointer-events-none" />
      <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-zinc-950 to-transparent z-10 pointer-events-none" />

      <motion.div
        className="flex gap-8 whitespace-nowrap"
        animate={{ x: ['0%', '-50%'] }}
        transition={{
          x: {
            duration: 30,
            repeat: Infinity,
            ease: 'linear',
          },
        }}
      >
        {duplicated.map((item, i) => (
          <div key={i} className="flex items-center gap-2.5 shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/60" />
            <span className="text-sm text-zinc-500">{item}</span>
          </div>
        ))}
      </motion.div>
    </div>
  );
}
