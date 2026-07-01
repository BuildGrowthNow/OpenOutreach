#!/bin/bash
# SSL Permissions Fix Script
# This script fixes nginx's ability to read Let's Encrypt certificates
# Run this after deployments to fix SSL permission errors

set -e

echo "Fixing SSL certificate permissions for nginx..."

# Add www-data to ssl-cert group (Let's Encrypt uses this group)
if getent group ssl-cert >/dev/null 2>&1; then
    usermod -a -G ssl-cert www-data 2>/dev/null || true
else
    # Create ssl-cert group if it doesn't exist
    groupadd ssl-cert 2>/dev/null || true
    usermod -a -G ssl-cert www-data 2>/dev/null || true
fi

# Make Let's Encrypt directories accessible by ssl-cert group
chmod 750 /etc/letsencrypt/live/ 2>/dev/null || true
chmod 750 /etc/letsencrypt/archive/ 2>/dev/null || true

# Make all certificate files readable by ssl-cert group
chmod -R 640 /etc/letsencrypt/archive/* 2>/dev/null || true
chmod -R 640 /etc/letsencrypt/live/* 2>/dev/null || true

# Ensure certificates are readable by nginx
chgrp -R ssl-cert /etc/letsencrypt/archive/ 2>/dev/null || true
chgrp -R ssl-cert /etc/letsencrypt/live/ 2>/dev/null || true

# Verify nginx can read the certificates
echo "Testing nginx configuration..."
nginx -t

if [ $? -eq 0 ]; then
    echo "Restarting nginx..."
    systemctl restart nginx
    
    if [ $? -eq 0 ]; then
        echo "SSL permissions fix completed successfully!"
        exit 0
    else
        echo "WARNING: nginx restart failed. Check nginx status."
        exit 1
    fi
else
    echo "ERROR: nginx configuration test failed. Please check SSL certificates manually."
    exit 1
fi