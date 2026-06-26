# Nginx SSL Setup Guide for OpenOutreach

This guide covers setting up nginx with free SSL certificates (Let's Encrypt) for your subdomains:
- `linkedin.lengrowth.com` → Frontend (port 3000)
- `linkedin-api.lengrowth.com` → API (port 8000)

---

## Prerequisites

You already have:
- DNS A records pointing to your server IP: `50.19.251.160`
  - `linkedin.lengrowth.com` → `50.19.251.160`
  - `linkedin-api.lengrowth.com` → `50.19.251.160`

---

## Step 1: Install Nginx

```bash
# SSH into your server
ssh -i "your-key.pem" ubuntu@50.19.251.160

# Update and install nginx
sudo apt update
sudo apt install -y nginx
```

---

## Step 2: Configure Nginx for Both Subdomains

### Create Configuration Files

Create the frontend configuration:

```bash
sudo nano /etc/nginx/sites-available/linkedin.lengrowth.com
```

**Configuration for `linkedin.lengrowth.com` (Frontend):**
```nginx
# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name linkedin.lengrowth.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name linkedin.lengrowth.com;
    http2 on;

    # SSL Certificate paths (will be set by certbot)
    ssl_certificate /etc/letsencrypt/live/linkedin.lengrowth.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/linkedin.lengrowth.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Root directory
    root /var/www/html;
    index index.html index.htm;

    # Frontend proxy (Next.js on port 3000)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

---

Create the API configuration:

```bash
sudo nano /etc/nginx/sites-available/linkedin-api.lengrowth.com
```

**Configuration for `linkedin-api.lengrowth.com` (API):**
```nginx
# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name linkedin-api.lengrowth.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name linkedin-api.lengrowth.com;
    http2 on;

    # SSL Certificate paths (will be set by certbot)
    ssl_certificate /etc/letsencrypt/live/linkedin-api.lengrowth.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/linkedin-api.lengrowth.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Django API proxy (port 8000)
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Media files
    location /media/ {
        alias /app/openoutreach/media/;
    }

    # Static files
    location /static/ {
        alias /app/static/;
    }
}
```

---

## Step 3: Create Temp Nginx Config (without SSL references for initial certbot run)

### View current nginx config:

```bash
sudo cat /etc/nginx/sites-available/linkedin.lengrowth.com
```

If certbot already updated it, you should see SSL config. If it's still HTTP-only, replace with:

**Complete Configuration (HTTP to HTTPS redirect + SSL):**
```nginx
# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name linkedin.lengrowth.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name linkedin.lengrowth.com;

    # SSL Certificate paths
    ssl_certificate /etc/letsencrypt/live/linkedin.lengrowth.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/linkedin.lengrowth.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend proxy (Next.js on port 3000)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### Create the API configuration:

**Complete Configuration (HTTP to HTTPS redirect + SSL):**
```nginx
# HTTP server - redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name linkedin-api.lengrowth.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name linkedin-api.lengrowth.com;

    # SSL Certificate paths
    ssl_certificate /etc/letsencrypt/live/linkedin-api.lengrowth.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/linkedin-api.lengrowth.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Django API proxy (port 8000)
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Media files
    location /media/ {
        alias /app/openoutreach/media/;
    }

    # Static files
    location /static/ {
        alias /app/static/;
    }
}
```

### Enable sites and test:

```bash
# Enable the configurations by creating symlinks
sudo ln -s /etc/nginx/sites-available/linkedin.lengrowth.com /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/linkedin-api.lengrowth.com /etc/nginx/sites-enabled/

# Remove default configuration
sudo rm /etc/nginx/sites-enabled/default 2>/dev/null || true

# Test nginx configuration (should pass now)
sudo nginx -t

# Start nginx
sudo systemctl start nginx
```

---

## Step 4: Install Certbot and Get SSL Certificates

### Install Certbot

```bash
# Install certbot and nginx plugin
sudo apt install -y certbot python3-certbot-nginx
```

### Request SSL Certificates

**Method 1: Automatic (Recommended)** - Certbot will automatically modify nginx config:

```bash
# Get certificate for both domains
sudo certbot --nginx -d linkedin.lengrowth.com -d linkedin-api.lengrowth.com
```

**Method 2: Manual** - Certbot will only get certificates (you manage nginx config):

```bash
# Get certificate without modifying nginx config
sudo certbot certonly --nginx -d linkedin.lengrowth.com -d linkedin-api.lengrowth.com
```

During the interactive process:
- Enter your email for expiration notices
- Agree to terms of service
- Choose whether to share email (optional)
- Certbot will verify domain ownership via HTTP challenge
- Certificates will be saved to `/etc/letsencrypt/live/`

---

## Step 5: Verify SSL Setup

### Check Certificate Status

```bash
# View certificate details
sudo certbot certificates

# Check when certificate expires
openssl x509 -in /etc/letsencrypt/live/linkedin.lengrowth.com/cert.pem -noout -dates
```

### Test Your Sites

Open in browser:
- https://linkedin.lengrowth.com
- https://linkedin-api.lengrowth.com

You should see:
- Padlock icon (HTTPS active)
- Valid certificate from "Let's Encrypt"

---

## Step 6: Auto-Renewal Setup

Certbot installs a cron job automatically, but verify it's working:

```bash
# Check certbot timer
sudo systemctl status certbot.timer

# Test dry-run of renewal
sudo certbot renew --dry-run

# Force renewal (if needed)
sudo certbot renew
```

---

## Complete Commands Summary

Here's the full sequence of commands to run on your server:

```bash
# 1. Install nginx
sudo apt update
sudo apt install -y nginx

# 2. Install certbot
sudo apt install -y certbot python3-certbot-nginx

# 3. Create frontend config
sudo nano /etc/nginx/sites-available/linkedin.lengrowth.com
# [Paste frontend config from above]

# 4. Create API config
sudo nano /etc/nginx/sites-available/linkedin-api.lengrowth.com
# [Paste API config from above]

# 5. Enable sites
sudo ln -s /etc/nginx/sites-available/linkedin.lengrowth.com /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/linkedin-api.lengrowth.com /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default 2>/dev/null || true

# 6. Test nginx config
sudo nginx -t

# 7. Restart nginx
sudo systemctl restart nginx
sudo systemctl enable nginx

# 8. Get SSL certificates
sudo certbot --nginx -d linkedin.lengrowth.com -d linkedin-api.lengrowth.com

# 9. Verify setup
sudo certbot certificates

# 10. Test auto-renewal
sudo certbot renew --dry-run
```

---

## Troubleshooting

### Nginx won't start

```bash
# Check nginx error logs
sudo tail -50 /var/log/nginx/error.log

# Check for syntax errors
sudo nginx -t

# Check what's using port 80/443
sudo lsof -i :80
sudo lsof -i :443
```

### Certbot fails to verify domain

```bash
# Ensure ports are open in AWS Security Group
# - Port 80 (HTTP) - required for Let's Encrypt verification
# - Port 443 (HTTPS) - for SSL traffic

# Check firewall
sudo ufw status

# Allow HTTP and HTTPS if using UFW
sudo ufw allow 'Nginx Full'

# Check DNS propagation
dig linkedin.lengrowth.com
dig linkedin-api.lengrowth.com
```

### Certificate renewal issues

```bash
# Check certificate status
sudo certbot certificates

# Force dry-run renewal
sudo certbot renew --dry-run

# Manual renewal
sudo certbot renew
```

---

## Security Group Requirements

Make sure your AWS Security Group has these inbound rules:

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | Your IP | SSH access |
| 80 | TCP | 0.0.0.0/0 | HTTP (for Let's Encrypt verification) |
| 443 | TCP | 0.0.0.0/0 | HTTPS (SSL traffic) |
| 3000 | TCP | 127.0.0.1 only | Frontend (nginx proxy) |
| 8000 | TCP | 127.0.0.1 only | API (nginx proxy) |

**Note:** Ports 3000 and 8000 should only be accessible from localhost (nginx), not from the internet.