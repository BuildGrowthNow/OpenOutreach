'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ChevronRight } from 'lucide-react';
import { Navbar } from '@/components/landing/Navbar';
import { Footer } from '@/components/landing/Footer';

export default function PrivacyPage() {
  const lastUpdated = '2026-07-19';

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <Navbar />

      <article className="py-16 sm:py-24">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 max-w-3xl">
          <div className="mb-12">
            <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4">Privacy Policy</h1>
            <p className="text-zinc-400">Last updated: {lastUpdated}</p>
          </div>

          <div className="prose prose-invert max-w-none space-y-8 text-zinc-300">
            {/* Introduction */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">1. Introduction</h2>
              <p>
                Lengrowth Outreach ("we," "us," "our," or "Company") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our Service, including our website and associated applications.
              </p>
              <p className="mt-4">
                Please read this Privacy Policy carefully. If you do not agree with our policies and practices, please do not use our Service. By accessing and using the Service, you acknowledge that you have read, understood, and agree to be bound by this Privacy Policy.
              </p>
            </section>

            {/* Information We Collect */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">2. Information We Collect</h2>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">2.1 Account Information</h3>
              <p>
                When you create an account, we collect:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Email address</li>
                <li>Password (hashed and encrypted)</li>
                <li>Full name</li>
                <li>Company name (optional)</li>
                <li>Phone number (optional)</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">2.2 LinkedIn Data</h3>
              <p>
                To provide the Service, we collect and store:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li><strong>LinkedIn Credentials:</strong> Email and password (encrypted at rest using AES-256)</li>
                <li><strong>Session Cookies:</strong> Authentication tokens for secure API access (encrypted)</li>
                <li><strong>Profile Data:</strong> Public profile information, connections, messages, and activity</li>
                <li><strong>Account Settings:</strong> Visibility settings, notification preferences</li>
                <li><strong>Search Activity:</strong> Saved searches and filters you create within the Service</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">2.3 Campaign Data</h3>
              <p>
                We collect:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Campaign names, descriptions, and objectives</li>
                <li>Target audience profiles and search criteria</li>
                <li>Message templates and AI-generated messages</li>
                <li>Leads and contact information collected or added to campaigns</li>
                <li>Deal states and qualification status</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">2.4 Communication Data</h3>
              <p>
                We store:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Messages sent and received through the Service</li>
                <li>Chat history and conversation transcripts</li>
                <li>Voice note recordings (if you use this feature)</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">2.5 Analytics and Usage Data</h3>
              <p>
                We automatically collect:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>IP address and browser type</li>
                <li>Pages visited and actions taken</li>
                <li>Time spent on features</li>
                <li>Feature usage (which campaigns are active, messages sent, etc.)</li>
                <li>Performance metrics and error logs</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">2.6 Payment Information</h3>
              <p>
                We collect payment details through our payment processor Stripe:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Billing name and address</li>
                <li>Credit card or payment method (processed by Stripe, not stored by us)</li>
                <li>Transaction history and invoice information</li>
              </ul>
              <p className="mt-4">
                We never store full credit card details. Stripe handles all payment processing securely.
              </p>
            </section>

            {/* How We Use Information */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">3. How We Use Your Information</h2>
              <p>We use the information we collect for the following purposes:</p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Service Delivery</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>To provide, maintain, and improve the Service</li>
                <li>To process your account registration and authentication</li>
                <li>To execute automation tasks on your LinkedIn accounts</li>
                <li>To store and retrieve your campaigns, leads, and messages</li>
                <li>To generate analytics reports and insights</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Billing and Payments</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>To process subscription payments and renewals</li>
                <li>To send invoices and billing notifications</li>
                <li>To track subscription status and plan limits</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Communication</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>To send account notifications (trial ending, payment failed, etc.)</li>
                <li>To respond to support requests</li>
                <li>To send product updates and feature announcements</li>
                <li>To send marketing emails (with unsubscribe option)</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Product Improvement</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>To analyze usage patterns and feature adoption</li>
                <li>To identify and fix bugs and performance issues</li>
                <li>To develop new features and improvements</li>
                <li>To train our AI models for better message generation</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Security and Compliance</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>To detect and prevent fraud, abuse, and security incidents</li>
                <li>To enforce our Terms of Service</li>
                <li>To comply with legal obligations and court orders</li>
              </ul>
            </section>

            {/* Data Storage and Security */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">4. Data Storage and Security</h2>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Storage Location</h3>
              <p>
                Your data is stored in MongoDB Atlas, hosted on Amazon Web Services (AWS) in the United States. We use encrypted connections (TLS 1.3+) for all data in transit.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Encryption</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li><strong>At Rest:</strong> LinkedIn credentials and sensitive data encrypted with AES-256</li>
                <li><strong>In Transit:</strong> All communications protected with TLS 1.3 or higher</li>
                <li><strong>Password:</strong> Your password is hashed using bcrypt with salt</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Access Controls</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Only authorized employees can access user data (with audit logging)</li>
                <li>All admin access is multi-factor authenticated</li>
                <li>Data is isolated by user (multi-tenant architecture with strict isolation)</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Security Measures</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Regular security audits and penetration testing</li>
                <li>Automated backups with encrypted backup storage</li>
                <li>Incident response plan and 24/7 monitoring</li>
                <li>Database authentication and network isolation</li>
              </ul>
            </section>

            {/* Third-Party Data Sharing */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">5. Third-Party Data Sharing</h2>
              <p>
                <strong>We do not sell, trade, or rent your personal information to third parties.</strong> We may share your data with the following:
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Required Sharing</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li><strong>LinkedIn:</strong> We send automation commands via LinkedIn's API (you control what data we access via OAuth scopes)</li>
                <li><strong>Stripe:</strong> Payment information for billing (Stripe is PCI DSS compliant)</li>
                <li><strong>LLM Providers:</strong> Message content sent to OpenAI, Anthropic, Google, or other AI providers for message generation (depends on your AI model choice)</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Optional Sharing</h3>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li><strong>Email Enrichment:</strong> If enabled, we share prospect emails with BetterContact for enrichment (they do not retain data)</li>
                <li><strong>Analytics:</strong> We may use aggregated, anonymized data with analytics services</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Legal Compliance</h3>
              <p>
                We may disclose your information if required by law, court order, or government request. We will notify you of such requests unless legally prohibited.
              </p>
            </section>

            {/* User Rights and Data Control */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">6. Your Data Rights</h2>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Access</h3>
              <p>
                You can access your personal data at any time by logging into your account.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Correction</h3>
              <p>
                You can update or correct your account information through your account settings.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Deletion</h3>
              <p>
                You can request deletion of your account and all associated data at any time. Upon request, we will:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Cancel your subscription immediately</li>
                <li>Delete all personal data within 30 days</li>
                <li>Remove all LinkedIn credentials and campaign data</li>
                <li>Release any LinkedIn accounts from our system</li>
              </ul>
              <p className="mt-4">
                Note: Aggregated and anonymized data may be retained for analytics and product improvement.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Data Export</h3>
              <p>
                You can request a copy of all your data in machine-readable format (JSON). Contact support@lengrowth.com to request an export.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Opt-Out</h3>
              <p>
                You can opt out of marketing emails by clicking "Unsubscribe" in any email we send. This does not apply to transactional or account-related emails (billing notifications, support responses, etc.).
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">GDPR and CCPA Compliance</h3>
              <p>
                If you are located in the European Union, you have additional rights under the General Data Protection Regulation (GDPR). If you are located in California, you have additional rights under the California Consumer Privacy Act (CCPA). Contact us to exercise these rights: support@lengrowth.com
              </p>
            </section>

            {/* Cookies and Tracking */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">7. Cookies and Tracking</h2>
              <p>
                We use cookies and similar tracking technologies to:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Maintain your login session</li>
                <li>Remember your preferences</li>
                <li>Track usage analytics</li>
                <li>Prevent fraud and abuse</li>
              </ul>
              <p className="mt-4">
                <strong>Session Cookies:</strong> These are necessary for the Service to function and are automatically cleared when you close your browser.
              </p>
              <p>
                <strong>Persistent Cookies:</strong> We use persistent cookies to remember your preferences (e.g., dashboard layout). You can disable these in your browser settings, but some features may not work properly.
              </p>
              <p>
                <strong>Third-Party Cookies:</strong> Our analytics provider may use cookies to track usage. You can opt out of this tracking in your account settings.
              </p>
            </section>

            {/* Data Retention */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">8. Data Retention</h2>
              <p>
                We retain your data for as long as your account is active and for a reasonable period afterward to comply with legal obligations and resolve disputes.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Active Accounts</h3>
              <p>
                Data is retained for the duration of your account subscription plus 30 days.
              </p>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Deleted Accounts</h3>
              <p>
                Upon account deletion request:
              </p>
              <ul className="list-disc list-inside space-y-2 ml-2">
                <li>Personal data (email, name, etc.) deleted within 30 days</li>
                <li>LinkedIn credentials and campaign data deleted immediately</li>
                <li>Chat history and messages deleted within 7 days</li>
                <li>Backups containing your data retained for 90 days (for disaster recovery)</li>
              </ul>

              <h3 className="text-lg font-semibold text-white mt-6 mb-3">Legal Hold</h3>
              <p>
                If we receive a legal request or are involved in litigation, we may retain data longer than specified above.
              </p>
            </section>

            {/* Children's Privacy */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">9. Children's Privacy</h2>
              <p>
                Our Service is not intended for children under the age of 13. We do not knowingly collect personal information from children under 13. If we become aware that a child under 13 has provided us with personal information, we will delete such information and terminate the child's account.
              </p>
            </section>

            {/* Updates to This Policy */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">10. Updates to This Policy</h2>
              <p>
                We may update this Privacy Policy from time to time. We will notify you of any material changes by posting the new Privacy Policy on the Service and updating the "Last Updated" date. Your continued use of the Service after such modifications constitutes your acceptance of the updated Privacy Policy.
              </p>
            </section>

            {/* Contact Us */}
            <section>
              <h2 className="text-2xl font-bold text-white mb-4">11. Contact Us</h2>
              <p>
                If you have questions about this Privacy Policy, your data, or our privacy practices, please contact us at:
              </p>
              <p className="mt-4 font-mono text-emerald-400">support@lengrowth.com</p>
              <p className="mt-4 text-sm text-zinc-400">
                We will respond to privacy inquiries within 30 days. For data subject requests (GDPR/CCPA), we will respond within 45 days.
              </p>
            </section>
          </div>

          {/* Bottom CTA */}
          <div className="mt-12 p-8 bg-zinc-900/50 border border-zinc-800 rounded-xl text-center">
            <h3 className="text-xl font-bold text-white mb-2">Ready to get started?</h3>
            <p className="text-zinc-400 mb-4">Start your free 7-day trial today. No credit card required.</p>
            <Link href="/signup">
              <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
                Start Free Trial
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>

          {/* Navigation Links */}
          <div className="mt-8 flex justify-center gap-4 text-sm">
            <Link href="/terms" className="text-emerald-400 hover:text-emerald-300">
              Terms of Service
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
