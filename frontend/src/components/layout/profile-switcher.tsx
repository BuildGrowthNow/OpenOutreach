'use client';

import { useState, useEffect, useCallback } from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/apiClientV2';

interface LinkedInProfile {
  id: string;
  linkedin_username: string;
  active: boolean;
  has_cookies: boolean;
  connect_daily_limit: number;
  follow_up_daily_limit: number;
}

export function ProfileSwitcher() {
  const [profiles, setProfiles] = useState<LinkedInProfile[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

  const loadProfiles = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const response = await apiClient.get<{ profiles: LinkedInProfile[]; count: number }>('/linkedin-profiles');

      if (response.error || !response.data) {
        throw new Error(response.error || 'Failed to load profiles');
      }

      const data = response.data;
      setProfiles(data.profiles || []);

      // Load saved selection or use first profile
      const saved = localStorage.getItem('selected_profile_id');
      if (saved && data.profiles?.find((p: LinkedInProfile) => p.id === saved)) {
        setSelectedId(saved);
      } else if (data.profiles?.length > 0) {
        const firstId = data.profiles[0].id;
        setSelectedId(firstId);
        localStorage.setItem('selected_profile_id', firstId);
      }
    } catch (err) {
      console.error('Failed to load profiles:', err);
      setError('Failed to load LinkedIn profiles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  const handleProfileChange = (profileId: string) => {
    setSelectedId(profileId);
    localStorage.setItem('selected_profile_id', profileId);
    // Reload page to reflect profile change
    window.location.reload();
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading profiles...
      </div>
    );
  }

  if (error) {
    return (
      <a href="/settings?tab=linkedin-credentials" className="inline-flex items-center gap-1.5 text-xs text-amber-500 hover:text-amber-400">
        <span>⚠️ Connect your profile</span>
      </a>
    );
  }

  if (profiles.length === 0) {
    return (
      <a href="/settings?tab=linkedin-credentials" className="inline-flex items-center gap-1.5 text-xs text-amber-500 hover:text-amber-400">
        <span>⚠️ Connect your profile</span>
      </a>
    );
  }

  if (profiles.length === 1) {
    const profile = profiles[0];
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-600">Profile:</span>
        <span className="font-medium">{profile.linkedin_username}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-600">Profile:</span>
      <Select value={selectedId} onValueChange={(v) => v && handleProfileChange(v)}>
        <SelectTrigger className="w-[200px]">
          <SelectValue placeholder="Select profile" />
        </SelectTrigger>
        <SelectContent>
          {profiles.map((profile) => (
            <SelectItem key={profile.id} value={profile.id}>
              {profile.linkedin_username}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
