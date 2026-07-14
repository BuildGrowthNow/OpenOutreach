#!/bin/bash
# Update Nginx to point to FastAPI port 8001 instead of Django port 8000

echo "Updating Nginx configuration for FastAPI (port 8001)..."

# Backup current config
sudo cp /etc/nginx/sites-available/linkedin-api.lengrowth.com /etc/nginx/sites-available/linkedin-api.lengrowth.com.bak

# Update port 8000 to 8001
sudo sed -i 's/proxy_pass http:\/\/localhost:8000;/proxy_pass http:\/\/localhost:8001;/g' /etc/nginx/sites-available/linkedin-api.lengrowth.com

# Test configuration
echo "Testing Nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
    echo "Reloading Nginx..."
    sudo systemctl reload nginx
    echo "✅ Nginx reloaded successfully"
    echo ""
    echo "Updated configuration:"
    grep "proxy_pass" /etc/nginx/sites-available/linkedin-api.lengrowth.com
else
    echo "❌ Nginx configuration test failed"
    echo "Restoring backup..."
    sudo cp /etc/nginx/sites-available/linkedin-api.lengrowth.com.bak /etc/nginx/sites-available/linkedin-api.lengrowth.com
    exit 1
fi
