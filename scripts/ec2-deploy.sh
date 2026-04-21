#!/bin/bash
# EC2 Initial Deployment Script - Deploy to EC2 for the first time
# This script should be run ON the EC2 instance after initial setup
# Usage: ./scripts/ec2-deploy.sh

set -e

# Configuration
PROJECT_DIR="/home/ubuntu/mortgage-rag-starter"
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"
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

# Check if running on EC2
check_environment() {
    log_info "Checking environment..."
    
    if [ ! -d "$PROJECT_DIR" ]; then
        log_error "Project directory not found: $PROJECT_DIR"
        log_info "Please run this script from: $PROJECT_DIR"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "$ENV_FILE not found"
        log_info "Please copy .env.production.template to .env.production and configure it"
        exit 1
    fi
    
    log_success "Environment check passed"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        log_info "Run: curl -fsSL https://get.docker.com | sudo sh"
        exit 1
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        log_info "Run: sudo apt-get install -y docker-compose-plugin"
        exit 1
    fi
    
    # Check if user is in docker group
    if ! groups | grep -q docker; then
        log_warning "User not in docker group"
        log_info "Run: sudo usermod -aG docker \$USER && newgrp docker"
    fi
    
    # Check OpenAI API key
    if ! grep -q "OPENAI_API_KEY=sk-" "$ENV_FILE"; then
        log_error "OpenAI API key not configured in $ENV_FILE"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Check Rasa project
check_rasa_project() {
    log_info "Checking Rasa project..."
    
    RASA_DIR=$(grep "RASA_PROJECT_DIR" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d "'" | sed 's/^[ \t]*//;s/[ \t]*$//')
    
    if [ -z "$RASA_DIR" ]; then
        RASA_DIR="../mortgage-rasa-chatbot"
    fi
    
    if [ ! -d "$RASA_DIR" ]; then
        log_warning "Rasa project directory not found: $RASA_DIR"
        log_info "The Rasa containers may fail to start without the project"
        read -p "Continue anyway? (yes/no): " continue_without_rasa
        if [ "$continue_without_rasa" != "yes" ]; then
            exit 1
        fi
    else
        log_success "Rasa project found: $RASA_DIR"
    fi
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p backups
    mkdir -p data/index
    mkdir -p data/raw
    
    log_success "Directories created"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    docker compose -f "$COMPOSE_FILE" build --no-cache
    
    log_success "Docker images built successfully"
}

# Pull Rasa images
pull_rasa_images() {
    log_info "Pulling Rasa images..."
    
    docker compose -f "$COMPOSE_FILE" pull rasa rasa-actions 2>/dev/null || log_warning "Could not pull Rasa images"
    
    log_success "Rasa images pulled"
}

# Start services
start_services() {
    log_info "Starting services..."
    
    docker compose -f "$COMPOSE_FILE" up -d --remove-orphans
    
    log_success "Services started"
}

# Wait for services
wait_for_services() {
    log_info "Waiting for services to become healthy..."
    
    local max_wait=180
    local elapsed=0
    local interval=10
    
    while [ $elapsed -lt $max_wait ]; do
        sleep $interval
        elapsed=$((elapsed + interval))
        
        echo -n "."
        
        # Check if services are running
        if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
            # Try health check
            if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
                echo ""
                log_success "Services are healthy!"
                return 0
            fi
        fi
    done
    
    echo ""
    log_error "Services did not become healthy within ${max_wait}s"
    return 1
}

# Run health checks
run_health_checks() {
    log_info "Running comprehensive health checks..."
    
    if [ -f "healthcheck.sh" ]; then
        bash healthcheck.sh
        return $?
    else
        log_warning "healthcheck.sh not found, running basic checks"
        
        # Basic health checks
        curl -sf http://localhost:8000/health || { log_error "RAG API health check failed"; return 1; }
        curl -sf http://localhost:5005/version || { log_warning "Rasa health check failed"; }
        curl -sf http://localhost:5055/health || { log_warning "Rasa Actions health check failed"; }
        
        # Test RAG endpoint
        response=$(curl -s -X POST "http://localhost:8000/ask" \
            -H "Content-Type: application/json" \
            -d '{"question":"What is mortgage pre-approval?"}')
        
        if echo "$response" | grep -q '"answer"'; then
            log_success "RAG functionality test passed"
            return 0
        else
            log_error "RAG functionality test failed"
            return 1
        fi
    fi
}

# Show deployment status
show_status() {
    log_info "Deployment Status:"
    echo ""
    
    docker compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log_info "Service URLs:"
    echo "  - RAG API:          http://$(curl -s ifconfig.me):8000"
    echo "  - RAG API (local):  http://localhost:8000"
    echo "  - RAG UI:           http://$(curl -s ifconfig.me):8000/ui"
    echo "  - Rasa Server:      http://localhost:5005"
    echo "  - Rasa Actions:     http://localhost:5055"
    echo ""
    
    log_info "Useful Commands:"
    echo "  - View logs:        docker compose -f $COMPOSE_FILE logs -f"
    echo "  - Restart service:  docker compose -f $COMPOSE_FILE restart [service]"
    echo "  - Stop all:         docker compose -f $COMPOSE_FILE down"
    echo "  - Update:           ./scripts/ec2-update.sh"
    echo "  - Health check:     bash healthcheck.sh"
    echo ""
}

# Create initial backup
create_initial_backup() {
    log_info "Creating initial backup..."
    
    mkdir -p backups
    
    # Backup environment file
    cp "$ENV_FILE" "backups/env_backup_initial_$TIMESTAMP"
    
    # Backup data
    tar -czf "backups/data_backup_initial_$TIMESTAMP.tar.gz" data/ 2>/dev/null || true
    
    log_success "Initial backup created"
}

# Setup systemd service (optional)
setup_systemd_service() {
    log_info "Would you like to set up systemd service for auto-start on reboot?"
    read -p "(yes/no): " setup_systemd
    
    if [ "$setup_systemd" = "yes" ]; then
        sudo tee /etc/systemd/system/mortgage-rag.service > /dev/null << EOF
[Unit]
Description=Mortgage RAG + RASA Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker compose -f $COMPOSE_FILE up -d
ExecStop=/usr/bin/docker compose -f $COMPOSE_FILE down
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable mortgage-rag.service
        
        log_success "Systemd service created and enabled"
        log_info "Service will auto-start on reboot"
    fi
}

# Main deployment flow
main() {
    echo "=========================================="
    echo "EC2 Initial Deployment"
    echo "Timestamp: $TIMESTAMP"
    echo "=========================================="
    echo ""
    
    check_environment
    check_prerequisites
    check_rasa_project
    create_directories
    create_initial_backup
    
    echo ""
    log_warning "This will deploy the full stack on this EC2 instance"
    read -p "Continue with deployment? (yes/no): " confirmation
    if [ "$confirmation" != "yes" ]; then
        log_info "Deployment cancelled"
        exit 0
    fi
    echo ""
    
    pull_rasa_images
    build_images
    start_services
    
    if wait_for_services; then
        if run_health_checks; then
            show_status
            setup_systemd_service
            echo ""
            log_success "🚀 Initial deployment completed successfully!"
            exit 0
        else
            log_error "Health checks failed"
            log_info "Check logs: docker compose -f $COMPOSE_FILE logs"
            exit 1
        fi
    else
        log_error "Services failed to start properly"
        log_info "Check logs: docker compose -f $COMPOSE_FILE logs"
        exit 1
    fi
}

# Run main deployment
main
