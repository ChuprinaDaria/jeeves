# 🚀 CI/CD Pipeline

## Швидкий старт

### 1. Налаштуйте GitHub Secrets

Перейдіть до **Settings → Secrets and variables → Actions** та додайте:

#### Backend
- `VPS_HOST` - IP або домен сервера
- `VPS_USER` - користувач для SSH (зазвичай `deploy`)
- `VPS_SSH_PRIVATE_KEY` - приватний SSH ключ
- `VPS_DOCKER_COMPOSE_PATH` - шлях до docker-compose.yml (наприклад `/opt/ai-nexelin/docker-compose.yml`)

#### Frontend
- `FTP_HOST` - `w020c360.kasserver.com`
- `FTP_USER` - `f017cd3a`
- `FTP_PASSWORD` - ваш FTP пароль (зберігається в secrets)
- `FTP_DIR` - `/`
- `VITE_API_URL` - `https://api.nexelin.com/api`

### 2. Як це працює

#### Main Branch (`main`)
- ✅ Автоматично запускає тести з покриттям при push
- ✅ Запускає тільки тести для змінених частин (frontend або backend)

#### Dev Branch (`dev`)
- ✅ Автоматично деплоїть при push
- ✅ **Розумний деплой**: деплоїть тільки те, що змінилося
  - Зміни в `nextlen/` → деплой тільки фронтенду
  - Зміни в `backend/` → деплой тільки бекенду
  - Зміни в обох → деплой обох

### 3. Безпека

- ✅ **Database volumes завжди зберігаються** - дані не будуть втрачені
- ✅ **Health checks** після кожного деплою
- ✅ **Детальне логування** всіх операцій

## 📚 Детальна документація

Дивіться [CI_CD_SETUP.md](./CI_CD_SETUP.md) для повної документації.

