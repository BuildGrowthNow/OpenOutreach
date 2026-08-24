"use client";

import { createContext, useContext, ReactNode, useEffect, useState, useCallback } from "react";
import { BillingStatus, BillingUsage, getBillingStatus, getUsage } from "@/lib/api/billing";
import { useAuthStore } from "@/lib/authStoreV2";

interface BillingContextType {
  billingStatus: BillingStatus | null;
  usage: BillingUsage | null;
  loading: boolean;
  refetch: () => Promise<void>;
}

const BillingContext = createContext<BillingContextType | undefined>(undefined);

export function BillingProvider({ children }: { children: ReactNode }) {
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [loading, setLoading] = useState(true);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const refetch = useCallback(async () => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
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
  }, [isAuthenticated]);

  useEffect(() => {
    void refetch();
    if (!isAuthenticated) return;
    const interval = setInterval(() => void refetch(), 60000);
    return () => clearInterval(interval);
  }, [isAuthenticated, refetch]);

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
