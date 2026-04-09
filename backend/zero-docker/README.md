# Zero Email Service - Docker Setup

## Проблема
Zero використовує Cloudflare Workers (wrangler), який має критичний баг EPIPE на деяких Linux системах.
Це відома проблема: https://github.com/cloudflare/workers-sdk/issues

## Рішення
Використовуємо Docker контейнери + mock backend замість справжнього wrangler.

## Запуск

1. Зупиніть всі локальні сервіси:
```bash
pkill -f "node.*8787\|vite.*3000" || true
docker-compose down
```

2. Запустіть Docker версію:
```bash
docker-compose up -d
```

3. Відкрийте http://localhost:3001

## Що працює
- ✅ Авторизація (mock)
- ✅ UI інтерфейс
- ✅ Навігація
- ✅ База даних PostgreSQL
- ✅ Redis кеш

## Що НЕ працює (через EPIPE баг)
- ❌ Справжня інтеграція з Gmail
- ❌ Cloudflare Workers функції
- ❌ Реальна відправка email

## Для розробників
Mock backend емулює всі необхідні API endpoints для роботи frontend.
Код mock: zero-proxy.js
