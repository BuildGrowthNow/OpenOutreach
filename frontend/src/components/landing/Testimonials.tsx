'use client';

import Image from 'next/image';

export function Testimonials() {
  const testimonials = [
    {
      name: 'Sarah Johnson',
      role: 'Sales Director at TechFlow',
      avatar: 'https://i.pravatar.cc/150?u=sarah',
      content: 'Lengrowth has transformed our outbound sales strategy. We\'re seeing a 3x increase in response rates and our pipeline has never been stronger. The AI-powered messaging is spot on!',
    },
    {
      name: 'Michael Chen',
      role: 'Founder, GrowthBoost',
      avatar: 'https://i.pravatar.cc/150?u=michael',
      content: 'As a startup founder, time is everything. Lengrowth automates my LinkedIn presence so I can focus on actual conversations. The analytics help me optimize every campaign.',
    },
    {
      name: 'Elena Rodriguez',
      role: 'B2B Marketing Manager',
      avatar: 'https://i.pravatar.cc/150?u=elena',
      content: 'The safety features give me peace of mind while the automation works wonders. I\'ve generated over 200 qualified leads in just three months. Highly recommend!',
    },
  ];

  return (
    <section id="testimonials" className="py-20 sm:py-32 bg-zinc-950">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-white sm:text-4xl mb-4">
            Trusted by <span className="text-emerald-400">Growth-focused Professionals</span>
          </h2>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto">
            Join thousands of sales professionals and businesses scaling their LinkedIn presence
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((t, index) => (
            <div key={index} className="bg-zinc-900/50 border border-zinc-800 p-8 rounded-2xl hover:border-emerald-500/30 transition-colors">
              <div className="flex items-center gap-4 mb-6">
                <Image src={t.avatar} alt={t.name} width={48} height={48} className="w-12 h-12 rounded-full object-cover ring-2 ring-emerald-500/20" />
                <div>
                  <div className="font-semibold text-white">{t.name}</div>
                  <div className="text-sm text-zinc-500">{t.role}</div>
                </div>
              </div>
              <div className="text-zinc-300 leading-relaxed italic">
                "{t.content}"
              </div>
              <div className="mt-6 flex gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <svg key={star} className="w-5 h-5 text-emerald-500 fill-current" viewBox="0 0 24 24">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                  </svg>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}