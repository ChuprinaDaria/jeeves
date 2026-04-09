# Salon AI - Frontend

SaaS платформа для салонів краси з AI-агентом для автоматизації спілкування з клієнтами.

## Технології

- **React 18** - UI фреймворк
- **Vite** - Build tool
- **React Router** - Маршрутизація
- **Tailwind CSS** - Стилізація
- **Axios** - HTTP клієнт
- **React Hook Form** - Управління формами
- **Lucide React** - Іконки
- **Stripe** - Платежі

## Структура проєкту

```
src/
├── components/
│   ├── dashboard/     # Компоненти дашборду
│   ├── history/       # Історія чатів
│   ├── layout/        # Layout компоненти (Sidebar, Header)
│   ├── sandbox/       # Тестова пісочниця
│   └── training/      # Тренування AI
├── pages/             # Сторінки додатку
├── context/           # React Context (Auth, Subscription)
├── api/               # API клієнти
└── utils/             # Допоміжні функції
```

## Встановлення

1. Клонуйте репозиторій
```bash
git clone <repository-url>
cd frontend
```

2. Встановіть залежності
```bash
npm install
```

3. Створіть `.env` файл на основі `.env.example`
```bash
cp .env.example .env
```

4. Налаштуйте змінні середовища в `.env`:
```env
VITE_API_URL=http://localhost:8000/api
```

## Запуск

### Режим розробки
```bash
npm run dev
```

Відкрийте [http://localhost:5173](http://localhost:5173) у браузері.

### Production build
```bash
npm run build
```

### Preview production build
```bash
npm run preview
```

## Основні функції


### 1. Тренування AI
- Завантаження файлів (PDF, DOC, TXT, XLS)
- Налаштування prompt для AI
- Моніторинг статусу тренування

### 2. Тестова пісочниця
- Тестування чат-бота
- Тестування розпізнавання фото
- Перегляд відповідей AI в реальному часі

### 3. Історія чатів
- Перегляд всіх розмов
- Детальний перегляд чату
- Фільтрація та пошук

## API Endpoints

Всі API endpoints налаштовані в `src/api/`:
- `agent.js` - Операції з AI агентом
- `axios.js` - Базова конфігурація axios

## Стилізація

Проєкт використовує Tailwind CSS з кастомною темою:
- **Primary** (Purple): #d946ef
- **Accent** (Orange): #f97316

Кастомні класи доступні в `src/index.css`:
- `.btn-primary` - Основна кнопка
- `.btn-secondary` - Вторинна кнопка
- `.card` - Картка
- `.input` - Поле вводу

## Deployment

### 1. Підготовка до деплою

#### Створіть `.env.production` файл:
```env
VITE_API_URL=https://api.nexelin.com/api
VITE_MOCK_MODE=false
```

#### Змініть `VITE_API_URL` на ваш production backend URL

### 2. Build для production

```bash
npm run build:prod
```

Це створить оптимізований build в папці `dist/`

### 3. Deployment варіанти

#### Варіант A: Docker (рекомендовано)

```bash
# Build Docker image
docker build -t nexelin-frontend .

# Запуск контейнера
docker run -d -p 80:80 --name nexelin-frontend nexelin-frontend
```

#### Варіант B: Nginx напряму

1. Скопіюйте папку `dist/` на сервер
2. Налаштуйте Nginx (використовуйте `nginx.conf` як приклад)
3. Вкажіть `root` на папку `dist`

#### Варіант C: Vercel / Netlify

1. Підключіть репозиторій
2. Налаштуйте змінні середовища:
   - `VITE_API_URL` - ваш backend URL
   - `VITE_MOCK_MODE=false`
3. Build command: `npm run build`
4. Output directory: `dist`

### 4. Перевірка після деплою

- Перевірте, що всі API запити йдуть на правильний backend
- Перевірте, що React Router працює (перехід між сторінками)
- Перевірте, що статичні файли (CSS, JS) завантажуються
- Перевірте CORS налаштування на backend

### 5. Environment Variables

**Production:**
- `VITE_API_URL` - URL вашого backend API (обов'язково)
- `VITE_MOCK_MODE` - завжди `false` в production

**Development:**
- `VITE_API_URL` - місцевий backend або production URL
- `VITE_MOCK_MODE` - `true` для розробки без backend

### Примітки

- В production build видаляються всі `console.log`
- Sourcemaps вимкнені для безпеки
- Статичні файли кешуються на 1 рік
- React Router налаштований для SPA (всі роути → index.html)

## Розробка

Проєкт налаштований з ESLint для якості коду.

```bash
npm run lint
```

## Ліцензія

MIT

## Підтримка

Для питань звертайтесь до команди розробки.
