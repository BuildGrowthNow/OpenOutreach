"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Icons } from "@/lib/types/components";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  getProxyConfig,
  updateProxyConfig,
  testProxy,
  type ProxyTestResult,
} from "@/lib/api/dashboard";
import { useToast } from "@/components/ui/use-toast";
import { Loader2, Shield, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown } from "lucide-react";

interface ProxyConfigFormProps {
  profileId: string;
  onConfigUpdate?: () => void;
  /** Render without the outer Card wrapper, for use inside a dialog. */
  embedded?: boolean;
}

export function ProxyConfigForm({
  profileId,
  onConfigUpdate,
  embedded = false,
}: ProxyConfigFormProps) {
  const [proxyServer, setProxyServer] = useState("");
  const [proxyUsername, setProxyUsername] = useState("");
  const [proxyPassword, setProxyPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<ProxyTestResult | null>(null);
  const [hasExistingProxy, setHasExistingProxy] = useState(false);
  const [proxyMode, setProxyMode] = useState<"none" | "managed" | "byo">("none");
  const [proxyRegion, setProxyRegion] = useState("");
  const [proxyHealth, setProxyHealth] = useState<{
    status?: string | null;
    testedAt?: string | null;
    ip?: string | null;
    country?: string | null;
    latencyMs?: number | null;
    error?: string | null;
    mismatch?: boolean | null;
  }>({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { toast } = useToast();

  const loadProxyConfig = async () => {
    try {
      setLoading(true);
      const response = await getProxyConfig(profileId);
      if (response.data) {
        setProxyServer(response.data.proxyServer || "");
        setProxyUsername(response.data.proxyUsername || "");
        setProxyPassword("");
        setHasExistingProxy(response.data.hasProxy);
        setProxyMode(response.data.proxyMode ?? "none");
        setProxyRegion(
          [
            response.data.proxyRegionCountry,
            response.data.proxyRegionSubdivision,
            response.data.proxyRegionCity,
          ]
            .filter(Boolean)
            .join(" · ")
        );
        setProxyHealth({
          status: response.data.proxyStatus,
          testedAt: response.data.lastTestedAt,
          ip: response.data.lastTestIp,
          country: response.data.lastTestCountry,
          latencyMs: response.data.lastTestLatencyMs,
          error: response.data.lastError,
          mismatch: response.data.countryMismatch,
        });
        setShowAdvanced(!!response.data.proxyUsername);
      }
    } catch (error) {
      console.error("Failed to load proxy config:", error);
      toast({
        title: "Error",
        description: "Failed to load proxy configuration",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProxyConfig();
  }, [profileId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleTest = async () => {
    if (!proxyServer) {
      toast({
        title: "Validation Error",
        description: "Please enter a proxy server URL",
        variant: "destructive",
      });
      return;
    }

    try {
      setTesting(true);
      setTestResult(null);
      const response = await testProxy(
        profileId,
        proxyServer,
        proxyUsername || null,
        proxyPassword || null,
      );
      if (response.data) {
        setTestResult(response.data);
        if (response.data.success) {
          toast({
            title: "Proxy Test Successful",
            description: response.data.ip
              ? `Connected through ${response.data.ip}`
              : "Proxy is working correctly",
          });
        } else {
          toast({
            title: "Proxy Test Failed",
            description: response.data.error || "Proxy connection failed",
            variant: "destructive",
          });
        }
      }
    } catch (error) {
      console.error("Proxy test failed:", error);
      setTestResult({
        success: false,
        message: "Proxy test failed",
        error: String(error),
      });
      toast({
        title: "Test Error",
        description: "Failed to test proxy connection",
        variant: "destructive",
      });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const response = await updateProxyConfig(
        profileId,
        proxyServer || null,
        proxyUsername,
        proxyPassword,
      );
      if (response.data?.success) {
        toast({
          title: "Proxy Updated",
          description: proxyServer
            ? "Proxy configuration saved successfully"
            : "Proxy configuration cleared",
        });
        setHasExistingProxy(!!proxyServer);
        setProxyPassword("");
        if (onConfigUpdate) {
          onConfigUpdate();
        }
      }
    } catch (error) {
      console.error("Failed to save proxy config:", error);
      toast({
        title: "Save Failed",
        description:
          error instanceof Error
            ? error.message
            : "Failed to save proxy configuration",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setProxyServer("");
    setProxyUsername("");
    setProxyPassword("");
    setTestResult(null);
    try {
      setSaving(true);
      const response = await updateProxyConfig(profileId, null, null, null);
      if (response.data?.success) {
        toast({
          title: "Proxy Cleared",
          description: "Proxy configuration has been removed",
        });
        setHasExistingProxy(false);
        if (onConfigUpdate) {
          onConfigUpdate();
        }
      }
    } catch (error) {
      console.error("Failed to clear proxy config:", error);
      toast({
        title: "Clear Failed",
        description:
          error instanceof Error
            ? error.message
            : "Failed to clear proxy configuration",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const requestProxyChange = () => {
    const subject = encodeURIComponent(`Proxy change request - ${profileId}`);
    const body = encodeURIComponent(
      "Please describe the region or proxy change you need:\n\n"
    );
    window.location.href = `mailto:support@lengrowth.com?subject=${subject}&body=${body}`;
  };

  if (loading) {
    const loader = (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
    return embedded ? loader : <Card><CardContent>{loader}</CardContent></Card>;
  }

  const formBody = (
    <div className="space-y-4">
      {proxyMode === "managed" ? (
        <Alert>
          <Shield className="h-4 w-4" />
          <AlertTitle>Managed proxy</AlertTitle>
          <AlertDescription>
            Lengrowth assigned this proxy automatically
            {proxyRegion ? ` · ${proxyRegion}` : ""}. It is encrypted and
            cannot be edited here. Use Test Connection to check the egress IP.
            {(proxyHealth.status || proxyHealth.ip || proxyHealth.testedAt) && (
              <div className="mt-2 text-xs text-muted-foreground">
                {proxyHealth.status ? `Status: ${proxyHealth.status}` : null}
                {proxyHealth.ip ? ` · Egress: ${proxyHealth.ip}` : null}
                {proxyHealth.country ? ` · ${proxyHealth.country}` : null}
                {typeof proxyHealth.latencyMs === "number"
                  ? ` · ${proxyHealth.latencyMs} ms`
                  : null}
                {proxyHealth.mismatch ? " · country mismatch" : null}
                {proxyHealth.testedAt
                  ? ` · tested ${new Date(proxyHealth.testedAt).toLocaleString()}`
                  : null}
              </div>
            )}
            {proxyHealth.error && (
              <div className="mt-1 text-xs text-destructive">
                {proxyHealth.error}
              </div>
            )}
            <div className="mt-3">
              <Button size="sm" variant="outline" onClick={requestProxyChange}>
                Request proxy change
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      ) : (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>One proxy per LinkedIn account</AlertTitle>
          <AlertDescription>
            Each profile MUST use a different proxy or a unique sticky session.
            Sharing one IP across multiple accounts can get them linked and
            restricted by LinkedIn.
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2">
        <Label htmlFor="proxy-server">Proxy URL</Label>
        <Input
          id="proxy-server"
          type="text"
          placeholder="http://network.joinmassive.com:65534"
          value={proxyServer}
          onChange={(e) => setProxyServer(e.target.value)}
          disabled={proxyMode === "managed"}
        />
        <p className="text-xs text-muted-foreground">
          Full proxy endpoint, for example{" "}
          <code>http://network.joinmassive.com:65534</code> for Massive
          residential HTTP.
        </p>
      </div>

      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <CollapsibleTrigger className="w-full">
          <Button variant="ghost" size="sm" className="gap-2">
            <ChevronDown
              className={`h-4 w-4 transition-transform ${
                showAdvanced ? "rotate-180" : ""
              }`}
            />
            Proxy login details
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label htmlFor="proxy-username">Username</Label>
            <Input
              id="proxy-username"
              type="text"
              placeholder="username"
              value={proxyUsername}
              onChange={(e) => setProxyUsername(e.target.value)}
              disabled={proxyMode === "managed"}
            />
            <p className="text-xs text-muted-foreground">
              For a sticky session, append the session parameters to your
              provider username, e.g.{" "}
              <code>user-session-li-001-sessionttl-1440</code>.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="proxy-password">Password</Label>
            <Input
              id="proxy-password"
              type="password"
              placeholder={
                hasExistingProxy ? "Leave blank to keep current password" : "password"
              }
              value={proxyPassword}
              onChange={(e) => setProxyPassword(e.target.value)}
              disabled={proxyMode === "managed"}
            />
          </div>
        </CollapsibleContent>
      </Collapsible>

      {testResult && (
        <Alert variant={testResult.success ? "default" : "destructive"}>
          {testResult.success ? (
            <CheckCircle className="h-4 w-4" />
          ) : (
            <XCircle className="h-4 w-4" />
          )}
          <AlertTitle>
            {testResult.success ? "Proxy Connected" : "Connection Failed"}
          </AlertTitle>
          <AlertDescription>
            {testResult.message}
            {testResult.ip && (
              <div className="mt-1 text-xs">
                Egress IP: <code>{testResult.ip}</code>
              </div>
            )}
            {typeof testResult.latencyMs === "number" && (
              <div className="mt-1 text-xs text-muted-foreground">
                {testResult.latencyMs} ms
              </div>
            )}
            {testResult.error && <div className="mt-1 text-xs">{testResult.error}</div>}
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={handleTest}
          disabled={!proxyServer || testing}
          variant="outline"
        >
          {testing ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Testing...
            </>
          ) : (
            "Test Connection"
          )}
        </Button>

        <Button onClick={handleSave} disabled={saving || proxyMode === "managed"}>
          {saving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            "Save Configuration"
          )}
        </Button>

        {hasExistingProxy && proxyMode !== "managed" && (
          <Button
            onClick={handleClear}
            disabled={saving}
            variant="destructive"
          >
            Clear Proxy
          </Button>
        )}
      </div>

      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Proxy Recommendations</AlertTitle>
        <AlertDescription>
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs">
            <li>
              <strong>Desktop app users:</strong> No proxy needed - your own internet connection is used
            </li>
            <li>
              <strong>Lengrowth Cloud users:</strong> One unique proxy or sticky session per account
            </li>
            <li>
              <strong>Avoid:</strong> Datacenter or hosting IPs - LinkedIn blocks these
            </li>
            <li>
              <strong>Massive residential:</strong> Keep the session parameters
              identical on every request so the account keeps the same egress IP.
            </li>
          </ul>
        </AlertDescription>
      </Alert>
    </div>
  );

  if (embedded) {
    return formBody;
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          <CardTitle>Proxy Configuration</CardTitle>
        </div>
        <CardDescription>
          Configure a proxy for this LinkedIn account when using Lengrowth Cloud.
          Users running the desktop app connect from their own computer and do not need a proxy.
        </CardDescription>
      </CardHeader>
      <CardContent>{formBody}</CardContent>
    </Card>
  );
}
