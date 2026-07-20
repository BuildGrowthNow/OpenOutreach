'use client';

import Link from 'next/link';
import { Logo } from '@/components/ui/logo';
import { Mail } from 'lucide-react';

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-zinc-950 border-t border-zinc-900/80 pt-20 pb-10 relative">
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-zinc-800 to-transparent" />

      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 mb-16">
          {/* Brand Column */}
          <div className="lg:col-span-1">
            <Link href="/" className="inline-flex mb-5">
              <Logo variant="dark" iconSize={28} className="text-sm text-white" />
            </Link>
            <p className="text-zinc-500 text-sm leading-relaxed mb-6">
              AI-powered LinkedIn outreach that runs on your desktop. Your IP, your browser, your conversations.
            </p>
            <a
              href="mailto:support@lengrowth.com"
              className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-emerald-400 transition-colors duration-200"
            >
              <Mail className="h-4 w-4" />
              support@lengrowth.com
            </a>
          </div>

          {/* Product */}
          <div>
            <h3 className="text-white font-semibold text-sm mb-5">Product</h3>
            <ul className="space-y-3">
              <li>
                <Link href="/pricing" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Pricing
                </Link>
              </li>
              <li>
                <Link href="/lifetime" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Lifetime Deal
                </Link>
              </li>
              <li>
                <Link href="/download" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Download
                </Link>
              </li>
              <li>
                <Link href="https://calendly.com/lengrowth/lengrowth" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Book a Demo
                </Link>
              </li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h3 className="text-white font-semibold text-sm mb-5">Company</h3>
            <ul className="space-y-3">
              <li>
                <Link href="https://www.lengrowth.com/contact" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Contact
                </Link>
              </li>
              <li>
                <a href="https://www.lengrowth.com" target="_blank" rel="noopener noreferrer" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Lengrowth
                </a>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-white font-semibold text-sm mb-5">Legal</h3>
            <ul className="space-y-3">
              <li>
                <Link href="/privacy" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Privacy Policy
                </Link>
              </li>
              <li>
                <Link href="/terms" className="text-zinc-500 text-sm hover:text-white transition-colors duration-200">
                  Terms of Service
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-zinc-900/80 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="text-zinc-600 text-sm">
            &copy; {currentYear} Lengrowth. All rights reserved.
          </div>
          <div className="flex items-center gap-6 text-xs text-zinc-600">
            <span>Runs on your machine</span>
            <span className="w-1 h-1 rounded-full bg-zinc-800" />
            <span>Your IP, your browser</span>
            <span className="w-1 h-1 rounded-full bg-zinc-800" />
            <span>No cloud required</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
