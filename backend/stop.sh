#!/bin/bash

# Кольорові виведення для кращої читабельності
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}===== Зупинка стеку AI Nexelin =====${NC}"

# Зупинка контейнерів
echo -e "${YELLOW}Зупинка контейнерів...${NC}"
docker-compose down

# Очищення невикористаних образів (опціонально)
read -p "Чи хочете видалити невикористані Docker образи? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Видалення невикористаних образів...${NC}"
    docker image prune -f
fi

echo -e "${GREEN}===== Зупинка завершена! =====${NC}"
