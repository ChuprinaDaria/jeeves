# 📤 Інструкція для завантаження через FileZilla

## Проблема: з'являється localhost замість production URL

Якщо після завантаження файлів через FileZilla з'являється помилка:
```
http://localhost:8000/api/... net::ERR_CONNECTION_REFUSED
```

Це означає, що завантажені **старі файли** або build був зроблений **без правильних налаштувань**.

---

## ✅ Правильна послідовність дій:

### Крок 1: Переконайтеся що `.env.production` існує і правильний

В директорії `frontend/` має бути файл `.env.production` з вмістом:

```bash
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

**Як перевірити:**
```bash
cd frontend
cat .env.production
```

Якщо файлу немає або він неправильний - створіть/виправте його:
```bash
echo "VITE_API_URL=https://api.nexelin.com/api" > .env.production
echo "VITE_MOCK_MODE=false" >> .env.production
```

---

### Крок 2: Зробіть НОВИЙ build з правильними налаштуваннями

**ВАЖЛИВО:** Завжди робіть свіжий build перед завантаженням!

```bash
cd frontend
npm run build:prod
```

Це створить нові файли в папці `dist/` з правильним API URL.

---

### Крок 3: Перевірте що build містить правильний URL

Після build перевірте один з файлів:

```bash
cd frontend/dist/assets
grep -r "api.nexelin.com" . | head -1
```

Якщо бачите `api.nexelin.com` - все добре! ✅

Якщо бачите `localhost:8000` - build неправильний, перевірте `.env.production` і зробіть build знову.

---

### Крок 4: Завантажте файли через FileZilla

1. **Підключіться до FTP:**
   - Host: `w020c360.kasserver.com`
   - Username: `f017cd3a`
   - Password: (ваш пароль)
   - Port: `21`

2. **Перейдіть в корінь сайту** (зазвичай `/` або `/public_html/`)

3. **Завантажте ВСІ файли з папки `frontend/dist/`:**
   - `index.html`
   - `.htaccess` (ВАЖЛИВО!)
   - `assets/` (вся папка)
   - `logo/` (вся папка)
   - `static/` (вся папка)
   - Всі інші файли (icon.svg, manifest.json, vite.svg тощо)

4. **ВАЖЛИВО:** Завантажуйте файли з папки `dist/`, а НЕ з `src/`!

---

### Крок 5: Перевірка після завантаження

1. Відкрийте сайт: https://app.nexelin.com
2. Відкрийте DevTools (F12) → Console
3. Перевірте чи немає помилок з localhost
4. Перевірте Network tab - запити мають йти на `https://api.nexelin.com/api`

---

## ❌ Типові помилки:

### Помилка 1: Завантажені файли з `src/` замість `dist/`
**Рішення:** Завжди завантажуйте з `dist/` - це зібраний production build!

### Помилка 2: Завантажені старі файли
**Рішення:** Завжди робіть `npm run build:prod` перед завантаженням!

### Помилка 3: `.env.production` неправильний або відсутній
**Рішення:** Перевірте що файл існує і містить `VITE_API_URL=https://api.nexelin.com/api`

### Помилка 4: Забули завантажити `.htaccess`
**Рішення:** `.htaccess` обов'язково має бути в корені сайту на FTP!

---

## 🔄 Швидкий чеклист перед завантаженням:

- [ ] `.env.production` існує і містить правильний URL
- [ ] Виконано `npm run build:prod` (без помилок)
- [ ] Перевірено що в `dist/assets/` є `api.nexelin.com` (не localhost)
- [ ] Готові завантажити файли з `dist/` (не з `src/`)
- [ ] `.htaccess` буде завантажений в корінь сайту

---

## 💡 Порада:

Якщо ви часто завантажуєте файли, використовуйте скрипт деплою замість FileZilla:

```bash
cd frontend
./deploy-ftp.sh
```

Це автоматично:
- Збере проєкт
- Скопіює `.htaccess`
- Завантажить на FTP

---

## 📞 Якщо проблема залишається:

1. Перевірте що `.env.production` правильний
2. Видаліть папку `dist/` і зробіть build знову:
   ```bash
   rm -rf dist/
   npm run build:prod
   ```
3. Перевірте що в build файлах немає localhost:
   ```bash
   grep -r "localhost:8000" dist/
   ```
   Якщо знайдено - проблема в `.env.production` або build не підхопив змінні





