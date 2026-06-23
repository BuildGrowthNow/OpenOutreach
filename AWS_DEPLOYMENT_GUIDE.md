# AWS Deployment Guide for OpenOutreach

This guide walks you through deploying OpenOutreach on AWS EC2 for 24/7 operation using a **single Docker container** that includes everything:
- **Next.js Frontend** - Web interface
- **Django Backend** - Business logic and API
- **LinkedIn Automation** - Playwright browser automation with VNC
- **Nginx** - Serves the frontend on port 3000

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [GitHub Repository Setup (Deploy Keys)](#github-repository-setup)
3. [AWS Cost Estimates](#aws-cost-estimates)
4. [Quick Start with GitHub Actions](#quick-start-with-github-actions)
5. [Manual Deployment](#manual-deployment)
6. [Access Your Application](#access-your-application)
7. [Updating the Application](#updating-the-application)
8. [Monitoring and Maintenance](#monitoring-and-maintenance)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have:
- An AWS account with EC2 access
- Git installed locally
- A GitHub account for your OpenOutreach repository

---

## GitHub Repository Setup (Deploy Keys)

To clone your repository on AWS EC2, you need to set up deploy keys. This allows your EC2 instance to fetch the code from GitHub without requiring SSH keys for each deployment.

### Option A: Using Deploy Keys (Recommended for single server)

#### Step 1: Generate a Deploy Key

```bash
# Generate a new SSH key pair for your EC2 server
ssh-keygen -t ed25519 -C "openoutreach-ec2-deploy" -f ~/.ssh/openoutreach-ec2

# Don't set a passphrase for automated deployments
```

#### Step 2: Add Public Key to GitHub

1. Go to your GitHub repository: `https://github.com/YOUR_USERNAME/openoutreach/settings/keys`
2. Click **"Deploy keys"** in the left sidebar
3. Click **"Add deploy key"**
4. Enter a title (e.g., "EC2 Deploy Key")
5. Paste the contents of your public key:
   ```bash
   cat ~/.ssh/openoutreach-ec2.pub
   ```
6. Check **"Allow write access"** if you plan to deploy via CI/CD
7. Click **"Add key"**

#### Step 3: Copy Private Key to Your EC2 Instance

```bash
# Copy the private key to your EC2 instance
scp -i "your-existing-key.pem" ~/.ssh/openoutreach-ec2 ubuntu@<EC2_PUBLIC_IP>:~/.ssh/id_rsa

# Or manually on the EC2 instance:
# ssh ubuntu@<EC2_PUBLIC_IP>
# mkdir -p ~/.ssh && chmod 700 ~/.ssh
# echo 'your-private-key-content' > ~/.ssh/id_rsa
# chmod 600 ~/.ssh/id_rsa
```

#### Step 4: Add GitHub to Known Hosts

```bash
# On EC2 instance, add GitHub to known_hosts
ssh-keyscan -H github.com >> ~/.ssh/known_hosts
```

### Option B: Using Personal Access Token (Alternative)

If you prefer not to use SSH keys:

```bash
# Clone using HTTPS with Personal Access Token
git clone https://YOUR_TOKEN@github.com/YOUR_USERNAME/openoutreach.git
```

### Verify Repository Access

```bash
# Test cloning the repository
git clone git@github.com:YOUR_USERNAME/openoutreach.git ~/openoutreach
cd ~/openoutreach
git pull
```

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
   Name: OpenOutreach
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
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=OpenOutreach}]'
```

---

## Step 2: Configure Security Group

### Purpose
Security groups act as a firewall. For OpenOutreach, you need:
- **SSH (port 22)** - For remote access
- **Frontend (port 3000)** - For Next.js frontend access
- **noVNC (port 6080)** - For web-based VNC interface
- **VNC (port 5900)** - For VNC protocol access
- **LinkedIn (outbound 443/80)** - For LinkedIn connections

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
    --port 3000 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 6080 \
    --cidr 0.0.0.0/0

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxxxxx \
    --protocol tcp \
    --port 5900 \
    --cidr 0.0.0.0/0
```

### Or via AWS Console

1. Go to **EC2 Dashboard** → **Security Groups**
2. **Create Security Group**
   - Name: `openoutreach-sg`
   - Description: `Security group for OpenOutreach`
3. **Add Inbound Rules:**
   - SSH (22) - Source: My IP or 0.0.0.0/0
   - Custom TCP (3000) - Source: 0.0.0.0/0 (Frontend)
   - Custom TCP (6080) - Source: 0.0.0.0/0 (noVNC)
   - Custom TCP (5900) - Source: 0.0.0.0/0 (VNC)

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

# Add Docker repository using Ubuntu 22.04 (jammy) codename
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  jammy stable" | \
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

### Alternative: One-Liner Install

```bash
# Install Docker using official script with codename override
curl -fsSL https://get.docker.com -o get-docker.sh
sudo UBUNTU_CODENAME=jammy sh get-docker.sh
sudo usermod -aG docker ubuntu
```

### Reconnect after adding to docker group

```bash
# Exit and reconnect to apply group changes
exit
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>
```

---

## Step 4: Clone and Setup OpenOutreach

### Clone the Repository

```bash
# Clone your OpenOutreach repository
cd ~
git clone https://github.com/YOUR_USERNAME/openoutreach.git openoutreach
cd openoutreach

# Or using SSH with deploy key:
# git clone git@github.com:YOUR_USERNAME/openoutreach.git openoutreach
```

### Create Environment File

```bash
# Create environment file with your configuration
cat > .env << 'EOF'
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=false
# Add other environment variables as needed
EOF
```

### Create Data Directory

```bash
# Create necessary directories
mkdir -p data
mkdir -p openoutreach/media

# Set permissions
chmod 755 data
chmod 755 openoutreach/media
```

### Build and Start the Application

```bash
# Build the Docker image (single container with frontend + backend)
docker build -t openoutreach:latest .

# Or use docker-compose
docker-compose build

# Start all services
docker-compose up -d

# Verify services are running
docker-compose ps
```

---

## Step 5: Verify Deployment

### Check Container Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f openoutreach

# Check container health
docker inspect --format='{{.State.Health.Status}}' openoutreach
```

### Test Frontend Access

```bash
# Get your EC2 public IP
hostname -I

# Test the frontend
curl http://localhost:3000
```

---

## Step 6: Access Your Application

### Frontend (Web Interface)

Open your browser and go to:
```
http://<EC2_PUBLIC_IP>:3000
```

### VNC Browser (LinkedIn Automation)

Open your browser and go to:
```
http://<EC2_PUBLIC_IP>:6080/vnc.html
```

### Complete Onboarding Wizard

1. In the VNC browser, complete the onboarding wizard
2. Enter your LinkedIn credentials
3. Set up your campaigns
4. Watch automation live in the browser

---

## Step 7: Updating the Application

### Using Git (Recommended)

```bash
# SSH into your server
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>

# Navigate to project directory
cd ~/openoutreach

# Pull latest changes
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d
```

### Using GitHub Actions (CI/CD)

See the [Quick Start with GitHub Actions](#quick-start-with-github-actions) section below.

---

## Quick Start with GitHub Actions

This project includes automated CI/CD via GitHub Actions. Every commit to `main` or `master` automatically deploys to your EC2 server.

### Prerequisites

1. **Deploy Key for EC2:**
```bash
# Generate a new key (or use existing)
ssh-keygen -t ed25519 -f ~/.ssh/openoutreach-ec2 -C "openoutreach-deployment"
```

2. **Add SSH Private Key to GitHub Secrets:**
   - Go to Your GitHub Repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `EC2_SSH_KEY`
   - Value: Paste the contents of your private key (`~/.ssh/openoutreach-ec2`)

3. **Add EC2 Connection Details:**
   - Name: `EC2_HOST` (your EC2 public IP or DNS)
   - Name: `EC2_USER` (usually `ubuntu`)

4. **Add Environment Variables:**
   - Name: `DJANGO_SECRET_KEY`
   - Name: `DJANGO_DEBUG` (optional)

### GitHub Actions Workflow

The workflow is defined in `.github/workflows/deploy-aws.yml` and runs automatically on:
- Pushes to `main` or `master` branch
- Manual workflow dispatch

### Manual Deployment Trigger

To trigger a deployment manually:
1. Go to your GitHub repository → Actions tab
2. Select "Deploy to AWS EC2" workflow
3. Click "Run workflow" → "Run workflow"

Or via CLI:
```bash
git push origin main
```

---

## Step 8: Monitor and Maintain

### Health Check Commands

```bash
# Check container is running
docker-compose ps

# View logs for debugging
docker-compose logs -f openoutreach

# Check docker stats
docker stats

# Check disk space
df -h

# Check memory usage
free -h

# Check container health
docker inspect --format='{{.State.Health.Status}}' openoutreach
```

### Backing Up Data

```bash
# Stop containers
docker-compose down

# Create backup
tar -czvf openoutreach-backup-$(date +%Y%m%d).tar.gz data/

# Move backup to safe location
cp openoutreach-backup-*.tar.gz ~/backups/

# Restart containers
docker-compose up -d
```

### Updating OpenOutreach

```bash
# Pull latest changes
git pull

# Rebuild image
docker-compose build

# Restart containers
docker-compose up -d
```

### Troubleshooting

```bash
# Container not starting?
docker logs openoutreach

# Check if ports are in use
sudo lsof -i :3000
sudo lsof -i :6080

# Restart container
docker-compose restart

# Rebuild if needed
docker-compose up -d --build

# Remove all containers and volumes (careful!)
docker-compose down -v
docker-compose up -d --build
```

---

## Important Notes

1. **Single Docker Architecture**: This project uses a single Dockerfile that builds and runs everything in one container:
   - Frontend is built during Docker build time
   - Nginx serves the frontend on port 3000
   - Django serves the API on port 8000 (proxied by nginx)
   - LinkedIn automation runs in the background with VNC

2. **Security Considerations**:
   - Never commit `.env` files with credentials to your repository
   - Use HTTPS in production (consider CloudFront + ACM or Let's Encrypt)
   - Restrict security group access to your IP when possible
   - Keep your deploy keys secure

3. **Data Persistence**: All data (LinkedIn sessions, campaigns, media) is stored in the Docker volume `./data`

4. **Cost Management**:
   - Use `docker-compose down` when not actively running
   - Consider spot instances for cost savings
   - Monitor with AWS Cost Explorer

---

## GitHub Actions CI/CD Deployment Details

### Prerequisites

1. **SSH Key for EC2:**
```bash
# Generate a new key (or use existing)
ssh-keygen -t ed25519 -f ~/.ssh/openoutreach-ec2 -C "openoutreach-deployment"

# Copy the public key to your EC2 instance
ssh-copy-id -i ~/.ssh/openoutreach-ec2.pub ubuntu@<EC2_PUBLIC_IP>
```

2. **Add SSH Private Key to GitHub Secrets:**
   - Go to Your GitHub Repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `EC2_SSH_KEY`
   - Value: Paste the contents of your private key (`~/.ssh/openoutreach-ec2`)

3. **Add EC2 Host Fingerprint (optional, for security):**
```bash
ssh-keyscan -H <EC2_PUBLIC_IP>
# Add the output to your repository's known_hosts if needed
```

### GitHub Actions Workflow

The workflow is defined in `.github/workflows/deploy-aws.yml` and runs automatically on:
- Pushes to `main` or `master` branch
- Manual workflow dispatch

### Manual Deployment Trigger

To trigger a deployment manually:
```bash
git push origin main
```

### Manual Deployment via SSH (Alternative)

If you prefer not to use GitHub Actions:

```bash
# Clone the repository on EC2
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>
cd ~
git clone https://github.com/YOUR_USERNAME/openoutreach.git openoutreach
cd openoutreach

# Create .env file
cat > .env << 'EOF'
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=false
EOF

# Build and start
docker-compose up -d --build
```

### Log Files Location

After deployment, logs are stored on the EC2 instance:
- **Docker logs:** `docker-compose logs openoutreach`
- **Django data directory:** `/app/data/`
- **Media files:** `/app/openoutreach/media/`

### Security Considerations

1. **HTTPS**: Currently, the setup uses HTTP. For production, consider:
   - Adding a reverse_proxy (nginx) with SSL termination
   - Using AWS ACM + CloudFront
   - Installing a Let's Encrypt certificate

2. **Environment Variables**: Never commit `.env` to your repository

3. **Firewall**: Ensure your security group only allows necessary ports:
   - Port 22 (SSH) - restrict to your IP
   - Port 3000 (HTTP) - 0.0.0.0/0
   - Port 6080 (noVNC) - consider restricting to your IP

---

## Cost-Saving Tips

1. **Use t3/t4g instances** - Burstable performance means you pay less for baseline
2. **Stop when not needed** - Use `docker-compose down` when not running
3. **Use Reserved Instances** - Save up to 75% for 1-year commitment
4. **Monitor data transfer** - Outbound data costs ~$0.09/GB

---

## Quick Reference Commands

```bash
# Connect to EC2
ssh -i "openoutreach-key.pem" ubuntu@<EC2_PUBLIC_IP>

# Navigate to project
cd ~/openoutreach

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f openoutreach

# Rebuild and restart
docker-compose up -d --build

# Check status
docker-compose ps

# Create backup
tar -czvf openoutreach-backup-$(date +%Y%m%d).tar.gz data/

# Clone repository with deploy key
git clone git@github.com:YOUR_USERNAME/openoutreach.git
```

---

## Estimated Monthly Costs Summary

| Scenario | Instance | Monthly Cost |
|----------|----------|--------------|
| **Minimal** | t3.micro | ~$7-10 |
| **Single Profile** | t3.small | ~$14-20 |
| **Multiple Profiles** | t3.medium | ~$28-35 |
| **Heavy Usage** | t3.large | ~$56-70 |

**Data Storage**: ~$0.10-0.50/month (EBS volumes)

**Total estimated range**: **$7-70/month** depending on instance size

---

## Appendix: What's in the Single Dockerfile

The unified Dockerfile (`Dockerfile`) in your project does the following:

1. **Stage 1 - Frontend Build**: Uses Node.js to build your Next.js frontend
2. **Stage 2 - Python Dependencies**: Installs all Python packages using uv
3. **Stage 3 - Runtime**: Combines everything into a single container with:
   - Next.js frontend (served via nginx on port 3000)
   - Django backend (API on port 8000)
   - LinkedIn automation (Playwright + Chromium)
   - VNC server for browser access (ports 5900, 6080)

No separate frontend Dockerfile or backend Dockerfile is needed - everything runs in one container.