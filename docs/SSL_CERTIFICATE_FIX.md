# SSL Certificate Permissions Fix

## Problem
After each deployment, nginx fails to start with the error:
```
cannot load certificate "/etc/letsencrypt/live/linkedin.lengrowth.com/fullchain.pem": 
BIO_new_file() failed (SSL: error:8000000D:system library::Permission denied)
```

## Root Cause
Nginx runs as the `www-data` user, but Let's Encrypt certificates are only readable by root. When the Docker deployment restarts services or nginx reloads, it can't access the SSL certificates.

## Solution
The fix is automatically applied by the deployment workflow. Manually, you can run:

```bash
# Add www-data to ssl-cert group
usermod -a -G ssl-cert www-data

# Make certificates readable by ssl-cert group
chmod 750 /etc/letsencrypt/live/
chmod 750 /etc/letsencrypt/archive/
chmod -R 640 /etc/letsencrypt/archive/*
chmod -R 640 /etc/letsencrypt/live/*
chgrp -R ssl-cert /etc/letsencrypt/archive/
chgrp -R ssl-cert /etc/letsencrypt/live/

# Restart nginx
systemctl restart nginx
```

## Files Changed
- `.github/workflows/deploy-aws.yml` - Added SSL permissions fix after deployment
- `openoutreach/settings.py` - Fixed CORS configuration

## How It Works
1. The deployment script adds `www-data` to the `ssl-cert` group
2. It sets read permissions for the ssl-cert group on Let's Encrypt directories
3. Nginx can now read the certificates as www-data is in the ssl-cert group