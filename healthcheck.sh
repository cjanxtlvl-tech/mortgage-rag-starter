#!/bin/bash
# Comprehensive health check script for production deployment
# Returns 0 if all services are healthy, 1 otherwise

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RAG_API_URL="${RAG_API_URL:-http://localhost:8000}"
RASA_API_URL="${RASA_API_URL:-http://localhost:5005}"
RASA_ACTIONS_URL="${RASA_ACTIONS_URL:-http://localhost:5055}"
TIMEOUT=5

# Function to check service health
check_service() {
    local service_name=$1
    local url=$2
    local max_retries=${3:-3}
    local retry_delay=${4:-2}
    
    echo -n "Checking $service_name... "
    
    for i in $(seq 1 $max_retries); do
        if curl -sf --connect-timeout $TIMEOUT "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Healthy${NC}"
            return 0
        fi
        
        if [ $i -lt $max_retries ]; then
            echo -n "."
            sleep $retry_delay
        fi
    done
    
    echo -e "${RED}✗ Unhealthy${NC}"
    return 1
}

# Function to check Docker container health
check_container_health() {
    local container_name=$1
    
    echo -n "Checking Docker container $container_name... "
    
    if ! docker ps --filter "name=$container_name" --format "{{.Status}}" | grep -q "Up"; then
        echo -e "${RED}✗ Not running${NC}"
        return 1
    fi
    
    local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")
    
    if [ "$health_status" = "healthy" ] || [ "$health_status" = "none" ]; then
        echo -e "${GREEN}✓ Running${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Status: $health_status${NC}"
        return 1
    fi
}

# Function to check API endpoint
check_api_endpoint() {
    local endpoint=$1
    local expected_status=${2:-200}
    
    echo -n "Testing endpoint $endpoint... "
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout $TIMEOUT "$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response" = "$expected_status" ]; then
        echo -e "${GREEN}✓ $response${NC}"
        return 0
    else
        echo -e "${RED}✗ $response (expected $expected_status)${NC}"
        return 1
    fi
}

# Main health check
echo "=========================================="
echo "Production Health Check"
echo "=========================================="
echo ""

FAILED=0

# Check Docker containers
echo "Docker Container Status:"
check_container_health "mortgage-rag-api-prod" || FAILED=$((FAILED+1))
check_container_health "mortgage-rasa-server-prod" || FAILED=$((FAILED+1))
check_container_health "mortgage-rasa-actions-prod" || FAILED=$((FAILED+1))
echo ""

# Check service endpoints
echo "Service Health Endpoints:"
check_service "RAG API Health" "$RAG_API_URL/health" || FAILED=$((FAILED+1))
check_service "Rasa Server" "$RASA_API_URL/version" || FAILED=$((FAILED+1))
check_service "Rasa Actions" "$RASA_ACTIONS_URL/health" || FAILED=$((FAILED+1))
echo ""

# Check critical API endpoints
echo "API Endpoint Tests:"
check_api_endpoint "$RAG_API_URL/health" "200" || FAILED=$((FAILED+1))
check_api_endpoint "$RAG_API_URL/health/rasa" "200" || FAILED=$((FAILED+1))
echo ""

# Test RAG functionality
echo "Functional Tests:"
echo -n "Testing RAG /ask endpoint... "
ask_response=$(curl -s -X POST "$RAG_API_URL/ask" \
    -H "Content-Type: application/json" \
    -d '{"question":"What is mortgage pre-approval?"}' \
    --connect-timeout $TIMEOUT 2>/dev/null || echo "{}")

if echo "$ask_response" | grep -q '"answer"'; then
    echo -e "${GREEN}✓ Functional${NC}"
else
    echo -e "${RED}✗ Failed${NC}"
    FAILED=$((FAILED+1))
fi
echo ""

# Summary
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All health checks passed!${NC}"
    echo "=========================================="
    exit 0
else
    echo -e "${RED}$FAILED health check(s) failed!${NC}"
    echo "=========================================="
    exit 1
fi
