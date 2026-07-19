'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ChevronRight } from 'lucide-react';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';

export default function TermsPage() {
  const lastUpdated = '2026-07-19';

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      <article className="py-16 sm:py-24">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl">
          <div className="mb-12">
            <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">Terms of Service</h1>
            <p className="text-zinc-400">Last updated: {lastUpdated}</p>
          </div>

          <div className="prose prose-invert max-w-none space-y-8 text-zinc-300">
            {/* Introduction */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">1. Acceptance of Terms</h2>
              <p>
                By accessing and using Lengrowth Outreach ("Service"), you agree to be bound by these Terms of Service. If you do not agree to any part of these terms, you may not use the Service. We reserve the right to modify these terms at any time, and your continued use of the Service constitutes acceptance of any such modifications.
              </p>
            </section>

            {/* Service Description */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">2. Service Description</h2>
              <p>
                Lengrowth Outreach is a LinkedIn automation platform that enables users to manage LinkedIn profiles, create campaigns, automate messaging, and generate analytics. The Service includes:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>LinkedIn account connectivity and management</li>
                <li>Campaign creation and automation</li>
                <li>AI-powered message composition and follow-ups</li>
                <li>Analytics and reporting</li>
                <li>Team collaboration and workspace management (depending on plan)</li>
                <li>Desktop and cloud-based execution options</li>
              </ul>
              <p className="mt-4">
                The Service is provided "as is" without warranties of any kind, express or implied. We do not guarantee any specific results, uptime, or performance metrics.
              </p>
            </section>

            {/* User Obligations */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">3. User Obligations</h2>
              <p>You agree to use the Service in compliance with all applicable laws and regulations. Specifically, you agree NOT to:</p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Violate LinkedIn's Terms of Service or User Agreement</li>
                <li>Use the Service to send spam, harassment, or unwanted bulk messages</li>
                <li>Create fake or fraudulent LinkedIn accounts or profiles</li>
                <li>Impersonate another person or entity</li>
                <li>Attempt to gain unauthorized access to the Service or linked accounts</li>
                <li>Reverse engineer, decompile, or attempt to extract the source code</li>
                <li>Use the Service for illegal activities or to facilitate illegal conduct</li>
                <li>Scrape, crawl, or systematically download data outside the normal use of the Service</li>
                <li>Exploit or abuse any technical vulnerabilities</li>
                <li>Interfere with the operation or security of the Service</li>
              </ul>
              <p className="mt-4">
                You are solely responsible for maintaining the confidentiality of your LinkedIn credentials and for all activities that occur under your account. You agree to notify us immediately of any unauthorized use of your account.
              </p>
            </section>

            {/* Payment and Billing */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">4. Payment and Billing Terms</h2>
              <p>
                <strong>Subscription Plans:</strong> All subscription plans renew automatically on a monthly or annual basis, depending on your selection. You authorize us to charge the payment method on file each billing cycle.
              </p>
              <p className="mt-4">
                <strong>Free Trial:</strong> New users receive a 3-day free trial of the Pro plan. The trial requires a valid payment method but will not be charged during the trial period. Your subscription will automatically begin at the end of the trial unless canceled.
              </p>
              <p className="mt-4">
                <strong>Cancellation:</strong> You may cancel your subscription at any time through your account settings. Cancellation takes effect at the end of your current billing period. No refunds are provided for partial months or unused portions of your subscription.
              </p>
              <p className="mt-4">
                <strong>Refunds:</strong> Refunds are not available after 14 days of purchase. If you believe you are entitled to a refund, contact support@lengrowth.com within 14 days of your charge.
              </p>
              <p className="mt-4">
                <strong>Price Changes:</strong> We may change subscription prices at any time, but we will notify you at least 30 days in advance. Your continued use of the Service after the price change constitutes acceptance.
              </p>
              <p className="mt-4">
                <strong>Taxes:</strong> All prices exclude applicable taxes (sales tax, VAT, etc.). You are responsible for paying any taxes owed on your purchases.
              </p>
            </section>

            {/* Intellectual Property */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">5. Intellectual Property Rights</h2>
              <p>
                The Service, including all content, features, and functionality (including but not limited to all information, software, text, displays, images, video, and audio), is owned by Lengrowth, its licensors, or other providers of such material and is protected by United States and international copyright, trademark, patent, and other intellectual property laws.
              </p>
              <p className="mt-4">
                You are granted a limited, non-exclusive, non-transferable license to access and use the Service for your personal or internal business purposes. This license does not permit you to sell, resell, or transfer the Service to others. You may not modify, copy, distribute, transmit, display, perform, reproduce, publish, license, create derivative works from, transfer, or sell any information obtained from the Service.
              </p>
              <p className="mt-4">
                Your content (messages, campaigns, uploaded files) remains your property. By using the Service, you grant us a non-exclusive, royalty-free license to use, reproduce, modify, and distribute your content solely to provide the Service to you.
              </p>
            </section>

            {/* Limitation of Liability */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">6. Limitation of Liability</h2>
              <p>
                <strong>LinkedIn Account Restrictions:</strong> LinkedIn maintains strict policies against automation and may restrict, suspend, or ban accounts that use automation tools. By using Lengrowth Outreach, you assume all risk of LinkedIn account restrictions, suspensions, or permanent bans. We are not responsible for any such actions taken by LinkedIn. You are solely responsible for your compliance with LinkedIn's Terms of Service.
              </p>
              <p className="mt-4">
                <strong>Disclaimer:</strong> TO THE FULLEST EXTENT PERMITTED BY LAW, LENGROWTH SHALL NOT BE LIABLE FOR:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Any indirect, incidental, special, consequential, or punitive damages</li>
                <li>Loss of profits, revenue, data, or business opportunities</li>
                <li>Loss of use or interruption of service</li>
                <li>Any damages arising from unauthorized access to or alteration of your account</li>
                <li>Any damages arising from third-party actions, including LinkedIn's actions</li>
              </ul>
              <p className="mt-4">
                THE TOTAL LIABILITY OF LENGROWTH, WHETHER IN CONTRACT, TORT, OR OTHERWISE, SHALL NOT EXCEED THE AMOUNT YOU PAID FOR THE SERVICE IN THE TWELVE MONTHS PRECEDING THE EVENT GIVING RISE TO LIABILITY.
              </p>
            </section>

            {/* Data and Privacy */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">7. Data and Privacy</h2>
              <p>
                Your use of the Service is subject to our Privacy Policy, which is incorporated by reference into these Terms. Please review our Privacy Policy to understand our practices regarding data collection and usage.
              </p>
              <p className="mt-4">
                <strong>LinkedIn Credentials:</strong> Your LinkedIn credentials are encrypted and stored securely. We will never share your credentials with third parties without your explicit consent, except as necessary to provide the Service.
              </p>
              <p className="mt-4">
                <strong>Data Retention:</strong> Upon account deletion, we will delete your personal data within 30 days. LinkedIn profile data, messages, and campaign data will be deleted immediately. However, aggregated and anonymized data may be retained for analytics purposes.
              </p>
            </section>

            {/* Termination */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">8. Termination</h2>
              <p>
                We may suspend or terminate your access to the Service at any time, with or without cause, and with or without notice. Reasons for termination include, but are not limited to:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Violation of these Terms of Service</li>
                <li>Violation of LinkedIn's Terms of Service</li>
                <li>Use of the Service for illegal purposes or to facilitate harm</li>
                <li>Non-payment of subscription fees</li>
                <li>Abuse or harassment of other users or support staff</li>
              </ul>
              <p className="mt-4">
                Upon termination, your right to use the Service ceases immediately. We will not be liable to you or any third party for any claims arising out of any suspension or termination of your account.
              </p>
            </section>

            {/* Third-Party Services */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">9. Third-Party Services</h2>
              <p>
                The Service may integrate with or rely on third-party services, including but not limited to:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li><strong>Stripe:</strong> Payment processing and billing management</li>
                <li><strong>LinkedIn:</strong> Account connectivity and data access</li>
                <li><strong>LLM Providers:</strong> AI message generation (OpenAI, Anthropic, Google, others)</li>
              </ul>
              <p className="mt-4">
                You are subject to the terms and privacy policies of these third-party services. We are not responsible for the actions, policies, or content of third-party services.
              </p>
            </section>

            {/* User Representations */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">10. User Representations</h2>
              <p>
                You represent and warrant that:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>You have the legal capacity to enter into this agreement</li>
                <li>You own or control all LinkedIn accounts connected to your Lengrowth account</li>
                <li>You have obtained all necessary permissions to use those accounts with automation tools</li>
                <li>Your use of the Service complies with all applicable laws and regulations</li>
                <li>You will not use the Service to infringe on the rights of any third party</li>
              </ul>
            </section>

            {/* Dispute Resolution */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">11. Dispute Resolution</h2>
              <p>
                <strong>Governing Law:</strong> These Terms shall be governed by and construed in accordance with the laws of the State of Delaware, without regard to its conflict of law provisions.
              </p>
              <p className="mt-4">
                <strong>Arbitration:</strong> Any dispute arising out of or relating to these Terms or your use of the Service shall be resolved by binding arbitration administered by the American Arbitration Association (AAA) under its Commercial Arbitration Rules. The arbitration shall take place in Wilmington, Delaware. Each party shall bear its own costs of arbitration, though the AAA may require cost-sharing in accordance with its rules.
              </p>
              <p className="mt-4">
                <strong>Informal Resolution:</strong> Before initiating arbitration, you agree to attempt to resolve the dispute informally by contacting support@lengrowth.com.
              </p>
            </section>

            {/* Severability */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">12. Severability</h2>
              <p>
                If any provision of these Terms is found to be invalid or unenforceable, that provision shall be severed, and the remaining provisions shall continue in full force and effect.
              </p>
            </section>

            {/* Entire Agreement */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">13. Entire Agreement</h2>
              <p>
                These Terms, together with our Privacy Policy and any other policies posted on the Service, constitute the entire agreement between you and Lengrowth regarding your use of the Service, and supersede all prior agreements and understandings, whether written or oral.
              </p>
            </section>

            {/* Contact */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">14. Contact Us</h2>
              <p>
                If you have any questions about these Terms of Service, please contact us at:
              </p>
              <p className="mt-4 font-mono text-emerald-400">support@lengrowth.com</p>
            </section>
          </div>

          {/* Bottom CTA */}
          <div className="mt-12 p-8 bg-zinc-900/50 border border-zinc-800 rounded-xl text-center">
            <h3 className="text-xl font-bold text-white mb-2">Ready to get started?</h3>
            <p className="text-zinc-400 mb-4">Start your free 3-day Pro trial today. No credit card required to cancel.</p>
            <Link href="/signup">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
                Start Free Trial
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          {/* Navigation Links */}
          <div className="mt-8 flex justify-center gap-4 text-sm">
            <Link href="/privacy" className="text-emerald-400 hover:text-emerald-300">
              Privacy Policy
            </Link>
            <span className="text-zinc-600">•</span>
            <Link href="/pricing" className="text-emerald-400 hover:text-emerald-300">
              Pricing
            </Link>
          </div>
        </div>
      </article>

      <Footer />
    </div>
  );
}
