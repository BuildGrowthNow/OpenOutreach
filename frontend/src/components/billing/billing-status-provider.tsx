"use client";

import { useRouter } from "next/navigation";
import { useBilling } from "@/lib/contexts/billing-context";
import { TrialBanner } from "./trial-banner";
import { PastDueBanner } from "./past-due-banner";
import { ApproachingLimitBanner } from "./approaching-limit-banner";
import { TrialExpiredOverlay } from "./trial-expired-overlay";
import { AccountBlockedOverlay } from "./account-blocked-overlay";
import { SubscriptionCanceledOverlay } from "./subscription-canceled-overlay";
import { useMemo } from "react";

interface BillingStatusProviderProps {
  userStatus: string;
  adminNotes?: string | null;
  children: React.ReactNode;
}

export function BillingStatusProvider({
  userStatus,
  adminNotes,
  children,
}: BillingStatusProviderProps) {
  const router = useRouter();
  const { billingStatus, usage } = useBilling();

  const handleUpgradeClick = () => {
    router.push("/settings/plan");
  };

  const handleManageClick = () => {
    router.push("/settings/billing");
  };

  const handleReactivate = () => {
    router.push("/settings/billing");
  };

  const linkedInAccountsUsed = useMemo(() => {
    return usage?.linkedin_accounts_used || 0;
  }, [usage?.linkedin_accounts_used]);

  const campaignsUsed = useMemo(() => {
    return usage?.campaigns_used || 0;
  }, [usage?.campaigns_used]);

  return (
    <TrialExpiredOverlay
      subscriptionStatus={billingStatus?.subscription_status || ""}
      onChoosePlan={handleUpgradeClick}
    >
      <AccountBlockedOverlay
        userStatus={userStatus}
        adminNotes={adminNotes}
      >
        <SubscriptionCanceledOverlay
          subscriptionStatus={billingStatus?.subscription_status || ""}
          currentPeriodEnd={billingStatus?.current_period_end || null}
          onReactivate={handleReactivate}
        >
          <div className="space-y-4">
            {/* Trial Banner - Global, dismissible */}
            {billingStatus && (
              <TrialBanner
                trialEndsAt={billingStatus.trial_ends_at}
                subscriptionStatus={billingStatus.subscription_status}
                onUpgradeClick={handleUpgradeClick}
              />
            )}

            {/* Past Due Banner - Global, non-dismissible */}
            {billingStatus && (
              <PastDueBanner
                subscriptionStatus={billingStatus.subscription_status}
                onManageClick={handleManageClick}
              />
            )}

            {/* Approaching Limits Banners - Contextual */}
            {billingStatus && linkedInAccountsUsed >= billingStatus.linkedin_account_limit * 0.8 && (
              <ApproachingLimitBanner
                resourceType="linkedin_accounts"
                used={linkedInAccountsUsed}
                limit={billingStatus.linkedin_account_limit}
                onUpgradeClick={handleUpgradeClick}
              />
            )}

            {billingStatus && billingStatus.campaign_limit && campaignsUsed >= billingStatus.campaign_limit * 0.8 && (
              <ApproachingLimitBanner
                resourceType="campaigns"
                used={campaignsUsed}
                limit={billingStatus.campaign_limit}
                onUpgradeClick={handleUpgradeClick}
              />
            )}

            {children}
          </div>
        </SubscriptionCanceledOverlay>
      </AccountBlockedOverlay>
    </TrialExpiredOverlay>
  );
}
