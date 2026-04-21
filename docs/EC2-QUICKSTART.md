# EC2 Quick Reference Guide

Quick commands and workflows for managing your Mortgage RAG + RASA deployment on EC2.

## 📋 Quick Links

- [Full Documentation](./EC2-DEPLOYMENT.md)
- [Validation Checklist](./bridge-rag-rasa-validation.md)
- [API Response Format](./api-response-format.md)

## 🚀 Common Commands

### Deployment

```bash
# Update deployment from local machine
./scripts/ec2-update.sh <ec2-ip> /path/to/key.pem

# Update to specific branch
./scripts/ec2-update.sh <ec2-ip> /path/to/key.pem feature-branch

# Initial deployment (run on EC2)
./scripts/ec2-deploy.sh

# Create backup (run on EC2)
./scripts/ec2-backup.sh

# Full backup with S3 upload (run on EC2)
./scripts/ec2-backup.sh --full --s3-bucket your-bucket-name
```

### Monitoring

```bash
# Health check
bash healthcheck.sh

# View all logs
docker compose -f docker-compose.production.yml logs -f

# View specific service logs
docker compose -f docker-compose.production.yml logs -f rag-api
docker compose -f docker-compose.production.yml logs -f rasa
docker compose -f docker-compose.production.yml logs -f rasa-actions

# Check container status
docker compose -f docker-compose.production.yml ps

# Monitor resource usage
docker stats
```

### Service Management

```bash
# Restart all services
docker compose -f docker-compose.production.yml restart

# Restart specific service
docker compose -f docker-compose.production.yml restart rag-api

# Stop all services
docker compose -f docker-compose.production.yml down

# Start all services
docker compose -f docker-compose.production.yml up -d

# Rebuild and restart specific service
docker compose -f docker-compose.production.yml build rag-api
docker compose -f docker-compose.production.yml up -d rag-api
```

### Rollback

```bash
# Automatic rollback to last backup
bash rollback.sh

# Rollback to specific backup
bash rollback.sh 20260421_091500
```

## 🔧 Troubleshooting Quick Fixes

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.production.yml logs <service-name>

# Rebuild and restart
docker compose -f docker-compose.production.yml build --no-cache <service-name>
docker compose -f docker-compose.production.yml up -d <service-name>
```

### Out of Memory

```bash
# Check memory usage
free -h
docker stats

# Restart services to free memory
docker compose -f docker-compose.production.yml restart
```

### Out of Disk Space

```bash
# Check disk usage
df -h
docker system df

# Clean up
docker system prune -a --volumes -f

# Remove old backups
cd backups
ls -t *.tar.gz | tail -n +6 | xargs rm -f
```

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>
```

### API Returning Errors

```bash
# Check environment variables
grep OPENAI_API_KEY .env.production

# Restart RAG API
docker compose -f docker-compose.production.yml restart rag-api

# View recent logs
docker compose -f docker-compose.production.yml logs --tail=100 rag-api
```

## 🧪 Testing Endpoints

### Test RAG API

```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is mortgage pre-approval?"}'
```

### Test Rasa

```bash
# Check version
curl http://localhost:5005/version

# Test webhook
curl -X POST "http://localhost:5005/webhooks/rest/webhook" \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"hello"}'
```

### Test Rasa Actions

```bash
# Health check
curl http://localhost:5055/health
```

## 📊 Monitoring & Logs

### View Live Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Last 100 lines
docker compose -f docker-compose.production.yml logs --tail=100

# Since specific time
docker compose -f docker-compose.production.yml logs --since 30m
```

### Check Service Health

```bash
# Comprehensive health check
bash healthcheck.sh

# Individual checks
curl http://localhost:8000/health
curl http://localhost:8000/health/rasa
curl http://localhost:5005/version
curl http://localhost:5055/health
```

### Resource Monitoring

```bash
# Container stats
docker stats

# System resources
htop

# Disk usage
df -h
du -sh /home/ubuntu/mortgage-rag-starter/*

# Memory usage
free -h
```

## 🔄 Update Workflow

### Standard Update (from local machine)

```bash
# 1. Commit and push changes
git add .
git commit -m "Update feature"
git push origin main

# 2. Deploy to EC2
./scripts/ec2-update.sh <ec2-ip> /path/to/key.pem

# 3. Verify deployment
# The script will automatically run health checks
```

### Manual Update (on EC2)

```bash
# 1. SSH to EC2
ssh -i /path/to/key.pem ubuntu@<ec2-ip>

# 2. Navigate to project
cd /home/ubuntu/mortgage-rag-starter

# 3. Backup current state
./scripts/ec2-backup.sh

# 4. Pull latest code
git stash
git pull origin main

# 5. Rebuild and restart
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

# 6. Verify
bash healthcheck.sh
```

## 🔐 Security Checks

```bash
# Check environment file permissions
ls -la .env.production  # Should be 600

# Set correct permissions
chmod 600 .env.production

# Verify security groups (from local)
aws ec2 describe-security-groups --group-ids <sg-id>

# Check open ports
sudo netstat -tulpn | grep LISTEN
```

## 💾 Backup & Restore

### Create Backup

```bash
# Standard backup
./scripts/ec2-backup.sh

# Full backup
./scripts/ec2-backup.sh --full

# Backup with S3 upload
./scripts/ec2-backup.sh --full --s3-bucket your-bucket
```

### List Backups

```bash
# List all backups
ls -lht backups/

# View backup manifest
cat backups/manifest_<timestamp>.txt
```

### Restore from Backup

```bash
# Automatic restore
bash rollback.sh

# Manual restore
TIMESTAMP=20260421_091500
docker compose -f docker-compose.production.yml down
tar -xzf backups/code_backup_$TIMESTAMP.tar.gz
cp backups/env_backup_$TIMESTAMP .env.production
docker compose -f docker-compose.production.yml up -d
```

## 📈 Performance Tuning

### Adjust Workers

```bash
# Edit docker-compose.production.yml
# Change --workers parameter (e.g., --workers 4)

# Restart service
docker compose -f docker-compose.production.yml restart rag-api
```

### Clean Up Resources

```bash
# Remove unused Docker resources
docker system prune -a --volumes

# Remove old logs
docker compose -f docker-compose.production.yml logs --tail=0

# Compact git repository
git gc --aggressive
```

## 🔍 Debugging

### Check Environment Variables

```bash
# View environment in container
docker compose -f docker-compose.production.yml exec rag-api env | grep OPENAI

# Check Docker Compose config
docker compose -f docker-compose.production.yml config
```

### Access Container Shell

```bash
# Access RAG API container
docker compose -f docker-compose.production.yml exec rag-api /bin/bash

# Access Rasa container
docker compose -f docker-compose.production.yml exec rasa /bin/bash
```

### Check Network

```bash
# Test internal networking
docker compose -f docker-compose.production.yml exec rag-api ping rasa
docker compose -f docker-compose.production.yml exec rag-api curl http://rasa:5005/version
```

## 📞 Quick Support

### Get System Info

```bash
# Docker info
docker version
docker compose version
docker info

# System info
uname -a
cat /etc/os-release
free -h
df -h

# Application info
cd /home/ubuntu/mortgage-rag-starter
git log -1 --oneline
docker compose -f docker-compose.production.yml ps
```

### Generate Support Report

```bash
# Create support report
{
  echo "=== System Info ==="
  uname -a
  echo ""
  echo "=== Docker Info ==="
  docker version
  echo ""
  echo "=== Container Status ==="
  docker compose -f docker-compose.production.yml ps
  echo ""
  echo "=== Recent Logs ==="
  docker compose -f docker-compose.production.yml logs --tail=50
  echo ""
  echo "=== Git Status ==="
  git log -1
  echo ""
  echo "=== Disk Usage ==="
  df -h
} > support-report-$(date +%Y%m%d_%H%M%S).txt
```

## 🌐 Access URLs

After deployment, services are available at:

- **RAG API**: `http://<ec2-ip>:8000`
- **RAG UI**: `http://<ec2-ip>:8000/ui`
- **API Docs**: `http://<ec2-ip>:8000/docs`
- **Rasa Server**: `http://<ec2-ip>:5005` (internal only)
- **Rasa Actions**: `http://<ec2-ip>:5055` (internal only)

## 📚 Related Documentation

- [Full EC2 Deployment Guide](./EC2-DEPLOYMENT.md)
- [API Response Format](./api-response-format.md)
- [Bridge Validation Checklist](./bridge-rag-rasa-validation.md)
- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
- [Main README](../README.md)

## 🚨 Emergency Procedures

### Service Down

```bash
# 1. Check status
docker compose -f docker-compose.production.yml ps

# 2. View logs
docker compose -f docker-compose.production.yml logs --tail=100

# 3. Restart
docker compose -f docker-compose.production.yml restart

# 4. If still down, rebuild
docker compose -f docker-compose.production.yml build --no-cache
docker compose -f docker-compose.production.yml up -d

# 5. If still issues, rollback
bash rollback.sh
```

### Complete System Failure

```bash
# 1. Stop everything
docker compose -f docker-compose.production.yml down

# 2. Clean Docker resources
docker system prune -a --volumes -f

# 3. Restore from backup
bash rollback.sh

# 4. If rollback fails, redeploy
git fetch origin
git reset --hard origin/main
./scripts/ec2-deploy.sh
```

## ⚡ Pro Tips

1. **Always backup before updates**: Automated in update script
2. **Monitor logs regularly**: Set up log rotation
3. **Use health checks**: Run `healthcheck.sh` daily
4. **Keep backups in S3**: Use `--s3-bucket` flag
5. **Set up systemd service**: Auto-start on reboot
6. **Use IAM roles**: Don't hardcode AWS credentials
7. **Enable HTTPS**: Use Let's Encrypt with Certbot
8. **Monitor resources**: Watch memory and disk usage
9. **Update regularly**: Security patches and dependencies
10. **Document changes**: Keep deployment notes
