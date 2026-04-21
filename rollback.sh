#!/bin/bash
# Emergency rollback script for production deployment
# Usage: ./rollback.sh [backup_timestamp]

set -e

# Configuration
COMPOSE_FILE="docker-compose.production.yml"
BACKUP_DIR="backups"
TIMESTAMP="${1:-latest}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Find latest backup
find_latest_backup() {
    if [ "$TIMESTAMP" = "latest" ]; then
        local latest_data=$(ls -t "$BACKUP_DIR"/data_backup_*.tar.gz 2>/dev/null | head -n1)
        if [ -n "$latest_data" ]; then
            TIMESTAMP=$(basename "$latest_data" | sed 's/data_backup_\(.*\)\.tar\.gz/\1/')
            log_info "Found latest backup: $TIMESTAMP"
        else
            log_error "No backups found in $BACKUP_DIR"
            exit 1
        fi
    fi
}

# Confirm rollback
confirm_rollback() {
    log_warning "⚠️  WARNING: This will rollback to backup from $TIMESTAMP"
    log_warning "⚠️  Current deployment will be stopped and replaced"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
}

# Stop current deployment
stop_current_deployment() {
    log_info "Stopping current deployment..."
    
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        docker-compose -f "$COMPOSE_FILE" down
        log_success "Current deployment stopped"
    else
        log_info "No running deployment found"
    fi
}

# Restore data backup
restore_data() {
    local data_backup="$BACKUP_DIR/data_backup_$TIMESTAMP.tar.gz"
    
    if [ -f "$data_backup" ]; then
        log_info "Restoring data backup..."
        
        # Backup current data first
        if [ -d "data" ]; then
            mv data "data.rollback_$(date +%Y%m%d_%H%M%S)"
        fi
        
        tar -xzf "$data_backup"
        log_success "Data restored"
    else
        log_warning "Data backup not found: $data_backup"
    fi
}

# Restore environment file
restore_env() {
    local env_backup="$BACKUP_DIR/env_backup_$TIMESTAMP"
    
    if [ -f "$env_backup" ]; then
        log_info "Restoring environment file..."
        
        # Backup current env
        if [ -f ".env.production" ]; then
            cp .env.production ".env.production.rollback_$(date +%Y%m%d_%H%M%S)"
        fi
        
        cp "$env_backup" ".env.production"
        log_success "Environment file restored"
    else
        log_warning "Environment backup not found: $env_backup"
    fi
}

# Restore volumes
restore_volumes() {
    local volumes_backup="$BACKUP_DIR/rasa_models_backup_$TIMESTAMP.tar.gz"
    
    if [ -f "$volumes_backup" ]; then
        log_info "Restoring Rasa models volume..."
        
        # Create volume if it doesn't exist
        docker volume create mortgage-rag-starter_rasa-models 2>/dev/null || true
        
        # Restore volume data
        docker run --rm -v mortgage-rag-starter_rasa-models:/data -v "$(pwd)/$BACKUP_DIR":/backup \
            alpine sh -c "rm -rf /data/* && tar -xzf /backup/rasa_models_backup_$TIMESTAMP.tar.gz -C /"
        
        log_success "Rasa models volume restored"
    else
        log_warning "Volume backup not found: $volumes_backup"
    fi
}

# Start previous deployment
start_previous_deployment() {
    log_info "Starting previous deployment..."
    
    docker-compose -f "$COMPOSE_FILE" up -d --remove-orphans
    
    log_success "Previous deployment started"
}

# Verify rollback
verify_rollback() {
    log_info "Verifying rollback..."
    
    # Wait for services to start
    sleep 10
    
    if bash healthcheck.sh > /dev/null 2>&1; then
        log_success "Rollback verification passed"
        return 0
    else
        log_error "Rollback verification failed"
        log_info "Check logs: docker-compose -f $COMPOSE_FILE logs"
        return 1
    fi
}

# Show rollback status
show_status() {
    log_info "Rollback Status:"
    echo ""
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    log_info "Backup used: $TIMESTAMP"
    log_info "Rollback artifacts saved with '.rollback_*' suffix"
    echo ""
}

# Main rollback flow
main() {
    echo "=========================================="
    echo "Emergency Rollback"
    echo "=========================================="
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory not found: $BACKUP_DIR"
        exit 1
    fi
    
    find_latest_backup
    confirm_rollback
    
    log_info "Starting rollback process..."
    echo ""
    
    stop_current_deployment
    restore_env
    restore_data
    restore_volumes
    start_previous_deployment
    
    if verify_rollback; then
        show_status
        log_success "✅ Rollback completed successfully!"
        exit 0
    else
        log_error "❌ Rollback verification failed"
        log_warning "Manual intervention may be required"
        exit 1
    fi
}

# Run main rollback
main
