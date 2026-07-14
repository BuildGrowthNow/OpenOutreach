# Production Deployment Status - Phase 3 Migration

**Date**: 2026-07-14  
**Server**: ec2-50-19-251-160.compute-1.amazonaws.com  
**Status**: 🟡 **In Progress - Nginx Update Needed**

---

## ✅ Completed

1. **Code Pushed to GitHub**
   - Main commit: `03a7e80` - Phase 3 complete
   - Fix commit: `a9aeda5` - Temporary linkedin-cli comment-out
   - All Django code removed
   - FastAPI + MongoDB ready

2. **Server Updated**
   - Latest code pulled to ~/OpenOutreach
   - Git status: `a9aeda5` (latest)

3. **Docker Build**
   - Building with FastAPI dependencies
   - Frontend building successfully
   - MongoDB service configured

---

## ⏳ In Progress

### Docker Services
```bash
# Check status
docker compose ps

# Check logs
docker compose logs -f openoutreach
docker compose logs -f mongodb
```

**Expected Services**:
- `openoutreach` - FastAPI (port 8001) + Next.js (port 3000) + Daemon
- `mongodb` - MongoDB 7.0 (port 27017)

---

## 🔧 Todo: Nginx Configuration

### Current State
Nginx is still pointing to **port 8000** (Django):
```nginx
proxy_pass http://localhost:8000;
```

### Required Change
Update to **port 8001** (FastAPI):
```nginx
proxy_pass http://localhost:8001;
```

### How to Update

**Option 1: Manual Edit**
```bash
# On server
sudo nano /etc/nginx/sites-available/linkedin-api.lengrowth.com

# Change line:
proxy_pass http://localhost:8000;
# To:
proxy_pass http://localhost:8001;

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

**Option 2: Use Update Script**
```bash
# Copy script to server
scp -i ~/.ssh/lenquant.pem update_nginx_ports.sh ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com:~/

# Run on server
ssh -i ~/.ssh/lenquant.pem ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com
chmod +x ~/update_nginx_ports.sh
sudo ~/update_nginx_ports.sh
```

---

## 🌐 Production URLs

Once Nginx is updated and services are running:

| Service | URL | Expected Response |
|---------|-----|-------------------|
| **API Health** | https://linkedin-api.lengrowth.com/api/health | `{"status": "healthy"}` |
| **API Docs** | https://linkedin-api.lengrowth.com/docs | FastAPI Swagger UI |
| **Frontend** | https://linkedin.lengrowth.com | Next.js app |
| **MongoDB** | Internal only (port 27017) | - |

---

## 📋 Verification Checklist

After Nginx update:

### 1. Check Docker Services
```bash
ssh -i ~/.ssh/lenquant.pem ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com
cd ~/OpenOutreach

# Check all services are running
docker compose ps

# Should show:
# openoutreach - Up
# mongodb - Up
```

### 2. Test Local API (on server)
```bash
# Test FastAPI directly
curl http://localhost:8001/api/health

# Should return:
# {"status":"healthy","mongodb":"connected"}
```

### 3. Test Production URLs
```bash
# Test API health (from anywhere)
curl https://linkedin-api.lengrowth.com/api/health

# Test API docs (from browser)
# Open: https://linkedin-api.lengrowth.com/docs

# Test frontend (from browser)
# Open: https://linkedin.lengrowth.com
```

### 4. Check Logs
```bash
# FastAPI logs
docker compose logs --tail=50 openoutreach | grep -i "fastapi\|uvicorn\|mongodb"

# MongoDB logs
docker compose logs --tail=20 mongodb

# Check for errors
docker compose logs --tail=100 openoutreach | grep -i "error\|fail\|exception"
```

### 5. Verify MongoDB Connection
```bash
# Connect to MongoDB shell
docker compose exec mongodb mongosh openoutreach

# Inside mongosh:
show collections
db.users.countDocuments()
db.campaigns.countDocuments()
exit
```

---

## 🐛 Known Issues

### 1. linkedin-cli Dependency
**Status**: Temporarily commented out  
**Issue**: Package source not available on PyPI  
**Impact**: Daemon won't be able to execute LinkedIn tasks until resolved  
**Fix**: Need to verify correct package source and update requirements

```python
# Currently in requirements/base.txt:
# linkedin-cli dependency - TODO: Add correct package source
# linkedin_cli @ git+https://github.com/eracle/linkedin-cli.git@main
```

**Resolution Path**:
1. Verify the correct package name/source from existing production install
2. Check if it's a private repo that needs authentication
3. Update requirements/base.txt with correct source
4. Rebuild Docker image

---

## 🔍 Troubleshooting

### Docker Build Fails
```bash
# Check build logs
docker compose build --no-cache 2>&1 | tee build.log

# Check for dependency errors
grep -i "error\|fail" build.log
```

### Services Won't Start
```bash
# Check for port conflicts
sudo lsof -i :3000  # Frontend
sudo lsof -i :8001  # FastAPI
sudo lsof -i :27017 # MongoDB

# Check disk space
df -h
```

### Nginx 502 Bad Gateway
```bash
# Check if FastAPI is running
curl http://localhost:8001/api/health

# Check Nginx error logs
sudo tail -50 /var/log/nginx/error.log

# Verify Nginx config
sudo nginx -t
```

### MongoDB Connection Errors
```bash
# Check MongoDB is running
docker compose logs mongodb | tail -20

# Try connecting
docker compose exec mongodb mongosh --eval "db.adminCommand('ping')"
```

---

## 📊 Migration Status

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: MongoDB Data Layer | ✅ Complete | 100% |
| Phase 2: FastAPI API Migration | ✅ Complete | 100% |
| Phase 3: Django Removal | ✅ Complete | 100% |
| **Production Deployment** | 🟡 In Progress | 80% |

### Remaining Steps
1. ⏳ Docker services running
2. ⏳ Nginx updated to port 8001
3. ⏳ Production URLs verified
4. ⏳ linkedin-cli dependency resolved
5. ⏳ Daemon functional testing

---

## 🎯 Success Criteria

- [x] Code pushed to GitHub
- [x] Latest code on server
- [ ] Docker containers running
- [ ] FastAPI responding on port 8001
- [ ] Nginx proxying to port 8001
- [ ] Production API accessible
- [ ] Production frontend accessible
- [ ] MongoDB connected
- [ ] No Django processes running
- [ ] linkedin-cli dependency resolved

---

## 📞 Quick Commands

```bash
# SSH to server
ssh -i C:\Users\smikl\.ssh\lenquant.pem ubuntu@ec2-50-19-251-160.compute-1.amazonaws.com

# Navigate to project
cd ~/OpenOutreach

# Check git status
git log --oneline -5

# Check Docker
docker compose ps
docker compose logs -f

# Update Nginx
sudo nano /etc/nginx/sites-available/linkedin-api.lengrowth.com
sudo nginx -t && sudo systemctl reload nginx

# Restart services
docker compose restart
```

---

**Last Updated**: 2026-07-14  
**Next Action**: Wait for Docker build to complete, then update Nginx configuration
