# Activate LenGrowth OpenOutreach - Quick Start

This document provides the quick commands to activate your OpenOutreach campaign for **LenGrowth**.

## Step-by-Step Activation

### 1. Navigate to the OpenOutreach Directory

```bash
cd OpenOutreach
```

### 2. Create Your `.env` File

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
LLM_API_KEY=sk-aws-bedrock-api-key-here
LLM_API_BASE=https://bedrock-mantle.us-east-1.api.aws/v1
AI_MODEL=qwen.qwen3-coder-next
LINKEDIN_USERNAME=your-email@example.com
LINKEDIN_PASSWORD=your-password-here
```

### 3. Run OpenOutreach (Docker - Recommended)

```bash
docker run --pull always -it \
  -p 5900:5900 \
  -p 6080:6080 \
  -v ~/.openoutreach/data:/app/data \
  -v "$(pwd)/.env":/app/.env \
  ghcr.io/eracle/openoutreach:latest
```

**What this does:**
- Pulls the latest OpenOutreach image
- Maps ports 5900 (VNC) and 6080 (noVNC web interface)
- Persists data in `~/.openoutreach/data`
- Mounts your `.env` file for API keys and LinkedIn credentials

### 4. Access the Browser Interface

Open your browser to: **http://localhost:6080/vnc.html**

You'll see the noVNC interface with the LinkedIn automation running.

### 5. Complete the Onboarding Wizard

When prompted, provide:

**Product Description:**
```
LenGrowth is a growth operating system that helps teams turn ideas into actual progress.

It gets the context of your business, shows you what really matters today, and gives you the path to growth with the best wins first.

What we help with:
- Figuring out what to do next for your growth
- Turning good ideas into tasks people actually finish
- Keeping work visible so it does not get lost in Slack or half-finished docs
- Marketing ideas that work for your specific business
- Distribution strategies that match what you are building

How it works:
- We learn your business context first
- Then suggest the next move with clear reasoning
- Help you track the work and keep it in one place
- Give you reusable assets as you go

Why it matters:
A lot of growing teams run into the same problem: too many good ideas, not enough clean follow-through.

They do not need more tools or more meetings. They need a cleaner way to turn their best ideas into work that actually moves the needle.

That is the gap LenGrowth fills.

IDEAL FOR: Founders, Growth Managers, Marketing Directors, and agencies
```

**Campaign Objective:**
```
Campaign Goal: Secure qualified leads for LenGrowth

Primary Objective:
Demonstrate our value as a comprehensive growth operating system that bridges
strategy and execution, converting discovered leads into booked discovery calls.

Target Audience:
- Founders and Growth Operators at scaling startups
- Marketing Leaders at mid-market companies
- Agency Directors managing multiple clients

Success Criteria:
1. High-quality connection requests (40%+ acceptance rate)
2. Engaged follow-up conversations (20-30% response rate)
3. Booked discovery calls (5-10% conversion)
4. Long-term fit identification (qualifying bad leads quickly)
```

**Booking Link:**
```
https://calendly.com/yourcompany/lengrowth-demo
```
*(Replace with your actual booking/demo link)*

### 6. Monitor Your Campaign

- **Browser:** Watch automation in real-time at http://localhost:6080/vnc.html
- **Admin:** http://localhost:8000/admin/ for detailed campaign analytics

## Alternative: Local Installation

If you prefer running locally (not Docker):

```bash
make setup
export LLM_API_KEY=sk-your-openai-api-key-here
export AI_MODEL=gpt-4o
make run
```

Then open admin in another terminal:
```bash
make admin
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No leads found | Check search keywords in Django Admin |
| Rate limit reached | Wait 24h or increase limits in LinkedIn Profile |
| Connection failed | Try restarting, check LinkedIn account status |
| Browser not opening | Check Docker port mappings |

## What Happens Next?

1. **Day 1-3:** Discovery phase - AI searches for leads, qualifies profiles
2. **Day 3-7:** Connection requests sent (follows rate limits)
3. **Day 7-14:** Follow-up messages sent via AI agent
4. **Ongoing:** Booking meetings, tracking conversions

## Support

- Docs: `openoutreach/docs/`
- Setup Guide: `SETUP_GUIDE.md`
- Campaign Config: `docs/lengrowth_campaign.md`

---

**You're all set!** The system will run continuously and autonomously discover, qualify, and contact LinkedIn leads for LenGrowth. 🚀