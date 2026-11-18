"use client";

import { useEffect, useState } from "react";
import { Building2, Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { useBilling } from "@/lib/contexts/billing-context";
import { useAuthStore } from "@/lib/authStoreV2";
import {
  activateOrganization,
  listOrganizations,
  type OrganizationSummary,
} from "@/lib/api/team";

export function OrgSwitcher() {
  const { billingStatus, refetch } = useBilling();
  const { user, refreshToken, initialize } = useAuthStore();
  const [orgs, setOrgs] = useState<OrganizationSummary[]>([]);
  const [switching, setSwitching] = useState(false);

  const enabled = billingStatus?.team_workspaces_enabled === true;

  useEffect(() => {
    if (!enabled) {
      setOrgs([]);
      return;
    }
    let cancelled = false;
    void listOrganizations().then((response) => {
      if (!cancelled && response.data) setOrgs(response.data);
    });
    return () => {
      cancelled = true;
    };
  }, [enabled, billingStatus?.org_id]);

  if (!enabled) return null;

  const currentId = billingStatus?.org_id || user?.org_id || "";
  const current = orgs.find((org) => org.id === currentId);

  const handleSwitch = async (orgId: string) => {
    if (orgId === currentId) return;
    setSwitching(true);
    try {
      const response = await activateOrganization(orgId);
      if (response.error) {
        console.error("Failed to switch workspace:", response.error);
        return;
      }
      await refetch();
      await refreshToken();
      await initialize();
      window.location.reload();
    } finally {
      setSwitching(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2" disabled={switching}>
          <Building2 className="h-4 w-4" />
          <span className="max-w-[160px] truncate">
            {current?.name || billingStatus?.org_name || "Workspace"}
          </span>
          {current?.is_shared && (
            <Badge variant="secondary" className="ml-1 hidden sm:inline-flex">
              Team
            </Badge>
          )}
          <ChevronsUpDown className="h-3.5 w-3.5 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {orgs.map((org) => (
          <DropdownMenuItem
            key={org.id}
            onClick={() => void handleSwitch(org.id)}
            className="flex items-center justify-between gap-2"
          >
            <span className="min-w-0">
              <span className="block truncate text-sm">{org.name}</span>
              <span className="block text-xs text-muted-foreground capitalize">
                {org.role} · {org.plan}
              </span>
            </span>
            {org.id === currentId && <Check className="h-4 w-4 shrink-0" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
