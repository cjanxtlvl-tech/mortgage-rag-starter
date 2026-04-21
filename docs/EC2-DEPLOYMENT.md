# EC2 Deployment Guide

Complete guide for deploying and updating the Mortgage RAG + RASA system on AWS EC2.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Deploying Updates](#deploying-updates)
- [Rollback Procedure](#rollback-procedure)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Local Machine Requirements

- SSH access to EC2 instance(s)
- AWS CLI configured (optional, for S3 backups)
- Git installed
- SSH key for EC2 access

### EC2 Instance Requirements

- Docker and Docker Compose installed
- Sufficient disk space (minimum 20GB recommended)
- Security groups configured for:
  - Port 22 (SSH)
  - Port 80 (HTTP) or 443 (HTTPS) via Nginx
  - Port 8000 (RAG API)
  - Port 5005 (Rasa Server)
  - Port 5055 (Rasa Actions)
- IAM role with appropriate permissions (recommended over API keys)

## Initial Setup

### 1. Prepare Your EC2 Instance

SSH into your EC2 instance:

```bash
ssh -i /path/to/your-key.pem ubuntu@your-ec2-ip
```

### 2. Install Docker (if not already installed)

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get install -y docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 3. Set Up Project Directory

```bash
# Create project directory
mkdir -p /home/ubuntu/mortgage-rag-starter
cd /home/ubuntu/mortgage-rag-starter

# Clone repository (or use deployment script)
git clone https://github.com/cjanxtlvl-tech/mortgage-rag-starter.git .
```

### 4. Set Up Rasa Project

```bash
# Clone Rasa project in sibling directory
cd /home/ubuntu
git clone <your-rasa-repo-url> mortgage-rasa-chatbot
```

### 5. Configure Environment Variables

```bash
cd /home/ubuntu/mortgage-rag-starter

# Copy production environment template
cp .env.production.template .env.production

# Edit with your actual values
nano .env.production
```

**Required Environment Variables:**

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

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

### 6. Initial Deployment

```bash
# Make scripts executable
chmod +x deploy.sh rollback.sh healthcheck.sh
chmod +x scripts/ec2-deploy.sh scripts/ec2-update.sh

# Run initial deployment
./scripts/ec2-deploy.sh
```

## Deploying Updates

### Method 1: Using the Automated Update Script (Recommended)

From your **local machine**, run:

```bash
./scripts/ec2-update.sh your-ec2-ip /path/to/your-key.pem
```

This script will:
1. Create a backup of the current deployment
2. Transfer updated code to EC2
3. Build new Docker images
4. Perform rolling update with zero downtime
5. Run health checks
6. Rollback automatically if health checks fail

### Method 2: Manual Update Process

#### Step 1: SSH into EC2

```bash
ssh -i /path/to/your-key.pem ubuntu@your-ec2-ip
cd /home/ubuntu/mortgage-rag-starter
```

#### Step 2: Backup Current Deployment

```bash
# Create backup directory
mkdir -p backups
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup current code
tar -czf backups/code_backup_$TIMESTAMP.tar.gz \
    --exclude='.git' \
    --exclude='backups' \
    --exclude='data/index' \
    --exclude='.venv' \
    .

# Backup environment file
cp .env.production backups/env_backup_$TIMESTAMP

# Backup data
tar -czf backups/data_backup_$TIMESTAMP.tar.gz data/

# Backup Docker volumes
docker run --rm \
    -v mortgage-rag-starter_rasa-models:/data \
    -v "$(pwd)/backups":/backup \
    alpine tar -czf "/backup/rasa_models_backup_$TIMESTAMP.tar.gz" /data/
```

#### Step 3: Pull Latest Code

```bash
# Stash any local changes
git stash

# Pull latest code
git pull origin main

# Or if you pushed to a specific branch
git fetch origin
git checkout your-branch-name
git pull origin your-branch-name
```

#### Step 4: Update Dependencies (if needed)

```bash
# Check for changes in requirements.txt
git diff HEAD@{1} requirements.txt

# If there are changes, rebuild images
docker compose -f docker-compose.production.yml build --no-cache
```

#### Step 5: Deploy with Zero Downtime

```bash
# Update services with rolling restart
docker compose -f docker-compose.production.yml up -d --remove-orphans

# Wait for services to stabilize
sleep 30

# Run health checks
bash healthcheck.sh
```

#### Step 6: Verify Deployment

```bash
# Check all containers are running
docker compose -f docker-compose.production.yml ps

# Check logs for errors
docker compose -f docker-compose.production.yml logs --tail=50

# Test RAG endpoint
curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"question":"What is mortgage pre-approval?"}'

# Test Rasa endpoint
curl http://localhost:5005/version
```

## Rollback Procedure

### Automatic Rollback

If the update script detects issues, it will automatically rollback. To manually trigger:

```bash
bash rollback.sh
```

### Manual Rollback

```bash
# List available backups
ls -lt backups/

# Choose the backup timestamp you want to restore
BACKUP_TIMESTAMP=20260421_091000  # Example

# Stop current deployment
docker compose -f docker-compose.production.yml down

# Restore code
tar -xzf backups/code_backup_$BACKUP_TIMESTAMP.tar.gz

# Restore environment
cp backups/env_backup_$BACKUP_TIMESTAMP .env.production

# Restore data
rm -rf data/
tar -xzf backups/data_backup_$BACKUP_TIMESTAMP.tar.gz

# Restore Docker volumes
docker run --rm \
    -v mortgage-rag-starter_rasa-models:/data \
    -v "$(pwd)/backups":/backup \
    alpine sh -c "rm -rf /data/* && tar -xzf /backup/rasa_models_backup_$BACKUP_TIMESTAMP.tar.gz -C /"

# Restart services
docker compose -f docker-compose.production.yml up -d

# Verify rollback
bash healthcheck.sh
```

## Monitoring

### View Logs

```bash
# All services
docker compose -f docker-compose.production.yml logs -f

# Specific service
docker compose -f docker-compose.production.yml logs -f rag-api
docker compose -f docker-compose.production.yml logs -f rasa
docker compose -f docker-compose.production.yml logs -f rasa-actions

# Last 100 lines
docker compose -f docker-compose.production.yml logs --tail=100
```

### Check Service Health

```bash
# Run comprehensive health check
bash healthcheck.sh

# Individual endpoint checks
curl http://localhost:8000/health
curl http://localhost:8000/health/rasa
curl http://localhost:5005/version
curl http://localhost:5055/health
```

### Monitor Resource Usage

```bash
# Container stats
docker stats

# Disk usage
df -h
docker system df

# Check memory and CPU
htop
```

### CloudWatch Integration (Optional)

If you've configured CloudWatch:

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure and start
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json
```

## Troubleshooting

### Issue: Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8000
sudo lsof -i :5005
sudo lsof -i :5055

# Stop conflicting services
sudo systemctl stop <service-name>

# Or kill the process
sudo kill -9 <PID>
```

### Issue: Out of Disk Space

```bash
# Check disk usage
df -h

# Clean Docker resources
docker system prune -a --volumes -f

# Remove old backups (keep last 5)
cd backups
ls -t code_backup_*.tar.gz | tail -n +6 | xargs rm -f
ls -t data_backup_*.tar.gz | tail -n +6 | xargs rm -f
```

### Issue: Container Won't Start

```bash
# Check container logs
docker compose -f docker-compose.production.yml logs <service-name>

# Inspect container
docker inspect <container-name>

# Try rebuilding
docker compose -f docker-compose.production.yml build --no-cache <service-name>
docker compose -f docker-compose.production.yml up -d <service-name>
```

### Issue: OpenAI API Errors

```bash
# Verify API key is set
grep OPENAI_API_KEY .env.production

# Test API key
curl https://api.openai.com/v1/models \
    -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Issue: Rasa Not Connecting

```bash
# Check if Rasa is running
docker ps | grep rasa

# Test Rasa endpoint
curl http://localhost:5005/version

# Check Rasa logs
docker compose -f docker-compose.production.yml logs rasa

# Verify Rasa project directory
ls -la ../mortgage-rasa-chatbot
```

### Issue: Memory Issues

```bash
# Check current memory usage
free -h

# Adjust Docker Compose resource limits in docker-compose.production.yml
# Restart services with new limits
docker compose -f docker-compose.production.yml up -d
```

## Security Best Practices

### 1. Use IAM Roles Instead of API Keys

```bash
# Attach IAM role to EC2 instance with permissions for:
# - S3 (for backups)
# - CloudWatch (for logging)
# - Secrets Manager (for sensitive data)
```

### 2. Secure Environment Variables

```bash
# Set restrictive permissions on .env files
chmod 600 .env.production

# Never commit .env.production to git
echo ".env.production" >> .gitignore
```

### 3. Configure Security Groups

Recommended inbound rules:
- SSH (22): Your IP only
- HTTP (80): 0.0.0.0/0 (if using Nginx)
- HTTPS (443): 0.0.0.0/0 (if using Nginx)
- Custom TCP (8000, 5005, 5055): Internal only or your IP

### 4. Enable HTTPS with SSL/TLS

```bash
# Install Certbot
sudo apt-get install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

### 5. Regular Updates

```bash
# System updates
sudo apt-get update
sudo apt-get upgrade -y

# Docker updates
sudo apt-get install --only-upgrade docker-ce docker-ce-cli
```

## Backup Strategy

### Automated Backups

Create a cron job for automated backups:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /home/ubuntu/mortgage-rag-starter/scripts/ec2-backup.sh

# Add weekly full backup on Sundays
0 3 * * 0 /home/ubuntu/mortgage-rag-starter/scripts/ec2-backup.sh --full
```

### S3 Backup (Recommended)

```bash
# Install AWS CLI (if not already installed)
sudo apt-get install -y awscli

# Sync backups to S3
aws s3 sync /home/ubuntu/mortgage-rag-starter/backups/ \
    s3://your-backup-bucket/mortgage-rag-backups/ \
    --exclude "*" \
    --include "*.tar.gz"
```

## Performance Optimization

### 1. Adjust Worker Count

Edit `docker-compose.production.yml`:

```yaml
command: >-
  sh -c "python scripts/process_data.py && 
  python -m uvicorn app.main:app 
  --host 0.0.0.0 --port 8000 
  --workers 4 --log-level info"  # Increase workers based on CPU cores
```

### 2. Enable Caching

Consider adding Redis for caching:

```yaml
redis:
  image: redis:7-alpine
  container_name: mortgage-redis
  ports:
    - "6379:6379"
```

### 3. Monitor and Adjust Resources

```bash
# Monitor resource usage
docker stats

# Adjust memory limits in docker-compose.production.yml if needed
```

## Next Steps

1. Set up monitoring alerts (CloudWatch, Datadog, etc.)
2. Configure automated backups to S3
3. Set up CI/CD pipeline with GitHub Actions
4. Implement blue-green deployment for zero downtime
5. Add load balancer if scaling to multiple instances

## Support

For issues or questions:
- Check logs: `docker compose -f docker-compose.production.yml logs`
- Run health checks: `bash healthcheck.sh`
- Review troubleshooting section above
- Check GitHub issues: https://github.com/cjanxtlvl-tech/mortgage-rag-starter/issues
