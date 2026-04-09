# ⚡ Швидкий деплой на FTP хостинг

## 🎯 Ваша ситуація:
- **Backend API:** https://api.nexelin.com (вже працює)
- **Frontend репо:** https://github.com/olegchensky/p004_web_nexelin/
- **FTP хостинг:** w020c360.kasserver.com
- **Production домен:** https://app.nexelin.com

## 📋 Крок за кроком:

### 1️⃣ Створіть `.env.production` файл

В корені проєкту `frontend/` створіть файл `.env.production`:

```env
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

### 2️⃣ Встановіть залежності та зробіть build

```bash
cd frontend
npm install
npm run build:ftp
```

Це:
- Створить production build в папці `dist/`
- Автоматично скопіює `.htaccess` в `dist/`

### 3️⃣ Завантажте на FTP

#### Варіант A: Через FileZilla (найпростіше)

1. Відкрийте **FileZilla**
2. Підключіться до FTP:
   - **Host:** `w020c360.kasserver.com`
   - **Username:** ваш FTP username
   - **Password:** ваш FTP password
   - **Port:** `21` (або `22` для SFTP)

3. Перейдіть в корінь сайту:
   - Зазвичай це `public_html` або `www`

4. Завантажте **ВСІ файли** з папки `dist/`:
   - Виберіть всі файли в `dist/`
   - Перетягніть їх в корінь сайту на FTP
   - **ВАЖЛИВО:** Завантажте також `.htaccess`!

5. Перевірте права доступу:
   - Файли: `644`
   - Директорії: `755`

#### Варіант B: Через командний рядок

```bash
# Після build:ftp
cd dist

# Завантажте через sftp/scp
scp -r * user@w020c360.kasserver.com:/path/to/public_html/
```

### 4️⃣ Структура на сервері

Після завантаження має бути так:

```
public_html/ (або www/)
├── index.html          ← Головний файл
├── .htaccess           ← ВАЖЛИВО! Для React Router
├── assets/
│   ├── index-[hash].js
│   ├── index-[hash].css
│   └── ...
└── vite.svg (та інші статичні)
```

### 5️⃣ Перевірка

1. **Відкрийте сайт в браузері**
2. **Відкрийте DevTools → Network**
3. **Спробуйте увійти** - перевірте чи запити йдуть на `https://api.nexelin.com/api`
4. **Перевірте React Router** - перейдіть на `/dashboard`

## ⚠️ Важливі моменти:

### ✅ Обов'язково:
- `.htaccess` має бути завантажений (для React Router)
- `VITE_API_URL` має вказувати на `https://api.nexelin.com/api`
- Всі файли з `dist/` мають бути завантажені

### 🔧 Якщо щось не працює:

**404 на прямих посиланнях:**
- Перевірте чи `.htaccess` завантажено
- Зверніться до хостингу для увімкнення `mod_rewrite`

**API не працює:**
- Перевірте `VITE_API_URL` в `.env.production`
- Перевірте CORS на backend (має дозволяти ваш домен)

**Біла сторінка:**
- Відкрийте DevTools → Console
- Перевірте помилки
- Перевірте чи всі файли завантажені

## 🚀 Готово!

Після виконання цих кроків ваш фронтенд буде доступний на FTP хостингу та підключений до API на https://api.nexelin.com

---

## 📝 Checklist:

- [ ] `.env.production` створено з правильним `VITE_API_URL`
- [ ] `npm run build:ftp` виконано успішно
- [ ] Всі файли з `dist/` завантажені на FTP
- [ ] `.htaccess` завантажено
- [ ] Права доступу перевірені (644 для файлів, 755 для директорій)
- [ ] Сайт відкривається в браузері
- [ ] API з'єднання працює
- [ ] React Router працює (перехід між сторінками)

