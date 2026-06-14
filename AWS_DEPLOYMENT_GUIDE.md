# AWS Deployment Guide for OpenOutreach

This guide walks you through deploying OpenOutreach on AWS EC2 for 24/7 operation, supporting multiple LinkedIn profiles (one per container).

---

## Table of Contents
1. [AWS Cost Estimates](#aws-cost-estimates)
2. [Step 1: Create EC2 Instance](#step-1-create-ec2-instance)
3. [Step 2: Configure Security Group](#step-2-configure-security-group)
4. [Step 3: Install Docker](#step-3-install-docker)
5. [Step 4: Setup Docker Compose](#step-4-setup-docker-compose)
6. [Step 5: Create Profile Configurations](#step-5-create-profile-configurations)
7. [Step 6: Deploy with Docker Compose](#step-6-deploy-with-docker-compose)
8. [Step 7: Configure LinkedIn Profiles](#step-7-configure-linkedin-profiles)
9. [Step 8: Monitor and Maintain](#step-8-monitor-and-maintain)

---

## AWS Cost Estimates ($/month)

### EC2 Instance Types

| Instance | vCPU | RAM | Storage | Monthly Cost (us-east-1) | Best For |
|----------|------|-----|---------|--------------------------|----------|
| **t3.micro** | 2 | 1 GB | EBS only | ~$7-10 | Testing, small campaigns |
| **t3.small** | 2 | 2 GB | EBS only | ~$14-20 | 1-2 profiles, moderate traffic |
| **t3.medium** | 2 | 4 GB | EBS only | ~$28-35 | 2-3 profiles, serious outreach |
| **t3.large** | 2 | 8 GB | EBS only | ~$56-70 | 3-5 profiles, heavy outreach |
| **t4g.micro** | 2 | 1 GB | EBS only | ~$5-8 | Testing (ARM, cheaper) |

**Notes:**
- **t3/t4g instances** are "burstable" - good for intermittent workloads like social media automation
- EBS storage is billed separately (~$0.10/Gb/month)
- Data transfer costs ~$0.09/GB outbound
- **Estimated monthly cost range: $7-70 + EBS**

**Recommended:** `t3.small` or `t3.medium` for reliable 24/7 operation

---

## Step 1: Create EC2 Instance

### Using AWS Console

1. **Login to AWS Console** - https://console.aws.amazon.com/ec2/

2. **Click "Launch Instances"**
   - Click "Launch instance" button

3. **Configure Instance**
   ```
   Name: OpenOutreach-Profile1
   Application and OS: Ubuntu (latest - 22.04 or 24.04)
   Instance type: t3.small (recommended for 1-2 profiles)
   Key pair: Create new or use existing
   ```

4. **Configure Security Group** (see Step 2 below)

5. **Click "Launch instance"**

### Using AWS CLI (Alternative)

```bash
# First, create a key pair (if you don't have one)
aws ec2 create-key-pair --key-name openoutreach-key --query 'KeyMaterial' --output text > openoutreach-key.pem
chmod 400 openoutreach-key.pem

# Create the instance
aws ec2 run-instances \
    --image-id ami-0c55b159cbfafe1f0 \
    --instance-type t3.small \
    --key-name openoutreach-key \
    --security-group-ids sg-xxxxxxxx \
    --region us-east-1 \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=OpenOutreach-Profile1}]'
```

---

## Step 2: Configure Security Group

### Purpose
Security groups act as a firewall. For OpenOutreach, you need:
- **SSH (port 22)** - For remote access
- **VNC (port 5900)** - For browser automation access
- **noVNC web (port 6080)** - For web-based VNC interface
- **Django Admin (port 8000)** - For management
- **LinkedIn (ports 443/80)** - Outbound for LinkedIn connections

### Create Security Group

```bash
# Create security group
aws ec2 create-security-group \
    --group-name openoutreach-sg \
    --description "Security group for OpenOutreach" \
    --vpc-id vpc-xxxxxxxx

# Add rules
aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 5900 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 6080 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 8000 \
    --cidr 0.0.0.0/0
```

### Or via AWS Console

1. Go to **EC2 Dashboard** → **Security Groups**
2. **Create Security Group**
   - Name: `openoutreach-sg`
   - Description: `Security group for OpenOutreach`
3. **Add Inbound Rules:**
   - SSH (22) - Source: My IP or 0.0.0.0/0
   - Custom TCP (5900) - Source: 0.0.0.0/0
   - Custom TCP (6080) - Source: 0.0.0.0/0
   - Custom TCP (8000) - Source: 0.0.0.0/0

---

## Step 3: Install Docker

### Connect to Your EC2 Instance

```bash
# SSH into your instance
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>

# Example:
ssh -i "openoutreach-key.pem" ubuntu@ec2-12-34-56-78.compute-1.amazonaws.com
```

### Install Docker

```bash
# Update package list
sudo apt update

# Install required packages
sudo apt install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
docker-compose --version

# Add ubuntu user to docker group (so you don't need sudo)
sudo usermod -aG docker ubuntu
```

### Reconnect after adding to docker group

```bash
# Exit and reconnect to apply group changes
exit
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

---

## Step 4: Setup Docker Compose

### Create Project Directory

```bash
# Create project directory
mkdir -p ~/openoutreach
cd ~/openoutreach

# Create data directory for persistence
mkdir -p data
chmod 777 data
```

### Create docker-compose.yml

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  # Profile 1: LinkedIn Account 1
  profile1:
    image: ghcr.io/eracle/openoutreach:latest
    container_name: openoutreach-profile1
    ports:
      - "5901:5900"  # VNC port (mapped to 5901 to avoid conflict)
      - "6081:6080"  # noVNC web port (mapped to 6081)
    volumes:
      - ./data/profile1:/app/data
      - ./profile1.env:/app/.env
    restart: unless-stopped
    security_opt:
      - seccomp:unconfined
    cap_add:
      - SYS_ADMIN
    shm_size: 2gb

  # Profile 2: LinkedIn Account 2 (uncomment to add more)
  # profile2:
  #   image: ghcr.io/eracle/openoutreach:latest
  #   container_name: openoutreach-profile2
  #   ports:
  #     - "5902:5900"
  #     - "6082:6080"
  #   volumes:
  #     - ./data/profile2:/app/data
  #     - ./profile2.env:/app/.env
  #   restart: unless-stopped
  #   security_opt:
  #     - seccomp:unconfined
  #   cap_add:
  #     - SYS_ADMIN
  #   shm_size: 2gb

  # Profile 3: LinkedIn Account 3 (uncomment to add more)
  # profile3:
  #   image: ghcr.io/eracle/openoutreach:latest
  #   container_name: openoutreach-profile3
  #   ports:
  #     - "5903:5900"
  #     - "6083:6080"
  #   volumes:
  #     - ./data/profile3:/app/data
  #     - ./profile3.env:/app/.env
  #   restart: unless-stopped
  #   security_opt:
  #     - seccomp:unconfined
  #   cap_add:
  #     - SYS_ADMIN
  #   shm_size: 2gb
EOF
```

---

## Step 5: Create Profile Configurations

### Create Environment Files

```bash
# Profile 1 configuration
cat > profile1.env << 'EOF'
# AWS Bedrock (Qwen model)
LLM_API_KEY=sk-your-aws-bedrock-api-key-here
LLM_API_BASE=https://bedrock-mantle.us-east-1.api.aws/v1
AI_MODEL=qwen.qwen3-coder-next

# OR use OpenAI
# LLM_API_KEY=sk-your-openai-api-key-here
# AI_MODEL=gpt-4o

LINKEDIN_USERNAME=your-email@example.com
LINKEDIN_PASSWORD=your-password-here
EOF

# Profile 2 configuration (if adding more)
# cat > profile2.env << 'EOF'
# LLM_API_KEY=sk-your-openai-api-key-here
# AI_MODEL=gpt-4o
# LINKEDIN_USERNAME=profile2-email@example.com
# LINKEDIN_PASSWORD=your-password-here
# EOF
```

### Verify File Structure

```bash
ls -la

# Should show:
# - docker-compose.yml
# - profile1.env
# - profile2.env (if created)
# - data/ directory
```

---

## Step 6: Deploy with Docker Compose

### Start All Services

```bash
# Pull and start all containers
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f profile1
```

### Stop Services

```bash
# Stop all containers
docker compose down

# Stop and remove volumes (data)
docker compose down -v
```

### Check Container Status

```bash
# View running containers
docker ps

# View logs for specific profile
docker logs openoutreach-profile1 -f

# View resource usage
docker stats
```

---

## Step 7: Configure LinkedIn Profiles

### Access the web interface

Open your browser and go to:

```
http://<EC2_PUBLIC_IP>:6081/vnc.html
```

For Profile 2:
```
http://<EC2_PUBLIC_IP>:6082/vnc.html
```

### Complete OnboardingWizard

Each profile will go through the onboarding wizard:

1. **Product Description** (LenGrowth):
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

2. **Campaign Objective**:
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

3. **Booking Link**:
```
https://calendly.com/yourcompany/lengrowth-demo
```

---

## Step 8: Monitor and Maintain

### Health Check Commands

```bash
# Check all containers are running
docker compose ps

# View logs for debugging
docker compose logs profile1 --tail=100

# Check docker stats
docker stats

# Check disk space
df -h

# Check memory usage
free -h
```

### Backing Up Data

```bash
# Stop containers
docker compose down

# Create backup
tar -czvf openoutreach-backup-$(date +%Y%m%d).tar.gz data/

# Move backup to safe location
cp openoutreach-backup-*.tar.gz ~/backups/

# Restart containers
docker compose up -d
```

### Updating OpenOutreach

```bash
# Pull latest image
docker compose pull

# Restart containers
docker compose up -d
```

### Troubleshooting

```bash
# Container not starting?
docker logs openoutreach-profile1

# Check if port is in use
sudo lsof -i :5901

# Restart a specific profile
docker compose restart profile1

# Rebuild if needed
docker compose up -d --build
```

---

## Cost-Saving Tips

1. **Use t3/t4g instances** - Burstable performance means you pay less for baseline
2. **Stop when not needed** - Use `docker compose down` when not running
3. **Use Reserved Instances** - Save up to 75% for 1-year commitment
4. **Monitor data transfer** - Outbound data costs ~$0.09/GB

---

## Quick Reference Commands

```bash
# Connect to EC2
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>

# Start all profiles
cd ~/openoutreach && docker compose up -d

# Stop all profiles
cd ~/openoutreach && docker compose down

# View logs
docker compose logs -f profile1

# Check status
docker compose ps
```

---

## Estimated Monthly Costs Summary

| Scenario | Instance | Monthly Cost |
|----------|----------|--------------|
| **Minimal** | t3.micro + 1 profile | ~$10 |
| **Single Profile** | t3.small + 1 profile | ~$20 |
| **Two Profiles** | t3.small + 2 profiles | ~$25-30 |
| **Three Profiles** | t3.medium + 3 profiles | ~$35-40 |
| **Five Profiles** | t3.large + 5 profiles | ~$60-70 |

**Data Storage**: ~$0.10-0.50/month (EBS volumes grow as you accumulate leads)

**Total estimated range**: **$10-70/month** depending on campaign scale