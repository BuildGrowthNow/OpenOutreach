# OpenOutreach Rollback Plan

This document describes the rollback procedures for both frontend and backend deployments.

## Overview

Rollback strategies are essential for quickly recovering from deployment issues. This document covers:
- Frontend rollback procedures
- Backend rollback procedures
- Coordinate rollback (both together)
- Verification steps

---

## Frontend Rollback Plan

### Prerequisites
- Git access to the repository
- Access to deployment platform (AWS, Vercel, etc.)
- Access to the CDN/cache system (CloudFront, Cloudflare, etc.)

### Rollback Steps

#### Option 1: Git-based Rollback (Recommended)
```bash
# 1. Identify the last known good commit
git log --oneline --graph -20

# 2. Identify the problematic commit
git log --oneline --graph -30

# 3. Rollback to the last good commit
git revert <bad-commit-hash> --no-edit

# 4. Push the rollback
git push origin main
```

#### Option 2: Manual Rollback (When Git is not available)
```bash
# 1. Download the last known good build artifact
curl -O https://storage.googleapis.com/your-bucket/frontend-build_v1.2.3.tar.gz

# 2. Extract the build
tar -xzf frontend-build_v1.2.3.tar.gz

# 3. Replace the current deployment
cp -r frontend-build_v1.2.3/* /var/www/frontend/

# 4. Clear the CDN cache
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

#### Option 3: Versioned Deployment Rollback
```bash
# 1. List available versions
ls -la /var/www/frontend/releases/

# 2. Identify the last good version
ls -lt /var/www/frontend/releases/

# 3. Switch to the last good version
rm /var/www/frontend/current
ln -s /var/www/frontend/releases/last-good-version /var/www/frontend/current
```

### Verification Steps
1. Check the health endpoint: `curl https://your-domain.com/api/health`
2. Verify the login page loads
3. Check the console for errors (browser dev tools)
4. Verify all critical paths work (login, navigation, forms)

---

## Backend Rollback Plan

### Prerequisites
- Git access to the repository
- Access to the deployment platform (AWS, Kubernetes, etc.)
- Database backup access
- SSH access to servers

### Rollback Steps

#### Option 1: Git-based Rollback (Recommended)
```bash
# 1. SSH into the server
ssh user@your-server

# 2. Navigate to the project
cd /opt/openoutreach

# 3. Identify the last known good commit
git log --oneline --graph -20

# 4. Identify the problematic commit
git log --oneline --graph -30

# 5. Stash local changes (if any)
git stash

# 6. Pull the last known good commit
git pull origin main --rebase
git checkout <last-good-commit-hash>

# 7. Run migrations (if needed - backward compatible)
python manage.py migrate

# 8. Restart the application
sudo systemctl restart gunicorn
sudo systemctl restart celery
```

#### Option 2: Docker-based Rollback
```bash
# 1. List available container images
docker images | grep openoutreach

# 2. Stop current containers
docker-compose down

# 3. Start containers with last good image
docker-compose up -d --force-recreate openoutreach-backend:<last-good-tag>

# 4. Verify the containers are running
docker-compose ps
```

#### Option 3: Backup-based Rollback (Emergency)
```bash
# 1. Stop all services
sudo systemctl stop gunicorn
sudo systemctl stop celery
sudo systemctl stop nginx

# 2. Restore database from backup
pg_restore -U openoutreach -d openoutreach < /backups/openoutreach-2024-01-01.sql

# 3. Restore application files
tar -xzf /backups/openoutreach-app-2024-01-01.tar.gz -C /opt/openoutreach/

# 4. Restart services
sudo systemctl start nginx
sudo systemctl start gunicorn
sudo systemctl start celery
```

### Verification Steps
1. Check the health endpoint: `curl https://api.your-domain.com/api/health`
2. Verify database connection
3. Check application logs: `journalctl -u gunicorn -n 100`
4. Verify API endpoints respond correctly

---

## Coordinate Rollback Plan (Frontend + Backend)

### When to Rollback Both
- Breaking changes in the API contract
- Mobile app compatibility issues
- Major UI/UX changes that depend on backend features
- Data migration issues

### Rollback Procedure

#### 1. Backend Rollback
```bash
# Rollback backend to last known good version
cd /opt/openoutreach
git checkout <last-good-backend-commit>
python manage.py migrate
sudo systemctl restart gunicorn celery
```

#### 2. Frontend Rollback
```bash
# Rollback frontend to version compatible with backend
cd /opt/openoutreach/frontend
git checkout <compatible-frontend-commit>
npm run build
sudo systemctl restart nginx
```

#### 3. Verification
```bash
# Test all critical paths
curl -s https://your-domain.com/api/health | python -m json.tool
curl -s -X POST https://api.your-domain.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test"}'
```

---

## Emergency Rollback Checklist

### For Frontend
- [ ] Identify the problematic commit
- [ ] Rollback to last known good version
- [ ] Clear CDN/cache
- [ ] Verify health endpoint
- [ ] Test critical paths
- [ ] Notify stakeholders

### For Backend
- [ ] Identify the problematic commit
- [ ] Rollback to last known good version
- [ ] Run database migrations (if needed)
- [ ] Restart services
- [ ] Verify health endpoint
- [ ] Check logs
- [ ] Test critical paths
- [ ] Notify stakeholders

### For Both
- [ ] Identify the problematic deploy
- [ ] Rollback frontend
- [ ] Rollback backend
- [ ] Verify both systems
- [ ] Test critical paths
- [ ] Notify stakeholders
- [ ] Post-incident review scheduled

---

## Post-Rollback Actions

### 1. Incident Documentation
- What broke
- When it was detected
- How it was resolved
- How long the outage lasted
- What lessons were learned

### 2. Preventive Measures
- Add monitoring for the issue
- Improve error messages
- Add integration tests
- Update documentation

### 3. Communication
- Update status page
- Notify customers if needed
- Schedule post-mortem meeting

---

## Contact Information

- **On-Call Engineer**: [Add contact info]
- **DevOps Team**: [Add contact info]
- **Engineering Manager**: [Add contact info]

---

## Rollback Drills

Perform rollback drills quarterly to ensure the process works:
1. Schedule a maintenance window
2. Simulate a production issue
3. Execute the rollback plan
4. Document the experience
5. Update the plan based on findings