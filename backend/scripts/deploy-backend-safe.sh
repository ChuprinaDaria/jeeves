#!/bin/bash

# ============================================================================
# Safe Backend Deployment Script
# Preserves database volumes and existing data
# ============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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
DOCKER_COMPOSE_PATH="/opt/ai-nexelin/docker-compose.yml"
BACKUP_DIR="/opt/ai-nexelin/backups"
COMMIT_SHA=""
BRANCH=""

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
        --compose-path)
            DOCKER_COMPOSE_PATH="$2"
            shift 2
            ;;
        --backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        --commit)
            COMMIT_SHA="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$VPS_HOST" ]; then
    log_error "VPS_HOST is required. Use --host"
    exit 1
fi

log_info "Starting safe backend deployment..."
log_info "Host: $VPS_HOST"
log_info "User: $VPS_USER"
log_info "Docker Compose: $DOCKER_COMPOSE_PATH"
log_info "Commit: ${COMMIT_SHA:-unknown}"
log_info "Branch: ${BRANCH:-unknown}"

# Deployment function
deploy() {
    log_info "Connecting to server..."
    
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=30 "$VPS_USER@$VPS_HOST" << 'DEPLOY_EOF'
        set -euo pipefail
        
        # Configuration
        DOCKER_COMPOSE_PATH="${DOCKER_COMPOSE_PATH:-/opt/ai-nexelin/docker-compose.yml}"
        BACKUP_DIR="${BACKUP_DIR:-/opt/ai-nexelin/backups}"
        COMMIT_SHA="${COMMIT_SHA:-unknown}"
        BRANCH="${BRANCH:-unknown}"
        
        # Logging
        LOG_FILE="/tmp/deployment-$(date +%Y%m%d-%H%M%S).log"
        
        log_info() {
            echo "[INFO] $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1" | tee -a "$LOG_FILE"
        }
        
        log_success() {
            echo "[SUCCESS] $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1" | tee -a "$LOG_FILE"
        }
        
        log_error() {
            echo "[ERROR] $(date -u +'%Y-%m-%d %H:%M:%S UTC') - $1" | tee -a "$LOG_FILE" >&2
        }
        
        log_info "=== Starting Safe Deployment ==="
        log_info "Commit: $COMMIT_SHA"
        log_info "Branch: $BRANCH"
        log_info "Docker Compose: $DOCKER_COMPOSE_PATH"
        
        # Check if docker-compose file exists
        if [ ! -f "$DOCKER_COMPOSE_PATH" ]; then
            log_error "Docker compose file not found: $DOCKER_COMPOSE_PATH"
            exit 1
        fi
        
        # Create backup directory
        mkdir -p "$BACKUP_DIR"
        log_info "Backup directory: $BACKUP_DIR"
        
        # Backup current container status
        log_info "Creating backup of current state..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" ps > "$BACKUP_DIR/containers-$(date +%Y%m%d-%H%M%S).txt" 2>/dev/null || true
        docker-compose -f "$DOCKER_COMPOSE_PATH" config > "$BACKUP_DIR/config-$(date +%Y%m%d-%H%M%S).yml" 2>/dev/null || true
        
        # Check database volume exists
        log_info "Checking database volumes..."
        DB_VOLUME_EXISTS=$(docker volume ls | grep -c "postgres_data" || echo "0")
        if [ "$DB_VOLUME_EXISTS" -eq "0" ]; then
            log_info "Database volume not found, will be created"
        else
            log_success "Database volume exists, will be preserved"
        fi
        
        # Stop only application containers (NOT database/redis)
        log_info "Stopping application containers (preserving database and redis)..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" stop web celery_worker celery_beat nginx 2>/dev/null || log_info "Some containers already stopped"
        
        # Pull latest code (if using git)
        if [ -d "/opt/ai-nexelin" ] && [ -d "/opt/ai-nexelin/.git" ]; then
            log_info "Pulling latest code..."
            cd /opt/ai-nexelin
            git fetch origin || log_warning "Git fetch failed"
            git checkout "$BRANCH" || log_warning "Git checkout failed"
            git pull origin "$BRANCH" || log_warning "Git pull failed"
        fi
        
        # Rebuild only application containers
        log_info "Rebuilding application containers..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" build web celery_worker celery_beat || {
            log_error "Build failed"
            exit 1
        }
        
        # Start all services (database/redis will use existing volumes)
        log_info "Starting all services..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" up -d || {
            log_error "Failed to start services"
            exit 1
        }
        
        # Wait for services to be healthy
        log_info "Waiting for services to be healthy..."
        sleep 10
        
        # Run migrations (safe, won't delete data)
        log_info "Running database migrations..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" exec -T web python manage.py migrate --noinput || {
            log_error "Migrations failed"
            exit 1
        }
        
        # Collect static files
        log_info "Collecting static files..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" exec -T web python manage.py collectstatic --noinput || {
            log_warning "Collectstatic failed, continuing..."
        }
        
        # Restart application services
        log_info "Restarting application services..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" restart web celery_worker celery_beat || log_warning "Some services failed to restart"
        
        # Check container status
        log_info "Checking container status..."
        docker-compose -f "$DOCKER_COMPOSE_PATH" ps
        
        # Health check
        log_info "Performing health check..."
        sleep 5
        if curl -f http://localhost:8000/ > /dev/null 2>&1; then
            log_success "Health check passed"
        else
            log_warning "Health check failed (may be normal during startup)"
        fi
        
        log_success "=== Deployment Completed Successfully ==="
        log_info "Log file: $LOG_FILE"
        echo "LOG_FILE=$LOG_FILE"
DEPLOY_EOF

    if [ $? -eq 0 ]; then
        log_success "Deployment completed successfully"
        return 0
    else
        log_error "Deployment failed"
        return 1
    fi
}

# Run deployment
if deploy; then
    log_success "Backend deployment completed at $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
    exit 0
else
    log_error "Backend deployment failed at $(date -u +'%Y-%m-%d %H:%M:%S UTC')"
    exit 1
fi

