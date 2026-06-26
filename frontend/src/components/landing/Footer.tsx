'use client';

import Link from 'next/link';
import { Mail, Shield, Zap, Users } from 'lucide-react';

export function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-zinc-950 border-t border-zinc-900 pt-20 pb-10">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 mb-16">
           {/* Brand Column */}
           <div>
             <Link href="https://www.lengrowth.com" className="flex items-center gap-2 mb-4">
               <span className="text-2xl font-bold bg-gradient-to-r from-emerald-500 to-emerald-400 bg-clip-text text-transparent">
                 Lengrowth
               </span>
             </Link>
             <p className="text-zinc-400 text-sm mb-6">
               Empowering professionals to grow their LinkedIn presence with AI-powered automation and smart workflows.
             </p>
             <div className="flex gap-4">
               <a href="https://www.lengrowth.com" className="w-10 h-10 rounded-full bg-zinc-900 flex items-center justify-center text-zinc-400 hover:bg-emerald-900/30 hover:text-emerald-400 transition-colors">
                 <Mail className="h-5 w-5" />
               </a>
             </div>
           </div>

           {/* Products */}
           <div>
             <h3 className="text-white font-semibold mb-4">Product</h3>
             <ul className="space-y-2">
               <li key="features">
                 <Link href="https://www.lengrowth.com#features" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Features
                 </Link>
               </li>
               <li key="pricing">
                 <Link href="https://www.lengrowth.com#pricing" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Pricing
                 </Link>
               </li>
               <li key="templates">
                 <Link href="https://www.lengrowth.com#templates" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Templates
                 </Link>
               </li>
               <li key="integrations">
                 <Link href="https://www.lengrowth.com#integrations" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Integrations
                 </Link>
               </li>
               <li key="case-studies">
                 <Link href="https://www.lengrowth.com#case-studies" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Case Studies
                 </Link>
               </li>
             </ul>
           </div>

           {/* Company */}
           <div>
             <h3 className="text-white font-semibold mb-4">Company</h3>
             <ul className="space-y-2">
               <li key="about">
                 <Link href="https://www.lengrowth.com/about" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   About Us
                 </Link>
               </li>
               <li key="careers">
                 <Link href="https://www.lengrowth.com/careers" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Careers
                 </Link>
               </li>
               <li key="blog">
                 <Link href="https://www.lengrowth.com/blog" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Blog
                 </Link>
               </li>
               <li key="contact">
                 <Link href="https://calendly.com/lengrowth/lengrowth" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Contact
                 </Link>
               </li>
               <li key="partners">
                 <Link href="https://www.lengrowth.com/partners" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Partners
                 </Link>
               </li>
             </ul>
           </div>

           {/* Legal */}
           <div>
             <h3 className="text-white font-semibold mb-4">Legal</h3>
             <ul className="space-y-2">
               <li key="privacy">
                 <Link href="https://www.lengrowth.com/privacy" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Privacy Policy
                 </Link>
               </li>
               <li key="terms">
                 <Link href="https://www.lengrowth.com/terms" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Terms of Service
                 </Link>
               </li>
               <li key="cookie">
                 <Link href="https://www.lengrowth.com/cookies" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Cookie Policy
                 </Link>
               </li>
               <li key="gdpr">
                 <Link href="https://www.lengrowth.com/gdpr" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   GDPR Compliance
                 </Link>
               </li>
               <li key="security">
                 <Link href="https://www.lengrowth.com/security" className="text-zinc-400 text-sm hover:text-emerald-400 transition-colors">
                   Security
                 </Link>
               </li>
             </ul>
           </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-zinc-900 pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="text-zinc-500 text-sm">
            © {currentYear} Lengrowth. All rights reserved.
          </div>
          <div className="flex items-center gap-6 text-sm text-zinc-500">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4" />
              <span>Secure by Design</span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4" />
              <span>99.9% Uptime</span>
            </div>
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4" />
              <span>24/7 Support</span>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}