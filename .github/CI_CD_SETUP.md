# CI/CD Pipeline Setup

## 📋 Огляд

Цей проєкт має повний CI/CD pipeline з автоматичним тестуванням та деплоєм:

- **Main branch**: Запускає тести з покриттям коду
- **Dev branch**: Автоматичний деплой бекенду та фронтенду

## 🎯 Логіка запуску

Pipeline автоматично визначає, що змінилося:

- ✅ **Якщо зміни тільки у фронтенді** (`frontend/**`) → деплоїться тільки фронтенд
- ✅ **Якщо зміни тільки у бекенді** (`backend/**`) → деплоїться тільки бекенд
- ✅ **Якщо зміни в обох** → деплоїться і фронтенд, і бекенд

## 🔐 Налаштування GitHub Secrets

Перейдіть до **Settings → Secrets and variables → Actions** та додайте:

### Backend Deployment Secrets

```bash
VPS_HOST=your.server.ip.or.domain
VPS_USER=deploy
VPS_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
VPS_DOCKER_COMPOSE_PATH=/opt/ai-nexelin/docker-compose.yml
```

### Frontend Deployment Secrets

```bash
FTP_HOST=w020c360.kasserver.com
FTP_USER=f017cd3a
FTP_PASSWORD=f5mPnpwnsotcoNraN4zF
FTP_DIR=/
VITE_API_URL=https://api.nexelin.com/api
```

## 📁 Структура Workflow

### Main Branch (`main-tests.yml`)

**Тригери:**
- Push до `main`
- Pull Request до `main`

**Jobs:**
1. **check-changes** - Визначає, що змінилося
2. **backend-tests** - Запускається тільки якщо зміни в `backend/**`
   - Тести з покриттям
   - Звіти coverage (XML, HTML)
3. **frontend-tests** - Запускається тільки якщо зміни в `frontend/**`
   - ESLint перевірка
   - Production build

### Dev Branch (`dev-deploy.yml`)

**Тригери:**
- Push до `dev`

**Jobs:**
1. **check-changes** - Визначає, що змінилося
2. **deploy-backend** - Запускається тільки якщо зміни в `backend/**`
   - Безпечний деплой (зберігає database volumes)
   - Health checks
   - Детальне логування
3. **deploy-frontend** - Запускається тільки якщо зміни в `frontend/**`
   - Build production версії
   - FTP деплой
   - Health check

## 🛡️ Безпека деплою бекенду

Скрипт `deploy-backend-safe.sh` **НЕ видаляє**:
- ✅ Database volumes (`postgres_data`)
- ✅ Static files volume (`static_volume`)
- ✅ Media files volume (`media_volume`)

Він тільки:
- 🔄 Перебудовує контейнери
- 🔄 Запускає міграції (безпечно)
- 🔄 Збирає статичні файли

## 🏥 Health Checks

### Backend Health Check

Перевіряє:
1. ✅ Статус Docker контейнерів
2. ✅ Підключення до бази даних
3. ✅ Підключення до Redis
4. ✅ Відповідь API endpoint
5. ✅ Помилки в логах

### Frontend Health Check

Перевіряє:
1. ✅ Доступність сайту `https://app.nexelin.com`

## 📊 Логування

Всі деплої мають детальне логування:
- ✅ Timestamp для кожної операції
- ✅ Кольорове форматування
- ✅ Збереження логів на сервері
- ✅ GitHub Actions Summary

## 🔧 Локальне тестування

### Тестування скриптів деплою

```bash
# Backend
cd backend
bash scripts/deploy-backend-safe.sh \
  --host your-server \
  --user deploy \
  --compose-path /opt/ai-nexelin/docker-compose.yml

# Frontend
cd frontend
bash scripts/deploy-ftp-safe.sh \
  --host w020c360.kasserver.com \
  --user f017cd3a \
  --pass your-password \
  --dir /
```

### Health Check

```bash
cd backend
bash scripts/health-check.sh \
  --host your-server \
  --user deploy \
  --url http://your-server:8000
```

## 📝 Приклади використання

### Зміни тільки у фронтенді

```bash
# Змінюємо файл у frontend/
git add frontend/src/pages/WebChatPage.jsx
git commit -m "Update chat page"
git push origin dev
```

**Результат:** Запуститься тільки `deploy-frontend` job

### Зміни тільки у бекенді

```bash
# Змінюємо файл у backend/
git add backend/MASTER/clients/views.py
git commit -m "Update client views"
git push origin dev
```

**Результат:** Запуститься тільки `deploy-backend` job

### Зміни в обох

```bash
# Змінюємо файли в обох частинах
git add frontend/ backend/
git commit -m "Update both frontend and backend"
git push origin dev
```

**Результат:** Запустяться обидва jobs паралельно

## ⚠️ Важливо

1. **Database volumes** завжди зберігаються - дані не будуть втрачені
2. **Secrets** мають бути налаштовані в GitHub перед першим деплоєм
3. **SSH ключ** має мати доступ до сервера без пароля
4. **FTP credentials** зберігаються в GitHub Secrets (не в коді!)

## 🐛 Troubleshooting

### Backend деплой не запускається

1. Перевірте, чи є зміни в `backend/**`
2. Перевірте SSH ключ у secrets
3. Перевірте права доступу на сервері

### Frontend деплой не запускається

1. Перевірте, чи є зміни в `frontend/**`
2. Перевірте FTP credentials у secrets
3. Перевірте, чи встановлено `lftp` на runner

### Health check не проходить

1. Перевірте логи контейнерів: `docker-compose logs`
2. Перевірте доступність портів
3. Перевірте database connection

