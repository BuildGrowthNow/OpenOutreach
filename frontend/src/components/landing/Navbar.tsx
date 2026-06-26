'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Calendar, Menu, X } from 'lucide-react';
import { useState } from 'react';

export function Navbar() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-2xl font-bold bg-gradient-to-r from-emerald-500 to-emerald-400 bg-clip-text text-transparent">
                Lengrowth
              </span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-8">
            <Link href="#features" className="text-sm font-medium text-zinc-300 hover:text-emerald-400 transition-colors">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm font-medium text-zinc-300 hover:text-emerald-400 transition-colors">
              How it Works
            </Link>
          </nav>

          {/* Desktop CTA */}
          <div className="hidden md:flex items-center gap-4">
            <Link href="/login">
              <Button variant="ghost" className="text-zinc-300 hover:text-zinc-100 hover:bg-zinc-800">
                Log in
              </Button>
            </Link>
            <Link href="/signup">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-lg shadow-emerald-600/20">
                Sign Up
              </Button>
            </Link>
            <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank" className="ml-2">
              <Button variant="outline" className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300 border-zinc-700">
                <Calendar className="mr-2 h-4 w-4" />
                Book a Demo
              </Button>
            </Link>
          </div>

          {/* Mobile Menu Button */}
          <button
            className="md:hidden text-zinc-300 hover:text-white"
            onClick={() => setIsOpen(!isOpen)}
          >
            {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {/* Mobile Navigation */}
      {isOpen && (
        <div className="md:hidden border-t border-zinc-800 bg-zinc-950">
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-4">
            <Link href="#features" className="text-base font-medium text-zinc-300 hover:text-emerald-400" onClick={() => setIsOpen(false)}>
              Features
            </Link>
            <Link href="#how-it-works" className="text-base font-medium text-zinc-300 hover:text-emerald-400" onClick={() => setIsOpen(false)}>
              How it Works
            </Link>
            <div className="flex flex-col gap-3 pt-4 border-t border-zinc-800">
              <Link href="/login" className="text-center text-zinc-300" onClick={() => setIsOpen(false)}>
                Log in
              </Link>
              <Link href="/signup" className="text-center" onClick={() => setIsOpen(false)}>
                <Button className="w-full bg-emerald-600 hover:bg-emerald-700 text-white">
                  Sign Up
                </Button>
              </Link>
              <Link href="https://calendly.com/lengrowth/lengrowth" target="_blank" onClick={() => setIsOpen(false)}>
                <Button variant="outline" className="w-full border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10">
                  <Calendar className="mr-2 h-4 w-4" />
                  Book a Demo
                </Button>
              </Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}