#!/bin/bash

# Кольорові виведення для кращої читабельності
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== Статус стеку AI Nexelin =====${NC}"

# Перевірка статусу контейнерів
echo -e "${YELLOW}Статус контейнерів:${NC}"
docker-compose ps

echo -e "\n${YELLOW}Використання ресурсів:${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

echo -e "\n${YELLOW}Логи останніх 10 рядків:${NC}"
docker-compose logs --tail=10

# Отримання IP-адреси сервера
SERVER_IP=$(hostname -I | awk '{print $1}')

echo -e "\n${GREEN}===== Доступні сервіси =====${NC}"
echo -e "${GREEN}Frontend: http://${SERVER_IP}${NC}"
echo -e "${GREEN}Backend API: http://${SERVER_IP}/api/${NC}"
echo -e "${GREEN}Admin-панель: http://${SERVER_IP}/admin/${NC}"
echo -e "${GREEN}PostgreSQL: ${SERVER_IP}:5432${NC}"
echo -e "${GREEN}Redis: ${SERVER_IP}:6379${NC}"
