# LenGrowth OpenOutreach Setup Guide

This guide walks you through setting up OpenOutreach for use with **LenGrowth** to automate LinkedIn outreach for lead generation.

## Prerequisites

Before you begin, ensure you have:

1. **A LinkedIn account** - The account you'll use for outreach (ideally a professional/business account)

2. **An LLM API Key** - One of:
   - [OpenAI API Key](https://platform.openai.com/api-keys) (recommended - uses GPT-4o)
   - [Anthropic API Key](https://console.anthropic.com/settings/keys) (for Claude)
   - AWS Bedrock (OpenAI-compatible endpoint) - `https://bedrock-mantle.us-east-1.api.aws/v1`
   - Any other OpenAI-compatible endpoint

3. **Docker Desktop** (for Docker deployment) OR
   **Python 3.12+** (for local installation)

## Quick Start (Docker - Recommended)

### 1. Navigate to OpenOutreach Directory

```bash
cd OpenOutreach
```

### 2. Create `.env` File

Copy the example environment file:

```bash
cp .env.example .env
```

Edit the `.env` file with your credentials:

```env
# AWS Bedrock (Qwen qwen3-coder-next model)
LLM_API_KEY=sk-your-aws-bedrock-api-key-here
LLM_API_BASE=https://bedrock-mantle.us-east-1.api.aws/v1
AI_MODEL=qwen.qwen3-coder-next

# OR use OpenAI (uncomment to switch)
# LLM_API_KEY=sk-your-openai-api-key-here
# AI_MODEL=gpt-4o

LINKEDIN_USERNAME=your-email@example.com
LINKEDIN_PASSWORD=your-password-here
```

### 3. Run with Docker

```bash
docker run --pull always -it \
  -p 5900:5900 \
  -p 6080:6080 \
  -v ~/.openoutreach/data:/app/data \
  -v "$(pwd)/.env":/app/.env \
  ghcr.io/eracle/openoutreach:latest
```

**What this does:**
- Maps port 5900 for VNC connections
- Maps port 6080 for noVNC web interface
- Persists data to `~/.openoutreach/data`
- Mounts your `.env` file for configuration

### 4. Access the Web Interface

Open your browser and go to:
```
http://localhost:6080/vnc.html
```

You should see the noVNC web interface. Click "Connect" and you'll see the automation in action.

### 5. Adding Your Existing 1st-Degree Connections (15k+ Connections)

If you already have 15k+ LinkedIn connections, use the bulk import script to add them all at once:

#### Step 1: Export Your LinkedIn Connections

1. Go to https://www.linkedin.com/myservices/connections-export/
2. Click **Export** to download your connections CSV file

#### Step 2: Run the Bulk Import Script

```bash
cd OpenOutreach
python bulk_add_connections.py --source /path/to/your_connections.csv
```

The script will:
- Parse your CSV file
- Create Lead records for each connection
- Create QUALIFIED Deals (skipping qualification)
- Add them to your campaign for messaging

#### What This Does

The system will create **QUALIFIED** deals for your existing 1st-degree connections, meaning they:
- Skip the qualification step
- Go directly to the follow-up messaging queue  
- DON'T need connection requests (you're already connected)
- The AI will message them directly about LenGrowth

#### Alternative: Manual Upload via Django Admin

For a small number of connections (< 100), you can also use the Django Admin:
1. Go to http://localhost:8000/admin/
2. Navigate to **LinkedIn > Campaigns**
3. Find your campaign
4. Edit the **Seed profile URLs** field with your connections' LinkedIn URLs
5. Save

## Local Installation (Development)

If you prefer to run locally instead of Docker:

### 1. Install Dependencies

```bash
cd OpenOutreach
make setup
```

This.command will:
- Install Python dependencies
- Install Playwright browsers
- Run database migrations
- Bootstrap the CRM

### 2. Set Environment Variables

```bash
# AWS Bedrock (Qwen qwen3-coder-next model)
export LLM_API_KEY=sk-your-aws-bedrock-api-key-here
export LLM_API_BASE=https://bedrock-mantle.us-east-1.api.aws/v1
export AI_MODEL=qwen.qwen3-coder-next

# OR use OpenAI (uncomment to switch)
# export LLM_API_KEY=sk-your-openai-api-key-here
# export AI_MODEL=gpt-4o

export LINKEDIN_USERNAME=your-email@example.com
export LINKEDIN_PASSWORD=your-password-here
```

### 3. Create Admin User

```bash
python manage.py createsuperuser
```

Follow the prompts to create your admin account.

### 4. Start the Daemon

```bash
make run
```

### 5. Start the Admin Interface (in another terminal)

```bash
make admin
```

Then open: http://localhost:8000/admin/

## Configuring the LenGrowth Campaign

When you first run OpenOutreach, you'll go through an onboarding wizard. Here's what to configure:

### Product Description (for LenGrowth)

Use this product description:

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

Ideal for: Founders, Growth Managers, Marketing Directors, and agencies managing multiple clients who need a centralized system for strategy, execution, and tracking.
```

### Campaign Objective

```
Campaign Goal: Secure qualified leads for LenGrowth

Primary Objective:
Turn ideas into actual progress by showing how LenGrowth helps teams bridge the gap between strategy and execution.

Target Audience:
- Founders and Growth Operators at scaling startups
- Marketing Leaders at mid-market companies
- Agency Directors managing multiple clients
- Business Development leaders seeking better processes

Success Criteria:
1. High-quality connection requests (40%+ acceptance rate)
2. Engaged follow-up conversations (20-30% response rate)
3. Booked discovery calls (5-10% conversion)
4. Long-term fit identification (qualifying bad leads quickly)

What We Will NOT Do:
- Spam or aggressive selling
- Contact inappropriate accounts (large enterprises, job seekers)
- Make unrealistic claims or promises
- Ignore follow-up frequency limits
```

### Booking Link

Enter your booking/demo link (e.g., Calendly, Lengrowth demo page, etc.)

## Understanding the LinkedIn Automation

### How It Works

1. **Discovery Phase**: The AI generates LinkedIn search queries based on your product description and campaign objective
2. **Lead Identification**: The system finds potential leads using the search queries
3. **Qualification**: A Bayesian ML model and LLM work together to qualify leads based on your ideal customer profile
4. **Connection Requests**: Qualified leads receive connection requests
5. **Follow-Up**: Once connected, the AI agent manages multi-turn conversations to book meetings

### What's Smart About This

- **Active Learning**: The system starts broadly but gets smarter over time about which leads are best for your campaign
- **Undetectable**: Uses Playwright + stealth plugins to mimic real user behavior
- **Self-Healing**: Automatically handles rate limits and LinkedIn restrictions
- **.Persistent State**: All data is saved locally; you can stop and restart anytime

## Managing Your Campaign

### Through the Web Interface

1. Open http://localhost:6080/vnc.html
2. The automation runs in the browser window
3. All data is persisted in the database

### Through Django Admin

1. Start admin: `make admin` or click the "Admin" button in the web interface
2. Visit http://localhost:8000/admin/
3. Log in with your admin credentials
4. Navigate to:
   - **LinkedIn > Campaigns** - Edit your campaign details
   - **LinkedIn > LinkedIn Profile** - Update rate limits
   - **CRM > Deals** - View your leads and follow-up progress

### Key Settings in Django Admin

- **Campaign**:
  - Edit `product_docs` with updated product description
  - Edit `campaign_objective` with new campaign goals
  - Set or update `booking_link`

- **LinkedIn Profile**:
  - `connect_daily_limit` - How many connection requests per day
  - `follow_up_daily_limit` - How many follow-up messages per day

## Troubleshooting

### Common Issues

**Issue**: "Rate limit reached"
- **Solution**: Wait 24 hours or increase limits in Django Admin > LinkedIn Profile

**Issue**: "Connection request failed"
- **Solution**: This is normal initially. Increase connection limits slightly and try again

**Issue**: "No leads found"
- **Solution**: Check your search keywords in Django Admin > LinkedIn > Search Keywords. Add more keywords related to your target market

**Issue**: "All leads disqualified"
- **Solution**: Your criteria may be too strict. Loosen the qualification criteria or expand your search keywords

**Issue**: "Browser automation failed"
- **Solution**: Try restarting the container or local process. Check for LinkedIn updates that may affect automation

### Logs & Monitoring

Check the logs for detailed information:
- Docker: `docker logs <container_id>`
- Local: Check your terminal output
- Django Admin: View the Task model for task status

## Next Steps After Setup

1. **Start with a small test**: Run for a day with low limits (5 connections, 5 follow-ups)
2. **Review results**: Check which leads qualified and why
3. **Tune keywords**: Add/remove keywords based on what's working
4. **Scale up**: Gradually increase limits as you see good results
5. **Monitor daily**: Check your leads and follow up on important conversations

## Getting Help

- Check the [OpenOutreach Documentation](./docs/)
- Review the [Architecture Guide](./docs/architecture.md)
- Join the [Telegram Community](https://t.me/+Y5bh9Vg8UVg5ODU0)

## Important Notes

### Data Persistence

All your data (leads, campaigns, messages) is stored in:
- Docker: `~/.openoutreach/data/db.sqlite3`
- Local: `openoutreach/data/db.sqlite3`

This means your progress is saved between restarts.

### Rate Limits

LinkedIn has unofficial limits. Default settings:
    - **50 connection requests/day** - Conservative but safe
    - **100 follow-up messages/day** - Moderate pace

Adjust based on your experience. Start conservative and increase gradually.

### Ethical Use

- Always provide value in your messages
- Don't spam - focus on quality over quantity
- Respect LinkedIn's terms of service
- Be prepared to answer questions about your offering

## Success Metrics

Track these metrics:

1. **Connection acceptance rate** - Aim for 40%+
2. **Response rate** - Aim for 20-30% on follow-ups
3. **Conversion rate** - Aim for 5-10% of conversations resulting in meetings

If your metrics are low:
- Review your product description and campaign objective
- Check your initial messages (should be personalized)
- Adjust your target audience keywords

---

**You're now ready to start outreach for LenGrowth!** 🚀

The first time you run, the onboarding wizard will guide you through the final setup. Welcome to autonomous lead generation!