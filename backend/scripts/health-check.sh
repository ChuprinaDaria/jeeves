#!/bin/bash

# ============================================================================
# Health Check Script for Backend
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  [INFO]${NC} $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1"
}

log_success() {
    echo -e "${GREEN}✅ [SUCCESS]${NC} $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️  [WARNING]${NC} $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1"
}

log_error() {
    echo -e "${RED}❌ [ERROR]${NC} $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1" >&2
}

# Parse arguments
VPS_HOST=""
VPS_USER="deploy"
HEALTH_URL=""
DOCKER_COMPOSE_PATH="/opt/concierge/docker-compose.yml"
MAX_RETRIES=5
RETRY_DELAY=10

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            VPS_HOST="$2"
            shift 2
            ;;
        --user)
            VPS_USER="$2"
            shift 2
            ;;
        --url)
            HEALTH_URL="$2"
            shift 2
            ;;
        --compose-path)
            DOCKER_COMPOSE_PATH="$2"
            shift 2
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ -z "$VPS_HOST" ]; then
    log_error "VPS_HOST is required"
    exit 1
fi

log_info "Starting health check..."
log_info "Host: $VPS_HOST"
log_info "URL: ${HEALTH_URL:-http://$VPS_HOST:8000}"

# Health check function
check_health() {
    local retries=0
    local url="${HEALTH_URL:-http://$VPS_HOST:8000}"
    
    ssh -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" << HEALTH_EOF
        set -euo pipefail
        
        DOCKER_COMPOSE_PATH="${DOCKER_COMPOSE_PATH:-/opt/concierge/docker-compose.yml}"
        MAX_RETRIES=${MAX_RETRIES:-5}
        RETRY_DELAY=${RETRY_DELAY:-10}
        
        log_info() {
            echo "[INFO] \$(date -u +'%Y-%m-%d %H:%M:%S UTC') - \$1"
        }
        
        log_success() {
            echo "[SUCCESS] \$(date -u +'%Y-%m-%d %H:%M:%S UTC') - \$1"
        }
        
        log_error() {
            echo "[ERROR] \$(date -u +'%Y-%m-%d %H:%M:%S UTC') - \$1" >&2
        }
        
        # Check 1: Docker containers status
        log_info "=== Health Check 1: Container Status ==="
        if [ -f "\$DOCKER_COMPOSE_PATH" ]; then
            docker-compose -f "\$DOCKER_COMPOSE_PATH" ps
            CONTAINER_COUNT=\$(docker-compose -f "\$DOCKER_COMPOSE_PATH" ps | grep -c "Up" || echo "0")
            if [ "\$CONTAINER_COUNT" -gt "0" ]; then
                log_success "Containers are running (\$CONTAINER_COUNT)"
            else
                log_error "No containers are running"
                exit 1
            fi
        else
            log_error "Docker compose file not found"
            exit 1
        fi
        
        # Check 2: Database connection
        log_info "=== Health Check 2: Database Connection ==="
        DB_CHECK=\$(docker-compose -f "\$DOCKER_COMPOSE_PATH" exec -T postgres pg_isready -U admin_user -d admin_db 2>/dev/null || echo "failed")
        if [ "\$DB_CHECK" != "failed" ]; then
            log_success "Database is ready"
        else
            log_error "Database is not ready"
            exit 1
        fi
        
        # Check 3: Redis connection
        log_info "=== Health Check 3: Redis Connection ==="
        REDIS_CHECK=\$(docker-compose -f "\$DOCKER_COMPOSE_PATH" exec -T redis redis-cli ping 2>/dev/null || echo "failed")
        if [ "\$REDIS_CHECK" = "PONG" ]; then
            log_success "Redis is ready"
        else
            log_error "Redis is not ready"
            exit 1
        fi
        
        # Check 4: API endpoint
        log_info "=== Health Check 4: API Endpoint ==="
        RETRIES=0
        while [ \$RETRIES -lt \$MAX_RETRIES ]; do
            if curl -f -s http://localhost:8000/ > /dev/null 2>&1; then
                log_success "API endpoint is responding"
                break
            else
                RETRIES=\$((RETRIES + 1))
                if [ \$RETRIES -lt \$MAX_RETRIES ]; then
                    log_info "API not ready yet, retrying... (\$RETRIES/\$MAX_RETRIES)"
                    sleep \$RETRY_DELAY
                else
                    log_error "API endpoint is not responding after \$MAX_RETRIES attempts"
                    exit 1
                fi
            fi
        done
        
        # Check 5: Application logs (check for errors)
        log_info "=== Health Check 5: Application Logs ==="
        ERROR_COUNT=\$(docker-compose -f "\$DOCKER_COMPOSE_PATH" logs --tail=50 web 2>/dev/null | grep -i "error\|exception\|traceback" | wc -l || echo "0")
        if [ "\$ERROR_COUNT" -eq "0" ]; then
            log_success "No recent errors in logs"
        else
            log_warning "Found \$ERROR_COUNT potential errors in recent logs"
            docker-compose -f "\$DOCKER_COMPOSE_PATH" logs --tail=20 web | grep -i "error\|exception" || true
        fi
        
        log_success "=== All Health Checks Passed ==="
HEALTH_EOF

    return $?
}

# Run health check
if check_health; then
    log_success "Health check passed"
    exit 0
else
    log_error "Health check failed"
    exit 1
fi

