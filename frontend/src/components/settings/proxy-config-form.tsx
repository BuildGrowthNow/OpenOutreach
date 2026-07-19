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
  type ProxyConfig,
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
}

export function ProxyConfigForm({ profileId, onConfigUpdate }: ProxyConfigFormProps) {
  const [proxyServer, setProxyServer] = useState("");
  const [proxyUsername, setProxyUsername] = useState("");
  const [proxyPassword, setProxyPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<ProxyTestResult | null>(null);
  const [hasExistingProxy, setHasExistingProxy] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { toast } = useToast();

  const loadProxyConfig = async () => {
    try {
      setLoading(true);
      const response = await getProxyConfig(profileId);
      if (response.success && response.data) {
        setProxyServer(response.data.proxyServer || "");
        setProxyUsername(response.data.proxyUsername || "");
        setProxyPassword("");
        setHasExistingProxy(response.data.hasProxy);
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
      if (response.success && response.data) {
        setTestResult(response.data);
        if (response.data.success) {
          toast({
            title: "Proxy Test Successful",
            description: "Proxy is working correctly",
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
        proxyUsername || null,
        proxyPassword || null,
      );
      if (response.success) {
        toast({
          title: "Proxy Updated",
          description: proxyServer
            ? "Proxy configuration saved successfully"
            : "Proxy configuration cleared",
        });
        setHasExistingProxy(!!proxyServer);
        if (onConfigUpdate) {
          onConfigUpdate();
        }
      }
    } catch (error) {
      console.error("Failed to save proxy config:", error);
      toast({
        title: "Save Failed",
        description: "Failed to save proxy configuration",
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
      if (response.success) {
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
        description: "Failed to clear proxy configuration",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          <CardTitle>Proxy Configuration</CardTitle>
        </div>
        <CardDescription>
          Configure a proxy server for this LinkedIn profile when running the cloud daemon.
          Desktop daemon users run on their own residential IP and do not need a proxy.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Multi-User Warning</AlertTitle>
          <AlertDescription>
            If you have multiple LinkedIn profiles, each profile MUST use a
            different proxy or residential IP. Using the same IP for multiple
            accounts will result in LinkedIn restrictions.
          </AlertDescription>
        </Alert>

        <div className="space-y-2">
          <Label htmlFor="proxy-server">Proxy Server URL</Label>
          <Input
            id="proxy-server"
            type="text"
            placeholder="http://proxy.example.com:8080 or socks5://proxy.example.com:1080"
            value={proxyServer}
            onChange={(e) => setProxyServer(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Format: http://host:port or socks5://host:port
          </p>
        </div>

        <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2">
              <ChevronDown
                className={`h-4 w-4 transition-transform ${
                  showAdvanced ? "rotate-180" : ""
                }`}
              />
              Advanced: Proxy Authentication
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label htmlFor="proxy-username">Proxy Username (Optional)</Label>
              <Input
                id="proxy-username"
                type="text"
                placeholder="username"
                value={proxyUsername}
                onChange={(e) => setProxyUsername(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="proxy-password">Proxy Password (Optional)</Label>
              <Input
                id="proxy-password"
                type="password"
                placeholder="password"
                value={proxyPassword}
                onChange={(e) => setProxyPassword(e.target.value)}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {testResult && (
          <Alert
            variant={testResult.success ? "default" : "destructive"}
          >
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
              {testResult.error && <div className="mt-1 text-xs">{testResult.error}</div>}
            </AlertDescription>
          </Alert>
        )}

        <div className="flex gap-2">
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

          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              "Save Configuration"
            )}
          </Button>

          {hasExistingProxy && (
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
                <strong>Desktop daemon:</strong> No proxy needed - uses your
                residential IP
              </li>
              <li>
                <strong>Cloud daemon:</strong> Mobile proxies recommended
                ($50-150/month unlimited bandwidth)
              </li>
              <li>
                <strong>Never use:</strong> Datacenter/Elastic IPs - LinkedIn
                actively blocks cloud provider IPs
              </li>
              <li>
                <strong>Budget:</strong> 1 IP per 2-3 profiles = $25-75 per
                profile/month
              </li>
            </ul>
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>
  );
}
