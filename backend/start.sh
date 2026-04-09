#!/bin/bash

# Кольорові виведення для кращої читабельності
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== Запуск повного стеку AI Nexelin =====${NC}"

# Перевірка наявності Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker не встановлений. Будь ласка, встановіть Docker перед запуском.${NC}"
    exit 1
fi

# Перевірка наявності docker-compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose не встановлений. Будь ласка, встановіть Docker Compose перед запуском.${NC}"
    exit 1
fi

# Створення директорій для NGINX
echo -e "${YELLOW}Створення директорій для NGINX...${NC}"
mkdir -p nginx/conf.d
mkdir -p nginx/ssl

# Копіювання конфігурації NGINX
echo -e "${YELLOW}Копіювання конфігурації NGINX...${NC}"
cp nginx/conf.d/default.conf nginx/conf.d/default.conf

# Створення директорії для фронтенду в MASTER/client_portal, якщо її немає
if [ ! -d "MASTER/client_portal" ]; then
    echo -e "${YELLOW}Створення директорії для фронтенду...${NC}"
    mkdir -p MASTER/client_portal
    
    # Копіювання Dockerfile.frontend
    cp Dockerfile.frontend MASTER/client_portal/Dockerfile
    
    # Створення nginx.conf для фронтенду
    cp nginx.conf MASTER/client_portal/nginx.conf
fi

# Перевірка наявності .env файлу
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Створення .env файлу із значеннями за замовчуванням...${NC}"
    cat > .env << EOF
SECRET_KEY=dev-secret
DEBUG=True
DB_NAME=admin_db
DB_USER=admin_user
DB_PASS=admin_pass
DB_HOST=postgres
DB_PORT=5432
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
OPENAI_API_KEY=

# Twilio WhatsApp
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
WHATSAPP_QR_SECRET=

# CORS
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*
CSRF_TRUSTED_ORIGINS=http://localhost,https://localhost,http://*,https://*
EOF
    echo -e "${YELLOW}Створено .env файл. Будь ласка, відредагуйте його з правильними налаштуваннями.${NC}"
fi

# Запуск Docker Compose
echo -e "${GREEN}Запуск контейнерів...${NC}"
docker-compose up -d

# Отримання IP-адреси сервера
SERVER_IP=$(hostname -I | awk '{print $1}')

echo -e "${GREEN}===== Розгортання завершено! =====${NC}"
echo -e "${GREEN}Frontend доступний за адресою: http://${SERVER_IP}${NC}"
echo -e "${GREEN}Backend API доступний за адресою: http://${SERVER_IP}/api/${NC}"
echo -e "${GREEN}Admin-панель доступна за адресою: http://${SERVER_IP}/admin/${NC}"
echo -e "${YELLOW}Для перегляду логів використовуйте: docker-compose logs -f${NC}"
