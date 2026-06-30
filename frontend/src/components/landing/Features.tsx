'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Zap, Users, TrendingUp, LayoutTemplate, Mail, MessageSquare, Clock, Target, BarChart, Shield } from 'lucide-react';

interface Feature {
  icon: React.ElementType;
  title: string;
  description: string;
}

const features: Feature[] = [
  {
    icon: Zap,
    title: 'Smart Automation',
    description: 'Automate your LinkedIn outreach with intelligent workflows that adapt to responses and engagement patterns.',
  },
  {
    icon: Users,
    title: 'Audience Targeting',
    description: 'Find and connect with the right prospects using advanced filters for industry, role, company size, and more.',
  },
  {
    icon: Mail,
    title: 'Multi-Channel Engagement',
    description: 'Manage LinkedIn InMail, connection requests, and personalized messages from one unified dashboard.',
  },
  {
    icon: MessageSquare,
    title: 'AI-Powered Messaging',
    description: 'Generate compelling messages with AI assistance while maintaining authenticity and brand voice.',
  },
  {
    icon: Clock,
    title: 'Optimal Timing',
    description: 'Our algorithm determines the best time to send messages for maximum response rates.',
  },
  {
    icon: Target,
    title: 'Lead Scoring',
    description: 'Prioritize your leads based on engagement levels and response probability.',
  },
  {
    icon: BarChart,
    title: 'Advanced Analytics',
    description: 'Track campaign performance with detailed metrics and actionable insights.',
  },
  {
    icon: Shield,
    title: 'Safe & Secure',
    description: 'Built-in rate limiting and safety features to protect your LinkedIn reputation.',
  },
  {
    icon: LayoutTemplate,
    title: 'Smart Sequences',
    description: 'Create multi-step follow-up sequences that nurture leads through the sales funnel.',
  },
  {
    icon: TrendingUp,
    title: 'Growth Tracking',
    description: 'Monitor your connection growth and engagement metrics over time.',
  },
  {
    icon: Mail,
    title: 'Email Integration',
    description: 'Sync your LinkedIn conversations with your email for seamless follow-up.',
  },
  {
    icon: Zap,
    title: 'Connects with Your Tools',
    description: 'Easily connect Lengrowth with your CRM and other business tools.',
  },
];

export function Features() {
  return (
    <section id="features" className="py-20 sm:py-32 bg-zinc-950 relative">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-white sm:text-4xl mb-4">
            Everything You Need to <br />
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-200 bg-clip-text text-transparent">
              Scale Your LinkedIn Growth
            </span>
          </h2>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto">
            Powered by advanced AI and designed for efficiency.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
           {features.map((feature, index) => (
              <Card key={index} className="bg-zinc-900/50 border-zinc-800 ring-0 hover:border-zinc-700 transition-all duration-300 hover:shadow-lg hover:shadow-zinc-900/10">
               <CardHeader>
                 <div className="flex items-center gap-3 mb-3">
                   <div className="p-2 bg-zinc-800 rounded-lg text-emerald-400">
                     <feature.icon className="h-6 w-6" />
                   </div>
                 </div>
                 <CardTitle className="text-xl text-white">{feature.title}</CardTitle>
               </CardHeader>
              <CardContent>
                <CardDescription className="text-zinc-400">
                  {feature.description}
                </CardDescription>
              </CardContent>
            </Card>
          ))}
        </div>

        <div className="mt-20 text-center">
          <Button className="bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/25">
            View All Features
          </Button>
        </div>
      </div>
    </section>
  );
}