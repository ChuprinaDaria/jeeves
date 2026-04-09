# Тестовий Dockerfile для імітації Zero email service
# В production використовуйте реальний репозиторій https://github.com/Mail-0/Zero

FROM node:18-alpine

WORKDIR /app

# Створити простий Express сервер для тестування
RUN npm init -y && \
    npm install express

# Створити простий API endpoint
RUN echo 'const express = require("express"); \
const app = express(); \
const PORT = process.env.PORT || 3000; \
\
app.get("/", (req, res) => { \
  res.json({ \
    service: "Zero Email Service (Test Mode)", \
    status: "running", \
    version: "test-1.0.0", \
    config: { \
      database: process.env.DATABASE_URL ? "connected" : "not configured", \
      auth: process.env.BETTER_AUTH_SECRET ? "configured" : "not configured" \
    } \
  }); \
}); \
\
app.get("/health", (req, res) => { \
  res.json({ status: "healthy", uptime: process.uptime() }); \
}); \
\
app.listen(PORT, "0.0.0.0", () => { \
  console.log(`Zero Test Service listening on port ${PORT}`); \
  console.log(`Environment:`); \
  console.log(`  DATABASE_URL: ${process.env.DATABASE_URL ? "SET" : "NOT SET"}`); \
  console.log(`  BETTER_AUTH_SECRET: ${process.env.BETTER_AUTH_SECRET ? "SET" : "NOT SET"}`); \
});' > /app/server.js

EXPOSE 3000

CMD ["node", "server.js"]

