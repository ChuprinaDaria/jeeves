# 🚀 Інструкція для Deployment React додатку

## Швидкий старт

### 1. Налаштування змінних середовища

Створіть файл `.env.production` в корені проєкту:

```bash
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

**Важливо:** Замініть `https://api.nexelin.com/api` на URL вашого production backend.

### 2. Build для production

```bash
npm install
npm run build:prod
```

Це створить оптимізований build в папці `dist/`

### 3. Варіанти деплою

## 🐳 Docker (рекомендовано)

### Білд та запуск:

```bash
# Build образ
docker build -t nexelin-frontend .

# Запуск контейнера
docker run -d \
  -p 80:80 \
  --name nexelin-frontend \
  --restart unless-stopped \
  nexelin-frontend
```

### Або через docker-compose:

```bash
# Встановіть VITE_API_URL в docker-compose.yml або .env
docker-compose up -d
```

## 🌐 Nginx напряму

### 1. Скопіюйте build на сервер:

```bash
scp -r dist/ user@server:/var/www/nexelin-frontend/
```

### 2. Налаштуйте Nginx:

Створіть `/etc/nginx/sites-available/nexelin-frontend`:

```nginx
server {
    listen 80;
    server_name app.nexelin.com;  # Ваш домен
    
    root /var/www/nexelin-frontend;
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # React Router
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3. Активуйте конфігурацію:

```bash
sudo ln -s /etc/nginx/sites-available/nexelin-frontend /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## ☁️ Vercel / Netlify

### Vercel:

1. Підключіть GitHub репозиторій
2. Налаштуйте:
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Environment Variables:
   - `VITE_API_URL` = ваш backend URL
   - `VITE_MOCK_MODE` = `false`

### Netlify:

1. Підключіть GitHub репозиторій
2. Налаштуйте:
   - **Build command:** `npm run build`
   - **Publish directory:** `dist`
3. Environment Variables (аналогічно Vercel)

## ✅ Перевірка після деплою

### 1. Перевірте API з'єднання:

Відкрийте DevTools → Network і перевірте:
- ✅ Запити йдуть на правильний `VITE_API_URL`
- ✅ Немає CORS помилок
- ✅ Токени зберігаються в localStorage

### 2. Перевірте React Router:

- ✅ Перехід між сторінками працює
- ✅ Прямі посилання на сторінки працюють (наприклад, `/dashboard`)

### 3. Перевірте статичні файли:

- ✅ CSS завантажується
- ✅ JS файли завантажуються
- ✅ Зображення відображаються

### 4. Перевірте CORS на backend:

Backend має дозволяти запити з вашого frontend домену:

```python
# Django settings.py
CORS_ALLOWED_ORIGINS = [
    "https://app.nexelin.com",  # Ваш frontend URL
]
```

## 🔧 Troubleshooting

### Проблема: API запити не працюють

**Рішення:**
1. Перевірте `VITE_API_URL` в `.env.production`
2. Перевірте CORS налаштування на backend
3. Перевірте Network tab в DevTools

### Проблема: 404 на прямих посиланнях

**Рішення:**
Nginx має мати `try_files $uri $uri/ /index.html;` для React Router

### Проблема: CSS не завантажується

**Рішення:**
1. Перевірте шляхи до статичних файлів
2. Перевірте `base` в `vite.config.js` (якщо додаток не в корені)

### Проблема: Docker контейнер не запускається

**Рішення:**
```bash
# Перевірте логи
docker logs nexelin-frontend

# Перевірте чи працює nginx
docker exec nexelin-frontend nginx -t
```

## 📝 Чеклист перед деплоєм

- [ ] `.env.production` створено з правильним `VITE_API_URL`
- [ ] `npm run build:prod` виконується без помилок
- [ ] Папка `dist/` містить всі файли
- [ ] CORS налаштовано на backend
- [ ] Домен налаштовано (якщо потрібно)
- [ ] SSL сертифікат налаштовано (для HTTPS)
- [ ] Environment variables налаштовано на хостингу
- [ ] Перевірено в production режимі локально (`npm run preview`)

## 🎯 Production Checklist

- [ ] `VITE_MOCK_MODE=false`
- [ ] `VITE_API_URL` вказує на production backend
- [ ] Sourcemaps вимкнені
- [ ] Console.log видалені
- [ ] Gzip увімкнено
- [ ] Кешування статичних файлів налаштовано
- [ ] Security headers додані (X-Frame-Options, тощо)

