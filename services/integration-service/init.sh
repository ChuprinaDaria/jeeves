#!/bin/bash
# ============================================
# Matrix Stack for grot.de - v3
# NPM on separate server
# Initialization Script
# ============================================

set -e

echo "=========================================="
echo "Matrix Stack v3 for grot.de"
echo "(NPM on separate server)"
echo "=========================================="
echo ""

if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: docker-compose.yml not found!"
    exit 1
fi

# ============================================
# Generate Secrets
# ============================================
echo "[1/7] Generating secrets..."

POSTGRES_SYNAPSE_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
POSTGRES_MAS_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
POSTGRES_SLIDING_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)

SYNAPSE_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64)
FORM_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64)
TURN_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)

MAS_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 64)
MAS_ENCRYPTION=$(openssl rand -hex 32)
MAS_KEY_ID=$(openssl rand -hex 8)

SLIDING_SYNC_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)

LIVEKIT_API_KEY="API$(openssl rand -hex 8)"
LIVEKIT_API_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)

echo "    ✓ All secrets generated"

# ============================================
# Generate MAS RSA Key
# ============================================
echo "[2/7] Generating MAS RSA key..."
openssl genrsa -out mas/private.pem 4096 2>/dev/null
echo "    ✓ RSA key generated"

# ============================================
# Get IPs
# ============================================
echo ""
echo "[3/7] Server configuration..."
read -p "Enter server's EXTERNAL (public) IP: " EXTERNAL_IP
read -p "Enter server's INTERNAL (LAN) IP: " INTERNAL_IP

if [ -z "$EXTERNAL_IP" ] || [ -z "$INTERNAL_IP" ]; then
    echo "ERROR: Both IPs are required!"
    exit 1
fi
echo "    ✓ External IP: $EXTERNAL_IP"
echo "    ✓ Internal IP: $INTERNAL_IP"

# ============================================
# Update .env
# ============================================
echo ""
echo "[4/7] Updating .env file..."
cat > .env << EOF
# ============================================
# Matrix Stack for grot.de - v3
# Generated on $(date)
# ============================================

DOMAIN=grot.de

# PostgreSQL
POSTGRES_SYNAPSE_PASSWORD=$POSTGRES_SYNAPSE_PASSWORD
POSTGRES_MAS_PASSWORD=$POSTGRES_MAS_PASSWORD
POSTGRES_SLIDING_PASSWORD=$POSTGRES_SLIDING_PASSWORD

# Synapse
SYNAPSE_REGISTRATION_SHARED_SECRET=$SYNAPSE_SECRET

# MAS
MAS_SECRET=$MAS_SECRET

# LiveKit
LIVEKIT_API_KEY=$LIVEKIT_API_KEY
LIVEKIT_API_SECRET=$LIVEKIT_API_SECRET

# coturn
TURN_SECRET=$TURN_SECRET

# Sliding Sync
SLIDING_SYNC_SECRET=$SLIDING_SYNC_SECRET

# Server IPs
EXTERNAL_IP=$EXTERNAL_IP
INTERNAL_IP=$INTERNAL_IP
EOF
echo "    ✓ .env updated"

# ============================================
# Update Synapse Config
# ============================================
echo ""
echo "[5/7] Updating Synapse configuration..."
sed -i "s/POSTGRES_SYNAPSE_PASSWORD_PLACEHOLDER/$POSTGRES_SYNAPSE_PASSWORD/g" synapse/homeserver.yaml
sed -i "s/REGISTRATION_SECRET_PLACEHOLDER/$SYNAPSE_SECRET/g" synapse/homeserver.yaml
sed -i "s/TURN_SECRET_PLACEHOLDER/$TURN_SECRET/g" synapse/homeserver.yaml
sed -i "s/FORM_SECRET_PLACEHOLDER/$FORM_SECRET/g" synapse/homeserver.yaml
sed -i "s/MAS_SECRET_PLACEHOLDER/$MAS_SECRET/g" synapse/homeserver.yaml
echo "    ✓ homeserver.yaml updated"

# ============================================
# Update MAS Config
# ============================================
echo ""
echo "[6/7] Updating MAS configuration..."

RSA_KEY=$(cat mas/private.pem | sed 's/^/        /')

sed -i "s/POSTGRES_MAS_PASSWORD_PLACEHOLDER/$POSTGRES_MAS_PASSWORD/g" mas/config.yaml
sed -i "s/MAS_SECRET_PLACEHOLDER/$MAS_SECRET/g" mas/config.yaml
sed -i "s/MAS_ENCRYPTION_PLACEHOLDER/$MAS_ENCRYPTION/g" mas/config.yaml
sed -i "s/MAS_KEY_ID_PLACEHOLDER/$MAS_KEY_ID/g" mas/config.yaml

awk -v key="$RSA_KEY" '{gsub(/        MAS_RSA_KEY_PLACEHOLDER/, key)}1' mas/config.yaml > mas/config.yaml.tmp
mv mas/config.yaml.tmp mas/config.yaml

echo "    ✓ MAS config.yaml updated"

# ============================================
# Update Other Configs
# ============================================
echo ""
echo "[7/7] Updating other configurations..."

# LiveKit
sed -i "s/LIVEKIT_API_KEY_PLACEHOLDER/$LIVEKIT_API_KEY/g" livekit/livekit.yaml
sed -i "s/LIVEKIT_API_SECRET_PLACEHOLDER/$LIVEKIT_API_SECRET/g" livekit/livekit.yaml

# coturn
sed -i "s/EXTERNAL_IP_PLACEHOLDER/$EXTERNAL_IP/g" coturn/turnserver.conf
sed -i "s/TURN_SECRET_PLACEHOLDER/$TURN_SECRET/g" coturn/turnserver.conf

echo "    ✓ All configurations updated"

# ============================================
# Create Data Directories
# ============================================
echo ""
echo "Creating data directories..."
mkdir -p data/postgres-synapse
mkdir -p data/postgres-mas
mkdir -p data/postgres-sliding

chmod -R 777 synapse/
chmod -R 777 mas/

echo "    ✓ Directories created"

# ============================================
# Done
# ============================================
echo ""
echo "=========================================="
echo "INITIALIZATION COMPLETE!"
echo "=========================================="
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              SAVE THESE CREDENTIALS!                       ║"
echo "╠════════════════════════════════════════════════════════════╣"
printf "║ PostgreSQL Synapse:  %-37s ║\n" "$POSTGRES_SYNAPSE_PASSWORD"
printf "║ PostgreSQL MAS:      %-37s ║\n" "$POSTGRES_MAS_PASSWORD"
printf "║ PostgreSQL Sliding:  %-37s ║\n" "$POSTGRES_SLIDING_PASSWORD"
printf "║ Synapse Secret:      %-37s ║\n" "$SYNAPSE_SECRET"
printf "║ MAS Secret:          %-37s ║\n" "$MAS_SECRET"
printf "║ TURN Secret:         %-37s ║\n" "$TURN_SECRET"
printf "║ LiveKit API Key:     %-37s ║\n" "$LIVEKIT_API_KEY"
printf "║ LiveKit API Secret:  %-37s ║\n" "$LIVEKIT_API_SECRET"
printf "║ Sliding Sync Secret: %-37s ║\n" "$SLIDING_SYNC_SECRET"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "=============================================="
echo "DNS A-records (9 records) → $EXTERNAL_IP"
echo "=============================================="
echo "  grot.de"
echo "  matrix.grot.de"
echo "  chat.grot.de"
echo "  auth.grot.de"
echo "  admin.grot.de"
echo "  livekit.grot.de"
echo "  livekit-jwt.grot.de"
echo "  sliding.grot.de"
echo "  turn.grot.de"
echo ""
echo "=============================================="
echo "NPM PROXY HOSTS (on NPM server)"
echo "Forward to: $INTERNAL_IP"
echo "=============================================="
echo ""
echo "  | Domain                | Forward To          | Port | WS  |"
echo "  |-----------------------|---------------------|------|-----|"
echo "  | grot.de               | $INTERNAL_IP        | 8084 |     |"
echo "  | matrix.grot.de        | $INTERNAL_IP        | 8008 |     |"
echo "  | chat.grot.de          | $INTERNAL_IP        | 8081 |     |"
echo "  | auth.grot.de          | $INTERNAL_IP        | 8080 |     |"
echo "  | admin.grot.de         | $INTERNAL_IP        | 8082 |     |"
echo "  | livekit.grot.de       | $INTERNAL_IP        | 7880 |  ✓  |"
echo "  | livekit-jwt.grot.de   | $INTERNAL_IP        | 8083 |     |"
echo "  | sliding.grot.de       | $INTERNAL_IP        | 8009 |     |"
echo ""
echo "  ⚠️  matrix.grot.de: Add 'client_max_body_size 100M;'"
echo "  ⚠️  livekit.grot.de: Enable WebSocket support!"
echo ""
echo "=============================================="
echo "ROUTER PORT FORWARDING → $INTERNAL_IP"
echo "=============================================="
echo ""
echo "  | External Port   | Protocol | Service      |"
echo "  |-----------------|----------|--------------|"
echo "  | 3478            | TCP+UDP  | coturn STUN  |"
echo "  | 5349            | TCP+UDP  | coturn TLS   |"
echo "  | 49152-49252     | UDP      | coturn relay |"
echo "  | 7881            | TCP      | LiveKit      |"
echo "  | 50000-50100     | UDP      | LiveKit      |"
echo ""
echo "=============================================="
echo "FIREWALL (on this server)"
echo "=============================================="
echo ""
echo "  # From LAN (NPM server)"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8008"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8009"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8080"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8081"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8082"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8083"
echo "  ufw allow from <NPM_SERVER_IP> to any port 8084"
echo "  ufw allow from <NPM_SERVER_IP> to any port 7880"
echo ""
echo "  # From Internet (media/calls)"
echo "  ufw allow 3478/tcp"
echo "  ufw allow 3478/udp"
echo "  ufw allow 5349/tcp"
echo "  ufw allow 5349/udp"
echo "  ufw allow 49152:49252/udp"
echo "  ufw allow 7881/tcp"
echo "  ufw allow 50000:50100/udp"
echo ""
echo "=============================================="
echo "NEXT STEPS"
echo "=============================================="
echo ""
echo "  1. Configure DNS records"
echo "  2. Configure router port forwarding"
echo "  3. Configure firewall (ufw commands above)"
echo "  4. Configure NPM proxy hosts"
echo "  5. Start: docker compose up -d"
echo "  6. Create admin user (see INSTALL.md)"
echo ""
