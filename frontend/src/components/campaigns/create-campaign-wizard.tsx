'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, ArrowRight, ArrowLeft, Sparkles, X, Plus } from 'lucide-react';
import { apiClient } from '@/lib/apiClientV2';

interface LinkedInProfile {
  id: string;
  linkedin_username: string;
}

interface WhatsAppProfile {
  id: string;
  phoneNumber?: string | null;
  displayName?: string | null;
  status: string;
}

interface CreateCampaignWizardProps {
  onSuccess?: (campaignId: string) => void;
  onCancel?: () => void;
}

export function CreateCampaignWizard({ onSuccess, onCancel }: CreateCampaignWizardProps) {
  const router = useRouter();

  // Step 1 fields
  const [name, setName] = useState('');
  const [productPitch, setProductPitch] = useState('');
  const [campaignObjective, setCampaignObjective] = useState('');
  const [profileId, setProfileId] = useState('');
  const [profiles, setProfiles] = useState<LinkedInProfile[]>([]);

  // Step 2 fields
  const [icpTitles, setIcpTitles] = useState<string[]>([]);
  const [icpInput, setIcpInput] = useState('');
  const [targetCompanySize, setTargetCompanySize] = useState('');
  const [bookingLink, setBookingLink] = useState('');

  // Step 3 fields — Channels
  const [enableWhatsApp, setEnableWhatsApp] = useState(false);
  const [waProfileId, setWaProfileId] = useState('');
  const [waMessageTemplate, setWaMessageTemplate] = useState('');
  const [waProfiles, setWaProfiles] = useState<WhatsAppProfile[]>([]);

  // Step 3 fields — Lead Source
  const [leadSource, setLeadSource] = useState<'linkedin_search' | 'google_maps' | 'csv_import'>('linkedin_search');
  const [mapsQuery, setMapsQuery] = useState('');
  const [mapsCountryCode, setMapsCountryCode] = useState('US');
  const [mapsBackends, setMapsBackends] = useState<string[]>(['google_maps', 'bing_maps', 'duckduckgo_maps']);

  // UI state
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const icpInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const load = async () => {
      const res = await apiClient.get<{ profiles: LinkedInProfile[] }>('/linkedin-profiles')
      if (res.data?.profiles?.length) {
        setProfiles(res.data.profiles)
        setProfileId(res.data.profiles[0].id)
      }
    }
    void load()
  }, [])

  useEffect(() => {
    const load = async () => {
      const res = await apiClient.get<WhatsAppProfile[]>('/whatsapp/profiles')
      const all = res.data ?? []
      const connected = all.filter(p => p.status === 'connected')
      setWaProfiles(connected)
      if (connected.length) setWaProfileId(connected[0].id)
    }
    void load()
  }, [])

  const validateStep1 = (): boolean => {
    if (!name.trim()) {
      setError('Campaign name is required');
      return false;
    }
    if (!productPitch.trim()) {
      setError('Please describe what problem you solve');
      return false;
    }
    if (!campaignObjective.trim()) {
      setError('Please describe your campaign goal');
      return false;
    }
    return true;
  };

  const handleNext = () => {
    setError('');
    if (validateStep1()) {
      setStep(2);
    }
  };

  const handleNextToChannels = () => {
    setError('');
    if (icpTitles.length === 0) {
      setError('Add at least one target job title so the AI knows who to search for');
      return;
    }
    setStep(3);
  };

  const handleAddTitle = () => {
    const title = icpInput.trim();
    if (title && !icpTitles.includes(title)) {
      setIcpTitles([...icpTitles, title]);
      setIcpInput('');
      icpInputRef.current?.focus();
    }
  };

  const handleIcpKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddTitle();
    }
  };

  const handleRemoveTitle = (title: string) => {
    setIcpTitles(icpTitles.filter(t => t !== title));
  };

  const toggleMapsBackend = (backend: string) => {
    setMapsBackends(prev =>
      prev.includes(backend) ? prev.filter(b => b !== backend) : [...prev, backend]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (leadSource === 'linkedin_search' && !profileId) {
      setError('No LinkedIn profile found. Connect your LinkedIn account in Settings first.');
      return;
    }
    if (enableWhatsApp && !waProfileId) {
      setError('Select a connected WhatsApp number or disable WhatsApp channel');
      return;
    }
    if (enableWhatsApp && !waMessageTemplate.trim()) {
      setError('Add a WhatsApp message template for the initial outreach');
      return;
    }

    const channelSequence = enableWhatsApp ? ['whatsapp', 'linkedin'] : ['linkedin'];
    const channelSettings: Record<string, unknown> = {
      linkedin: { max_attempts: 5 },
    };
    if (enableWhatsApp) {
      channelSettings.whatsapp = {
        max_attempts: 3,
        message_template: waMessageTemplate.trim(),
      };
    }

    try {
      setSubmitting(true);

      const res = await apiClient.post<{ id: string }>('/campaigns', {
        name: name.trim(),
        product_pitch: productPitch.trim(),
        campaign_objective: campaignObjective.trim(),
        linkedin_profile_id: profileId || undefined,
        booking_link: bookingLink.trim(),
        velocity: 20,
        icp_titles: icpTitles,
        target_company_size: targetCompanySize.trim() || undefined,
        channel_sequence: channelSequence,
        channel_settings: channelSettings,
        whatsapp_profile_id: enableWhatsApp ? waProfileId : undefined,
        lead_source: leadSource,
        maps_query: leadSource === 'google_maps' ? mapsQuery.trim() || undefined : undefined,
        maps_country_code: leadSource === 'google_maps' ? mapsCountryCode : undefined,
        maps_backends: leadSource === 'google_maps' ? mapsBackends : undefined,
      });

      if (res.error || !res.data) {
        throw new Error(res.error || 'Failed to create campaign');
      }

      const campaign = res.data;

      // Activate the campaign immediately
      await apiClient.patch(`/campaigns/${campaign.id}`, {
        status: 'active',
        is_paused: false,
      });

      localStorage.setItem('first_campaign_banner_dismissed', '1');

      if (onSuccess) {
        onSuccess(campaign.id);
      } else {
        router.push(`/campaigns/${campaign.id}`);
      }
    } catch (err) {
      console.error('Failed to create campaign:', err);
      setError(err instanceof Error ? err.message : 'Failed to create campaign');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <div className="space-y-1 text-center pb-2">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-900/20 mb-3">
          <Sparkles className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <h2 className="text-2xl font-semibold">Create Campaign</h2>
        <p className="text-sm text-muted-foreground">
          Step {step} of 3 — {step === 1 ? 'Define your offer' : step === 2 ? 'Who are you targeting?' : 'Channels'}
        </p>
        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 pt-2">
          <div className={`h-1.5 w-12 rounded-full transition-colors ${step >= 1 ? 'bg-emerald-500' : 'bg-zinc-200 dark:bg-zinc-700'}`} />
          <div className={`h-1.5 w-12 rounded-full transition-colors ${step >= 2 ? 'bg-emerald-500' : 'bg-zinc-200 dark:bg-zinc-700'}`} />
          <div className={`h-1.5 w-12 rounded-full transition-colors ${step >= 3 ? 'bg-emerald-500' : 'bg-zinc-200 dark:bg-zinc-700'}`} />
        </div>
      </div>

      {/* Step 1: Core campaign info */}
      {step === 1 && (
        <div className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="name" className="text-base">
              Campaign Name
            </Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., B2B SaaS Founders Q1 2026"
              className="text-base h-11"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Internal name for tracking
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="pitch" className="text-base">
              What Problem Do You Solve?
            </Label>
            <Textarea
              id="pitch"
              value={productPitch}
              onChange={(e) => setProductPitch(e.target.value)}
              placeholder="Example: We help SaaS founders automate their outbound sales so they can focus on product instead of cold emails."
              rows={3}
              className="text-base resize-none"
            />
            <p className="text-xs text-muted-foreground">
              The AI uses this to personalize outreach messages
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="objective" className="text-base">
              Campaign Goal
            </Label>
            <Textarea
              id="objective"
              value={campaignObjective}
              onChange={(e) => setCampaignObjective(e.target.value)}
              placeholder="Example: Book 20 qualified demos with founders who spend >$5k/month on outbound sales tools."
              rows={3}
              className="text-base resize-none"
            />
            <p className="text-xs text-muted-foreground">
              Be specific — this guides who the AI searches for
            </p>
          </div>

          {profiles.length > 1 && (
            <div className="space-y-2">
              <Label className="text-base">LinkedIn Profile</Label>
              <Select value={profileId} onValueChange={(v) => v && setProfileId(v)}>
                <SelectTrigger className="h-11">
                  <SelectValue placeholder="Select a profile" />
                </SelectTrigger>
                <SelectContent>
                  {profiles.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.linkedin_username}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex gap-3 pt-4 border-t">
            {onCancel && (
              <Button type="button" variant="outline" onClick={onCancel} className="flex-1">
                Cancel
              </Button>
            )}
            <Button
              type="button"
              onClick={handleNext}
              className="flex-1 h-11 text-base gap-2"
            >
              Next: Targeting
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 2: Targeting */}
      {step === 2 && (
        <div className="space-y-5">
          <div className="space-y-2">
            <Label className="text-base">
              Target Job Titles
            </Label>
            <div className="flex gap-2">
              <Input
                ref={icpInputRef}
                value={icpInput}
                onChange={(e) => setIcpInput(e.target.value)}
                onKeyDown={handleIcpKeyDown}
                placeholder="e.g., CEO, VP of Sales, Head of Growth"
                className="text-base h-11 flex-1"
                autoFocus
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                className="h-11 w-11 shrink-0"
                onClick={handleAddTitle}
                disabled={!icpInput.trim()}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Press Enter to add. The AI generates LinkedIn search queries from these titles combined with your pitch and goal.
            </p>
            {icpTitles.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {icpTitles.map((title) => (
                  <Badge
                    key={title}
                    variant="secondary"
                    className="text-sm py-1 px-3 gap-1.5"
                  >
                    {title}
                    <button
                      type="button"
                      onClick={() => handleRemoveTitle(title)}
                      className="hover:text-destructive transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="targetCompanySize" className="text-base">
              Target Company Size <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="targetCompanySize"
              value={targetCompanySize}
              onChange={(e) => setTargetCompanySize(e.target.value)}
              placeholder="e.g., small to medium companies, 10-500 employees, no enterprise"
              className="text-base h-11"
            />
            <p className="text-xs text-muted-foreground">
              The AI will disqualify leads who clearly work at companies outside this range (e.g. Google, Spotify, Fortune 500)
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="bookingLink" className="text-base">
              Booking Link <span className="text-muted-foreground font-normal">(optional)</span>
            </Label>
            <Input
              id="bookingLink"
              value={bookingLink}
              onChange={(e) => setBookingLink(e.target.value)}
              placeholder="https://calendly.com/you/30min"
              className="text-base h-11"
              type="url"
            />
            <p className="text-xs text-muted-foreground">
              Calendly, Cal.com, or similar — the AI includes this when a lead shows interest
            </p>
          </div>

          <div className="flex gap-3 pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={() => { setStep(1); setError(''); }}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
            <Button
              type="button"
              onClick={handleNextToChannels}
              className="flex-1 h-11 text-base gap-2"
            >
              Next: Channels
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Step 3: Channels */}
      {step === 3 && (
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-lg border bg-muted/30">
              <Checkbox id="ch-linkedin" checked disabled />
              <div>
                <Label htmlFor="ch-linkedin" className="text-base font-medium cursor-default">LinkedIn</Label>
                <p className="text-xs text-muted-foreground">Always active — connection requests + follow-ups</p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg border">
              <Checkbox
                id="ch-whatsapp"
                checked={enableWhatsApp}
                onCheckedChange={(checked) => setEnableWhatsApp(Boolean(checked))}
                className="mt-0.5"
              />
              <div className="flex-1 space-y-3">
                <div>
                  <Label htmlFor="ch-whatsapp" className="text-base font-medium cursor-pointer">WhatsApp</Label>
                  <p className="text-xs text-muted-foreground">
                    Message leads with a phone number via WhatsApp Web
                    {waProfiles.length === 0 && ' — connect a number in Settings → WhatsApp first'}
                  </p>
                </div>

                {enableWhatsApp && (
                  <>
                    {waProfiles.length > 0 ? (
                      <div className="space-y-2">
                        <Label className="text-sm">WhatsApp Number</Label>
                        <Select value={waProfileId} onValueChange={(v) => v && setWaProfileId(v)}>
                          <SelectTrigger className="h-10">
                            <SelectValue placeholder="Select number" />
                          </SelectTrigger>
                          <SelectContent>
                            {waProfiles.map((p) => (
                              <SelectItem key={p.id} value={p.id}>
                                {p.displayName || p.phoneNumber || p.id}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ) : (
                      <p className="text-xs text-amber-600 dark:text-amber-400">
                        No connected WhatsApp numbers found. Connect one in Settings → WhatsApp.
                      </p>
                    )}

                    <div className="space-y-2">
                      <Label className="text-sm">Initial Message Template</Label>
                      <Textarea
                        value={waMessageTemplate}
                        onChange={(e) => setWaMessageTemplate(e.target.value)}
                        placeholder="Hi {first_name}, I came across your profile and wanted to reach out about..."
                        rows={4}
                        className="resize-none text-sm"
                      />
                      <p className="text-xs text-muted-foreground">
                        Sent as the first WhatsApp message to each lead
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Lead Source */}
          <div className="space-y-3 pt-2">
            <Label className="text-base">Lead Source</Label>
            <Select value={leadSource} onValueChange={(v) => setLeadSource(v as typeof leadSource)}>
              <SelectTrigger className="h-10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="linkedin_search">LinkedIn Search</SelectItem>
                <SelectItem value="google_maps">Google Maps</SelectItem>
                <SelectItem value="csv_import">CSV Import</SelectItem>
              </SelectContent>
            </Select>

            {leadSource === 'google_maps' && (
              <div className="space-y-3 pl-1">
                <div className="space-y-1">
                  <Label className="text-sm">Search Query</Label>
                  <Input
                    value={mapsQuery}
                    onChange={(e) => setMapsQuery(e.target.value)}
                    placeholder="e.g. plumbers in New York"
                    className="h-10 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-sm">Country</Label>
                  <Select value={mapsCountryCode} onValueChange={(v) => v && setMapsCountryCode(v)}>
                    <SelectTrigger className="h-10">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="US">United States</SelectItem>
                      <SelectItem value="GB">United Kingdom</SelectItem>
                      <SelectItem value="CA">Canada</SelectItem>
                      <SelectItem value="AU">Australia</SelectItem>
                      <SelectItem value="DE">Germany</SelectItem>
                      <SelectItem value="FR">France</SelectItem>
                      <SelectItem value="ES">Spain</SelectItem>
                      <SelectItem value="IT">Italy</SelectItem>
                      <SelectItem value="BR">Brazil</SelectItem>
                      <SelectItem value="MX">Mexico</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-sm">Backends</Label>
                  <div className="flex flex-col gap-1.5">
                    {(['google_maps', 'bing_maps', 'duckduckgo_maps'] as const).map((b) => (
                      <div key={b} className="flex items-center gap-2">
                        <Checkbox
                          id={`backend-${b}`}
                          checked={mapsBackends.includes(b)}
                          onCheckedChange={() => toggleMapsBackend(b)}
                        />
                        <Label htmlFor={`backend-${b}`} className="text-sm font-normal cursor-pointer">
                          {b === 'google_maps' ? 'Google Maps' : b === 'bing_maps' ? 'Bing Maps' : 'DuckDuckGo Maps'}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {leadSource === 'csv_import' && (
              <p className="text-xs text-muted-foreground pl-1">
                After creating the campaign, upload a CSV file from the campaign leads page.
              </p>
            )}
          </div>

          <div className="flex gap-3 pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={() => { setStep(2); setError(''); }}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className="flex-1 h-11 text-base gap-2"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  Launch Campaign
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
