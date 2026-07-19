"use client";

import { useAuthStore } from "@/lib/authStoreV2";
import { BillingStatusProvider } from "./billing-status-provider";

interface DashboardBillingWrapperProps {
  children: React.ReactNode;
}

export function DashboardBillingWrapper({ children }: DashboardBillingWrapperProps) {
  const user = useAuthStore((state) => state.user);

  if (!user) {
    return <>{children}</>;
  }

  return (
    <BillingStatusProvider
      userStatus={user.status || "active"}
      adminNotes={user.admin_notes}
    >
      {children}
    </BillingStatusProvider>
  );
}
