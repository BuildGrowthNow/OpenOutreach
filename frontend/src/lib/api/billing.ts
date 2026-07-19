import { get, post, ApiResponse } from "../api";

export interface Plan {
  name: string;
  display_name: string;
  monthly_price: number;
  annual_price: number;
  max_linkedin_accounts: number;
  max_campaigns: number | null;
  features: string[];
}

export interface BillingStatus {
  plan: string;
  subscription_status: string;
  billing_period: string | null;
  trial_ends_at: string | null;
  current_period_end: string | null;
  linkedin_account_limit: number;
  campaign_limit: number | null;
  cloud_profiles: number;
  user_status: string;
  admin_notes: string | null;
  stripe_subscription_id?: string;
}

export interface Invoice {
  id: string;
  number: string | null;
  status: string;
  amount_paid: number;
  amount_due: number;
  currency: string;
  created: number;
  period_start: number;
  period_end: number;
  paid: boolean;
  pdf_url: string | null;
}

export interface BillingUsage {
  linkedin_accounts_used: number;
  linkedin_accounts_limit: number;
  campaigns_used: number;
  campaigns_limit: number | null;
}

export async function getPlans(): Promise<ApiResponse<Plan[]>> {
  return get<Plan[]>("/api/billing/plans");
}

export async function isLifetimeDealActive(): Promise<ApiResponse<{ active: boolean }>> {
  return get<{ active: boolean }>("/api/billing/lifetime-deal-active");
}

export async function getBillingStatus(): Promise<ApiResponse<BillingStatus>> {
  return get<BillingStatus>("/api/billing/status");
}

export async function getInvoices(): Promise<ApiResponse<Invoice[]>> {
  return get<Invoice[]>("/api/billing/invoices");
}

export async function getUsage(): Promise<ApiResponse<{ linkedin_accounts_used: number; campaigns_used: number }>> {
  return get<{ linkedin_accounts_used: number; campaigns_used: number }>("/api/billing/usage");
}

export async function createCheckoutSession(
  planName: string,
  billingPeriod: string
): Promise<ApiResponse<{ url: string }>> {
  return post<{ url: string }>("/api/billing/checkout", {
    plan_name: planName,
    billing_period: billingPeriod,
  });
}

export async function createPortalSession(): Promise<ApiResponse<{ url: string }>> {
  return post<{ url: string }>("/api/billing/portal", {});
}

export async function changePlan(
  planName: string,
  billingPeriod: string
): Promise<ApiResponse<{ status: string; message: string }>> {
  return post<{ status: string; message: string }>(
    "/api/billing/plan-change",
    {
      plan_name: planName,
      billing_period: billingPeriod,
    }
  );
}

export async function updateCloudAddon(
  quantity: number
): Promise<ApiResponse<{ cloud_profiles: number }>> {
  return post<{ cloud_profiles: number }>("/api/billing/cloud-addon", {
    quantity,
  });
}

export async function cancelSubscription(): Promise<ApiResponse<{ status: string }>> {
  return post<{ status: string }>("/api/billing/cancel-subscription", {});
}

export async function reactivateSubscription(): Promise<ApiResponse<{ status: string }>> {
  return post<{ status: string }>(
    "/api/billing/reactivate-subscription",
    {}
  );
}

export async function checkFeature(
  featureName: string
): Promise<ApiResponse<{ has_access: boolean }>> {
  return get<{ has_access: boolean }>(
    `/api/billing/feature-check/${featureName}`
  );
}
