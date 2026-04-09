# Multi-stage build для оптимізації розміру образу
FROM node:20-alpine AS builder

WORKDIR /app

# Копіюємо файли залежностей
COPY package*.json ./

# Встановлюємо залежності
RUN npm ci --only=production=false

# Копіюємо вихідний код
COPY . .

# Створюємо production build
RUN npm run build

# Production stage
FROM nginx:alpine

# Копіюємо збірку з builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Копіюємо nginx конфігурацію
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Відкриваємо порт
EXPOSE 80

# Запускаємо nginx
CMD ["nginx", "-g", "daemon off;"]

