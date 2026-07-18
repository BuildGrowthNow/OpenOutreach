'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, ArrowRight, Sparkles } from 'lucide-react';
import { useAuthStore } from '@/lib/authStore';

interface CreateCampaignWizardProps {
  onSuccess?: (campaignId: string) => void;
  onCancel?: () => void;
}

export function CreateCampaignWizard({ onSuccess, onCancel }: CreateCampaignWizardProps) {
  const router = useRouter();
  const session = useAuthStore((state) => state.session);

  const [name, setName] = useState('');
  const [productPitch, setProductPitch] = useState('');
  const [campaignObjective, setCampaignObjective] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!name.trim()) {
      setError('Campaign name is required');
      return;
    }

    if (!productPitch.trim()) {
      setError('Please describe what problem you solve');
      return;
    }

    if (!campaignObjective.trim()) {
      setError('Please describe your campaign goal');
      return;
    }

    try {
      setSubmitting(true);

      const response = await fetch('/api/campaigns', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          name: name.trim(),
          product_pitch: productPitch.trim(),
          campaign_objective: campaignObjective.trim(),
          // Defaults - user can configure in settings
          velocity: 20,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create campaign');
      }

      const campaign = await response.json();

      // Success - redirect to campaign settings for configuration
      if (onSuccess) {
        onSuccess(campaign.id);
      } else {
        router.push(`/campaigns/${campaign.id}`);
      }
    } catch (err: any) {
      console.error('Failed to create campaign:', err);
      setError(err.message || 'Failed to create campaign');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-1 text-center pb-2">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/20 mb-3">
          <Sparkles className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <h2 className="text-2xl font-semibold">Create Campaign</h2>
        <p className="text-sm text-muted-foreground">
          Get started in 3 quick steps. Configure targeting & pacing after creation.
        </p>
      </div>

      <div className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="name" className="text-base">
            1. Campaign Name
          </Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., B2B SaaS Founders Q1 2026"
            className="text-base h-11"
            autoFocus
            required
          />
          <p className="text-xs text-muted-foreground">
            Choose a memorable name for internal tracking
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="pitch" className="text-base">
            2. What Problem Do You Solve?
          </Label>
          <Textarea
            id="pitch"
            value={productPitch}
            onChange={(e) => setProductPitch(e.target.value)}
            placeholder="Example: We help SaaS founders automate their outbound sales so they can focus on product instead of cold emails."
            rows={3}
            className="text-base resize-none"
            required
          />
          <p className="text-xs text-muted-foreground">
            This helps AI personalize your messages
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="objective" className="text-base">
            3. Campaign Goal
          </Label>
          <Textarea
            id="objective"
            value={campaignObjective}
            onChange={(e) => setCampaignObjective(e.target.value)}
            placeholder="Example: Book 20 qualified demos with founders who spend >$5k/month on outbound sales tools."
            rows={3}
            className="text-base resize-none"
            required
          />
          <p className="text-xs text-muted-foreground">
            Be specific about what success looks like
          </p>
        </div>
      </div>

      <div className="flex gap-3 pt-4 border-t">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} className="flex-1">
            Cancel
          </Button>
        )}
        <Button
          type="submit"
          disabled={submitting}
          className="flex-1 h-11 text-base gap-2"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating Campaign...
            </>
          ) : (
            <>
              Create & Configure
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>

      <div className="text-xs text-center text-muted-foreground pt-2">
        After creation, you'll configure targeting, pacing, and LinkedIn profile
      </div>
    </form>
  );
}
