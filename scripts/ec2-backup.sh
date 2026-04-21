#!/bin/bash
# EC2 Backup Script - Create backups on EC2 instance
# This script should be run ON the EC2 instance
# Usage: ./scripts/ec2-backup.sh [--full] [--s3-bucket bucket-name]

set -e

# Configuration
PROJECT_DIR="/home/ubuntu/mortgage-rag-starter"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FULL_BACKUP=false
S3_BUCKET=""

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

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --full)
            FULL_BACKUP=true
            shift
            ;;
        --s3-bucket)
            S3_BUCKET="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Usage: $0 [--full] [--s3-bucket bucket-name]"
            exit 1
            ;;
    esac
done

# Check environment
check_environment() {
    log_info "Checking environment..."
    
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    
    mkdir -p "$BACKUP_DIR"
    
    log_success "Environment check passed"
}

# Backup code
backup_code() {
    log_info "Backing up application code..."
    
    tar -czf "$BACKUP_DIR/code_backup_$TIMESTAMP.tar.gz" \
        --exclude='.git' \
        --exclude='backups' \
        --exclude='data/index' \
        --exclude='.venv' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='*.pyo' \
        --exclude='.pytest_cache' \
        . 2>/dev/null
    
    log_success "Code backup created: code_backup_$TIMESTAMP.tar.gz"
}

# Backup environment file
backup_env() {
    log_info "Backing up environment configuration..."
    
    if [ -f ".env.production" ]; then
        cp .env.production "$BACKUP_DIR/env_backup_$TIMESTAMP"
        log_success "Environment backup created: env_backup_$TIMESTAMP"
    else
        log_warning "No .env.production file found"
    fi
}

# Backup data directory
backup_data() {
    log_info "Backing up data directory..."
    
    if [ -d "data" ]; then
        tar -czf "$BACKUP_DIR/data_backup_$TIMESTAMP.tar.gz" data/ 2>/dev/null
        log_success "Data backup created: data_backup_$TIMESTAMP.tar.gz"
    else
        log_warning "No data directory found"
    fi
}

# Backup Docker volumes
backup_volumes() {
    log_info "Backing up Docker volumes..."
    
    # Backup Rasa models volume
    if docker volume ls | grep -q "mortgage-rag-starter_rasa-models"; then
        docker run --rm \
            -v mortgage-rag-starter_rasa-models:/data \
            -v "$BACKUP_DIR":/backup \
            alpine tar -czf "/backup/rasa_models_backup_$TIMESTAMP.tar.gz" /data/ 2>/dev/null
        log_success "Rasa models backup created: rasa_models_backup_$TIMESTAMP.tar.gz"
    else
        log_warning "Rasa models volume not found"
    fi
    
    # Backup RAG logs volume (if exists)
    if docker volume ls | grep -q "mortgage-rag-starter_rag-logs"; then
        docker run --rm \
            -v mortgage-rag-starter_rag-logs:/data \
            -v "$BACKUP_DIR":/backup \
            alpine tar -czf "/backup/rag_logs_backup_$TIMESTAMP.tar.gz" /data/ 2>/dev/null
        log_success "RAG logs backup created: rag_logs_backup_$TIMESTAMP.tar.gz"
    fi
}

# Backup database (if applicable)
backup_database() {
    log_info "Checking for databases to backup..."
    
    # Add database backup logic here if you have databases
    # Example for PostgreSQL:
    # docker compose -f docker-compose.production.yml exec -T postgres \
    #     pg_dump -U user dbname > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
    
    log_info "No databases configured for backup"
}

# Create backup manifest
create_manifest() {
    log_info "Creating backup manifest..."
    
    cat > "$BACKUP_DIR/manifest_$TIMESTAMP.txt" << EOF
Backup Manifest
===============
Timestamp: $TIMESTAMP
Date: $(date)
Hostname: $(hostname)
Backup Type: $([ "$FULL_BACKUP" = true ] && echo "Full" || echo "Incremental")

Files Included:
---------------
EOF
    
    ls -lh "$BACKUP_DIR/"*_$TIMESTAMP.* >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt" 2>/dev/null || true
    
    # Add git info
    echo "" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    echo "Git Information:" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    echo "---------------" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    git log -1 >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt" 2>/dev/null || echo "No git info" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    
    # Add Docker info
    echo "" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    echo "Docker Containers:" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    echo "-----------------" >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt"
    docker compose -f docker-compose.production.yml ps >> "$BACKUP_DIR/manifest_$TIMESTAMP.txt" 2>/dev/null || true
    
    log_success "Manifest created: manifest_$TIMESTAMP.txt"
}

# Upload to S3 (optional)
upload_to_s3() {
    if [ -n "$S3_BUCKET" ]; then
        log_info "Uploading backups to S3: $S3_BUCKET"
        
        # Check if AWS CLI is available
        if ! command -v aws &> /dev/null; then
            log_warning "AWS CLI not found, skipping S3 upload"
            return
        fi
        
        # Upload backup files
        aws s3 sync "$BACKUP_DIR/" "s3://$S3_BUCKET/mortgage-rag-backups/" \
            --exclude "*" \
            --include "*_$TIMESTAMP.*" \
            --storage-class STANDARD_IA
        
        if [ $? -eq 0 ]; then
            log_success "Backups uploaded to S3"
        else
            log_error "Failed to upload to S3"
        fi
    fi
}

# Clean up old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping last 5)..."
    
    cd "$BACKUP_DIR"
    
    # Keep only last 5 backups of each type
    ls -t code_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    ls -t data_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    ls -t rasa_models_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    ls -t rag_logs_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    ls -t env_backup_* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    ls -t manifest_*.txt 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null || true
    
    log_success "Old backups cleaned up"
}

# Display backup summary
show_summary() {
    log_info "Backup Summary:"
    echo ""
    echo "Backup Location: $BACKUP_DIR"
    echo "Backup Timestamp: $TIMESTAMP"
    echo "Backup Type: $([ "$FULL_BACKUP" = true ] && echo "Full" || echo "Incremental")"
    echo ""
    echo "Files created:"
    ls -lh "$BACKUP_DIR/"*_$TIMESTAMP.* 2>/dev/null || echo "No files found"
    echo ""
    
    # Calculate total size
    TOTAL_SIZE=$(du -sh "$BACKUP_DIR/"*_$TIMESTAMP.* 2>/dev/null | awk '{sum+=$1} END {print sum}')
    echo "Total backup size: $(du -sh "$BACKUP_DIR" | awk '{print $1}')"
    echo ""
    
    # Show disk usage
    echo "Disk usage:"
    df -h "$BACKUP_DIR" | tail -1
    echo ""
}

# Main backup flow
main() {
    echo "=========================================="
    echo "EC2 Backup Script"
    echo "Timestamp: $TIMESTAMP"
    echo "Type: $([ "$FULL_BACKUP" = true ] && echo "Full Backup" || echo "Incremental Backup")"
    echo "=========================================="
    echo ""
    
    check_environment
    
    # Standard backups
    backup_env
    backup_data
    backup_volumes
    
    # Code backup (always for full, or if requested)
    if [ "$FULL_BACKUP" = true ]; then
        backup_code
        backup_database
    fi
    
    create_manifest
    upload_to_s3
    cleanup_old_backups
    show_summary
    
    # Save latest backup timestamp
    echo "$TIMESTAMP" > "$BACKUP_DIR/latest_backup.txt"
    
    log_success "✅ Backup completed successfully!"
}

# Run main backup
main
