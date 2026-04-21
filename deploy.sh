#!/bin/bash
# Production deployment script with zero-downtime strategy
# Usage: ./deploy.sh [environment]

set -e

# Configuration
ENVIRONMENT="${1:-production}"
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"
BACKUP_DIR="backups"
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

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    log_error "Do not run this script as root"
    exit 1
fi

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "$ENV_FILE not found. Copy from .env.production.template and configure."
        exit 1
    fi
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "$COMPOSE_FILE not found"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Backup current deployment
backup_deployment() {
    log_info "Creating backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup environment file
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "$BACKUP_DIR/env_backup_$TIMESTAMP"
        log_success "Environment file backed up"
    fi
    
    # Backup data directory
    if [ -d "data" ]; then
        tar -czf "$BACKUP_DIR/data_backup_$TIMESTAMP.tar.gz" data/
        log_success "Data directory backed up"
    fi
    
    # Backup docker volumes
    log_info "Backing up Docker volumes..."
    docker run --rm -v mortgage-rag-starter_rasa-models:/data -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine tar -czf "/backup/rasa_models_backup_$TIMESTAMP.tar.gz" /data/ 2>/dev/null || log_warning "Rasa models volume not found"
    
    log_success "Backup completed: $BACKUP_DIR"
}

# Pre-deployment tests
run_pre_deployment_tests() {
    log_info "Running pre-deployment tests..."
    
    # Check if OpenAI API key is set
    if ! grep -q "OPENAI_API_KEY=sk-" "$ENV_FILE" && ! grep -q "OPENAI_API_KEY=your_" "$ENV_FILE"; then
        log_warning "OpenAI API key might not be configured"
    fi
    
    # Check if Rasa project exists
    RASA_DIR=$(grep "RASA_PROJECT_DIR" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | sed 's/^[ \t]*//;s/[ \t]*$//')
    if [ -z "$RASA_DIR" ]; then
        RASA_DIR="../mortgage-rasa-chatbot"
    fi
    
    if [ ! -d "$RASA_DIR" ]; then
        log_error "Rasa project directory not found: $RASA_DIR"
        exit 1
    fi
    
    log_success "Pre-deployment tests passed"
}

# Build images
build_images() {
    log_info "Building Docker images..."
    
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    
    log_success "Images built successfully"
}

# Deploy with health checks
deploy() {
    log_info "Starting deployment..."
    
    # Pull latest Rasa images
    log_info "Pulling Rasa images..."
    docker-compose -f "$COMPOSE_FILE" pull rasa rasa-actions
    
    # Start services with rolling update
    log_info "Starting services..."
    docker-compose -f "$COMPOSE_FILE" up -d --remove-orphans
    
    log_success "Services started"
    
    # Wait for services to be healthy
    log_info "Waiting for services to become healthy..."
    
    local max_wait=180
    local elapsed=0
    local interval=5
    
    while [ $elapsed -lt $max_wait ]; do
        if bash healthcheck.sh > /dev/null 2>&1; then
            log_success "All services are healthy!"
            return 0
        fi
        
        echo -n "."
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    
    log_error "Services failed to become healthy within ${max_wait}s"
    log_info "Check logs: docker-compose -f $COMPOSE_FILE logs"
    return 1
}

# Post-deployment verification
verify_deployment() {
    log_info "Running post-deployment verification..."
    
    # Run comprehensive health check
    if bash healthcheck.sh; then
        log_success "Health check passed"
    else
        log_error "Health check failed"
        return 1
    fi
    
    # Test RAG endpoint
    log_info "Testing RAG functionality..."
    response=$(curl -s -X POST "http://localhost:8000/ask" \
        -H "Content-Type: application/json" \
        -d '{"question":"What is mortgage pre-approval?"}' || echo "{}")
    
    if echo "$response" | grep -q '"answer"'; then
        log_success "RAG endpoint functional"
    else
        log_error "RAG endpoint test failed"
        return 1
    fi
    
    log_success "Deployment verification complete"
}

# Show deployment status
show_status() {
    log_info "Deployment Status:"
    echo ""
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    log_info "Service URLs:"
    echo "  - RAG API:          http://localhost:8000"
    echo "  - RAG UI:           http://localhost:8000/ui"
    echo "  - Rasa Server:      http://localhost:5005"
    echo "  - Rasa Actions:     http://localhost:5055"
    echo ""
    
    log_info "Useful Commands:"
    echo "  - View logs:        docker-compose -f $COMPOSE_FILE logs -f"
    echo "  - Restart service:  docker-compose -f $COMPOSE_FILE restart [service]"
    echo "  - Stop all:         docker-compose -f $COMPOSE_FILE down"
    echo "  - Health check:     bash healthcheck.sh"
    echo "  - Rollback:         bash rollback.sh"
    echo ""
}

# Cleanup old backups (keep last 5)
cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    if [ -d "$BACKUP_DIR" ]; then
        # Keep only the 5 most recent backup files
        ls -t "$BACKUP_DIR"/data_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
        ls -t "$BACKUP_DIR"/rasa_models_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
        ls -t "$BACKUP_DIR"/env_backup_* 2>/dev/null | tail -n +6 | xargs -r rm -f
        
        log_success "Old backups cleaned up"
    fi
}

# Main deployment flow
main() {
    echo "=========================================="
    echo "Production Deployment - $ENVIRONMENT"
    echo "Timestamp: $TIMESTAMP"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    backup_deployment
    run_pre_deployment_tests
    build_images
    
    if deploy; then
        if verify_deployment; then
            show_status
            cleanup_old_backups
            log_success "🚀 Deployment completed successfully!"
            exit 0
        else
            log_error "Deployment verification failed"
            log_warning "Consider rolling back: bash rollback.sh"
            exit 1
        fi
    else
        log_error "Deployment failed"
        log_warning "Attempting automatic rollback..."
        bash rollback.sh
        exit 1
    fi
}

# Run main deployment
main
