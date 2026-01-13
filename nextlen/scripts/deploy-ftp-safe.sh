#!/bin/bash

# ============================================================================
# Safe FTP Deployment Script for Frontend
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
FTP_HOST=""
FTP_USER=""
FTP_PASS=""
FTP_DIR="/"
COMMIT_SHA=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            FTP_HOST="$2"
            shift 2
            ;;
        --user)
            FTP_USER="$2"
            shift 2
            ;;
        --pass)
            FTP_PASS="$2"
            shift 2
            ;;
        --dir)
            FTP_DIR="$2"
            shift 2
            ;;
        --commit)
            COMMIT_SHA="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$FTP_HOST" ] || [ -z "$FTP_USER" ] || [ -z "$FTP_PASS" ]; then
    log_error "FTP_HOST, FTP_USER, and FTP_PASS are required"
    exit 1
fi

log_info "Starting FTP deployment..."
log_info "Host: $FTP_HOST"
log_info "User: $FTP_USER"
log_info "Directory: $FTP_DIR"
log_info "Commit: ${COMMIT_SHA:-unknown}"

# Check if dist directory exists
if [ ! -d "dist" ]; then
    log_error "dist directory not found. Please build the project first."
    exit 1
fi

log_info "Build directory found: $(du -sh dist | cut -f1)"

# Check if lftp is installed
if ! command -v lftp &> /dev/null; then
    log_info "Installing lftp..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y lftp
    elif command -v yum &> /dev/null; then
        sudo yum install -y lftp
    else
        log_error "lftp is not installed and package manager not found"
        exit 1
    fi
fi

# Create backup of current deployment (if possible)
log_info "Attempting to backup current deployment..."
BACKUP_FILE="/tmp/ftp-backup-$(date +%Y%m%d-%H%M%S).tar.gz"

lftp -c "
set ftp:ssl-allow no
set ssl:verify-certificate no
set ftp:passive-mode yes
open -u $FTP_USER,$FTP_PASS $FTP_HOST
cd $FTP_DIR
mirror -R . $BACKUP_FILE --only-newer --parallel=1 || true
quit
" 2>/dev/null || log_warning "Backup failed (may be first deployment)"

# Deploy to FTP
log_info "Uploading files to FTP..."
cd dist

DEPLOY_LOG="/tmp/ftp-deploy-$(date +%Y%m%d-%H%M%S).log"

lftp -c "
set ftp:ssl-allow no
set ssl:verify-certificate no
set ftp:passive-mode yes
set net:timeout 30
set net:max-retries 3
open -u $FTP_USER,$FTP_PASS $FTP_HOST
cd $FTP_DIR
lcd $(pwd)
mirror -R --delete --parallel=3 --verbose
quit
" 2>&1 | tee "$DEPLOY_LOG"

DEPLOY_EXIT_CODE=${PIPESTATUS[0]}

if [ $DEPLOY_EXIT_CODE -eq 0 ]; then
    log_success "Files uploaded successfully"
    
    # Verify upload
    log_info "Verifying upload..."
    UPLOADED_FILES=$(lftp -c "
    set ftp:ssl-allow no
    set ssl:verify-certificate no
    set ftp:passive-mode yes
    open -u $FTP_USER,$FTP_PASS $FTP_HOST
    cd $FTP_DIR
    ls -la index.html
    quit
    " 2>/dev/null | grep -c "index.html" || echo "0")
    
    if [ "$UPLOADED_FILES" -gt "0" ]; then
        log_success "Upload verification passed"
    else
        log_warning "Upload verification failed (index.html not found)"
    fi
    
    log_success "FTP deployment completed"
    log_info "Deployment log: $DEPLOY_LOG"
    log_info "Website: https://app.nexelin.com"
    exit 0
else
    log_error "FTP deployment failed (exit code: $DEPLOY_EXIT_CODE)"
    log_error "Deployment log: $DEPLOY_LOG"
    exit 1
fi

