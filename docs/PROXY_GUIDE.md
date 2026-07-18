# Proxy Configuration Guide

## TL;DR Cost Comparison

| Solution | Monthly Cost per Profile | Bandwidth | Best For |
|----------|-------------------------|-----------|----------|
| **No Proxy (Recommended)** | $0 | Unlimited | Self-hosted, local deployments |
| **Mobile Proxy** | $50-150 | Unlimited | Multi-account, safest for LinkedIn |
| **Residential (IPRoyal)** | $7-20 | 4-10 GB* | Budget cloud hosting |
| **Residential (Bright Data)** | $32-96 | 8-24 GB* | Enterprise |
| **Datacenter/Elastic IP** | ❌ Don't use | - | LinkedIn blocks datacenter IPs |

*With bandwidth optimization enabled (60-70% reduction)

## Why Not Elastic IPs?

**Elastic IPs are datacenter IPs** from known AWS/GCP/Azure ranges. LinkedIn actively:
- ✅ Maintains blocklists of cloud provider IP ranges
- ✅ Detects unusual patterns from datacenter IPs
- ✅ Flags accounts even with rotation
- ❌ **High risk of account restrictions/bans**

## Recommended Solutions

### 1. No Proxy (Best for Most Users)

**Cost**: $0  
**Setup**: None required (default)

If users run the daemon on their local machines or dedicated servers with clean residential/business IPs, no proxy is needed. LinkedIn already trusts their normal IP.

**Best for:**
- Self-hosted single-user deployments
- Each user runs their own daemon
- Servers with clean non-datacenter IPs

### 2. Mobile Proxies (Best for Cloud)

**Cost**: $50-150/month per IP (unlimited bandwidth)  
**Providers**: Proxy-Cheap, ProxyEmpire, IPRoyal Mobile

Mobile carrier IPs are **most trusted** by LinkedIn:
- ✅ Unlimited bandwidth
- ✅ 1 IP can safely serve 2-3 profiles
- ✅ Lowest detection risk
- ✅ **Recommended for multi-account cloud deployments**

**Effective cost**: $25-75 per profile/month

**Setup**:
```bash
# Edit linkedin_cli/conf.py
BROWSER_PROXY_SERVER = "http://proxy-provider.com:12345"
BROWSER_PROXY_USERNAME = "your-username"
BROWSER_PROXY_PASSWORD = "your-password"
```

### 3. Residential Proxies (Budget Cloud)

**Cost**: $1.75-8/GB  
**Providers**:

| Provider | Cost/GB | Notes |
|----------|---------|-------|
| IPRoyal | $1.75 | Budget option, smaller pool |
| Smartproxy | $8.50 | Good balance |
| Bright Data | $4.00* | Enterprise, use code RESIGB50 |
| Oxylabs | $8.00 | Premium quality |

**With bandwidth optimization** (enabled by default):
- Average preset: 24 GB → **7-10 GB** = $12-85/month
- Slow preset: 18 GB → **5-7 GB** = $9-60/month

## Bandwidth Usage by Preset

| Preset | Actions/Month* | Raw Bandwidth | Optimized** | Cost Range*** |
|--------|---------------|---------------|-------------|---------------|
| Very Slow | 4,800 | 12 GB | 4 GB | $7-34 |
| Slow | 7,200 | 18 GB | 6 GB | $11-51 |
| Average | 9,600 | 24 GB | 8 GB | $14-68 |
| Aggressive | 19,200 | 48 GB | 16 GB | $28-136 |
| Very Aggressive | 28,800 | 72 GB | 24 GB | $42-204 |

*16 active hours/day  
**With resource blocking enabled (default)  
***IPRoyal ($1.75/GB) to Smartproxy ($8.50/GB)

## Configuration

### Option 1: Environment Variables (Recommended)

```bash
export BROWSER_PROXY_SERVER="http://proxy.example.com:12345"
export BROWSER_PROXY_USERNAME="your-username"
export BROWSER_PROXY_PASSWORD="your-password"
```

Then update `linkedin_cli/conf.py` to read from env:
```python
import os

BROWSER_PROXY_SERVER = os.getenv("BROWSER_PROXY_SERVER")
BROWSER_PROXY_USERNAME = os.getenv("BROWSER_PROXY_USERNAME")
BROWSER_PROXY_PASSWORD = os.getenv("BROWSER_PROXY_PASSWORD")
```

### Option 2: Direct Configuration

Edit `linkedin_cli/conf.py`:

```python
# Format: "http://user:pass@host:port" or "socks5://user:pass@host:port"
BROWSER_PROXY_SERVER = "http://proxy-provider.com:12345"
BROWSER_PROXY_USERNAME = "your-username"  # Optional if auth is in URL
BROWSER_PROXY_PASSWORD = "your-password"  # Optional if auth is in URL
```

**Formats supported:**
```python
# HTTP with inline auth
"http://user:pass@proxy.example.com:12345"

# HTTP with separate credentials
BROWSER_PROXY_SERVER = "http://proxy.example.com:12345"
BROWSER_PROXY_USERNAME = "user"
BROWSER_PROXY_PASSWORD = "pass"

# SOCKS5
"socks5://user:pass@proxy.example.com:1080"
```

## Bandwidth Optimization

The platform automatically blocks resource-heavy content while preserving LinkedIn functionality:

- ❌ Blocks: Third-party images, fonts, stylesheets, media
- ✅ Keeps: All LinkedIn/licdn.com resources, API calls, HTML

**Result**: 60-70% bandwidth reduction with zero functionality loss.

To disable (not recommended):
```python
# In linkedin_cli/browser/login.py, comment out the route blocker:
# context.route("**/*", lambda route: ...)
```

## Proxy Providers Comparison

### Mobile Proxies (Recommended for Cloud)

| Provider | Price | Pool Size | Rotation | Notes |
|----------|-------|-----------|----------|-------|
| **Proxy-Cheap** | $50/month | 7M+ | Sticky/Rotating | Best value |
| **ProxyEmpire** | $100/month | 10M+ | Advanced rotation | Premium |
| **IPRoyal Mobile** | $80/month | 5M+ | Custom rotation | Good support |

### Residential Proxies (Budget Option)

| Provider | Price | Pool Size | Bandwidth | Notes |
|----------|-------|-----------|-----------|-------|
| **IPRoyal** | $1.75/GB | 2M+ | Pay-as-you-go | Best $/GB |
| **Smartproxy** | $8.50/GB | 40M+ | Pay-as-you-go | Good quality |
| **Bright Data** | $4/GB* | 72M+ | Enterprise SLA | Use code RESIGB50 |

## Multi-Profile Strategy

### Cloud Deployment (Multi-Tenant)

**Option A**: 1 Mobile Proxy per 2-3 profiles
- Cost: $25-50/profile/month
- Risk: Low
- Setup: Simple (one proxy URL for all)

**Option B**: Residential proxy pool with rotation
- Cost: $10-30/profile/month (bandwidth-based)
- Risk: Medium
- Setup: Configure rotating proxy endpoint

### Self-Hosted (Recommended)

No proxy needed - each user's daemon runs on their own IP.
- Cost: $0
- Risk: Lowest (using their real IP)
- Setup: None

## Testing Your Proxy

```bash
# Check IP detection
curl --proxy http://user:pass@proxy.example.com:12345 https://api.ipify.org

# Check if IP is flagged as datacenter
curl --proxy http://user:pass@proxy.example.com:12345 https://ipinfo.io
# Look for "type": "hosting" (bad) vs "type": "isp" (good)
```

## Troubleshooting

### Proxy Connection Failed
```
Error: net::ERR_PROXY_CONNECTION_FAILED
```
**Fix**: Check proxy URL format, credentials, and that proxy is online.

### LinkedIn Detects Automation
```
We've detected unusual activity on your account
```
**Causes**:
- Using datacenter/cloud IP (use mobile/residential)
- Too aggressive pacing (reduce velocity)
- Shared proxy with many LinkedIn users

**Fix**: Switch to mobile proxy or reduce aggressiveness preset.

### High Bandwidth Usage

**Check**: Is resource blocking enabled?
```python
# In linkedin_cli/browser/login.py, verify this exists:
context.route("**/*", lambda route: (
    route.abort() if route.request.resource_type in ["image", "media", "font", "stylesheet"]
    ...
```

## Cost Calculator

Use this formula to estimate monthly proxy costs:

```
actions_per_day = velocity * active_hours
actions_per_month = actions_per_day * 30
bandwidth_gb = (actions_per_month * 2.5 MB) / 1024  # Raw
optimized_gb = bandwidth_gb * 0.35  # With blocking (65% reduction)
monthly_cost = optimized_gb * cost_per_gb
```

**Example** (Average preset, IPRoyal):
```
20 actions/hr * 16 hrs = 320 actions/day
320 * 30 = 9,600 actions/month
9,600 * 2.5 MB / 1024 = 23.4 GB raw
23.4 * 0.35 = 8.2 GB optimized
8.2 GB * $1.75 = $14.35/month
```

## Recommendations by Use Case

| Use Case | Solution | Monthly Cost |
|----------|----------|--------------|
| Single user, self-hosted | No proxy | $0 |
| 1-5 users, cloud | Mobile proxy | $50-150 total |
| 10+ users, cloud | Mobile (1 per 3 profiles) | $17-50/profile |
| Enterprise, 100+ users | Bright Data residential | $15-30/profile |
| Budget cloud, 5-10 users | IPRoyal residential | $10-20/profile |

## Security Notes

- **Never commit proxy credentials** to version control
- Use environment variables for sensitive data
- Rotate proxy credentials regularly
- Monitor for IP leaks: https://ipleak.net
- Test proxy quality: https://whoer.net

## References

- [Playwright Proxy Documentation](https://playwright.dev/docs/network#http-proxy)
- [LinkedIn IP Blocklist Discussion](https://github.com/topics/linkedin-automation)
- [Residential vs Mobile Proxies](https://www.zenrows.com/blog/residential-proxies)
