'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2 } from 'lucide-react';

interface LinkedInProfile {
  id: string;
  linkedin_username: string;
  active: boolean;
  has_cookies: boolean;
}

interface CreateCampaignFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function CreateCampaignForm({ onSuccess, onCancel }: CreateCampaignFormProps) {
  const router = useRouter();
  const { getHeaders } = useAuthStore();

  const [profiles, setProfiles] = useState<LinkedInProfile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);

  const [name, setName] = useState('');
  const [productPitch, setProductPitch] = useState('');
  const [campaignObjective, setCampaignObjective] = useState('');
  const [selectedProfileId, setSelectedProfileId] = useState('');
  const [bookingLink, setBookingLink] = useState('');
  const [velocity, setVelocity] = useState('20');

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProfiles();
  }, []);

  const loadProfiles = async () => {
    try {
      setLoadingProfiles(true);
      const response = await fetch('/api/linkedin-profiles', {
        headers: getHeaders(),
      });

      if (!response.ok) {
        throw new Error('Failed to load profiles');
      }

      const data = await response.json();
      setProfiles(data.profiles || []);

      // Auto-select first profile if available
      if (data.profiles && data.profiles.length > 0) {
        setSelectedProfileId(data.profiles[0].id);
      }
    } catch (err) {
      console.error('Failed to load profiles:', err);
      setError('Failed to load LinkedIn profiles. Please add one in Settings.');
    } finally {
      setLoadingProfiles(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!name || !productPitch || !campaignObjective || !selectedProfileId) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      setSubmitting(true);

      const response = await fetch('/api/campaigns', {
        method: 'POST',
        headers: {
          ...getHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          product_pitch: productPitch,
          campaign_objective: campaignObjective,
          linkedin_profile_id: selectedProfileId,
          booking_link: bookingLink,
          velocity: parseInt(velocity, 10),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create campaign');
      }

      const campaign = await response.json();

      // Success
      if (onSuccess) {
        onSuccess();
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

  if (loadingProfiles) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (profiles.length === 0) {
    return (
      <Alert className="bg-yellow-50 border-yellow-200">
        <AlertDescription className="text-yellow-800">
          ⚠️ No LinkedIn profiles found. Please{' '}
          <a href="/settings" className="underline font-medium">
            add a LinkedIn profile in Settings
          </a>{' '}
          before creating a campaign.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-4">
        <div>
          <Label htmlFor="profile">
            LinkedIn Profile <span className="text-red-500">*</span>
          </Label>
          <Select value={selectedProfileId} onValueChange={(v) => setSelectedProfileId(v ?? "")}>
            <SelectTrigger id="profile" className="w-full">
              <SelectValue placeholder="Select profile..." />
            </SelectTrigger>
            <SelectContent>
              {profiles.map((profile) => (
                <SelectItem key={profile.id} value={profile.id}>
                  {profile.linkedin_username}
                  {!profile.has_cookies && ' ⚠️ No cookies'}
                  {!profile.active && ' (Inactive)'}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-sm text-gray-500 mt-1">
            Which LinkedIn profile will execute this campaign
          </p>
        </div>

        <div>
          <Label htmlFor="name">
            Campaign Name <span className="text-red-500">*</span>
          </Label>
          <Input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., SaaS Founders Outreach"
            required
          />
        </div>

        <div>
          <Label htmlFor="pitch">
            Product Pitch <span className="text-red-500">*</span>
          </Label>
          <Textarea
            id="pitch"
            value={productPitch}
            onChange={(e) => setProductPitch(e.target.value)}
            placeholder="What problem does your product solve?"
            rows={3}
            required
          />
        </div>

        <div>
          <Label htmlFor="objective">
            Campaign Objective <span className="text-red-500">*</span>
          </Label>
          <Textarea
            id="objective"
            value={campaignObjective}
            onChange={(e) => setCampaignObjective(e.target.value)}
            placeholder="What's the goal of this campaign?"
            rows={3}
            required
          />
        </div>

        <div>
          <Label htmlFor="booking">Booking Link (Optional)</Label>
          <Input
            id="booking"
            type="url"
            value={bookingLink}
            onChange={(e) => setBookingLink(e.target.value)}
            placeholder="https://calendly.com/your-link"
          />
          <p className="text-sm text-gray-500 mt-1">
            Calendar link for scheduling calls
          </p>
        </div>

        <div>
          <Label htmlFor="velocity">
            Velocity (connections per day)
          </Label>
          <Input
            id="velocity"
            type="number"
            min="5"
            max="50"
            value={velocity}
            onChange={(e) => setVelocity(e.target.value)}
            required
          />
          <p className="text-sm text-gray-500 mt-1">
            Recommended: 15-25 for safe automation
          </p>
        </div>
      </div>

      <div className="flex gap-3 pt-4 border-t">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={submitting} className="flex-1">
          {submitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating...
            </>
          ) : (
            'Create Campaign'
          )}
        </Button>
      </div>
    </form>
  );
}
