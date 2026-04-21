# EC2 Migration Summary

Complete overview of EC2 deployment assets created for your Mortgage RAG + RASA system.

## 📦 What Was Created

### Documentation Files

1. **[docs/EC2-DEPLOYMENT.md](./EC2-DEPLOYMENT.md)** - Complete deployment guide
   - Prerequisites and requirements
   - Initial EC2 setup instructions
   - Deployment procedures (automated & manual)
   - Rollback procedures
   - Monitoring and troubleshooting
   - Security best practices
   - Backup strategies
   - Performance optimization

2. **[docs/EC2-QUICKSTART.md](./EC2-QUICKSTART.md)** - Quick reference guide
   - Common commands
   - Quick troubleshooting fixes
   - Testing endpoints
   - Update workflows
   - Emergency procedures
   - Pro tips

3. **[docs/EC2-MIGRATION-SUMMARY.md](./EC2-MIGRATION-SUMMARY.md)** - This file
   - Overview of created assets
   - Usage instructions
   - Next steps

### Deployment Scripts

1. **scripts/ec2-update.sh** - Remote deployment script (run from local machine)
   - Updates running EC2 deployment with zero downtime
   - Automatic backup before deployment
   - Health checks with automatic rollback on failure
   - Supports branch-specific deployments
   - Cleans up old backups automatically

2. **scripts/ec2-deploy.sh** - Initial deployment script (run on EC2)
   - First-time deployment on EC2 instance
   - Environment validation
   - Docker image building
   - Service startup with health checks
   - Optional systemd service setup

3. **scripts/ec2-backup.sh** - Backup script (run on EC2)
   - Incremental and full backup support
   - Backup code, data, environment, and Docker volumes
   - S3 upload support
   - Automatic cleanup of old backups
   - Backup manifest generation

### Updated Files

1. **README.md** - Added AWS EC2 Deployment section
   - Quick start instructions
   - Available scripts overview
   - Key features
   - Quick commands

## 🚀 How to Use

### Initial EC2 Setup (First Time)

**Step 1: SSH into your EC2 instance**

```bash
ssh -i /path/to/your-key.pem ubuntu@your-ec2-ip
```

**Step 2: Clone the repository**

```bash
cd /home/ubuntu
git clone https://github.com/cjanxtlvl-tech/mortgage-rag-starter.git
cd mortgage-rag-starter
```

**Step 3: Clone your Rasa project** (if separate repo)

```bash
cd /home/ubuntu
git clone <your-rasa-repo-url> mortgage-rasa-chatbot
```

**Step 4: Configure environment**

```bash
cd /home/ubuntu/mortgage-rag-starter
cp .env.production.template .env.production
nano .env.production
```

Set at minimum:
- `OPENAI_API_KEY=sk-your-key-here`
- `RASA_PROJECT_DIR=../mortgage-rasa-chatbot`
- Other settings as needed

**Step 5: Run initial deployment**

```bash
chmod +x scripts/ec2-deploy.sh
./scripts/ec2-deploy.sh
```

The script will:
- ✅ Check prerequisites (Docker, Docker Compose)
- ✅ Validate environment configuration
- ✅ Build Docker images
- ✅ Start all services
- ✅ Run health checks
- ✅ Display service URLs

### Updating Your Deployment

**From your local machine** (recommended):

```bash
# Update to latest main branch
./scripts/ec2-update.sh <ec2-ip> /path/to/your-key.pem

# Update to specific branch
./scripts/ec2-update.sh <ec2-ip> /path/to/your-key.pem feature-branch
```

The update script will:
1. ✅ Test SSH connection
2. ✅ Create backup of current deployment
3. ✅ Pull latest code from Git
4. ✅ Update Rasa project (if exists)
5. ✅ Build Docker images
6. ✅ Deploy with zero downtime
7. ✅ Run health checks
8. ✅ Rollback automatically if health checks fail
9. ✅ Clean up old backups

**Manual update** (on EC2):

```bash
ssh -i /path/to/key.pem ubuntu@<ec2-ip>
cd /home/ubuntu/mortgage-rag-starter

# Create backup
./scripts/ec2-backup.sh

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

# Verify
bash healthcheck.sh
```

### Creating Backups

**Standard backup** (environment, data, volumes):

```bash
./scripts/ec2-backup.sh
```

**Full backup** (includes code):

```bash
./scripts/ec2-backup.sh --full
```

**Full backup with S3 upload**:

```bash
./scripts/ec2-backup.sh --full --s3-bucket your-bucket-name
```

### Rollback

If something goes wrong:

```bash
# Automatic rollback to last backup
bash rollback.sh

# Rollback to specific backup
bash rollback.sh 20260421_091500
```

## 📊 Monitoring Your Deployment

### Health Checks

```bash
# Comprehensive health check
bash healthcheck.sh

# Individual endpoint checks
curl http://localhost:8000/health
curl http://localhost:8000/health/rasa
curl http://localhost:5005/version
curl http://localhost:5055/health
```

### View Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f rag-api

# Last 100 lines
docker compose -f docker-compose.production.yml logs --tail=100
```

### Check Status

```bash
# Container status
docker compose -f docker-compose.production.yml ps

# Resource usage
docker stats

# System resources
free -h
df -h
```

## 🔧 Configuration Files Used

### Existing Files
- `docker-compose.production.yml` - Production Docker Compose config
- `Dockerfile.production` - Multi-stage production Dockerfile
- `.env.production.template` - Environment template
- `deploy.sh` - Production deployment script
- `rollback.sh` - Rollback script
- `healthcheck.sh` - Health check script

### Environment Variables
Key settings in `.env.production`:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# Application Configuration
APP_ENV=production
HOST=0.0.0.0
PORT=8000

# Rasa Configuration
RASA_WEBHOOK_URL=http://rasa:5005/webhooks/rest/webhook
RASA_PROJECT_DIR=../mortgage-rasa-chatbot

# AWS Configuration
AWS_REGION=us-east-1
```

## 🔐 Security Considerations

### Before Deployment

1. **Security Groups**: Ensure EC2 security group allows:
   - Port 22 (SSH) - Your IP only
   - Port 80/443 (HTTP/HTTPS) - If using Nginx
   - Port 8000 (RAG API) - Your IP or internal only

2. **IAM Roles**: Attach IAM role to EC2 with permissions for:
   - S3 (for backups)
   - CloudWatch (for logging)
   - Secrets Manager (optional)

3. **Environment Files**: 
   ```bash
   chmod 600 .env.production
   ```
   Never commit `.env.production` to Git

4. **SSH Keys**: Use strong SSH keys and restrict access

### Enable HTTPS (Recommended)

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

## 📈 Performance Tuning

### Adjust Uvicorn Workers

Edit `docker-compose.production.yml`:

```yaml
command: >-
  sh -c "python scripts/process_data.py && 
  python -m uvicorn app.main:app 
  --host 0.0.0.0 --port 8000 
  --workers 4 --log-level info"  # Adjust based on CPU cores
```

### Resource Limits

The production Docker Compose file includes resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 2G
```

Adjust based on your EC2 instance type.

## 🔄 Typical Update Workflow

### Development → Production

1. **Develop locally** and test:
   ```bash
   # Local development
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```

2. **Commit and push changes**:
   ```bash
   git add .
   git commit -m "Add new feature"
   git push origin main
   ```

3. **Deploy to EC2** from local machine:
   ```bash
   ./scripts/ec2-update.sh <ec2-ip> /path/to/key.pem
   ```

4. **Verify deployment**:
   - Script automatically runs health checks
   - Check logs if needed: 
     ```bash
     ssh -i key.pem ubuntu@<ec2-ip>
     cd /home/ubuntu/mortgage-rag-starter
     docker compose -f docker-compose.production.yml logs --tail=50
     ```

5. **If issues occur**:
   - Script automatically rolls back on health check failure
   - Or manually rollback:
     ```bash
     ssh -i key.pem ubuntu@<ec2-ip>
     cd /home/ubuntu/mortgage-rag-starter
     bash rollback.sh
     ```

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

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean Docker resources
docker system prune -a --volumes -f

# Remove old backups
cd backups
ls -t *.tar.gz | tail -n +6 | xargs rm -f
```

### Complete System Recovery

```bash
# 1. Stop everything
docker compose -f docker-compose.production.yml down

# 2. Clean Docker
docker system prune -a --volumes -f

# 3. Restore from backup
bash rollback.sh

# 4. If rollback fails, redeploy
git fetch origin
git reset --hard origin/main
./scripts/ec2-deploy.sh
```

## 📋 Next Steps

### Immediate Actions

1. ✅ **Test the update script** on your EC2 instance:
   ```bash
   ./scripts/ec2-update.sh <your-ec2-ip> /path/to/key.pem
   ```

2. ✅ **Set up automated backups** (cron job on EC2):
   ```bash
   crontab -e
   # Add: 0 2 * * * /home/ubuntu/mortgage-rag-starter/scripts/ec2-backup.sh
   ```

3. ✅ **Configure S3 backups** for disaster recovery:
   ```bash
   # Create S3 bucket
   aws s3 mb s3://your-backup-bucket
   
   # Run backup with S3 upload
   ./scripts/ec2-backup.sh --full --s3-bucket your-backup-bucket
   ```

### Recommended Enhancements

1. **Set up monitoring**:
   - CloudWatch for logs and metrics
   - Set up alarms for disk space, memory, CPU
   - Configure SNS for alerts

2. **Enable HTTPS**:
   - Set up domain name
   - Configure SSL with Let's Encrypt
   - Update security groups

3. **Implement CI/CD**:
   - GitHub Actions for automated deployment
   - Automated testing before deployment
   - Branch-based deployment strategies

4. **Add load balancer** (if scaling):
   - Application Load Balancer
   - Auto Scaling Group
   - Multiple availability zones

5. **Database integration** (if needed):
   - RDS for persistent storage
   - Redis for caching
   - Update backup scripts

## 📚 Documentation Index

- **[EC2-DEPLOYMENT.md](./EC2-DEPLOYMENT.md)** - Complete deployment guide
- **[EC2-QUICKSTART.md](./EC2-QUICKSTART.md)** - Quick reference
- **[bridge-rag-rasa-validation.md](./bridge-rag-rasa-validation.md)** - Validation checklist
- **[api-response-format.md](./api-response-format.md)** - API documentation
- **[../README.md](../README.md)** - Main project README

## 🆘 Getting Help

### Check Logs First

```bash
# Application logs
docker compose -f docker-compose.production.yml logs -f

# System logs
journalctl -xe

# Specific service
docker compose -f docker-compose.production.yml logs rag-api
```

### Common Issues

See [EC2-QUICKSTART.md](./EC2-QUICKSTART.md) troubleshooting section

### Generate Support Report

```bash
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
} > support-report-$(date +%Y%m%d_%H%M%S).txt
```

## ✅ Validation Checklist

Before considering migration complete:

- [ ] Initial deployment successful on EC2
- [ ] All services running (RAG API, Rasa, Rasa Actions)
- [ ] Health checks passing
- [ ] Can update from local machine
- [ ] Rollback tested and working
- [ ] Backups configured and tested
- [ ] S3 backup working (optional)
- [ ] Monitoring set up
- [ ] Security groups configured
- [ ] SSL/HTTPS enabled (recommended)
- [ ] Documentation reviewed

## 🎉 Success Criteria

Your EC2 deployment is successful when:

✅ Services are accessible at `http://<ec2-ip>:8000`  
✅ UI loads at `http://<ec2-ip>:8000/ui`  
✅ Health checks pass: `bash healthcheck.sh`  
✅ Can ask questions and get responses  
✅ Rasa integration working  
✅ Updates deploy successfully  
✅ Rollback works when tested  
✅ Backups are being created  

## 📞 Support Resources

- **GitHub Issues**: https://github.com/cjanxtlvl-tech/mortgage-rag-starter/issues
- **Documentation**: See files in `docs/` directory
- **Validation**: Run `bash healthcheck.sh` for diagnostics

---

**Created**: 2026-04-21  
**Purpose**: EC2 migration for existing RAG + RASA deployment  
**Status**: Ready for deployment
