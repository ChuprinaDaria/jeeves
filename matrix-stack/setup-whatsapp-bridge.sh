#!/bin/bash
# ============================================
# Setup mautrix-whatsapp bridge for Nexelin
# ============================================
#
# Порядок запуску:
# 1. Запусти postgres-mautrix: docker compose up -d postgres-mautrix
# 2. Запусти mautrix-whatsapp (він згенерує registration.yaml):
#    docker compose up mautrix-whatsapp
#    (зупини його після генерації Ctrl+C)
# 3. Запусти цей скрипт: ./setup-whatsapp-bridge.sh
# 4. Перезапусти все: docker compose up -d
#
# Після запуску:
# - Напиши @whatsappbot:grot.de в Element
# - Відправ: login
# - Скануй QR код телефоном
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAUTRIX_DIR="$SCRIPT_DIR/mautrix-whatsapp"
SYNAPSE_DIR="$SCRIPT_DIR/synapse"

# Перевіряємо що registration.yaml існує
if [ ! -f "$MAUTRIX_DIR/registration.yaml" ]; then
    echo "❌ $MAUTRIX_DIR/registration.yaml не знайдено!"
    echo ""
    echo "Спочатку запусти mautrix-whatsapp щоб він згенерував registration:"
    echo "  docker compose up -d postgres-mautrix"
    echo "  docker compose up mautrix-whatsapp"
    echo "  (зачекай поки згенерується, потім Ctrl+C)"
    exit 1
fi

# Копіюємо registration в Synapse
cp "$MAUTRIX_DIR/registration.yaml" "$SYNAPSE_DIR/whatsapp-registration.yaml"
echo "✅ registration.yaml скопійовано в synapse/whatsapp-registration.yaml"

echo ""
echo "Готово! Тепер перезапусти стек:"
echo "  docker compose down"
echo "  docker compose up -d"
echo ""
echo "Після запуску:"
echo "  1. Відкрий Element (https://element.grot.de)"
echo "  2. Напиши боту @whatsappbot:grot.de"
echo "  3. Відправ: login"
echo "  4. Скануй QR код з WhatsApp на телефоні"
