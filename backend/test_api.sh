#!/bin/bash

# Тестування API через curl
# Запуск: chmod +x test_api.sh && ./test_api.sh

BASE_URL="http://localhost:8000"
COOKIES_FILE="cookies.txt"

echo "🚀 Початок тестування API..."

# Очистити файл cookies
rm -f $COOKIES_FILE

echo ""
echo "1️⃣ Логін в адмінку (отримання session cookie)..."
curl -X POST $BASE_URL/admin/login/ \
  -d "username=admin&password=admin" \
  -c $COOKIES_FILE \
  -s -o /dev/null -w "HTTP Status: %{http_code}\n"

echo ""
echo "2️⃣ Створення Branch..."
curl -X POST $BASE_URL/api/branches/create/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Restaurants",
    "slug": "restaurants",
    "description": "Restaurant services"
  }' \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "3️⃣ Отримання списку Branches..."
curl $BASE_URL/api/branches/list/ \
  -b $COOKIES_FILE \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "4️⃣ Створення Specialization..."
curl -X POST $BASE_URL/api/specializations/create/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Italian",
    "slug": "italian",
    "branch_id": 1,
    "description": "Italian cuisine"
  }' \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "5️⃣ Отримання списку Specializations..."
curl "$BASE_URL/api/specializations/list/?branch_id=1" \
  -b $COOKIES_FILE \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "6️⃣ Створення Client..."
curl -X POST $BASE_URL/api/clients/clients/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d '{
    "specialization": 1,
    "company_name": "Mario Pizza",
    "client_type": "restaurant"
  }' \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "7️⃣ Отримання розширеного списку клієнтів..."
curl $BASE_URL/api/clients/list-extended/ \
  -b $COOKIES_FILE \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "8️⃣ Створення API key для клієнта..."
curl -X POST $BASE_URL/api/clients/1/create-api-key/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main API Key"
  }' \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "9️⃣ Отримання статистики клієнта..."
curl $BASE_URL/api/clients/1/stats/ \
  -b $COOKIES_FILE \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "✅ Тестування завершено!"
echo "📁 Cookies збережено в файлі: $COOKIES_FILE"
