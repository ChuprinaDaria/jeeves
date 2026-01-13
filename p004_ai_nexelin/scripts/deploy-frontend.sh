#!/bin/bash

# Frontend Deployment Script
# This script can be used for manual deployment or as a reference for CI/CD

set -e

echo "🚀 Starting frontend deployment..."

# Configuration
FTP_SERVER="${FTP_SERVER:-}"
FTP_USERNAME="${FTP_USERNAME:-}"
FTP_PASSWORD="${FTP_PASSWORD:-}"
FTP_REMOTE_DIR="${FTP_REMOTE_DIR:-/public_html/}"
BUILD_DIR="MASTER/client_portal/dist"

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

# Check if build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    log_error "Build directory not found: $BUILD_DIR"
    log_error "Please run 'npm run build' first"
    exit 1
fi

# Validate FTP credentials
if [ -z "$FTP_SERVER" ] || [ -z "$FTP_USERNAME" ] || [ -z "$FTP_PASSWORD" ]; then
    log_error "FTP credentials not set. Please set FTP_SERVER, FTP_USERNAME, and FTP_PASSWORD"
    exit 1
fi

log_success "Build directory found: $BUILD_DIR"
log_success "FTP Server: $FTP_SERVER"
log_success "Remote Directory: $FTP_REMOTE_DIR"

# Deploy using lftp (if available)
if command -v lftp &> /dev/null; then
    log_success "Using lftp for deployment..."
    
    lftp -c "
    set ftp:ssl-allow no
    open -u $FTP_USERNAME,$FTP_PASSWORD $FTP_SERVER
    cd $FTP_REMOTE_DIR
    mirror -R --delete --verbose $BUILD_DIR .
    bye
    " || {
        log_error "lftp deployment failed"
        exit 1
    }
    
    log_success "Deployment completed successfully"
else
    log_warning "lftp not found. Install it for better deployment experience."
    log_warning "Alternative: Use FTP client or GitHub Actions workflow"
fi

# Create deployment archive
ARCHIVE_NAME="frontend-deployment-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$ARCHIVE_NAME" -C "$BUILD_DIR" . || log_warning "Failed to create archive"

log_success "Deployment archive created: $ARCHIVE_NAME"
log_success "Deployment completed at $(date -u +'%Y-%m-%d %H:%M:%S UTC')"

