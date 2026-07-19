'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Check, ChevronRight, Clock, Zap } from 'lucide-react';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';

export default function LifetimeDealPage() {
  const [timeRemaining, setTimeRemaining] = useState({
    days: 30,
    hours: 0,
    minutes: 0,
    seconds: 0,
  });
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    // Calculate time remaining from launch date (2026-07-19)
    const launchDate = new Date('2026-07-19T00:00:00Z').getTime();
    const endDate = new Date(launchDate + 30 * 24 * 60 * 60 * 1000).getTime();

    const updateTimer = () => {
      const now = new Date().getTime();
      const distance = endDate - now;

      if (distance <= 0) {
        setIsExpired(true);
        return;
      }

      const days = Math.floor(distance / (1000 * 60 * 60 * 24));
      const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((distance % (1000 * 60)) / 1000);

      setTimeRemaining({ days, hours, minutes, seconds });
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, []);

  const features = [
    'All Pro plan features',
    'Unlimited campaigns',
    'Unlimited LinkedIn accounts (up to plan limits)',
    'Voice notes',
    'AI-powered follow-ups',
    'Sales Navigator access',
    'API access',
    'Priority email support',
    'Forever—no recurring charges',
  ];

  const comparisons = [
    {
      item: 'Pro Plan (Annual)',
      lifetime: false,
      value: '$492/year',
    },
    {
      item: '5-Year Cost (Pro Annual)',
      lifetime: false,
      value: '$2,460',
    },
    {
      item: '10-Year Cost (Pro Annual)',
      lifetime: false,
      value: '$4,920',
    },
    {
      item: 'Lifetime Deal (One-time)',
      lifetime: true,
      value: '$149 forever',
    },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      <main className="py-16 sm:py-24">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
          {/* Hero Section */}
          <div className="max-w-3xl mx-auto text-center mb-16">
            <div className="inline-block px-4 py-2 bg-emerald-600/20 border border-emerald-500/30 rounded-full mb-6">
              <p className="text-emerald-300 text-sm font-semibold">LIMITED TIME OFFER</p>
            </div>

            <h1 className="text-5xl sm:text-6xl font-bold text-white mb-6">
              Lifetime Deal
            </h1>

            <p className="text-xl sm:text-2xl text-zinc-300 mb-8">
              Pro plan features <span className="text-emerald-400 font-bold">forever</span> for a one-time payment of <span className="text-emerald-400 font-bold">$149</span>
            </p>

            <p className="text-zinc-400 mb-12">
              Lock in Pro plan access permanently. No recurring charges, no price increases. Ever.
            </p>

            {!isExpired && (
              <div className="mb-12">
                <p className="text-zinc-400 text-sm mb-4">Offer ends in:</p>
                <div className="flex justify-center gap-4 mb-4">
                  {[
                    { label: 'Days', value: timeRemaining.days },
                    { label: 'Hours', value: timeRemaining.hours },
                    { label: 'Minutes', value: timeRemaining.minutes },
                    { label: 'Seconds', value: timeRemaining.seconds },
                  ].map((item) => (
                    <div key={item.label} className="bg-zinc-900 border border-emerald-500/30 rounded-lg p-4 min-w-20">
                      <div className="text-2xl sm:text-3xl font-bold text-emerald-400">
                        {String(item.value).padStart(2, '0')}
                      </div>
                      <div className="text-xs text-zinc-400 mt-2">{item.label}</div>
                    </div>
                  ))}
                </div>
                <p className="text-emerald-400 text-sm font-semibold">Don't miss out!</p>
              </div>
            )}

            {isExpired && (
              <div className="mb-12 p-6 bg-red-600/20 border border-red-500/30 rounded-lg">
                <p className="text-red-300 font-semibold">This offer has ended. Thank you to all who participated!</p>
              </div>
            )}

            <Link href="/signup" className="inline-block">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white text-lg px-8 py-6 h-auto">
                Claim Your Lifetime Deal
                <ChevronRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
          </div>

          {/* Main Offer Card */}
          <div className="max-w-2xl mx-auto mb-16">
            <div className="bg-gradient-to-br from-emerald-600/20 to-emerald-500/10 border border-emerald-500/30 rounded-2xl p-8 sm:p-12">
              <div className="grid grid-cols-2 gap-8 mb-8">
                <div>
                  <p className="text-zinc-400 text-sm mb-2">One-time payment</p>
                  <p className="text-4xl sm:text-5xl font-bold text-emerald-400">$149</p>
                </div>
                <div>
                  <p className="text-zinc-400 text-sm mb-2">Forever access to</p>
                  <p className="text-2xl sm:text-3xl font-bold text-white">Pro Plan</p>
                </div>
              </div>

              <div className="border-t border-emerald-500/30 pt-8">
                <h3 className="text-lg font-bold text-white mb-6">What's Included:</h3>
                <ul className="space-y-4">
                  {features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      <Check className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                      <span className="text-zinc-200">{feature}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t border-emerald-500/30 mt-8 pt-8">
                <p className="text-sm text-zinc-400 text-center">
                  Plus all future Pro plan improvements at no additional cost.
                </p>
              </div>
            </div>
          </div>

          {/* Cost Comparison */}
          <div className="max-w-3xl mx-auto mb-16">
            <h2 className="text-2xl sm:text-3xl font-bold text-center text-white mb-8">
              Why This Deal Makes Sense
            </h2>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {comparisons.map((item, idx) => (
                <div
                  key={idx}
                  className={`p-6 rounded-lg border ${
                    item.lifetime
                      ? 'bg-emerald-600/20 border-emerald-500/30'
                      : 'bg-zinc-900/50 border-zinc-800'
                  }`}
                >
                  <p className={`text-sm font-semibold mb-2 ${item.lifetime ? 'text-emerald-300' : 'text-zinc-400'}`}>
                    {item.item}
                  </p>
                  <p className={`text-2xl font-bold ${item.lifetime ? 'text-emerald-400' : 'text-zinc-300'}`}>
                    {item.value}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-8 p-6 bg-zinc-900/50 border border-zinc-800 rounded-lg">
              <p className="text-zinc-300 text-center">
                <span className="font-bold text-emerald-400">In just 4 months</span>, the lifetime deal pays for itself compared to annual billing. After that, you're saving forever.
              </p>
            </div>
          </div>

          {/* FAQ Section */}
          <div className="max-w-2xl mx-auto mb-16">
            <h2 className="text-2xl sm:text-3xl font-bold text-center text-white mb-8">
              Frequently Asked Questions
            </h2>

            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white mb-2">Is this a limited quantity offer?</h3>
                <p className="text-zinc-400">
                  The lifetime deal is available for 30 days from our launch date (July 19, 2026). It's first-come, first-served. Once the 30 days end, the offer is no longer available.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">Can I really use this forever?</h3>
                <p className="text-zinc-400">
                  Yes! Once you purchase the lifetime deal, you have permanent access to Pro plan features. If we ever discontinue Lengrowth Outreach, you'll receive a refund of any unused credit or prorated amount. This is a real, genuine lifetime offer.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">What if I already have a subscription?</h3>
                <p className="text-zinc-400">
                  If you purchase the lifetime deal, we'll credit any remaining time on your current subscription toward the $149 payment. You'll then switch to the lifetime deal immediately.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">Are there any hidden fees?</h3>
                <p className="text-zinc-400">
                  No. The $149 is a one-time payment. The only additional cost would be the optional cloud add-on ($39/profile/month) if you choose to use cloud-based execution instead of your desktop.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">What if the price increases for Pro?</h3>
                <p className="text-zinc-400">
                  Your lifetime deal is locked in forever at Pro plan features. If we raise Pro pricing for new customers, your access doesn't change—you still pay nothing additional.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">Can I get a refund?</h3>
                <p className="text-zinc-400">
                  Lifetime deals are non-refundable. However, if you haven't used the Service yet, contact support@lengrowth.com within 14 days for a full refund.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">Will I still get updates and support?</h3>
                <p className="text-zinc-400">
                  Yes! You'll receive all Pro plan updates, new features, and priority email support. You're a lifetime customer—we want to make sure you have a great experience.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-bold text-white mb-2">What about LinkedIn account limits?</h3>
                <p className="text-zinc-400">
                  Your lifetime deal includes Pro plan features: 1 LinkedIn account. If you want to upgrade to Business (3 accounts) or Agency (10+ accounts), you would need to pay the difference between Pro and those plans.
                </p>
              </div>
            </div>
          </div>

          {/* Terms Section */}
          <div className="max-w-2xl mx-auto mb-16 p-6 bg-zinc-900/50 border border-zinc-800 rounded-lg">
            <h3 className="text-lg font-bold text-white mb-4">Lifetime Deal Terms</h3>
            <ul className="space-y-2 text-sm text-zinc-400">
              <li>✓ Non-transferable: Cannot be sold, gifted, or transferred to another account</li>
              <li>✓ Non-refundable: Once purchased, no refunds (except within 14 days of signup if not yet used)</li>
              <li>✓ Includes Pro plan features forever</li>
              <li>✓ LinkedIn account limit: 1 (Pro plan limit)</li>
              <li>✓ Priority support via email</li>
              <li>✓ Excludes cloud add-on (can be purchased separately at $39/profile/month)</li>
              <li>✓ Valid only during the 30-day promotional period</li>
            </ul>
          </div>

          {/* CTA Section */}
          <div className="max-w-2xl mx-auto mb-16 text-center">
            <h2 className="text-3xl sm:text-4xl font-bold text-white mb-6">
              Ready to Secure Pro Forever?
            </h2>
            <p className="text-xl text-zinc-400 mb-8">
              Lock in unlimited campaigns, AI features, and priority support for $149. One-time payment. Forever access.
            </p>
            <Link href="/signup">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white text-lg px-8 py-6 h-auto mb-4">
                Claim Lifetime Deal Now
                <Zap className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <p className="text-zinc-500 text-sm">
              <Clock className="inline h-4 w-4 mr-1" />
              {isExpired ? 'This offer has ended.' : 'Offer expires in 30 days from launch.'}
            </p>
          </div>

          {/* Comparison with Regular Pricing */}
          <div className="max-w-3xl mx-auto p-8 bg-gradient-to-br from-zinc-900/50 to-zinc-800/50 border border-zinc-800 rounded-xl">
            <h3 className="text-lg font-bold text-white mb-6 text-center">How It Compares</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <p className="text-zinc-400 text-sm mb-2">Monthly (Pro)</p>
                <p className="text-3xl font-bold text-white">$49</p>
                <p className="text-zinc-500 text-xs mt-2">Recurring each month</p>
              </div>
              <div>
                <p className="text-zinc-400 text-sm mb-2">Annual (Pro)</p>
                <p className="text-3xl font-bold text-white">$41</p>
                <p className="text-zinc-500 text-xs mt-2">Per month, paid yearly</p>
              </div>
              <div className="bg-emerald-600/20 border border-emerald-500/30 rounded-lg p-4">
                <p className="text-emerald-300 text-sm mb-2 font-semibold">Lifetime (This Deal)</p>
                <p className="text-3xl font-bold text-emerald-400">$149</p>
                <p className="text-emerald-200 text-xs mt-2">One-time payment</p>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
