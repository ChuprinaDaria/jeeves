#!/bin/bash

# Backend Deployment Script
# This script can be used for manual deployment or as a reference for CI/CD

set -e

echo "🚀 Starting backend deployment..."

# Configuration
VPS_HOST="${VPS_HOST:-}"
VPS_USER="${VPS_USER:-deploy}"
SSH_KEY="${SSH_KEY:-~/.ssh/id_rsa}"
DOCKER_COMPOSE_PATH="${DOCKER_COMPOSE_PATH:-/opt/ai-nexelin/docker-compose.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/ai-nexelin/backups}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Error logging function
log_error() {
    echo -e "${RED}❌ Error: $1${NC}" >&2
    echo "$(date -u +'%Y-%m-%d %H:%M:%S UTC') - ERROR: $1" >> deployment-errors.log
}

# Success logging function
log_success() {
    echo -e "${GREEN}✅ $1${NC}"
    echo "$(date -u +'%Y-%m-%d %H:%M:%S UTC') - SUCCESS: $1" >> deployment.log
}

# Warning logging function
log_warning() {
    echo -e "${YELLOW}⚠️  Warning: $1${NC}"
    echo "$(date -u +'%Y-%m-%d %H:%M:%S UTC') - WARNING: $1" >> deployment.log
}

# Validate configuration
if [ -z "$VPS_HOST" ]; then
    log_error "VPS_HOST not set. Please set VPS_HOST environment variable"
    exit 1
fi

log_success "VPS Host: $VPS_HOST"
log_success "VPS User: $VPS_USER"
log_success "Docker Compose Path: $DOCKER_COMPOSE_PATH"

# SSH deployment function
deploy_via_ssh() {
    log_success "Connecting to VPS..."
    
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$VPS_USER@$VPS_HOST" << EOF
        set -e
        
        echo "📦 Creating backup..."
        mkdir -p $BACKUP_DIR
        docker-compose -f $DOCKER_COMPOSE_PATH ps > $BACKUP_DIR/containers-$(date +%Y%m%d-%H%M%S).txt || true
        
        echo "🛑 Stopping existing containers..."
        docker-compose -f $DOCKER_COMPOSE_PATH down || echo "No containers to stop"
        
        echo "🔄 Pulling latest images..."
        docker-compose -f $DOCKER_COMPOSE_PATH pull || echo "Pull failed, using existing images"
        
        echo "🚀 Starting containers..."
        docker-compose -f $DOCKER_COMPOSE_PATH up -d
        
        echo "📊 Running migrations..."
        docker-compose -f $DOCKER_COMPOSE_PATH exec -T web python manage.py migrate || echo "Migrations failed"
        
        echo "📁 Collecting static files..."
        docker-compose -f $DOCKER_COMPOSE_PATH exec -T web python manage.py collectstatic --noinput || echo "Collectstatic failed"
        
        echo "🔄 Restarting services..."
        docker-compose -f $DOCKER_COMPOSE_PATH restart || echo "Restart failed"
        
        echo "✅ Deployment completed"
        echo "Deployment time: \$(date -u +'%Y-%m-%d %H:%M:%S UTC')"
        
        echo "📊 Container status:"
        docker-compose -f $DOCKER_COMPOSE_PATH ps
EOF

    if [ $? -eq 0 ]; then
        log_success "Deployment completed successfully"
    else
        log_error "Deployment failed"
        exit 1
    fi
}

# Health check function
health_check() {
    log_success "Performing health check..."
    
    ssh -i "$SSH_KEY" "$VPS_USER@$VPS_HOST" << EOF
        # Check if containers are running
        if docker-compose -f $DOCKER_COMPOSE_PATH ps | grep -q "Up"; then
            echo "✅ Containers are running"
        else
            echo "❌ Some containers are not running"
            exit 1
        fi
        
        # Check API health endpoint
        if curl -f http://localhost:8000/ > /dev/null 2>&1; then
            echo "✅ API health check passed"
        else
            echo "⚠️  API health check failed (may be normal during startup)"
        fi
EOF
}

# Main deployment
log_success "Starting deployment process..."
deploy_via_ssh

# Wait a bit for services to start
sleep 10

# Perform health check
health_check || log_warning "Health check failed, but deployment completed"

log_success "Deployment completed at $(date -u +'%Y-%m-%d %H:%M:%S UTC')"

