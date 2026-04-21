#!/bin/bash
# EC2 Update Script - Deploy updates to running EC2 instance with zero downtime
# Usage: ./scripts/ec2-update.sh <ec2-ip> <path-to-ssh-key> [branch-name]

set -e

# Configuration
EC2_HOST="${1}"
SSH_KEY="${2}"
BRANCH="${3:-main}"
EC2_USER="${EC2_USER:-ubuntu}"
PROJECT_DIR="/home/$EC2_USER/mortgage-rag-starter"
RASA_DIR="/home/$EC2_USER/mortgage-rasa-chatbot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if [ -z "$EC2_HOST" ]; then
        log_error "EC2 host/IP is required"
        echo "Usage: $0 <ec2-ip> <path-to-ssh-key> [branch-name]"
        exit 1
    fi
    
    if [ -z "$SSH_KEY" ]; then
        log_error "SSH key path is required"
        echo "Usage: $0 <ec2-ip> <path-to-ssh-key> [branch-name]"
        exit 1
    fi
    
    if [ ! -f "$SSH_KEY" ]; then
        log_error "SSH key not found: $SSH_KEY"
        exit 1
    fi
    
    # Test SSH connection
    if ! ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes "$EC2_USER@$EC2_HOST" "echo 'SSH OK'" > /dev/null 2>&1; then
        log_error "Cannot connect to EC2 instance via SSH"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Create backup on EC2
create_backup() {
    log_info "Creating backup on EC2..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
        cd /home/ubuntu/mortgage-rag-starter
        mkdir -p backups
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        
        echo "Creating code backup..."
        tar -czf backups/code_backup_$TIMESTAMP.tar.gz \
            --exclude='.git' \
            --exclude='backups' \
            --exclude='data/index' \
            --exclude='.venv' \
            --exclude='__pycache__' \
            . 2>/dev/null || true
        
        echo "Backing up environment file..."
        cp .env.production backups/env_backup_$TIMESTAMP 2>/dev/null || true
        
        echo "Backing up data..."
        tar -czf backups/data_backup_$TIMESTAMP.tar.gz data/ 2>/dev/null || true
        
        echo "Backing up Docker volumes..."
        docker run --rm \
            -v mortgage-rag-starter_rasa-models:/data \
            -v "$(pwd)/backups":/backup \
            alpine tar -czf "/backup/rasa_models_backup_$TIMESTAMP.tar.gz" /data/ 2>/dev/null || true
        
        echo "Backup completed: $TIMESTAMP"
        echo $TIMESTAMP > backups/latest_backup.txt
ENDSSH
    
    log_success "Backup created on EC2"
}

# Update code on EC2
update_code() {
    log_info "Updating code on EC2..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
        cd $PROJECT_DIR
        
        # Stash any local changes
        git stash 2>/dev/null || true
        
        # Fetch latest code
        git fetch origin
        
        # Checkout and pull the specified branch
        git checkout $BRANCH
        git pull origin $BRANCH
        
        echo "Code updated to branch: $BRANCH"
        git log -1 --oneline
ENDSSH
    
    log_success "Code updated on EC2"
}

# Update Rasa project (optional)
update_rasa() {
    log_info "Checking for Rasa project updates..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
        if [ -d "$RASA_DIR" ]; then
            cd $RASA_DIR
            git stash 2>/dev/null || true
            git fetch origin
            git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || true
            echo "Rasa project updated"
        else
            echo "Rasa project directory not found, skipping"
        fi
ENDSSH
}

# Build Docker images
build_images() {
    log_info "Building Docker images on EC2..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << ENDSSH
        cd $PROJECT_DIR
        
        # Check if requirements.txt changed
        if git diff HEAD@{1} requirements.txt | grep -q '^[+-]'; then
            echo "Dependencies changed, building with --no-cache"
            docker compose -f docker-compose.production.yml build --no-cache
        else
            echo "Building images (using cache)"
            docker compose -f docker-compose.production.yml build
        fi
ENDSSH
    
    log_success "Docker images built"
}

# Deploy with zero downtime
deploy_services() {
    log_info "Deploying services with zero downtime..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
        cd /home/ubuntu/mortgage-rag-starter
        
        # Update services with rolling restart
        docker compose -f docker-compose.production.yml up -d --remove-orphans
        
        echo "Waiting for services to stabilize..."
        sleep 30
ENDSSH
    
    log_success "Services deployed"
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."
    
    HEALTH_CHECK=$(ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
        cd /home/ubuntu/mortgage-rag-starter
        
        # Run health check script
        if [ -f "healthcheck.sh" ]; then
            bash healthcheck.sh
            exit $?
        else
            # Manual health checks
            echo "Checking RAG API..."
            curl -sf http://localhost:8000/health > /dev/null || exit 1
            
            echo "Checking Rasa..."
            curl -sf http://localhost:5005/version > /dev/null || exit 1
            
            echo "Checking Rasa Actions..."
            curl -sf http://localhost:5055/health > /dev/null || exit 1
            
            echo "Testing RAG endpoint..."
            RESPONSE=$(curl -s -X POST "http://localhost:8000/ask" \
                -H "Content-Type: application/json" \
                -d '{"question":"Health check test"}')
            
            if echo "$RESPONSE" | grep -q '"answer"'; then
                echo "Health checks passed"
                exit 0
            else
                echo "Health check failed"
                exit 1
            fi
        fi
ENDSSH
)
    
    if [ $? -eq 0 ]; then
        log_success "All health checks passed"
        return 0
    else
        log_error "Health checks failed"
        return 1
    fi
}

# Rollback on failure
rollback() {
    log_warning "Rolling back to previous deployment..."
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
        cd /home/ubuntu/mortgage-rag-starter
        
        if [ -f "backups/latest_backup.txt" ]; then
            BACKUP_TIMESTAMP=$(cat backups/latest_backup.txt)
            echo "Rolling back to: $BACKUP_TIMESTAMP"
            
            # Stop current deployment
            docker compose -f docker-compose.production.yml down
            
            # Restore code
            tar -xzf backups/code_backup_$BACKUP_TIMESTAMP.tar.gz
            
            # Restore environment
            cp backups/env_backup_$BACKUP_TIMESTAMP .env.production 2>/dev/null || true
            
            # Restore Docker volumes
            docker run --rm \
                -v mortgage-rag-starter_rasa-models:/data \
                -v "$(pwd)/backups":/backup \
                alpine sh -c "rm -rf /data/* && tar -xzf /backup/rasa_models_backup_$BACKUP_TIMESTAMP.tar.gz -C /" 2>/dev/null || true
            
            # Restart previous version
            docker compose -f docker-compose.production.yml up -d
            
            echo "Rollback completed"
        else
            echo "No backup found for rollback"
            exit 1
        fi
ENDSSH
    
    if [ $? -eq 0 ]; then
        log_success "Rollback completed"
    else
        log_error "Rollback failed - manual intervention required"
        exit 1
    fi
}

# Show deployment status
show_status() {
    log_info "Deployment Status:"
    echo ""
    
    ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
        cd /home/ubuntu/mortgage-rag-starter
        
        echo "=== Docker Containers ==="
        docker compose -f docker-compose.production.yml ps
        
        echo ""
        echo "=== Recent Logs ==="
        docker compose -f docker-compose.production.yml logs --tail=20
        
        echo ""
        echo "=== Git Status ==="
        git log -1 --oneline
        git status --short
ENDSSH
    
    echo ""
    log_info "Access URLs:"
    echo "  - RAG API:     http://$EC2_HOST:8000"
    echo "  - RAG UI:      http://$EC2_HOST:8000/ui"
    echo "  - Rasa Server: http://$EC2_HOST:5005"
}

# Main deployment flow
main() {
    echo "=========================================="
    echo "EC2 Deployment Update"
    echo "Host: $EC2_HOST"
    echo "Branch: $BRANCH"
    echo "Timestamp: $TIMESTAMP"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    
    echo ""
    read -p "Proceed with deployment to EC2? (yes/no): " confirmation
    if [ "$confirmation" != "yes" ]; then
        log_info "Deployment cancelled"
        exit 0
    fi
    echo ""
    
    create_backup
    update_code
    update_rasa
    build_images
    deploy_services
    
    if run_health_checks; then
        show_status
        echo ""
        log_success "🚀 Deployment completed successfully!"
        
        # Clean up old backups (keep last 5)
        ssh -i "$SSH_KEY" "$EC2_USER@$EC2_HOST" << 'ENDSSH'
            cd /home/ubuntu/mortgage-rag-starter/backups
            ls -t code_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
            ls -t data_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
            ls -t rasa_models_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
ENDSSH
        
        exit 0
    else
        log_error "Deployment verification failed"
        rollback
        exit 1
    fi
}

# Run main deployment
main
