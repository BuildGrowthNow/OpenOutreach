"use client";

import { createContext, useContext, ReactNode, useEffect, useState } from "react";
import { BillingStatus, getBillingStatus, getUsage } from "@/lib/api/billing";

interface BillingContextType {
  billingStatus: BillingStatus | null;
  usage: { linkedin_accounts_used: number; campaigns_used: number } | null;
  loading: boolean;
  refetch: () => Promise<void>;
}

const BillingContext = createContext<BillingContextType | undefined>(undefined);

export function BillingProvider({ children }: { children: ReactNode }) {
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [usage, setUsage] = useState<{ linkedin_accounts_used: number; campaigns_used: number } | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = async () => {
    try {
      setLoading(true);
      const [statusRes, usageRes] = await Promise.all([
        getBillingStatus(),
        getUsage(),
      ]);
      if (statusRes.data) {
        setBillingStatus(statusRes.data);
      }
      if (usageRes.data) {
        setUsage(usageRes.data);
      }
    } catch (error) {
      console.error("Failed to fetch billing data:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refetch();
    const interval = setInterval(() => void refetch(), 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  return (
    <BillingContext.Provider value={{ billingStatus, usage, loading, refetch }}>
      {children}
    </BillingContext.Provider>
  );
}

export function useBilling() {
  const context = useContext(BillingContext);
  if (!context) {
    throw new Error("useBilling must be used within BillingProvider");
  }
  return context;
}
