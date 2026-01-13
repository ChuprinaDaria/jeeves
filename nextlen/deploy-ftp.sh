#!/bin/bash

# FTP credentials
FTP_USER="f017cd3a"
FTP_PASS="f5mPnpwnsotcoNraN4zF"
FTP_HOST="w020c360.kasserver.com"
FTP_DIR="/"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔨 Building project...${NC}"
npm run build:prod

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}❌ Build failed!${NC}"
    exit 1
fi

# Copy .htaccess to dist
echo -e "${BLUE}📋 Copying .htaccess...${NC}"
if [ -f "public/.htaccess" ]; then
    cp public/.htaccess dist/
else
    echo -e "${YELLOW}⚠️  Warning: public/.htaccess not found${NC}"
fi

# Copy static/extensions directory to dist
echo -e "${BLUE}📦 Copying static extensions...${NC}"
if [ -d "public/static/extensions" ]; then
    mkdir -p dist/static/extensions
    cp -r public/static/extensions/* dist/static/extensions/
else
    echo -e "${YELLOW}⚠️  Warning: public/static/extensions not found${NC}"
fi

# Check if lftp is installed
if ! command -v lftp &> /dev/null; then
    echo -e "${YELLOW}⚠️  lftp not found. Installing...${NC}"
    echo -e "${YELLOW}Please install lftp: sudo apt-get install lftp (Ubuntu/Debian) or brew install lftp (macOS)${NC}"
    exit 1
fi

# Upload to FTP using lftp
echo -e "${BLUE}📤 Uploading files to FTP...${NC}"
cd dist

# Upload files using lftp
lftp -c "
set ftp:ssl-allow no
set ssl:verify-certificate no
set ftp:passive-mode yes
open -u $FTP_USER,$FTP_PASS $FTP_HOST
cd $FTP_DIR
mput index.html
mput .htaccess
mput icon.svg
mput manifest.json
mput vite.svg
mirror -R assets/ assets/
mirror -R logo/ logo/
mirror -R static/ static/
quit
"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
    echo -e "${BLUE}🌐 Website: https://app.nexelin.com${NC}"
    echo -e "${YELLOW}🔄 Please clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)${NC}"
else
    echo -e "${YELLOW}❌ Deployment failed!${NC}"
    exit 1
fi

cd ..
