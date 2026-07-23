import { apiClient } from "../apiClientV2";
import { ApiResponse } from "../api";

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
  return apiClient.get<Plan[]>("/billing/plans");
}

export async function isLifetimeDealActive(): Promise<ApiResponse<{ active: boolean }>> {
  return apiClient.get<{ active: boolean }>("/billing/lifetime-deal-active");
}

export async function getBillingStatus(): Promise<ApiResponse<BillingStatus>> {
  return apiClient.get<BillingStatus>("/billing/status");
}

export async function getInvoices(): Promise<ApiResponse<Invoice[]>> {
  return apiClient.get<Invoice[]>("/billing/invoices");
}

export async function getUsage(): Promise<ApiResponse<{ linkedin_accounts_used: number; campaigns_used: number }>> {
  return apiClient.get<{ linkedin_accounts_used: number; campaigns_used: number }>("/billing/usage");
}

export async function createCheckoutSession(
  planName: string,
  billingPeriod: string
): Promise<ApiResponse<{ url: string }>> {
  return apiClient.post<{ url: string }>("/billing/checkout", {
    plan_name: planName,
    billing_period: billingPeriod,
  });
}

export async function createPortalSession(): Promise<ApiResponse<{ url: string }>> {
  return apiClient.post<{ url: string }>("/billing/portal", {});
}

export async function changePlan(
  planName: string,
  billingPeriod: string
): Promise<ApiResponse<{ status: string; message: string }>> {
  return apiClient.post<{ status: string; message: string }>(
    "/billing/plan-change",
    {
      plan_name: planName,
      billing_period: billingPeriod,
    }
  );
}

export async function updateCloudAddon(
  quantity: number
): Promise<ApiResponse<{ cloud_profiles: number }>> {
  return apiClient.post<{ cloud_profiles: number }>("/billing/cloud-addon", {
    quantity,
  });
}

export async function cancelSubscription(): Promise<ApiResponse<{ status: string }>> {
  return apiClient.post<{ status: string }>("/billing/cancel-subscription", {});
}

export async function reactivateSubscription(): Promise<ApiResponse<{ status: string }>> {
  return apiClient.post<{ status: string }>(
    "/billing/reactivate-subscription",
    {}
  );
}

export async function checkFeature(
  featureName: string
): Promise<ApiResponse<{ has_access: boolean }>> {
  return apiClient.get<{ has_access: boolean }>(
    `/billing/feature-check/${featureName}`
  );
}
