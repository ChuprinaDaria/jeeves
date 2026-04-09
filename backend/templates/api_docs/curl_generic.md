# cURL Generic

Base URL: {{ base_url }}
API Key: {{ api_key }}
Specialization: {{ specialization }}

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {{ api_key }}" \
  -d '{"q":"hello"}' \
  {{ base_url }}api/your-endpoint/
```
