# 🚀 Інструкція для Deployment на FTP хостинг

## Налаштування для w020c360.kasserver.com
**Production домен:** https://app.nexelin.com

### Крок 1: Налаштування змінних середовища

Створіть файл `.env.production` в корені проєкту:

```bash
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

### Крок 2: Production Build

```bash
cd frontend
npm install
npm run build:prod
```

Це створить оптимізований build в папці `dist/`

### Крок 3: Підготовка файлів для FTP

1. **Скопіюйте вміст папки `dist/`** - це всі файли для завантаження

2. **Додайте `.htaccess` файл** (для Apache на FTP хостингу):
   - Файл `.htaccess` вже створено в корені проєкту
   - Скопіюйте його в папку `dist/` після build

### Крок 4: Завантаження на FTP

#### Варіант A: Через FTP клієнт (FileZilla, WinSCP, тощо)

1. Підключіться до FTP:
   - **Host:** w020c360.kasserver.com
   - **Username:** (ваш FTP username)
   - **Password:** (ваш FTP password)
   - **Port:** 21 (або 22 для SFTP)

2. Перейдіть в корінь вашого сайту (зазвичай `public_html` або `www`)

3. Завантажте всі файли з папки `dist/`:
   - Всі файли з `dist/` → корінь сайту
   - `.htaccess` → корінь сайту (важливо!)

4. Переконайтеся, що права доступу правильні:
   - Файли: `644`
   - `.htaccess`: `644`
   - Директорії: `755`

#### Варіант B: Через командний рядок (scp/sftp)

```bash
# Створіть build
npm run build:prod

# Скопіюйте .htaccess в dist
cp .htaccess dist/

# Завантажте на сервер
scp -r dist/* user@w020c360.kasserver.com:/path/to/public_html/
```

### Крок 5: Структура файлів на сервері

Після завантаження структура має виглядати так:

```
public_html/ (або www/)
├── index.html
├── .htaccess          ← ВАЖЛИВО!
├── assets/
│   ├── index-[hash].js
│   ├── index-[hash].css
│   └── ...
└── vite.svg (та інші статичні файли)
```

### Крок 6: Перевірка

1. **Відкрийте сайт в браузері:**
   - Перевірте, що головна сторінка завантажується

2. **Перевірте API з'єднання:**
   - Відкрийте DevTools → Network
   - Спробуйте увійти в систему
   - Перевірте, що запити йдуть на `https://api.nexelin.com/api`

3. **Перевірте React Router:**
   - Перейдіть на `/dashboard`
   - Переконайтеся, що сторінка завантажується (не 404)

4. **Перевірте .htaccess:**
   - Якщо прямі посилання не працюють, перевірте чи `.htaccess` завантажено
   - Перевірте чи Apache підтримує `mod_rewrite`

### Troubleshooting

#### Проблема: 404 на прямих посиланнях

**Рішення:**
1. Перевірте чи `.htaccess` завантажено
2. Перевірте чи Apache підтримує `mod_rewrite`
3. Зверніться до хостинг-провайдера для увімкнення `mod_rewrite`

#### Проблема: API запити не працюють

**Рішення:**
1. Перевірте `VITE_API_URL` в `.env.production`
2. Перевірте CORS налаштування на backend:
   ```python
   # Django settings.py
   CORS_ALLOWED_ORIGINS = [
       "https://ваш-домен.com",  # Ваш FTP домен
   ]
   ```

#### Проблема: CSS/JS не завантажуються

**Рішення:**
1. Перевірте шляхи до файлів в `index.html`
2. Перевірте чи всі файли з папки `assets/` завантажені
3. Перевірте права доступу (мають бути `644`)

#### Проблема: Біла сторінка

**Рішення:**
1. Відкрийте DevTools → Console
2. Перевірте помилки JavaScript
3. Перевірте чи `index.html` завантажений
4. Перевірте чи API URL правильний

### Автоматизація через скрипт

Створіть `deploy-ftp.sh` для автоматичного деплою:

```bash
#!/bin/bash

echo "🔨 Building production..."
npm run build:prod

echo "📋 Copying .htaccess..."
cp .htaccess dist/

echo "📤 Uploading to FTP..."
# Використовуйте lftp або інший FTP клієнт
lftp -c "
open -u USERNAME,PASSWORD w020c360.kasserver.com
cd public_html
mirror -R dist/ .
quit
"

echo "✅ Deployment complete!"
```

## Чеклист перед деплоєм

- [ ] `.env.production` створено з `VITE_API_URL=https://api.nexelin.com/api`
- [ ] `npm run build:prod` виконується без помилок
- [ ] `.htaccess` скопійовано в `dist/`
- [ ] Всі файли з `dist/` готові до завантаження
- [ ] FTP credentials готові
- [ ] CORS налаштовано на backend для вашого домену
- [ ] Перевірено build локально (`npm run preview`)

## Після деплою

1. Перевірте доступність сайту
2. Перевірте API з'єднання
3. Перевірте React Router
4. Перевірте роботу всіх функцій
5. Перевірте мобільну версію

