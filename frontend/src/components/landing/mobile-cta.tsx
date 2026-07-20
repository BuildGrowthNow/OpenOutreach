'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ArrowRight } from 'lucide-react';
import { motion, useScroll, useTransform } from 'framer-motion';

export function MobileCta() {
  const { scrollYProgress } = useScroll();
  const opacity = useTransform(scrollYProgress, [0, 0.1], [0, 1]);

  return (
    <motion.div
      style={{ opacity }}
      className="fixed bottom-0 left-0 right-0 z-50 md:hidden"
    >
      <div className="bg-zinc-950/95 backdrop-blur-xl border-t border-zinc-800/60 px-4 py-3 safe-bottom">
        <Link href="/signup" className="block">
          <Button className="w-full h-12 text-sm font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-xl shadow-emerald-600/20 group">
            Start your first campaign
            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-0.5" />
          </Button>
        </Link>
      </div>
    </motion.div>
  );
}
