# 📤 Інструкція для завантаження через FileZilla (Windows)

## Проблема: з'являється localhost замість production URL

Якщо після завантаження файлів через FileZilla з'являється помилка:
```
http://localhost:8000/api/... net::ERR_CONNECTION_REFUSED
```

Це означає, що завантажені **старі файли** або build був зроблений **без правильних налаштувань**.

---

## ✅ Правильна послідовність дій:

### Крок 1: Переконайтеся що `.env.production` існує і правильний

В директорії `frontend\` має бути файл `.env.production` з вмістом:

```
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

**Як перевірити (PowerShell):**
```powershell
cd frontend
Get-Content .env.production
```

**Або через CMD:**
```cmd
cd frontend
type .env.production
```

**Якщо файлу немає або він неправильний:**

Відкрийте Блокнот (Notepad) і створіть файл `.env.production` в папці `frontend\` з таким вмістом:
```
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

**Важливо:** Збережіть файл як `.env.production` (з крапкою на початку!). Якщо Блокнот не дозволяє, збережіть як `env.production` і потім перейменуйте через Провідник.

---

### Крок 2: Зробіть НОВИЙ build з правильними налаштуваннями

**ВАЖЛИВО:** Завжди робіть свіжий build перед завантаженням!

**Відкрийте PowerShell або CMD в папці проєкту:**

```powershell
cd C:\шлях\до\nexelin_web\frontend
npm run build:prod
```

Або якщо ви вже в папці `frontend`:
```powershell
npm run build:prod
```

Це створить нові файли в папці `dist\` з правильним API URL.

**Чекайте поки build завершиться!** Може зайняти 1-2 хвилини.

---

### Крок 3: Перевірте що build містить правильний URL

**PowerShell:**
```powershell
cd dist\assets
Select-String -Path *.js -Pattern "api.nexelin.com" | Select-Object -First 1
```

**CMD:**
```cmd
cd dist\assets
findstr /S /I "api.nexelin.com" *.js
```

Якщо бачите `api.nexelin.com` - все добре! ✅

Якщо бачите `localhost:8000` - build неправильний, перевірте `.env.production` і зробіть build знову.

---

### Крок 4: Завантажте файли через FileZilla

1. **Відкрийте FileZilla**

2. **Підключіться до FTP:**
   - Host: `w020c360.kasserver.com`
   - Username: `f017cd3a`
   - Password: (ваш пароль)
   - Port: `21`
   - Натисніть "Quickconnect"

3. **У лівій панелі (Local site)** перейдіть в папку:
   ```
   C:\шлях\до\nexelin_web\frontend\dist
   ```

4. **У правій панелі (Remote site)** перейдіть в корінь сайту (зазвичай `/` або `/public_html/`)

5. **Завантажте ВСІ файли:**
   - Виділіть ВСІ файли і папки в `dist\` (Ctrl+A)
   - Перетягніть їх в праву панель (Remote site)
   - Або виділіть все і натисніть правою кнопкою → Upload

   **Завантажити потрібно:**
   - `index.html`
   - `.htaccess` (ВАЖЛИВО! Переконайтеся що він завантажився)
   - `assets\` (вся папка)
   - `logo\` (вся папка)
   - `static\` (вся папка)
   - Всі інші файли (icon.svg, manifest.json, vite.svg тощо)

6. **ВАЖЛИВО:** Завантажуйте файли з папки `dist\`, а НЕ з `src\`!

7. **Чекайте поки всі файли завантажаться** (внизу буде прогрес)

---

### Крок 5: Перевірка після завантаження

1. Відкрийте сайт: https://app.nexelin.com
2. Відкрийте DevTools (F12) → Console
3. Перевірте чи немає помилок з localhost
4. Перейдіть в Network tab - запити мають йти на `https://api.nexelin.com/api`

---

## ❌ Типові помилки:

### Помилка 1: Завантажені файли з `src\` замість `dist\`
**Рішення:** Завжди завантажуйте з `dist\` - це зібраний production build!

### Помилка 2: Завантажені старі файли
**Рішення:** Завжди робіть `npm run build:prod` перед завантаженням!

### Помилка 3: `.env.production` неправильний або відсутній
**Рішення:** 
- Перевірте що файл існує в `frontend\`
- Відкрийте його в Блокноті і перевірте що там `VITE_API_URL=https://api.nexelin.com/api`

### Помилка 4: Забули завантажити `.htaccess`
**Рішення:** 
- `.htaccess` обов'язково має бути в корені сайту на FTP!
- Переконайтеся що він завантажився (перевірте в правій панелі FileZilla)

### Помилка 5: Не бачу файл `.env.production` в Провіднику
**Рішення:** 
- Файли що починаються з крапки (`.env`) можуть бути приховані
- У Провіднику: View → Show → Hidden items
- Або створіть файл через Блокнот і збережіть як `.env.production`

---

## 🔄 Швидкий чеклист перед завантаженням:

- [ ] `.env.production` існує в `frontend\` і містить правильний URL
- [ ] Виконано `npm run build:prod` (без помилок)
- [ ] Перевірено що в `dist\assets\` є `api.nexelin.com` (не localhost)
- [ ] Готові завантажити файли з `dist\` (не з `src\`)
- [ ] `.htaccess` буде завантажений в корінь сайту
- [ ] FileZilla підключена до правильного FTP сервера

---

## 💡 Поради для Windows:

### Як швидко відкрити PowerShell в потрібній папці:

1. Відкрийте Провідник (Explorer)
2. Перейдіть в папку `frontend`
3. Натисніть Shift + Права кнопка миші
4. Виберіть "Open PowerShell window here" або "Open in Terminal"

### Як перевірити чи Node.js встановлений:

```powershell
node --version
npm --version
```

Якщо помилка - встановіть Node.js з https://nodejs.org/

### Як видалити стару папку dist і зробити свіжий build:

```powershell
cd frontend
Remove-Item -Recurse -Force dist
npm run build:prod
```

---

## 📞 Якщо проблема залишається:

1. **Перевірте `.env.production`:**
   ```powershell
   Get-Content .env.production
   ```
   Має бути: `VITE_API_URL=https://api.nexelin.com/api`

2. **Видаліть папку `dist\` і зробіть build знову:**
   ```powershell
   Remove-Item -Recurse -Force dist
   npm run build:prod
   ```

3. **Перевірте що в build файлах немає localhost:**
   ```powershell
   Select-String -Path dist\* -Pattern "localhost:8000" -Recurse
   ```
   Якщо знайдено - проблема в `.env.production` або build не підхопив змінні

4. **Переконайтеся що ви завантажуєте з `dist\`, а не з `src\`!**

---

## 🎯 Швидка команда для перевірки:

Після build виконайте в PowerShell:
```powershell
cd frontend\dist\assets
Select-String -Path *.js -Pattern "api.nexelin.com" | Select-Object -First 1
```

Якщо бачите результат - все добре! ✅
Якщо нічого не знайдено - перевірте `.env.production` і зробіть build знову.





