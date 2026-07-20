'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Logo } from '@/components/ui/logo';
import { Menu, X } from 'lucide-react';
import { useState, useEffect } from 'react';

export function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 16);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  return (
    <header
      className={`fixed top-0 z-50 w-full transition-all duration-500 ${
        scrolled
          ? 'border-b border-zinc-800/60 bg-zinc-950/80 backdrop-blur-xl shadow-2xl shadow-black/20'
          : 'border-b border-transparent bg-transparent'
      }`}
    >
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="shrink-0">
            <Logo variant="dark" iconSize={28} className="text-sm text-white" />
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-8 text-sm">
            <Link href="/pricing" className="text-zinc-400 hover:text-white transition-colors duration-200">
              Pricing
            </Link>
            <Link href="/lifetime" className="text-zinc-400 hover:text-white transition-colors duration-200">
              Lifetime Deal
            </Link>
            <Link href="/download" className="text-zinc-400 hover:text-white transition-colors duration-200">
              Download
            </Link>
          </nav>

          {/* Desktop CTAs */}
          <div className="hidden md:flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-white hover:bg-zinc-800/60 transition-all duration-200">
                Log in
              </Button>
            </Link>
            <Link href="/signup">
              <Button size="sm" className="bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/20 font-semibold transition-all duration-300 hover:-translate-y-0.5">
                Start Free Trial
              </Button>
            </Link>
          </div>

          {/* Mobile toggle */}
          <button
            className="md:hidden p-2 text-zinc-400 hover:text-white transition-colors"
            onClick={() => setIsOpen(!isOpen)}
            aria-label="Toggle menu"
          >
            {isOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile drawer */}
      {isOpen && (
        <div className="md:hidden border-t border-zinc-800/60 bg-zinc-950/95 backdrop-blur-xl">
          <div className="container mx-auto px-4 py-6 flex flex-col gap-4">
            <Link
              href="/pricing"
              className="text-zinc-300 text-sm hover:text-white transition-colors"
              onClick={() => setIsOpen(false)}
            >
              Pricing
            </Link>
            <Link
              href="/lifetime"
              className="text-zinc-300 text-sm hover:text-white transition-colors"
              onClick={() => setIsOpen(false)}
            >
              Lifetime Deal
            </Link>
            <Link
              href="/download"
              className="text-zinc-300 text-sm hover:text-white transition-colors"
              onClick={() => setIsOpen(false)}
            >
              Download
            </Link>
            <div className="pt-4 flex flex-col gap-3 border-t border-zinc-800/60">
              <Link href="/login" onClick={() => setIsOpen(false)}>
                <Button variant="outline" className="w-full border-zinc-700 text-zinc-300 hover:bg-zinc-800">
                  Log in
                </Button>
              </Link>
              <Link href="/signup" onClick={() => setIsOpen(false)}>
                <Button className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold">
                  Start Free Trial
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
