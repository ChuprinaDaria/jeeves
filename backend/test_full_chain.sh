#!/bin/bash

# Full chain testing script
# Tests the complete hierarchy creation and API functionality

BASE_URL="http://localhost:8000"
COOKIES_FILE="cookies.txt"

echo "🚀 Starting full chain API test..."

# Clear cookies
rm -f $COOKIES_FILE

echo ""
echo "1️⃣ Login to admin panel..."
curl -X POST $BASE_URL/admin/login/ \
  -d "username=admin&password=admin" \
  -c $COOKIES_FILE \
  -s -o /dev/null -w "HTTP Status: %{http_code}\n"

echo ""
echo "2️⃣ Creating Branch..."
BRANCH_RESPONSE=$(curl -s -X POST $BASE_URL/api/branches/create/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Medicine",
    "slug": "medicine",
    "description": "Medical services"
  }')

echo "Branch Response: $BRANCH_RESPONSE"
BRANCH_ID=$(echo $BRANCH_RESPONSE | jq -r '.id')
echo "Branch ID: $BRANCH_ID"

echo ""
echo "3️⃣ Creating Specialization..."
SPEC_RESPONSE=$(curl -s -X POST $BASE_URL/api/specializations/create/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Dentistry\",
    \"slug\": \"dentistry\",
    \"branch_id\": $BRANCH_ID,
    \"description\": \"Dental services\"
  }")

echo "Specialization Response: $SPEC_RESPONSE"
SPEC_ID=$(echo $SPEC_RESPONSE | jq -r '.id')
echo "Specialization ID: $SPEC_ID"

echo ""
echo "4️⃣ Creating Client..."
CLIENT_RESPONSE=$(curl -s -X POST $BASE_URL/api/clients/clients/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d "{
    \"specialization\": $SPEC_ID,
    \"company_name\": \"Dr. Smith Clinic\",
    \"client_type\": \"medical\"
  }")

echo "Client Response: $CLIENT_RESPONSE"
CLIENT_ID=$(echo $CLIENT_RESPONSE | jq -r '.id')
echo "Client ID: $CLIENT_ID"

echo ""
echo "5️⃣ Creating API Key..."
API_KEY_RESPONSE=$(curl -s -X POST $BASE_URL/api/clients/$CLIENT_ID/create-api-key/ \
  -b $COOKIES_FILE \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Key",
    "rate_limit_per_minute": 60,
    "rate_limit_per_day": 10000
  }')

echo "API Key Response: $API_KEY_RESPONSE"
API_KEY=$(echo $API_KEY_RESPONSE | jq -r '.key')
echo "API Key: $API_KEY"

echo ""
echo "6️⃣ Getting Client Stats..."
curl $BASE_URL/api/clients/$CLIENT_ID/stats/ \
  -b $COOKIES_FILE \
  -s -w "HTTP Status: %{http_code}\n" | jq '.'

echo ""
echo "7️⃣ Testing Bootstrap Endpoint..."
BOOTSTRAP_RESPONSE=$(curl -s -X POST $BASE_URL/api/bootstrap/medicine/dentistry/$API_KEY/)
echo "Bootstrap Response: $BOOTSTRAP_RESPONSE"

echo ""
echo "8️⃣ Testing Provision Link..."
PROVISION_RESPONSE=$(curl -s -X POST $BASE_URL/api/provision-link/ \
  -H "Content-Type: application/json" \
  -d "{
    \"branch\": \"medicine\",
    \"specialization\": \"dentistry\",
    \"token\": \"$API_KEY\"
  }")
echo "Provision Response: $PROVISION_RESPONSE"

echo ""
echo "9️⃣ Testing RAG Chat..."
RAG_RESPONSE=$(curl -s -X POST $BASE_URL/api/rag/chat/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What services do you offer?",
    "stream": false
  }')
echo "RAG Response: $RAG_RESPONSE"

echo ""
echo "🔟 Testing Restaurant Chat (if applicable)..."
RESTAURANT_RESPONSE=$(curl -s -X POST $BASE_URL/api/restaurant/chat/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me your services",
    "table_id": 1
  }')
echo "Restaurant Response: $RESTAURANT_RESPONSE"

echo ""
echo "✅ Full chain test completed!"
echo "📊 Summary:"
echo "   Branch ID: $BRANCH_ID"
echo "   Specialization ID: $SPEC_ID"
echo "   Client ID: $CLIENT_ID"
echo "   API Key: $API_KEY"
echo "📁 Cookies saved in: $COOKIES_FILE"
