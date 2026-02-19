# Matrix Bot Credentials - grot.de

## Production Credentials

**⚠️ ЦЕЙ ФАЙЛ МІСТИТЬ ЧУТЛИВІ ДАНІ - НЕ КОМІТИТИ В GIT!**

```
User ID: @nexelin-bot:grot.de
Access Token: syt_bmV4ZWxpbi1ib3Q_fuwbUhVuxZFcJwDQiBac_4cfwL6
Homeserver: https://matrix.grot.de
```

## Environment Variables

```bash
MATRIX_HOMESERVER_URL=https://matrix.grot.de
MATRIX_BOT_USER_ID=@nexelin-bot:grot.de
MATRIX_BOT_ACCESS_TOKEN=syt_bmV4ZWxpbi1ib3Q_fuwbUhVuxZFcJwDQiBac_4cfwL6
```

## Використання

1. Скопіюйте `config.example.env` в `.env`
2. Вставте credentials зверху
3. Запустіть сервіс: `go run cmd/server/main.go`

## Безпека

- ✅ `.env` файли вже в `.gitignore`
- ✅ Access Token не зберігається в git
- ⚠️ НЕ діліться цими credentials публічно
- ⚠️ Якщо token скомпрометовано - згенеруйте новий

## Оновлення Token

Якщо потрібно оновити access token:

1. Увійдіть в Matrix клієнт (Element) як `@nexelin-bot:grot.de`
2. Отримайте новий access token через:
   - Element Settings → Help & About → Advanced → Access Token
   - Або через Matrix Client API: `POST /_matrix/client/r0/login`
3. Оновіть `.env` файл
4. Перезапустіть Integration Service

